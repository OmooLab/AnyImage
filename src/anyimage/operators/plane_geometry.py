"""Submit and apply geometry jobs shared by depth and relief conversion."""

import bpy

from ..common.ai import geometry_job_parameters, invoke_ai_setup_if_needed, report_ai_error, require_environment, require_input_path, require_model
from ..common.color_image import (cleanup_material_color_input, prepare_material_color_input, require_static_color_image)
from ..common.job_image import material_analysis_input
from ..preferences import addon_preferences
from ..ai_preferences import configured_geometry_model, configured_max_ai_input_size
from ..common.depth_plane import create_depth_plane_from_result
from ..common.image import require_image_empty, image_content_signature
from ..runtime import JobOperator
from ..server.model_catalog import DEFAULT_GEOMETRY_MODEL_KEY
from ..server.media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, MAX_MAX_AI_INPUT_SIZE, MIN_MAX_AI_INPUT_SIZE

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


class GeneratePlaneGeometry(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.generate_plane_geometry"
    bl_label = "Generate Plane Geometry"
    job_type = "generate_depth_plane_geometry"
    starting_message = "Preparing depth conversion"

    input_path: bpy.props.StringProperty(options=_HIDDEN)
    color_path: bpy.props.StringProperty(options=_HIDDEN)
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    plane_type: bpy.props.EnumProperty(
        items=(("DEPTH", "Depth Plane", ""), ("RELIEF", "Relief", "")),
        default="DEPTH", options=_HIDDEN,
    )
    model: bpy.props.StringProperty(default=DEFAULT_GEOMETRY_MODEL_KEY, options=_HIDDEN)
    resolution_level: bpy.props.IntProperty(default=5, min=0, max=9, options=_HIDDEN)
    max_input_size: bpy.props.IntProperty(
        default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE,
        max=MAX_MAX_AI_INPUT_SIZE,
        options=_HIDDEN,
    )

    def execute(self, context):
        try:
            self._source_object = require_image_empty(self.source_object_name)
            self._source_image = self._source_object.data
            self._source_signature = image_content_signature(self._source_image)
        except RuntimeError as error:
            cleanup_material_color_input(self.color_path)
            report_ai_error(self, error)
            return {"CANCELLED"}
        return super().execute(context)

    def request(self, context):
        require_environment()
        require_model(self.model)
        input_path = require_input_path(self.input_path)
        return {
            **geometry_job_parameters(input_path, self.model, self.resolution_level),
            "max_input_size": int(self.max_input_size),
            "plane_type": self.plane_type,
        }

    def response(self, context, result):
        label = "Convert to Relief" if self.plane_type == "RELIEF" else "Convert to Depth Plane"
        create_depth_plane_from_result(
            context, result, self, plane_type=self.plane_type, undo_label=label,
        )
        return "Relief is ready" if self.plane_type == "RELIEF" else "Depth Plane is ready"

    def cleanup(self):
        cleanup_material_color_input(self.color_path)
        self._source_object = self._source_image = self._source_signature = None


def depth_plane_settings(context):
    preferences = addon_preferences(context)
    return (
        configured_geometry_model(context),
        int(getattr(preferences, "geometry_resolution_level", 5)),
    )


def start_depth_conversion(operator, context, plane_type):
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
        result = bpy.ops.anyimage.generate_plane_geometry(
            input_path=str(source_path),
            plane_type=plane_type,
            color_path=str(color_path),
            source_object_name=source_object.name,
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
