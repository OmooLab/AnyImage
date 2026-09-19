import sys

import bpy

from .operators.clipboard_image import PasteClipboardImage, TrackNativeCopy


_items = []
_PRIMARY_MODIFIER = {"oskey": True} if sys.platform == "darwin" else {"ctrl": True}

CLIPBOARD_SHORTCUTS = (
    {
        "idname": PasteClipboardImage.bl_idname,
        "type": "V",
        "value": "PRESS",
        **_PRIMARY_MODIFIER,
    },
    {
        "idname": TrackNativeCopy.bl_idname,
        "type": "C",
        "value": "PRESS",
        **_PRIMARY_MODIFIER,
    },
)

KEYMAPS = (
    {
        "name": "3D View",
        "space_type": "VIEW_3D",
        "shortcuts": CLIPBOARD_SHORTCUTS,
    },
    {
        "name": "Node Editor",
        "space_type": "NODE_EDITOR",
        "shortcuts": CLIPBOARD_SHORTCUTS,
    },
)


def _add(keymap, shortcut):
    options = dict(shortcut)
    item = keymap.keymap_items.new(
        options.pop("idname"),
        options.pop("type"),
        options.pop("value"),
        **options,
    )
    _items.append((keymap, item))


def register():
    window_manager = getattr(bpy.context, "window_manager", None)
    keyconfigs = getattr(window_manager, "keyconfigs", None)
    addon_keyconfig = getattr(keyconfigs, "addon", None)
    if addon_keyconfig is None:
        return

    for definition in KEYMAPS:
        keymap = addon_keyconfig.keymaps.new(
            name=definition["name"],
            space_type=definition["space_type"],
        )
        for shortcut in definition["shortcuts"]:
            _add(keymap, shortcut)


def unregister():
    for keymap, item in _items:
        keymap.keymap_items.remove(item)
    _items.clear()
