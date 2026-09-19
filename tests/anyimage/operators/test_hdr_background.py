from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bpy
import numpy as np
import pytest

from anyimage.common.hdr_image import HdrBackgroundInput
from anyimage.common.image import cleanup_image_input, image_rgba
from anyimage.common.image_target import ImageEditTarget
from anyimage.operators import remove_background as operators
from anyimage.runtime import JobOperatorBase
from tests.support.hdr_image import hdr_texture
from tests.support.image_texture import texture, texture_context


@pytest.mark.parametrize("owner_kind", ["texture", "empty"])
@pytest.mark.parametrize("shared", [False, True])
def test_hdr_background_undo_redo(hdr_texture, tmp_path, owner_kind, shared):
    node = hdr_texture
    source = node.image
    before = image_rgba(source).copy()
    if owner_kind == "empty":
        owner = bpy.data.objects.new("HDR Empty", None)
        owner.empty_display_type = "IMAGE"
        owner.data = source
        bpy.context.scene.collection.objects.link(owner)
        node.image = source if shared else None
    elif shared:
        other = node.id_data.nodes.new("ShaderNodeTexImage")
        other.image = source
    alpha_path = tmp_path / "alpha.npy"
    np.save(alpha_path, np.full((3, 4), 0.37123, np.float32))

    def current_owner():
        if owner_kind == "empty":
            return bpy.data.objects["HDR Empty"]
        return bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]

    def current_image():
        owner = current_owner()
        return owner.data if owner_kind == "empty" else owner.image

    def execute(operator, context):
        owner = current_owner()
        target_context = SimpleNamespace(object=owner, space_data=None) if owner_kind == "empty" else texture_context(owner)
        operator._image_target = ImageEditTarget.capture(target_context)
        operator._hdr_input = HdrBackgroundInput.prepare(current_image())
        operator.input_path, operator.delete_input = str(operator._hdr_input.path), True
        try:
            operator.response(context, SimpleNamespace(file=lambda key: alpha_path))
        finally:
            operator.cleanup()
        return {"FINISHED"}

    operation = operators.RunBackgroundRemoval
    bpy.context.preferences.edit.use_global_undo = True
    with patch.object(operation, "execute", execute), patch.object(operation, "poll", classmethod(lambda cls, context: True), create=True):
        bpy.utils.register_class(operation)
        try:
            bpy.ops.ed.undo_push(message="Before HDR removal")
            assert bpy.ops.anyimage.run_background_removal("EXEC_DEFAULT", True) == {"FINISHED"}
            after = image_rgba(current_image()).copy()
            np.testing.assert_array_equal(after[..., :3], before[..., :3])
            np.testing.assert_allclose(after[..., 3], before[..., 3] * np.float32(0.37123), atol=1e-7)
            assert bpy.ops.ed.undo() == {"FINISHED"}
            np.testing.assert_array_equal(image_rgba(current_image()), before)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            np.testing.assert_array_equal(image_rgba(current_image()), after)
            assert current_image().is_float
        finally:
            bpy.utils.unregister_class(operation)


@pytest.mark.parametrize("outcome", ["cancel", "raise"])
def test_hdr_submission_failure_releases_preview_and_snapshot(hdr_texture, outcome):
    target = ImageEditTarget.capture(texture_context(hdr_texture))
    paths = []

    def submit(operator, context):
        paths.append(Path(operator.input_path))
        assert paths[-1].is_file()
        if outcome == "raise":
            raise RuntimeError("Submission failed")
        return {"CANCELLED"}

    # Use the registered type so super().execute follows the real Operator inheritance.
    operation = operators.RunBackgroundRemoval
    with patch.object(ImageEditTarget, "capture", return_value=target), patch.object(JobOperatorBase, "execute", submit):
        bpy.utils.register_class(operation)
        try:
            if outcome == "raise":
                with pytest.raises(RuntimeError, match="Submission failed"):
                    bpy.ops.anyimage.run_background_removal("EXEC_DEFAULT")
            else:
                assert bpy.ops.anyimage.run_background_removal("EXEC_DEFAULT") == {"CANCELLED"}
        finally:
            bpy.utils.unregister_class(operation)
    assert paths and not paths[0].parent.exists()


def test_hdr_request_uses_alpha_output_and_current_still(hdr_texture):
    operation = operators.RunBackgroundRemoval
    snapshot = HdrBackgroundInput.prepare(hdr_texture.image)
    operator = SimpleNamespace(input_path=str(snapshot.path), _hdr_input=snapshot,
                               _image_target=SimpleNamespace())
    context = SimpleNamespace(scene=SimpleNamespace(anyimage_settings=SimpleNamespace()))
    try:
        with patch.object(operators, "require_environment"), patch.object(operators, "require_model"), patch.object(operators, "production_device", return_value="CPU"):
            parameters = operation.request(operator, context)
        assert parameters["output_kind"] == "alpha"
        assert "start_frame" not in parameters and "video_frames" not in parameters
    finally:
        cleanup_image_input(snapshot.path, True)
