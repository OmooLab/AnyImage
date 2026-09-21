import bpy


class ActivateWorkspaceTool(bpy.types.Operator):
    bl_idname = "anyimage.activate_workspace_tool"
    bl_label = "Activate Workspace Tool"
    bl_options = {"INTERNAL"}

    tool_id: bpy.props.StringProperty(options={"HIDDEN"})

    def execute(self, _context):
        return bpy.ops.wm.tool_set_by_id(name=self.tool_id)
