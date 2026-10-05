import importlib
from types import SimpleNamespace

from tests.support.blender import BlenderTestCase


class ColorMatchPanelTest(BlenderTestCase):

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
                        "scale": 6.0,
                        "scale_popup": 5.0,
                    },
                ),
            ],
        )
        self.assertTrue(palette_row.enabled)
        self.assertEqual(
            [name for _owner, name, _options in palette_calls],
            list(panel_module.COLOR_REFERENCE_PALETTE_PROPERTIES[:3]),
        )
        self.assertEqual(
            [round(cell.scale_x, 6) for cell in palette_cells],
            [1.246338, 0.965409, 0.788253],
        )

        settings.color_reference_palette_count = 0
        palette_calls.clear()
        palette_cells.clear()
        panel.draw(
            SimpleNamespace(
                scene=SimpleNamespace(anyimage_settings=settings),
            )
        )

        self.assertEqual(len(palette_cells), 1)
        self.assertEqual(
            [name for _owner, name, _options in palette_calls],
            list(panel_module.COLOR_REFERENCE_PALETTE_PROPERTIES[:1]),
        )
        self.assertEqual(
            [round(cell.scale_x, 6) for cell in palette_cells],
            [1.0],
        )
        self.assertEqual(panel.bl_label, "Color Match")
        self.assertLess(panel_module.ServerPanel.bl_order, panel.bl_order)
        self.assertLess(panel.bl_order, panel_module.DangerZonePanel.bl_order)
