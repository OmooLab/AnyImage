import json
from types import SimpleNamespace
from types import MethodType
from unittest.mock import Mock

import pytest


from anyimage.common.selection import SelectionPath
from anyimage.common import viewport
from anyimage.operators.cutout_tool import interaction
from anyimage.operators.cutout_tool import operators as cutout_main


class Pie:
    def __init__(self):
        self.calls = []

    def operator(self, identifier, **options):
        operator = SimpleNamespace()
        self.calls.append((identifier, options, operator))
        return operator


class WindowManager:
    def __init__(self):
        self.pie = Pie()
        self.events = []

    def popup_menu_pie(self, _event, draw, **_options):
        self.events.append(_event)
        menu = SimpleNamespace(layout=SimpleNamespace(menu_pie=lambda: self.pie))
        draw(menu, None)


def cutout_context(
    window_manager,
    edge_length=0.1,
    generate_normal=False,
    alpha_threshold=0.9,
    fine_outline=True,
):
    settings = SimpleNamespace(
        cutout_edge_length=edge_length,
        cutout_generate_normal=generate_normal,
        cutout_alpha_threshold=alpha_threshold,
        cutout_fine_outline=fine_outline,
    )
    return SimpleNamespace(
        window_manager=window_manager,
        scene=SimpleNamespace(anyimage_settings=settings),
    )


def test_cutout_menu_captures_fine_outline_before_later_redraw(monkeypatch):
    window_manager = WindowManager()
    context = cutout_context(window_manager)
    monkeypatch.setattr(interaction, "ai_ready", lambda: False)

    def delayed_popup(_event, draw, **_options):
        context.scene.anyimage_settings.cutout_fine_outline = False
        draw(SimpleNamespace(layout=SimpleNamespace(menu_pie=lambda: window_manager.pie)), None)

    window_manager.popup_menu_pie = delayed_popup
    interaction.open_shape_pie(context, object(), cutout_source(),
                               SelectionPath(points=((0, 0), (10, 0), (0, 10))))
    assert all(call[2].fine_outline is True for call in window_manager.pie.calls)


def cutout_source(name="Source", size=(2048, 1024)):
    return SimpleNamespace(name=name, data=SimpleNamespace(size=size))


def test_cutout_pie_uses_two_local_shapes_without_ai(monkeypatch):
    window_manager = WindowManager()
    context = cutout_context(window_manager, generate_normal=True)
    source = cutout_source()
    monkeypatch.setattr(interaction, "ai_ready", lambda: False)

    interaction.open_shape_pie(
        context,
        object(),
        source,
        SelectionPath(points=((0, 0), (10, 0), (0, 10))),
    )

    assert [call[2].shape for call in window_manager.pie.calls] == [
        "FLAT",
        "SOLID",
    ]
    assert [call[1]["text"] for call in window_manager.pie.calls] == [
        "Flat",
        "Solid",
    ]
    assert all(
        call[0] == "anyimage.cutout_selection_to_shape"
        for call in window_manager.pie.calls
    )
    assert not any(call[2].generate_normal for call in window_manager.pie.calls)
    assert all(call[2].edge_length == 0.1 for call in window_manager.pie.calls)


def test_cutout_pie_passes_image_lasso_options_to_all_ai_shapes(monkeypatch):
    window_manager = WindowManager()
    context = cutout_context(
        window_manager,
        edge_length=0.05,
        generate_normal=True,
        alpha_threshold=0.1,
        fine_outline=False,
    )
    source = cutout_source(size=(4096, 2048))
    monkeypatch.setattr(interaction, "ai_ready", lambda: True)
    serialized = []
    original_to_json = SelectionPath.to_json

    def record_to_json(selection_path):
        value = original_to_json(selection_path)
        serialized.append(value)
        return value

    monkeypatch.setattr(SelectionPath, "to_json", record_to_json)

    interaction.open_shape_pie(
        context,
        object(),
        source,
        SelectionPath(
            points=((0, 0), (10, 0), (0, 10)),
        ),
    )

    assert [call[2].shape for call in window_manager.pie.calls] == [
        "FLAT",
        "SOLID",
        "DEPTH_SYMMETRY",
        "DEPTH_SOLID",
    ]
    assert all(call[2].generate_normal for call in window_manager.pie.calls)
    assert all(call[2].alpha_threshold == 0.1 for call in window_manager.pie.calls)
    assert all(call[2].fine_outline is False for call in window_manager.pie.calls)
    assert len(serialized) == 1
    assert set(json.loads(serialized[0])) == {"points"}
    assert all(
        call[2].selection_path_json == serialized[0]
        for call in window_manager.pie.calls
    )
    assert all(
        SelectionPath.from_json(call[2].selection_path_json).points
        == ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))
        for call in window_manager.pie.calls
    )
    assert all(call[2].edge_length == 0.05 for call in window_manager.pie.calls)


def test_cutout_lasso_submission_passes_only_the_selected_path(monkeypatch):
    source = cutout_source()
    window_manager = WindowManager()
    context = cutout_context(window_manager)
    monkeypatch.setattr(cutout_main, "require_image_empty", lambda _name: source)
    monkeypatch.setattr(interaction, "ai_ready", lambda: False)
    path = SelectionPath(points=((0, 0), (10, 0), (0, 10)))
    operator = SimpleNamespace(source_object_name=source.name, _pie_event=object(), gesture="LASSO")
    result = cutout_main.SelectCutoutSelection._submit_selection_path(operator, context, path)
    assert result == {"FINISHED"}
    assert SelectionPath.from_json(window_manager.pie.calls[0][2].selection_path_json) == path


def test_cutout_tool_starts_on_press_and_keeps_shift_selection():
    from anyimage.tools import CutoutTool

    keymap = CutoutTool.bl_keymap
    assert keymap[0][1]["value"] == "PRESS"
    assert len(keymap) == 2
    assert keymap[1][0] == "view3d.select"
    assert keymap[1][2] == {"properties": [("toggle", True)]}
    assert cutout_main.SelectCutoutSelection.resolve_on_press


def test_cutout_f_has_no_option_shortcut(monkeypatch):
    operator = SimpleNamespace(
        gesture="LASSO",
        active_tool_id="anyimage.cutout_lasso",
    )
    monkeypatch.setattr(viewport, "active_view3d_tool_id", lambda _context: None)

    result = cutout_main.SelectCutoutSelection.modal(
        operator,
        SimpleNamespace(),
        SimpleNamespace(type="F", value="PRESS"),
    )

    assert result == {"PASS_THROUGH"}


def test_cutout_menu_keeps_submitted_gesture_during_redraw(monkeypatch):
    window_manager = WindowManager()
    context = cutout_context(window_manager)
    monkeypatch.setattr(interaction, "ai_ready", lambda: True)

    def delayed_popup(_event, draw, **_options):
        context.scene.anyimage_settings.cutout_gesture = "LASSO"
        draw(SimpleNamespace(layout=SimpleNamespace(menu_pie=lambda: window_manager.pie)), None)

    window_manager.popup_menu_pie = delayed_popup
    interaction.open_shape_pie(
        context, object(), cutout_source(),
        SelectionPath(points=((0, 0), (10, 0), (0, 10))), gesture="POLYLINE",
    )
    assert all(call[2].gesture == "POLYLINE" for call in window_manager.pie.calls)


@pytest.mark.parametrize("finish", ("START", "DOUBLE_CLICK", "RET", "NUMPAD_ENTER"))
def test_cutout_polyline_edits_and_submits_through_shared_gesture(monkeypatch, finish):
    window_manager = WindowManager()
    context = cutout_context(window_manager)
    context.area = SimpleNamespace(tag_redraw=Mock())
    context.region = context.region_data = object()
    context.scene.anyimage_settings.cutout_gesture = "POLYLINE"
    source = cutout_source()
    monkeypatch.setattr(viewport, "active_view3d_tool_id", lambda _context: None)
    monkeypatch.setattr(viewport, "require_image_empty", lambda _name: source)
    monkeypatch.setattr(cutout_main, "require_image_empty", lambda _name: source)
    monkeypatch.setattr(viewport, "deserialize_matrix", lambda _data: None)
    monkeypatch.setattr(viewport, "image_empty_bounds", lambda _source: None)
    monkeypatch.setattr(viewport, "screen_path_to_image_pixels", lambda path, *_args: path)
    monkeypatch.setattr(interaction, "ai_ready", lambda: False)
    operator = SimpleNamespace(
        source_object_name=source.name, source_matrix_data="matrix",
        active_tool_id="anyimage.cutout_lasso", _path=[(0, 0)],
        _polyline_confirm_type=None,
        _finish=Mock(),
    )
    for name in ("_modal_polyline", "_confirm_polyline", "_complete", "_submit_selection_path"):
        setattr(operator, name, MethodType(getattr(cutout_main.SelectCutoutSelection, name), operator))
    cutout_main.SelectCutoutSelection._read_gesture_settings(operator, context)

    def event(kind, value="PRESS", point=(100, 100)):
        return cutout_main.SelectCutoutSelection.modal(operator, context, SimpleNamespace(
            type=kind, value=value, mouse_region_x=point[0], mouse_region_y=point[1],
        ))

    assert event("RET") == {"RUNNING_MODAL"}
    event("LEFTMOUSE", point=(100, 0))
    event("LEFTMOUSE", point=(100, 100))
    event("BACK_SPACE")
    assert operator._path == [(0, 0), (100, 0)]
    event("LEFTMOUSE", point=(100, 100))
    if finish == "START":
        result = event("LEFTMOUSE", point=(0, 0))
    elif finish == "DOUBLE_CLICK":
        result = event("LEFTMOUSE", "DOUBLE_CLICK")
    else:
        result = event(finish)
    assert result == {"RUNNING_MODAL"}
    assert window_manager.events == []
    operator._finish.assert_not_called()
    points = tuple(operator._path)
    assert event("MOUSEMOVE", point=(200, 200)) == {"RUNNING_MODAL"}
    assert event("BACK_SPACE") == {"RUNNING_MODAL"}
    assert tuple(operator._path) == points
    release_type = "LEFTMOUSE" if finish in {"START", "DOUBLE_CLICK"} else finish
    assert event("SPACE", "RELEASE") == {"RUNNING_MODAL"}
    result = event(release_type, "RELEASE")
    assert result == {"FINISHED"}
    assert len(window_manager.events) == 1
    assert window_manager.events[0].value == "RELEASE"
    operator._finish.assert_called_once_with(context)
    submitted = window_manager.pie.calls[0][2]
    assert submitted.gesture == "POLYLINE"
    assert SelectionPath.from_json(submitted.selection_path_json).points == ((0, 0), (100, 0), (100, 100))


@pytest.mark.parametrize("reason", ("ESC", "RIGHTMOUSE", "TOOL_SWITCH"))
def test_cutout_polyline_cancel_cleans_preview(monkeypatch, reason):
    context = SimpleNamespace()
    operator = SimpleNamespace(
        gesture="POLYLINE", active_tool_id="anyimage.cutout_lasso", _finish=Mock(),
        _polyline_confirm_type="LEFTMOUSE",
    )
    operator._cancel_and_finish = MethodType(viewport.ImageGesture._cancel_and_finish, operator)
    monkeypatch.setattr(viewport, "active_view3d_tool_id", lambda _context: "other" if reason == "TOOL_SWITCH" else None)
    result = cutout_main.SelectCutoutSelection.modal(operator, context, SimpleNamespace(type=reason, value="PRESS"))
    assert result == {"CANCELLED"}
    operator._finish.assert_called_once_with(context)
