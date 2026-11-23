"""Submit and apply geometry jobs shared by depth and relief conversion."""

import bpy

from ..ai_preferences import configured_max_ai_input_size
from ..common.ai import geometry_job_parameters, invoke_ai_setup_if_needed
from ..common.color_image import load_material_color, require_static_color_image, write_material_color
from ..common.depth_geometry import (
    depth_plane_limit_preset,
    depth_node_direction,
    depth_uniform_scale,
    fit_image_depth_direction,
    reference_and_median_depth,
)
from ..common.geometry_image import (
    camera_depth_values, depth_data_name, normal_data_name,
    load_depth_result_image,
    load_normal_result_image,
)
from ..common.image import ImageFormat, image_base_name, image_empty_bounds, image_rgba, is_image_empty
from ..common.image_input import cleanup_image_input, prepare_ai_input
from ..common.image_plane import (
    build_image_plane_matrix,
    create_image_plane_mesh,
)
from ..common.image_target import prepare_image_undo
from ..common.material import create_image_material
from ..common.node import load_node_group, set_modifier_input
from ..common.object import conversion_source, finalize_object_result
from ..runtime import JobOperator


def create_depth_plane_object(
    context,
    source_object,
    subdivisions,
    material,
    depth_image,
    intrinsics,
    plane_type,
    *,
    image_size=None,
):
    node_group = load_node_group({
        "DEPTH": "O Depth Plane",
        "RELIEF": "O Depth Relief",
    }[plane_type])
    source_name = source_object.name
    bounds = image_empty_bounds(source_object, image_size)
    mesh = create_image_plane_mesh(source_name, bounds)
    plane = None
    try:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        mesh.materials.append(material)
        plane = bpy.data.objects.new(source_name, mesh)
        context.collection.objects.link(plane)
        plane.matrix_world = build_image_plane_matrix(source_object.matrix_world, bounds)
        plane["o_image_object"] = True

        modifier = plane.modifiers.new(name=node_group.name, type="NODES")
        modifier.node_group = node_group
        modifier.show_group_selector = False
        depth, valid = camera_depth_values(image_rgba(depth_image))
        values = depth[valid]
        model_reference, model_median = reference_and_median_depth(values)
        uniform_scale = depth_uniform_scale(bounds, depth_image.size, intrinsics, model_reference)
        inputs = [
            ("Subdivide", max(0, min(8, int(subdivisions)))),
            ("Reference Depth", model_reference * uniform_scale),
            ("Uniform Scale", uniform_scale),
            ("Depth Image", depth_image),
        ]
        if plane_type == "DEPTH":
            limit = depth_plane_limit_preset(values, model_median, model_reference, uniform_scale)
            inputs.append(("Depth Limit", limit))
        else:
            depth_direction = depth_node_direction(
                fit_image_depth_direction(depth, valid, bounds, uniform_scale)
            )
            inputs.append((
                "Depth Direction",
                depth_direction,
            ))
        for name, value in inputs:
            set_modifier_input(modifier, name, value)
        return finalize_object_result(context, source_object, plane)
    except Exception:
        if plane is not None:
            bpy.data.objects.remove(plane, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise


class DepthPlaneJob(JobOperator):
    bl_options = {"REGISTER"}
    job_type = "generate_depth_plane_geometry"
    starting_message = "Preparing depth conversion"
    _input_path = None

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        source = context.object
        try:
            require_static_color_image(source.data)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        setup = invoke_ai_setup_if_needed(self)
        if setup is not None:
            return setup
        self._scene = context.scene
        self._source_object = source
        self._source_image = source.data
        return super().execute(context)

    def request(self, context):
        parameters = geometry_job_parameters(context)
        image = self._source_image
        rgba = image_rgba(image)
        self._input_path = prepare_ai_input(
            image, rgba, max_input_size=configured_max_ai_input_size(context),
        )
        self._color_format = ImageFormat.capture(image)
        self._color_path = write_material_color(self._input_path.parent, self._color_format, rgba)
        return {
            **parameters,
            "input": str(self._input_path),
            "output_size": tuple(image.size),
            "plane_type": self.plane_type,
        }

    def response(self, context, result):
        plane_type = self.plane_type
        normal_space = {"DEPTH": "OBJECT", "RELIEF": "TANGENT"}[plane_type]
        source_object = conversion_source(self, context.scene)
        prepare_image_undo(source_object.data)
        color_image = material = None
        depth_image = None
        normal_image = None
        try:
            color_image = load_material_color(self._color_path, image_base_name(source_object.data), self._color_format)
            depth_image = load_depth_result_image(result.file("depth"), depth_data_name(source_object))
            depth_image.pack()
            normal_image = load_normal_result_image(
                result.file(f"{normal_space.lower()}_normal"), normal_data_name(source_object),
            )
            material = create_image_material(
                source_object.data, color_image,
                color_is_full_source=True,
                normal_image=normal_image, normal_space=normal_space,
                scene=context.scene,
            )
            create_depth_plane_object(
                context, source_object, 6, material,
                depth_image, result.value["intrinsics"], plane_type, image_size=color_image.size,
            )
        except Exception:
            if material is not None and material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)
            for image in (depth_image, normal_image, color_image):
                if image is not None and image.users == 0:
                    bpy.data.images.remove(image, do_unlink=True)
            raise
        if "FINISHED" not in bpy.ops.ed.undo_push(message=self.bl_label):
            raise RuntimeError(f"Unable to create the {self.bl_label} Undo step")
        return self.ready_message

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._scene = self._source_object = self._source_image = None


class ConvertToDepthPlane(DepthPlaneJob, bpy.types.Operator):
    bl_idname = "anyimage.convert_to_depth_plane"
    bl_label = "Convert to Depth Plane"
    bl_description = (
        "Use AI-estimated depth to turn the image into a 3D surface "
        "that follows the source image's perspective."
    )
    plane_type = "DEPTH"
    ready_message = "Depth Plane is ready"


class ConvertToReliefPlane(DepthPlaneJob, bpy.types.Operator):
    bl_idname = "anyimage.convert_to_relief_plane"
    bl_label = "Convert to Relief"
    bl_description = "Use AI-estimated depth to create a raised relief on a flat base."
    plane_type = "RELIEF"
    ready_message = "Relief is ready"
