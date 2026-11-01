"""Cover translation catalogs and runtime-formatted UI messages."""

from string import Formatter
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blendjob.jobs import Job
from blendjob.translations import TRANSLATIONS as BLENDJOB_TRANSLATIONS

from tests.support.blender import BlenderTestCase


class TranslationsTest(BlenderTestCase):
    def test_tool_labels_do_not_use_builtin_mask_and_frame_translations(self):
        catalog = self.anyimage.TRANSLATIONS["zh_HANS"]
        builtin = {("Operator", "Mask"): "遮罩", ("Operator", "Frame"): "帧"}
        for tool, expected in ((self.tools.MaskTool, "局部显隐"),
                               (self.tools.FrameTool, "重设画框")):
            key = ("Operator", tool.bl_label)
            self.assertEqual(builtin.get(key, catalog.get(key)), expected)

    def test_base_messages_are_available_in_both_editions(self):
        from anyimage.translations import TRANSLATIONS as base
        from anyimage.ai_translations import TRANSLATIONS as ai

        self.assertFalse(base["zh_HANS"].keys() & ai["zh_HANS"].keys())
        self.assertEqual(self.anyimage.TRANSLATIONS["zh_HANS"], {
            **base["zh_HANS"], **ai["zh_HANS"],
        })
        for message in (
            "Frame: drag a rectangle to merge selected Image Empties; RMB or Esc cancels",
            "Rectify Aspect {ratio:.3f}: move mouse horizontally, LMB confirms, Backspace returns, RMB or Esc cancels",
            "click points; click start, double-click, or Enter to finish; Backspace removes",
            "Exclude areas below this opacity from the Cutout outline. Higher values exclude more semi-transparent edges.",
        ):
            self.assertIn(("*", message), base["zh_HANS"])

    def test_sidebar_translates_on_each_draw_without_changing_job_data(self):
        runtime = self.runtime.runtime
        catalog = self.anyimage.TRANSLATIONS["zh_HANS"]
        layout = Mock()
        layout.row.return_value = layout
        owner = SimpleNamespace(layout=layout)
        context = SimpleNamespace()
        message = "Generating panorama view {index}/{total}"
        args = {"index": 3, "total": 12}
        job = Job(runtime, "work", {}, progress=0.25, message=message, message_args=args)
        with patch.object(runtime, "jobs", [job]), patch.object(runtime, "redraw_ui"):
            runtime.draw_jobs(layout)
            self.assertEqual(layout.progress.call_args.kwargs["text"], "Generating panorama view 3/12")
            with patch.object(self.fake_bpy.app.translations, "pgettext_iface",
                              side_effect=lambda text: catalog.get(("*", text), text)):
                runtime.draw_jobs(layout)
                self.assertEqual(layout.progress.call_args.kwargs,
                                 {"factor": 0.25, "type": "BAR", "text": "全景视角生成中 3/12"})
                self.assertEqual(job.message, message)
            runtime.draw_jobs(layout)
            self.assertEqual(layout.progress.call_args.kwargs["text"], "Generating panorama view 3/12")
        layout.operator.assert_called_with("anyimage.cancel_job", text="", icon="X")

    def test_runtime_uses_registered_business_and_builtin_translations(self):
        from blendjob import JobRuntime
        runtime = self.runtime.runtime
        self.assertIs(type(runtime), JobRuntime)
        business = self.anyimage.TRANSLATIONS["zh_HANS"]
        builtin = BLENDJOB_TRANSLATIONS["zh_HANS"]
        for source in ("Installing Python", "Preparing Server", "Migrate Storage", "Downloading packages {count}"):
            self.assertNotIn(("*", source), business)
            self.assertIn(("*", source), builtin)
        catalog = {**builtin, **business}
        cases = (
            ("Removing background", {}, "背景移除中"),
            ("Generating panorama view {index}/{total}", {"index": 3, "total": 12}, "全景视角生成中 3/12"),
            ("Downloading {item} (mirror) {rate}", {"item": "MoGe 2", "rate": "1.2 MB/s"}, "MoGe 2 下载中（镜像） 1.2 MB/s"),
            ("Loading {model}", {"model": "Model {raw}"}, "Model {raw} 加载中"),
            ("Unknown {model}", {"model": "MoGe"}, "Unknown MoGe"),
            ("Unknown diagnostic: {path}", {}, "Unknown diagnostic: {path}"),
            ("Downloading packages (mirror) {count}", {"count": "4/10"}, "依赖包下载中（镜像） 4/10"),
        )
        with patch.object(runtime, "redraw_ui"):
            for source, args, expected in cases:
                job = Job(runtime, "work", {}, message=source, message_args=args)
                with patch.object(self.fake_bpy.app.translations, "pgettext_iface",
                                  side_effect=lambda text: catalog.get(("*", text), text)):
                    self.assertEqual(job.text, expected)
                if args:
                    self.assertEqual(job.text, source.format(**args))
                self.assertEqual(job.message, source)

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
