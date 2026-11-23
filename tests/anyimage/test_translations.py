"""Cover translation catalogs and runtime-formatted UI messages."""

from string import Formatter
from types import SimpleNamespace
from unittest.mock import Mock, patch

from blendjob.jobs import Job
from blendjob.translations import TRANSLATIONS as BLENDJOB_TRANSLATIONS

from tests.support.blender import BlenderTestCase


class TranslationsTest(BlenderTestCase):
    def test_short_toolbar_labels_have_their_own_chinese_translations(self):
        for addon in (self.anyimage, self.lite_addon):
            catalog = addon.TRANSLATIONS["zh_HANS"]
            for tool, english, chinese in (
                (self.tools.FrameTool, "Frame", "重设画框"),
                (self.tools.MaskTool, "Mask", "局部显隐"),
            ):
                self.assertEqual(tool.bl_label.rstrip("\u200b"), english)
                self.assertNotIn(("Operator", english), catalog)
                self.assertEqual(catalog["Operator", tool.bl_label], chinese)

    def test_base_messages_are_available_in_both_editions(self):
        lite = self.lite_addon.TRANSLATIONS["zh_HANS"]
        full = self.anyimage.TRANSLATIONS["zh_HANS"]
        self.assertLess(lite.items(), full.items())
        self.assertNotIn(("*", "Set Up AI Server"), lite)
        self.assertEqual(full[("*", "Set Up AI Server")], "设置 AI 服务器")
        for message in (
            "Automatic Material Preview",
            "Draw Frame",
            "Snap to Preset",
            "Choose Shape",
            "Exclude areas below this opacity from the Cutout outline. Higher values exclude more semi-transparent edges.",
        ):
            self.assertIn(("*", message), lite)

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
        menu = self.anyimage.ai_menus
        translate = self.fake_bpy.app.translations
        source = "Upscale ({width} × {height})"
        chinese = self.anyimage.TRANSLATIONS["zh_HANS"][("*", source)]
        with patch.object(menu, "editable_still_image", return_value=SimpleNamespace(size=(640, 480))):
            self.assertEqual(menu.upscale_menu_label(None), "Upscale (1280 × 960)")
            with patch.object(translate, "pgettext_iface", return_value=chinese) as lookup:
                self.assertEqual(menu.upscale_menu_label(None), "2倍高清（1280 × 960）")
                lookup.assert_called_once_with(source)
            self.assertEqual(menu.upscale_menu_label(None), "Upscale (1280 × 960)")
