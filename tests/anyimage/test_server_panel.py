import importlib
from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ServerPanelTest(BlenderTestCase):

    def test_server_panel_disables_all_controls_during_migration(self):
        for state, installed in (("STOPPED", True), ("ERROR", True), ("READY", True), ("STOPPED", False)):
            with self.subTest(state=state, installed=installed):
                events = self._draw_server_panel(
                    state, environment_ready=installed, migrating=True,
                    cached_names=("BIREFNET_LITE",),
                )
                self.assertTrue(events.operators)
                self.assertTrue(all(not enabled for _identifier, enabled in events.operators))


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
                self.assertNotIn("anyimage.unload_models", operators)
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
        events = self._draw_server_panel("READY", panel_type=panel_type)
        self.assertEqual(events.operators, [("anyimage.clear_job_files", True)])
        self.assertEqual(events.parents["anyimage.clear_job_files"].operator_context, "INVOKE_DEFAULT")

    def _draw_server_panel(self, state, cached_names=(), environment_ready=True, panel_type=None, migrating=False):
        events = SimpleNamespace(labels=[], operators=[], options={}, sequence=[], parents={})

        class Layout:
            def __init__(self, kind="layout", parent=None):
                self.kind = kind
                self.parent = parent
                self._enabled = True

            @property
            def enabled(self):
                return self._enabled and (self.parent is None or self.parent.enabled)

            @enabled.setter
            def enabled(self, value):
                self._enabled = value

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
                return_value=state == "BUSY" or migrating,
            ),
            patch.object(panel_module.runtime, "maintenance_busy", return_value=migrating),
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
