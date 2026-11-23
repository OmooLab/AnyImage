"""Convert a static panorama into a textured mesh and a matching World."""

from contextlib import ExitStack

import bpy
import numpy as np

from ..ai_preferences import configured_max_ai_input_size
from ..common.bake import BAKE_MARGIN, bake_context
from ..common.ai import geometry_job_parameters, invoke_ai_setup_if_needed
from ..common.color_image import load_material_color, material_highlight_threshold, write_material_color
from ..common.geometry_image import depth_data_name, load_depth_result_image, normal_data_name
from ..common.image import ImageFormat, image_base_name, image_pixels, image_rgba, is_animated_image, is_image_empty
from ..common.image_input import cleanup_image_input, prepare_ai_input
from ..common.image_target import prepare_image_undo
from ..common.material import create_image_material
from ..common.node import load_node_group, set_modifier_input
from ..common.object import conversion_source, finalize_object_result
from ..common.panorama import create_panorama_world, panorama_crop_bounds, report_panorama_crop
from ..runtime import JobOperator


def bake_panorama_normal(context, obj, normal, depth):
    """Combine a terrain-only bake and the generated sky in one packed image."""
    width, height = normal.size
    if tuple(depth.size) != (width, height):
        raise ValueError("Panorama depth and normal dimensions do not match")
    with ExitStack() as cleanup:
        image = bpy.data.images.new("Terrain normal bake", width=width, height=height, alpha=False)
        cleanup.callback(bpy.data.images.remove, image)
        image.colorspace_settings.name = "Non-Color"

        graph = context.evaluated_depsgraph_get()
        mesh = obj.evaluated_get(graph).data.copy()
        cleanup.callback(bpy.data.meshes.remove, mesh)
        uv = mesh.uv_layers.get("UVMap")
        if uv is None:
            raise ValueError("The evaluated panorama mesh is missing UVMap")
        mesh.uv_layers.active = uv
        uv.active_render = True
        bake_material = bpy.data.materials.new("Terrain normal bake")
        cleanup.callback(bpy.data.materials.remove, bake_material, do_unlink=True)
        bake_material.use_nodes = True
        nodes, links = bake_material.node_tree.nodes, bake_material.node_tree.links
        nodes.clear()
        normal_texture = nodes.new("ShaderNodeTexImage")
        normal_texture.image = normal
        normal_texture.extension = "REPEAT"
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.space = "OBJECT"
        links.new(normal_texture.outputs["Color"], normal_map.inputs["Color"])
        # Alpha blends the mesh normal (0) with the predicted normal (1).
        links.new(normal_texture.outputs["Alpha"], normal_map.inputs["Strength"])
        local = nodes.new("ShaderNodeVectorTransform")
        local.vector_type = "NORMAL"
        local.convert_from = "WORLD"
        local.convert_to = "OBJECT"
        links.new(normal_map.outputs["Normal"], local.inputs["Vector"])
        encode = nodes.new("ShaderNodeVectorMath")
        encode.operation = "MULTIPLY_ADD"
        encode.inputs[1].default_value = (.5, .5, .5)
        encode.inputs[2].default_value = (.5, .5, .5)
        links.new(local.outputs["Vector"], encode.inputs[0])
        emission = nodes.new("ShaderNodeEmission")
        links.new(encode.outputs["Vector"], emission.inputs["Color"])
        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(emission.outputs[0], output.inputs["Surface"])
        target = nodes.new("ShaderNodeTexImage")
        target.image = image
        nodes.active = target

        with bake_context(mesh, bake_material, obj.matrix_world):
            result = bpy.ops.object.bake(type="EMIT", uv_layer=uv.name,
                                         use_selected_to_active=False, margin=BAKE_MARGIN, margin_type="EXTEND")
        if result != {"FINISHED"}:
            raise RuntimeError("Panorama normal baking was cancelled")

        baked = image_pixels(image).reshape(-1, 4)

    generated = image_pixels(normal).reshape(-1, 4)
    terrain = image_pixels(depth).reshape(-1, 4)[:, 3] >= 0.9
    # Black is unfilled bake output. An encoded unit normal cannot be black.
    usable = terrain & baked[:, :3].any(axis=1)
    np.copyto(generated, baked, where=usable[:, None])
    generated[:, 3] = 1.0
    normal.pixels.foreach_set(generated.ravel())
    normal.update()
    normal.pack()


class ConvertToPanorama(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.convert_to_panorama"
    bl_label = "Convert to Panorama"
    bl_description = "Turn a still panoramic image into a surrounding 3D surface using AI-estimated depth."
    bl_options = {"REGISTER"}

    job_type = "generate_panorama_geometry"
    starting_message = "Preparing panorama conversion"
    _input_path = None

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        source = context.object
        image = source.data
        width, height = image.size
        if is_animated_image(image):
            self.report({"ERROR"}, "Panorama conversion requires a static image")
            return {"CANCELLED"}
        try:
            bounds = panorama_crop_bounds(width, height)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        setup = invoke_ai_setup_if_needed(self)
        if setup is not None:
            return setup
        report_panorama_crop(self, image.size, bounds)
        self._scene = context.scene
        self._source_object = source
        self._source_image = image
        self.crop_bounds = bounds
        return super().execute(context)

    def request(self, context):
        parameters = geometry_job_parameters(context)
        image = self._source_image
        rgba = image_rgba(image)
        self._input_path = prepare_ai_input(
            image, rgba, bounds=self.crop_bounds,
            max_input_size=configured_max_ai_input_size(context), panorama=True,
        )
        self._color_format = ImageFormat.capture(image)
        left, top, right, bottom = self.crop_bounds
        self._highlight_threshold = None
        if (right - left, bottom - top) != tuple(image.size):
            self._highlight_threshold = material_highlight_threshold(image, rgba, context.scene, panorama=True)
        self._color_path = write_material_color(self._input_path.parent, self._color_format, rgba[top:bottom, left:right])
        return {
            **parameters,
            "input": str(self._input_path),
        }

    def response(self, context, result):
        source = conversion_source(self, context.scene)
        prepare_image_undo(source.data)
        color = depth = normal = material = mesh = obj = world = None
        previous_world = context.scene.world
        try:
            depth = load_depth_result_image(result.file("depth"), depth_data_name(source))
            depth.pack()
            width, height = depth.size
            if height <= 0 or width != 2 * height:
                raise ValueError("Panorama depth texture must have a 2:1 aspect ratio")
            color = load_material_color(self._color_path, image_base_name(source.data), self._color_format)
            group = load_node_group("O Depth Panorama")
            normal = bpy.data.images.load(str(result.file("object_normal")), check_existing=False)
            normal.name = normal_data_name(source)
            normal.colorspace_settings.is_data = True
            normal.alpha_mode = "CHANNEL_PACKED"
            material = create_image_material(
                source.data, color,
                color_is_full_source=True, highlight_threshold=self._highlight_threshold,
                normal_image=normal, normal_space="OBJECT",
                scene=context.scene, texture_extension="REPEAT", emission_strength=1.0, panorama=True)
            material.use_backface_culling = True
            material.use_backface_culling_shadow = True
            mesh = bpy.data.meshes.new(source.name)
            mesh.from_pydata([(0, 0, 0)], [], [])
            mesh.materials.append(material)
            obj = bpy.data.objects.new(source.name, mesh)
            context.collection.objects.link(obj)
            obj.location = source.matrix_world.translation
            obj.scale = source.matrix_world.to_scale()
            obj.visible_shadow = False
            obj["o_image_object"] = True
            modifier = obj.modifiers.new(group.name, "NODES")
            modifier.node_group = group
            modifier.show_group_selector = False
            for name, value in (
                ("Subdivide", 6), ("Depth Image", depth),
                ("Depth Mask", True), ("Depth Split", 0.01),
            ):
                set_modifier_input(modifier, name, value)
            set_modifier_input(modifier, "Horizon Bend", 0.0)
            obj.update_tag(refresh={"DATA"})
            bake_panorama_normal(context, obj, normal, depth)
            set_modifier_input(modifier, "Horizon Bend", -0.1)
            obj.update_tag(refresh={"DATA"})
            world = create_panorama_world(source.data, color, panorama_object=obj)
            context.scene.world = world
            finalize_object_result(context, source, obj)
        except Exception:
            if world is not None:
                context.scene.world = previous_world
                bpy.data.worlds.remove(world, do_unlink=True)
            if obj is not None:
                bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            if material is not None and material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)
            for image in (depth, normal, color):
                if image is not None and image.users == 0:
                    bpy.data.images.remove(image, do_unlink=True)
            raise
        if "FINISHED" not in bpy.ops.ed.undo_push(message="Convert to Panorama"):
            raise RuntimeError("Unable to create the Convert to Panorama Undo step")
        return "Panorama is ready"

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._scene = self._source_object = self._source_image = None
