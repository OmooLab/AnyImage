"""Verify queued image edits retain independent inputs and result targets."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common.job_image import prepare_target_input, apply_image_result
from anyimage.common.image import cleanup_image_input
from anyimage.common.image_target import ImageEditTarget
from anyimage.runtime import runtime
from tests.support.image_texture import write_result


@pytest.mark.parametrize("same_target,shared,delete_target", [
    (False, False, False), (True, False, False), (True, True, False), (False, False, True),
])
def test_queued_edits_capture_inputs_and_apply_in_order(tmp_path, same_target, shared, delete_target):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("A", width=4, height=3, alpha=True)
    image.filepath_raw = str(tmp_path / "input.png")
    image.file_format = "PNG"
    image.save()
    image.source = "FILE"
    image.pack()
    a = bpy.data.objects.new("A", None)
    a.empty_display_type = "IMAGE"
    a.data = image
    bpy.context.collection.objects.link(a)
    b = bpy.data.objects.new("B", None)
    b.empty_display_type = "IMAGE"
    b.data = image if shared else image.copy()
    b.data.pack()
    bpy.context.collection.objects.link(b)
    completed = []
    inputs = []

    class Edit(runtime.JobOperator):
        job_type = "remove_background"
        input_path = None

        def request(self, context):
            self.target = ImageEditTarget.capture(context)
            self.input_path = prepare_target_input(self.target)
            inputs.append(self.input_path)
            return {"input": str(self.input_path)}

        def response(self, context, result):
            apply_image_result(self.target, result.file("foreground"))
            completed.append(self.target.owner)

        def cleanup(self):
            cleanup_image_input(self.input_path)

    states = {}

    def submit(obj, index):
        output = tmp_path / str(index)
        output.mkdir()
        write_result(output, "foreground.png")
        runtime.server.submit.return_value = {"job_id": str(index), "directory": str(output)}
        states[str(index)] = {"state": "running"}
        operator = Edit()
        operator.report = Mock()
        context = SimpleNamespace(object=obj, scene=bpy.context.scene,
                                  space_data=SimpleNamespace(type="VIEW_3D"),
                                  window=None, window_manager=Mock())
        assert operator.execute(context) == {"RUNNING_MODAL"}
        return operator, context

    with (
        patch.object(runtime, "can_submit", return_value=True),
        patch.object(runtime, "redraw_ui"), patch.object(runtime, "enable"),
        patch.object(runtime.server, "submit"), patch.object(runtime.server, "poll"),
        patch.object(runtime.server, "mark_job_complete"),
        patch.object(runtime.server, "status", side_effect=states.__getitem__),
    ):
        first, ctx1 = submit(a, 1)
        second, ctx2 = submit(a if same_target else b, 2)
        assert inputs[0] != inputs[1]
        assert all(path.exists() for path in inputs)
        # Runtime waits for the earlier result even when the second is ready.
        states["2"] = {"state": "succeeded", "result": {"foreground": "foreground.png"}}
        runtime._tick()
        assert completed == [] and inputs[1].exists()
        if delete_target:
            bpy.data.objects.remove(a, do_unlink=True)
        states["1"] = {"state": "succeeded", "result": {"foreground": "foreground.png"}}
        runtime._tick()
        assert first._job.state == ("failed" if delete_target else "succeeded")
        assert second._job.state == "succeeded"
        assert completed == ([b] if delete_target else [a, a if same_target else b])
        assert not runtime.jobs
        assert all(not path.exists() for path in inputs)
        if shared:
            assert tuple(b.data.size) == (4, 3)


def test_disk_input_is_snapshotted_before_queueing(tmp_path):
    from anyimage.common.job_image import prepare_image_input
    source = tmp_path / "source.png"
    source.write_bytes(b"first")
    with patch("anyimage.common.job_image.is_animated_image", return_value=False), \
         patch("anyimage.common.job_image.image_is_packed", return_value=False), \
         patch("anyimage.common.job_image.image_path", return_value=source):
        first = prepare_image_input(SimpleNamespace(is_dirty=False, source="FILE"))
        source.write_bytes(b"second")
        second = prepare_image_input(SimpleNamespace(is_dirty=False, source="FILE"))
    try:
        assert first.read_bytes() == b"first"
        assert second.read_bytes() == b"second"
    finally:
        cleanup_image_input(first)
        cleanup_image_input(second)
    assert source.read_bytes() == b"second"


@pytest.mark.parametrize("kind", ["dirty", "generated"])
def test_input_snapshot_exports_current_unsaved_pixels(tmp_path, kind):
    from anyimage.common.image import image_pixels
    from anyimage.common.job_image import prepare_image_input

    if kind == "dirty":
        original = tmp_path / "original.png"
        Image.new("RGBA", (2, 1), (255, 0, 0, 255)).save(original)
        image = bpy.data.images.load(str(original), check_existing=False)
    else:
        image = bpy.data.images.new("Generated input", width=2, height=1, alpha=True)
    image.colorspace_settings.name = "sRGB"
    image.alpha_mode = "STRAIGHT"
    image.pixels.foreach_set([0.1, 0.4, 0.7, 0.5, 0.8, 0.2, 0.3, 1.0])
    image.update()
    before = image_pixels(image)
    settings = image.source, image.filepath_raw, image.file_format
    path = None
    try:
        path = prepare_image_input(image)
        with Image.open(path) as snapshot:
            np.testing.assert_allclose(np.asarray(snapshot).reshape(-1) / 255, before, atol=1 / 255)
        np.testing.assert_array_equal(image_pixels(image), before)
        assert (image.source, image.filepath_raw, image.file_format) == settings
        if kind == "dirty":
            with Image.open(original) as disk:
                assert disk.getpixel((0, 0)) == (255, 0, 0, 255)
    finally:
        cleanup_image_input(path)
        bpy.data.images.remove(image)
