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
                self.assertIn(("row", "No Models Loaded", None), events.labels)
                self.assertIn(
                    ("anyimage.clear_models", state == "READY"), events.operators
                )

        for state in ("STOPPED", "STARTING", "ERROR"):
            with self.subTest(state=state):
                events = self._draw_server_panel(state)
                operators = [identifier for identifier, _enabled in events.operators]
                self.assertNotIn("anyimage.restart_server", operators)
                self.assertNotIn("anyimage.stop_server", operators)


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


    def _draw_server_panel(self, state, cached_names=()):
        events = SimpleNamespace(labels=[], operators=[])

        class Layout:
            def __init__(self, kind="layout"):
                self.kind = kind
                self.enabled = True

            def row(self, **_options):
                return Layout("row")

            def column(self, **_options):
                return Layout("column")

            def label(self, **options):
                events.labels.append(
                    (self.kind, options.get("text"), options.get("icon"))
                )

            def operator(self, identifier, **_options):
                events.operators.append((identifier, self.enabled))
                return SimpleNamespace()

        panel_module = importlib.import_module("anyimage.panel")
        panel = panel_module.ServerPanel()
        panel.layout = Layout()
        loaded = {
            str(index): name
            for index, name in enumerate(cached_names)
        }
        with (
            patch.object(
                panel_module.runtime,
                "environment_ready",
                return_value=True,
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
