from tests.support.paths import PROJECT_ROOT
import importlib
import builtins
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

SOURCE_ROOT = PROJECT_ROOT / "src"


def mock_bpy_imports(fake_bpy):
    """Stub Python imports while preserving Blender's native module identity."""
    original_import = builtins.__import__

    def import_with_fake_bpy(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "bpy" and level == 0:
            return fake_bpy
        return original_import(name, globals, locals, fromlist, level)

    return patch("builtins.__import__", import_with_fake_bpy)


class BlenderTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_addon_modules = {
            name: module for name, module in sys.modules.items()
            if name == "anyimage" or name.startswith("anyimage.")
        }
        cls.remove_modules()

        def draw_status_bar(_owner, _context):
            pass

        draw_status_bar._draw_funcs = [draw_status_bar]

        def append_status_bar(draw):
            draw._owner = "anyimage"
            draw_status_bar._draw_funcs.append(draw)
            cls.status_bar_draws.append(draw)

        def remove_status_bar(draw):
            draw_status_bar._draw_funcs.remove(draw)
            cls.status_bar_draws.remove(draw)

        fake_bpy = ModuleType("bpy")
        fake_bpy.props = SimpleNamespace(
            BoolProperty=lambda **options: options,
            EnumProperty=lambda **options: options,
            FloatProperty=lambda **options: options,
            FloatVectorProperty=lambda **options: options,
            IntProperty=lambda **options: options,
            PointerProperty=lambda **options: options,
            StringProperty=lambda **options: options,
        )
        fake_bpy.types = SimpleNamespace(
            AddonPreferences=object,
            Menu=object,
            Operator=object,
            Panel=object,
            PropertyGroup=object,
            WorkSpaceTool=object,
            Image=type("Image", (), {}),
            Scene=type("Scene", (), {}),
            STATUSBAR_HT_header=SimpleNamespace(
                draw=draw_status_bar,
                append=append_status_bar,
                remove=remove_status_bar,
            ),
            VIEW3D_MT_object_context_menu=SimpleNamespace(
                append=lambda draw: cls.context_menu_draws.append(draw),
                prepend=lambda draw: cls.context_menu_draws.insert(0, draw),
                remove=lambda draw: cls.context_menu_draws.remove(draw),
            ),
            OUTLINER_MT_object=SimpleNamespace(
                append=lambda draw: cls.outliner_menu_draws.append(draw),
                prepend=lambda draw: cls.outliner_menu_draws.insert(0, draw),
                remove=lambda draw: cls.outliner_menu_draws.remove(draw),
            ),
            NODE_MT_context_menu=SimpleNamespace(
                prepend=lambda draw: cls.node_menu_draws.insert(0, draw),
                remove=lambda draw: cls.node_menu_draws.remove(draw),
            ),
        )
        cls.registered = []
        cls.registered_tools = []
        cls.status_bar_draws = []
        cls.context_menu_draws = []
        cls.outliner_menu_draws = []
        cls.node_menu_draws = []
        fake_bpy.utils = SimpleNamespace(
            register_class=cls.registered.append,
            unregister_class=cls.registered.remove,
            register_tool=lambda tool, **options: cls.registered_tools.append(
                (tool, options)
            ),
            unregister_tool=lambda tool: cls.registered_tools.remove(
                next(item for item in cls.registered_tools if item[0] is tool)
            ),
        )
        fake_bpy.context = SimpleNamespace(
            preferences=SimpleNamespace(addons={}),
        )
        fake_bpy.app = SimpleNamespace(online_access=True)
        fake_bpy.path = SimpleNamespace(abspath=lambda path: path)
        fake_bpy.data = SimpleNamespace(
            objects=SimpleNamespace(get=lambda _name: None),
        )
        cls.bpy_import_patch = mock_bpy_imports(fake_bpy)
        cls.bpy_import_patch.start()
        cls.addClassCleanup(cls.bpy_import_patch.stop)
        sys.path.insert(0, str(SOURCE_ROOT))
        cls.paths_before_import = tuple(sys.path)
        cls.anyimage = importlib.import_module("anyimage")
        cls.tools = importlib.import_module("anyimage.tools")
        cls.keymaps = importlib.import_module("anyimage.keymaps")
        cls.runtime = importlib.import_module("anyimage.runtime")
        cls.ai_setup = importlib.import_module("anyimage.operators.ai_setup")
        cls.ai = importlib.import_module("anyimage.common.ai")
        cls.image_data = importlib.import_module("anyimage.common.image")
        cls.convert_to_plane = importlib.import_module(
            "anyimage.operators.convert_to_plane.operators"
        )
        cls.convert_to_plane_object = importlib.import_module(
            "anyimage.operators.convert_to_plane.object"
        )
        cls.cutout_main = importlib.import_module(
            "anyimage.operators.cutout_tool.operators"
        )
        cls.remove_background = importlib.import_module(
            "anyimage.operators.remove_background"
        )
        cls.upscale = importlib.import_module("anyimage.operators.upscale")
        cls.image_interaction = importlib.import_module("anyimage.common.viewport")
        cls.edit_mask = importlib.import_module(
            "anyimage.operators.mask_tool"
        )
        cls.image_selection = importlib.import_module("anyimage.common.selection")
        cls.image_frame = importlib.import_module(
            "anyimage.operators.frame_tool.operators"
        )
        cls.rectify = importlib.import_module(
            "anyimage.operators.rectify_tool.operators"
        )
        cls.rectify_geometry = importlib.import_module("anyimage.operators.rectify_tool.geometry")
        cls.rectify_preview = importlib.import_module("anyimage.operators.rectify_tool.preview")
        cls.cutout_geometry = importlib.import_module(
            "anyimage.operators.cutout_tool.geometry"
        )
        cls.paths_after_import = tuple(sys.path)
        cls.fake_bpy = fake_bpy


    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SOURCE_ROOT))
        cls.remove_modules()

        sys.modules.update(cls.previous_addon_modules)


    @staticmethod
    def remove_modules():
        for module_name in tuple(sys.modules):
            if module_name == "anyimage" or module_name.startswith("anyimage."):
                sys.modules.pop(module_name)


    def setUp(self):
        timer_callbacks = set()
        self.fake_bpy.app.timers = SimpleNamespace(
            is_registered=timer_callbacks.__contains__,
            register=lambda callback, **options: timer_callbacks.add(callback),
            unregister=timer_callbacks.remove,
        )
        preferences = SimpleNamespace(
            storage_root="",
            device="CUDA",
            upscale_model="REALESRGAN_GENERAL_WDN_X4V3",
            max_ai_input_size=2048,
        )
        self.fake_bpy.context.preferences.addons = {
            "anyimage": SimpleNamespace(preferences=preferences)
        }


    def tearDown(self):
        self.anyimage.runtime.close_active()
        self.registered.clear()
        self.registered_tools.clear()
        self.status_bar_draws.clear()
        self.context_menu_draws.clear()
        self.outliner_menu_draws.clear()
        self.node_menu_draws.clear()
        self.fake_bpy.data = SimpleNamespace(
            objects=SimpleNamespace(get=lambda _name: None),
        )
        if hasattr(self.fake_bpy.types.Scene, "anyimage_settings"):
            del self.fake_bpy.types.Scene.anyimage_settings
