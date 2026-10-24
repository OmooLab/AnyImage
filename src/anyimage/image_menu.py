from .common.image import is_image_empty
from .common.image_target import is_image_object, active_texture_node


def draw_image_context_menu(self, context):
    if not is_image_empty(context.object):
        return
    from .menu import AnyImageImageMenu

    self.layout.menu(AnyImageImageMenu.bl_idname)
    self.layout.separator()


def draw_image_object_context_menu(self, context):
    if not is_image_object(getattr(context, "object", None)):
        return
    from .menu import AnyImageObjectMenu

    self.layout.menu(AnyImageObjectMenu.bl_idname)
    self.layout.separator()


def draw_texture_node_context_menu(self, context):
    if active_texture_node(context) is None:
        return
    from .menu import AnyImageTextureNodeMenu

    self.layout.menu(AnyImageTextureNodeMenu.bl_idname)
    self.layout.separator()
