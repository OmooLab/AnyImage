import bpy

from ...preferences import addon_preferences, configured_max_ai_input_size, configured_geometry_model
from ...server.model_catalog import DEFAULT_GEOMETRY_MODEL_KEY
from ...runtime import JobOperatorBase
from ...server.media.resolution import (
    DEFAULT_MAX_AI_INPUT_SIZE,
    MAX_MAX_AI_INPUT_SIZE,
    MIN_MAX_AI_INPUT_SIZE,
)
from ...common.ai import (
    invoke_ai_setup_if_needed,
    moge2_parameters,
    production_device,
    require_environment,
    require_input_path,
    require_model,
    report_ai_error,
)
from ...common.image import is_image_empty
from ...common.material import create_image_material
from ...common.color_image import (
    cleanup_material_color_input,
    material_analysis_input,
    material_color_image,
    prepare_material_color_input,
    require_static_color_image,
)
from .object import (
    create_depth_plane_from_result,
    create_plane_object,
)

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


def depth_plane_settings(context):
    preferences = addon_preferences(context)
    return (
        configured_geometry_model(context),
        int(getattr(preferences, "geometry_resolution_level", 5)),
    )


class GenerateDepthPlane(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.generate_depth_plane"
    bl_label = "Generate Depth Plane"
    job_type = "generate-depth-plane-geometry"
    starting_message = "Preparing depth conversion"

    input_path: bpy.props.StringProperty(options=_HIDDEN)
    color_path: bpy.props.StringProperty(options=_HIDDEN)
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    source_identity: bpy.props.StringProperty(options=_HIDDEN)
    image_identity: bpy.props.StringProperty(options=_HIDDEN)
    plane_type: bpy.props.EnumProperty(
        items=(("DEPTH", "Depth Plane", ""), ("RELIEF", "Relief Plane", "")),
        default="DEPTH",
        options=_HIDDEN,
    )
    mesh_detail: bpy.props.IntProperty(default=6, min=0, max=10, options=_HIDDEN)
    model: bpy.props.StringProperty(default=DEFAULT_GEOMETRY_MODEL_KEY, options=_HIDDEN)
    resolution_level: bpy.props.IntProperty(default=5, min=0, max=9, options=_HIDDEN)
    max_input_size: bpy.props.IntProperty(
        default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE,
        max=MAX_MAX_AI_INPUT_SIZE,
        options=_HIDDEN,
    )

    def request(self, context):
        require_environment()
        require_model(self.model)
        input_path = require_input_path(self.input_path)
        parameters = {
            "input": str(input_path),
            "device": production_device().lower(),
            "max_input_size": int(self.max_input_size),
            "plane_type": self.plane_type,
        }
        parameters.update(
            moge2_parameters(
                input_path,
                self.model,
                self.resolution_level,
            )
        )
        return parameters

    def response(self, context, result):
        create_depth_plane_from_result(context, result, self)
        return f"{self.plane_type.title()} Plane is ready"

    def cleanup(self):
        cleanup_material_color_input(self.color_path)


def start_depth_plane_job(operator, context, plane_type):
    source_object = context.object
    try:
        require_static_color_image(source_object.data)
    except ValueError as error:
        operator.report({"ERROR"}, str(error))
        return {"CANCELLED"}
    setup_result = invoke_ai_setup_if_needed(operator)
    if setup_result is not None:
        return setup_result
    color_path = None
    try:
        color_path = prepare_material_color_input(source_object.data)
        source_path = material_analysis_input(color_path)
        model, resolution_level = depth_plane_settings(context)
        result = bpy.ops.anyimage.generate_depth_plane(
            input_path=str(source_path),
            color_path=str(color_path),
            source_object_name=source_object.name,
            source_identity=str(source_object.as_pointer()),
            image_identity=str(source_object.data.as_pointer()),
            mesh_detail=operator.mesh_detail,
            plane_type=plane_type,
            model=model,
            resolution_level=resolution_level,
            max_input_size=configured_max_ai_input_size(context),
        )
    except (OSError, RuntimeError, ValueError) as error:
        cleanup_material_color_input(color_path)
        report_ai_error(operator, error)
        return {"CANCELLED"}
    if "CANCELLED" in result:
        cleanup_material_color_input(color_path)
    return {"CANCELLED"} if "CANCELLED" in result else {"FINISHED"}


class ConvertToPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_plane"
    bl_label = "Convert to Plane"
    bl_description = "Convert the complete Image Empty into a rectangular plane"
    bl_options = {"REGISTER", "UNDO"}

    mesh_detail: bpy.props.IntProperty(name="Subdivide", default=0, min=0, max=10)

    @classmethod
    def poll(cls, context):
        return is_image_empty(context.object)

    def execute(self, context):
        source_object = context.object
        try:
            require_static_color_image(source_object.data)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        material = None
        try:
            with material_color_image(source_object.data) as color_image:
                material = create_image_material(
                    source_object.data, color_image,
                    scene=context.scene,
                )
                create_plane_object(context, source_object, self.mesh_detail, material)
        except Exception as error:
            if material is not None and material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)
            if isinstance(error, ValueError):
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}
            raise
        return {"FINISHED"}


class ConvertToDepthPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_depth_plane"
    bl_label = "Convert to Depth Plane"
    bl_description = (
        "Use AI-estimated depth to turn the image into a 3D surface "
        "that follows the source image's perspective."
    )
    bl_options = {"REGISTER", "UNDO"}

    mesh_detail: bpy.props.IntProperty(name="Subdivide", default=6, min=0, max=10)

    @classmethod
    def poll(cls, context):
        from ...runtime import runtime

        return is_image_empty(context.object) and not runtime.server_busy()

    def execute(self, context):
        return start_depth_plane_job(self, context, "DEPTH")


class ConvertToReliefPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_relief_plane"
    bl_label = "Convert to Relief Plane"
    bl_description = "Use AI-estimated depth to create a raised relief on a flat base."
    bl_options = {"REGISTER", "UNDO"}

    mesh_detail: bpy.props.IntProperty(name="Subdivide", default=6, min=0, max=10)

    @classmethod
    def poll(cls, context):
        from ...runtime import runtime

        return is_image_empty(context.object) and not runtime.server_busy()

    def execute(self, context):
        return start_depth_plane_job(self, context, "RELIEF")
