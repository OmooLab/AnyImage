import importlib
from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ServerPanelTest(BlenderTestCase):


    def test_server_panel_shows_controls_for_every_running_state(self):
        for state, label, icon in (
            ("READY", "Running", "RADIOBUT_ON"),
            ("BUSY", "Running (Busy)", "TIME"),
        ):
            with self.subTest(state=state):
                events = self._draw_server_panel(state)
                operators = [identifier for identifier, _enabled in events.operators]
                self.assertIn(("row", label, icon), events.labels)
                self.assertIn("anyimage.restart_server", operators)
                self.assertIn("anyimage.stop_server", operators)
                self.assertIn(("row", "Models Loaded", None), events.labels)
                self.assertNotIn("anyimage.clear_models", operators)
                self.assertIn(("row", "Generate Depth Map", "RADIOBUT_OFF"), events.labels)
                self.assertIn(("row", "Remove Background", "RADIOBUT_OFF"), events.labels)
                self.assertIn(("row", "Upscale Image", "RADIOBUT_OFF"), events.labels)
                self.assertIn(("anyimage.open_server_log", True), events.operators)
                self.assertNotIn("anyimage.clear_job_files", operators)
                self.assertLess(events.sequence.index("anyimage.open_server_log"),
                                events.sequence.index("Models Loaded"))

        for state in ("STOPPED", "STARTING", "ERROR"):
            with self.subTest(state=state):
                events = self._draw_server_panel(state)
                operators = [identifier for identifier, _enabled in events.operators]
                self.assertNotIn("anyimage.restart_server", operators)
                self.assertNotIn("anyimage.stop_server", operators)
                self.assertIn(("row", "Models Loaded", None), events.labels)
                self.assertIn(("row", "Generate Depth Map", "RADIOBUT_OFF"), events.labels)
                self.assertIn(("row", "Remove Background", "RADIOBUT_OFF"), events.labels)
                self.assertIn(("row", "Upscale Image", "RADIOBUT_OFF"), events.labels)


    def test_status_bar_reads_runtime_state(self):
        calls = []

        class Layout:
            def row(self, **_options):
                return self

            def progress(self, **options):
                calls.append(("progress", options))

            def operator(self, identifier, **_options):
                calls.append(("operator", identifier))

        runtime = self.anyimage.runtime
        runtime.active_job = object()
        runtime.progress = 0.4
        runtime.message = "Working"
        runtime._draw_status_bar(SimpleNamespace(layout=Layout()), None)
        runtime.active_job = None

        self.assertEqual(calls[0][1]["factor"], 0.4)
        self.assertEqual(calls[0][1]["text"], "Working")
        self.assertEqual(calls[1], ("operator", "anyimage.cancel_job"))

    def test_loaded_names_use_full_width_rows_below_header(self):
        names = ("MOGE2_VITS_NORMAL", "BIREFNET_LITE", "REALESRGAN_GENERAL_WDN_X4V3")
        for count in (1, 3):
            events = self._draw_server_panel("READY", cached_names=names[:count])
            header = events.parents["Models Loaded"]
            self.assertIs(events.parents["anyimage.clear_models"].parent, header)
            self.assertEqual(events.options["anyimage.clear_models"]["text"], "Unload")
            for task in (
                "Generate Depth Map  [ Fast ]",
                "Remove Background  [ Fast ]",
                "Upscale Image  [ Fast ]",
            )[:count]:
                self.assertIn(("row", task, "RADIOBUT_ON"), events.labels)
                self.assertIs(events.parents[task].parent.parent, header.parent)
                self.assertGreater(events.sequence.index(task), events.sequence.index("anyimage.clear_models"))


    def test_maintenance_controls_without_environment(self):
        events = self._draw_server_panel("STOPPED", environment_ready=False)
        self.assertIn(("anyimage.open_server_log", True), events.operators)
        self.assertNotIn("anyimage.clear_job_files", events.options)
        self.assertEqual(events.sequence[:2], ["Environment is not installed", "anyimage.open_server_log"])

    def test_danger_zone_is_last_collapsed_and_contains_only_cleanup(self):
        panel_module = importlib.import_module("anyimage.panel")
        panel_type = panel_module.DangerZonePanel
        self.assertIn(panel_type, self.anyimage.CLASSES)
        self.assertEqual(panel_type.bl_options, {"DEFAULT_CLOSED"})
        self.assertGreater(panel_type.bl_order, panel_module.ServerPanel.bl_order)
        for state, enabled in (("READY", True), ("BUSY", False), ("STOPPED", True)):
            events = self._draw_server_panel(state, panel_type=panel_type)
            self.assertEqual(events.operators, [("anyimage.clear_job_files", enabled)])

    def _draw_server_panel(self, state, cached_names=(), environment_ready=True, panel_type=None):
        events = SimpleNamespace(labels=[], operators=[], options={}, sequence=[], parents={})

        class Layout:
            def __init__(self, kind="layout", parent=None):
                self.kind = kind
                self.parent = parent
                self.enabled = True

            def row(self, **_options):
                return Layout("row", self)

            def column(self, **_options):
                return Layout("column", self)

            def label(self, **options):
                events.sequence.append(options.get("text"))
                events.parents[options.get("text")] = self
                events.labels.append(
                    (self.kind, options.get("text"), options.get("icon"))
                )

            def operator(self, identifier, **_options):
                events.sequence.append(identifier)
                events.parents[identifier] = self
                events.operators.append((identifier, self.enabled))
                events.options[identifier] = _options
                return SimpleNamespace()

        panel_module = importlib.import_module("anyimage.panel")
        panel = (panel_type or panel_module.ServerPanel)()
        panel.layout = Layout()
        loaded = dict(
            zip(("geometry", "background", "upscale"), cached_names)
        )
        with (
            patch.object(
                panel_module.runtime,
                "environment_ready",
                return_value=environment_ready,
            ),
            patch.object(
                panel_module.runtime,
                "server_busy",
                return_value=state == "BUSY",
            ),
            patch.object(
                panel_module.runtime,
                "server_status",
                return_value={
                    "state": state,
                    "message": state.title(),
                    "resources": {
                        "model_manager": {"loaded": loaded},
                    },
                },
            ),
        ):
            panel.draw(None)
        return events
