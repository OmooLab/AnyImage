import importlib
from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ServerPanelTest(BlenderTestCase):

    def test_color_match_panel_draws_the_scene_reference_selector(self):
        panel_module = importlib.import_module("anyimage.panel")
        panel = panel_module.ColorMatchPanel()
        calls = []
        palette_calls = []
        palette_cells = []

        def palette_cell(**_options):
            cell = SimpleNamespace(
                scale_x=1.0,
                prop=lambda owner, name, **options: palette_calls.append(
                    (owner, name, options)
                ),
            )
            palette_cells.append(cell)
            return cell

        palette_row = SimpleNamespace(
            enabled=True,
            row=palette_cell,
        )
        panel.layout = SimpleNamespace(
            template_icon_view=lambda owner, name, **options: calls.append(
                (owner, name, options)
            ),
            label=lambda **options: calls.append(("label", options)),
            row=lambda **options: palette_row,
        )
        settings = SimpleNamespace(
            color_reference=None,
            color_reference_palette_count=3,
            **{
                name: (0.0, 0.0, 0.0)
                for name in panel_module.COLOR_REFERENCE_PALETTE_PROPERTIES
            },
            **{
                name: weight
                for name, weight in zip(
                    panel_module.COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES,
                    (0.5, 0.3, 0.2, 0.0, 0.0, 0.0, 0.0),
                )
            },
        )

        panel.draw(
            SimpleNamespace(
                scene=SimpleNamespace(anyimage_settings=settings),
            )
        )

        self.assertEqual(
            calls,
            [
                (
                    settings,
                    "color_reference_choice",
                    {
                        "show_labels": False,
                        "scale": 8.0,
                        "scale_popup": 5.0,
                    },
                ),
                ("label", {"text": "Reference Palette"}),
            ],
        )
        self.assertTrue(palette_row.enabled)
        self.assertEqual(
            [name for _owner, name, _options in palette_calls],
            list(panel_module.COLOR_REFERENCE_PALETTE_PROPERTIES[:3]),
        )
        self.assertEqual(
            [round(cell.scale_x, 6) for cell in palette_cells],
            [1.5, 0.9, 0.6],
        )
        self.assertEqual(panel.bl_label, "Color Match")
        self.assertLess(panel_module.ServerPanel.bl_order, panel.bl_order)
        self.assertLess(panel.bl_order, panel_module.DangerZonePanel.bl_order)


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
                self.assertEqual(events.options["anyimage.clear_models"]["text"], "Unload")
                self.assertIn(("anyimage.open_server_log", True), events.operators)
                self.assertNotIn("anyimage.clear_job_files", operators)
                self.assertLess(events.sequence.index("anyimage.open_server_log"),
                                events.sequence.index("No Models Loaded"))
                self.assertIs(events.parents["anyimage.clear_models"].parent,
                              events.parents["No Models Loaded"])

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

    def test_loaded_names_use_full_width_rows_below_header(self):
        names = ("MoGe-2 ViT-S Normal", "BiRefNet Lite", "Real-ESRGAN General WDN x4v3")
        for count in (1, 3):
            events = self._draw_server_panel("READY", cached_names=names[:count])
            header = events.parents["Loaded Models:"]
            self.assertIs(events.parents["anyimage.clear_models"].parent, header)
            for name in names[:count]:
                self.assertIn(("column", name, None), events.labels)
                self.assertIs(events.parents[name].parent, header.parent)
                self.assertGreater(events.sequence.index(name), events.sequence.index("anyimage.clear_models"))

    def test_panel_clear_control_uses_shared_operator_state(self):
        panel_module = importlib.import_module("anyimage.panel")
        for state, expected in (("READY", True), ("BUSY", False), ("STOPPED", False)):
            with (
                self.subTest(state=state),
                patch.object(
                    panel_module.runtime,
                    "server_status",
                    return_value={"state": state},
                ),
            ):
                self.assertEqual(panel_module.ClearModels.poll(None), expected)


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
        loaded = {
            str(index): name
            for index, name in enumerate(cached_names)
        }
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
