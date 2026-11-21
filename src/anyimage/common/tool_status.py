"""Draw modal tool hints using Blender's keymap event template."""

import bpy


# Display-only items supply event data to UILayout.template_event_from_keymap_item.
# The map has no event handler and the items have no operator.
KEYMAP_NAME = f"{__package__} tool status"
_event_items = {}


def register(keymaps):
    keymap = keymaps.new(name=KEYMAP_NAME, space_type="EMPTY")
    for event in ("LEFTMOUSE", "RIGHTMOUSE", "LEFT_SHIFT", "LEFT_CTRL", "ESC", "RET"):
        item = keymap.keymap_items.new("", event, "PRESS")
        _event_items[event] = item
    _event_items["DRAG"] = keymap.keymap_items.new("", "LEFTMOUSE", "CLICK_DRAG")


def unregister():
    if _event_items:
        keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
        _event_items.clear()
        keymaps.remove(keymaps[KEYMAP_NAME])


def draw_tool_status(layout, *hints):
    row = layout.row(align=True)
    for text, event in hints:
        row.template_event_from_keymap_item(_event_items[event], text=text)
    layout.separator_spacer()
    layout.template_reports_banner()
    layout.template_running_jobs()
    layout.separator_spacer()
    layout.template_status_info()


def set_tool_status(context, *hints, cancel_event="RIGHTMOUSE"):
    def draw(header, _context):
        draw_tool_status(header.layout, *hints, ("Cancel", cancel_event))

    context.workspace.status_text_set(draw)
