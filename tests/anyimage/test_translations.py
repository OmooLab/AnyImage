"""Cover translation catalogs and runtime-formatted UI messages."""

from string import Formatter
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support.blender import BlenderTestCase


class TranslationsTest(BlenderTestCase):
    def test_tool_labels_do_not_use_builtin_mask_and_frame_translations(self):
        catalog = self.anyimage.TRANSLATIONS["zh_HANS"]
        builtin = {("Operator", "Mask"): "遮罩", ("Operator", "Frame"): "帧"}
        for tool, expected in ((self.tools.MaskTool, "局部显隐"),
                               (self.tools.FrameTool, "重设画框")):
            key = ("Operator", tool.bl_label)
            self.assertEqual(builtin.get(key, catalog.get(key)), expected)

    def test_paste_plane_uses_addon_translation_context(self):
        prop = self.anyimage.keymaps.PasteClipboardImage.__annotations__["import_as"]
        catalog = self.anyimage.TRANSLATIONS["zh_HANS"]
        self.assertNotIn(prop["translation_context"], ("*", "Operator"))
        self.assertEqual(catalog[(prop["translation_context"], prop["items"][0][1])], "面片")

    def test_status_bar_translates_on_each_draw_without_changing_job_data(self):
        runtime = self.runtime.runtime
        catalog = self.anyimage.TRANSLATIONS["zh_HANS"]
        layout = Mock()
        layout.row.return_value = layout
        owner = SimpleNamespace(layout=layout)
        context = SimpleNamespace()
        message = "Generating panorama view 3/12"
        with patch.object(runtime, "active_job", object()), patch.object(runtime, "redraw_ui"):
            runtime.update_ui(context, 0.25, message)
            runtime._draw_status_bar(owner, context)
            self.assertEqual(layout.progress.call_args.kwargs["text"], message)
            with patch.object(self.fake_bpy.app.translations, "pgettext_iface",
                              side_effect=lambda text: catalog.get(("*", text), text)):
                runtime._draw_status_bar(owner, context)
                self.assertEqual(layout.progress.call_args.kwargs,
                                 {"factor": 0.25, "type": "BAR", "text": "正在生成全景视角 3/12"})
                self.assertEqual(runtime._progress_message, message)
            runtime._draw_status_bar(owner, context)
            self.assertEqual(layout.progress.call_args.kwargs["text"], message)
        layout.operator.assert_called_with("anyimage.cancel_job", text="", icon="X")

    def test_progress_translates_installation_downloads_and_keeps_unknown_messages(self):
        module = self.anyimage.ai_translations
        catalog = module.TRANSLATIONS["zh_HANS"]
        cases = {
            "Upscaling image": "正在生成2倍高清图像",
            "Generating depth texture": "正在生成深度纹理",
            "Removing background": "正在移除背景",
            "Preparing Cutout Selection": "正在准备立体裁切选区",
            "3/3 Downloading packages (mirror) 4/10": "3/3 正在通过镜像下载依赖包 4/10",
            "2/3 Installing Python ...": "2/3 正在安装 Python…",
            "Downloading MoGe 2 (mirror) 1.2 MB/s": "正在通过镜像下载 MoGe 2 1.2 MB/s",
            "Downloading HAT Sharper 2.5 MB/s": "正在下载 HAT Sharper 2.5 MB/s",
            "Loading BEN2_BASE": "正在加载 BEN2_BASE",
            "MoGe 2 ready": "MoGe 2 已就绪",
            "Starting HAT Sharper download": "正在开始下载 HAT Sharper",
            "Background removed in 123 ms (model load 45 ms, total 200 ms)":
                "背景移除耗时 123 毫秒（模型加载 45 毫秒，总计 200 毫秒）",
            "Image is upscaled with HAT Sharper": "已使用 HAT Sharper 生成2倍高清图像",
            "Unknown diagnostic: {path} C:/models/model.onnx": "Unknown diagnostic: {path} C:/models/model.onnx",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(module.translate_progress(source), source)
                with patch.object(self.fake_bpy.app.translations, "pgettext_iface",
                                  side_effect=lambda text: catalog.get(("*", text), text)):
                    self.assertEqual(module.translate_progress(source), expected)

    def test_translations_preserve_format_fields(self):
        def fields(message):
            return sorted((name, spec, conversion) for _, name, spec, conversion in Formatter().parse(message)
                          if name is not None)

        for (_, source), translated in self.anyimage.TRANSLATIONS["zh_HANS"].items():
            self.assertTrue(translated)
            self.assertEqual(fields(source), fields(translated), source)

    def test_dynamic_menu_uses_current_blender_translation(self):
        menu = self.anyimage.ai_menu
        translate = self.fake_bpy.app.translations
        source = "Upscale ({width} × {height})"
        chinese = self.anyimage.TRANSLATIONS["zh_HANS"][("*", source)]
        with patch.object(menu, "image_edit_owner", return_value=object()), \
             patch.object(menu, "owner_image", return_value=SimpleNamespace(size=(640, 480))):
            self.assertEqual(menu.upscale_menu_label(None), "Upscale (1280 × 960)")
            with patch.object(translate, "pgettext_iface", return_value=chinese) as lookup:
                self.assertEqual(menu.upscale_menu_label(None), "2倍高清（1280 × 960）")
                lookup.assert_called_once_with(source)
            self.assertEqual(menu.upscale_menu_label(None), "Upscale (1280 × 960)")

    def test_reference_tooltip_cache_tracks_language_and_tooltip_setting(self):
        properties = self.anyimage.properties
        reference = SimpleNamespace(session_uid=1, name="Photo.png", size=(4, 3), as_pointer=lambda: 123)
        translations = self.fake_bpy.app.translations
        view = self.fake_bpy.context.preferences.view
        properties.invalidate_color_reference_items()
        with patch.object(properties, "color_reference_candidates", return_value=[reference]), \
             patch.object(properties, "release_unused_color_references"), \
             patch.object(properties, "color_reference_preview_icon", return_value=1):
            english = properties.color_reference_items(None, None)
            self.assertEqual(english[1][2], "Use Photo.png as the color reference")
            with patch.object(translations, "locale", "zh_HANS"), \
                 patch.object(translations, "pgettext_tip", return_value="使用 {name} 作为色彩参考图"):
                chinese = properties.color_reference_items(None, None)
                self.assertEqual(chinese[1][2], "使用 Photo.png 作为色彩参考图")
            with patch.object(translations, "locale", "zh_HANS"), \
                 patch.object(view, "use_translate_tooltips", False):
                self.assertEqual(properties.color_reference_items(None, None)[1][2], english[1][2])
        properties.invalidate_color_reference_items()

    def test_mask_status_translates_template_and_keeps_radius(self):
        catalog = self.anyimage.TRANSLATIONS["zh_HANS"]
        context = SimpleNamespace(workspace=SimpleNamespace(status_text_set=Mock()))
        operator = self.edit_mask.EditImageAlpha()
        operator.gesture, operator.mode, operator.radius = "BRUSH", "SUBTRACT", 25
        with patch.object(self.fake_bpy.app.translations, "pgettext_iface",
                          side_effect=lambda message: catalog.get(("*", message), message)):
            operator._set_status(context)
        context.workspace.status_text_set.assert_called_once_with(
            "局部显隐画笔：使用半径 25 像素的画笔涂绘；减去；右键或 Esc 取消"
        )
