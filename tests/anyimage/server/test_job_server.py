import subprocess
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

import server as server_module
from server.models import onnx_runtime
from tests.support.paths import PROJECT_ROOT


def test_server_registration_and_metadata_do_not_load_backend_dependencies():
    script = textwrap.dedent("""
        import sys
        from types import SimpleNamespace

        blocked = ('server.jobs', 'server.model_manager', 'server.models',
                   'numpy', 'scipy', 'PIL', 'onnxruntime', 'fastapi', 'uvicorn')

        class BlockBackend:
            def find_spec(self, fullname, path=None, target=None):
                if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
                    raise ImportError('Backend dependency loaded early: ' + fullname)

        sys.meta_path.insert(0, BlockBackend())
        import server
        from server import model_catalog

        assert set(server.server.handlers) == {
            'download_model', 'download_required_models', 'remove_background',
            'upscale_image', 'generate_depth_plane_geometry',
            'generate_cutout_artifacts', 'generate_panorama_geometry',
        }
        assert set(server.server.resource_factories) == {'model_manager'}
        assert server.server.resources == {}

        manager = SimpleNamespace(download=lambda context, model: {"model": model})
        context = SimpleNamespace(resource=lambda name: manager)
        assert server.download_model(context, {"model": "test"}) == {"model": "test"}
        assert not any(name == "scipy" or name.startswith("scipy.") for name in sys.modules)
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT / "src/anyimage",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

class JobServerTest(unittest.TestCase):
    def test_model_job_resource_failure_clears_cache_without_retry(self):
        error = onnx_runtime.OnnxResourceError("memory exhausted")
        manager = SimpleNamespace(clear=Mock())
        context = SimpleNamespace(resource=lambda _name: manager)
        handler = Mock(side_effect=error)

        with self.assertRaises(onnx_runtime.OnnxResourceError) as raised:
            server_module._run_model_job(handler, context, {"value": 1})

        self.assertIs(raised.exception, error)
        handler.assert_called_once_with(context, {"value": 1})
        manager.clear.assert_called_once_with()

    def test_model_job_success_and_ordinary_failure_keep_cache(self):
        manager = SimpleNamespace(clear=Mock())
        context = SimpleNamespace(resource=lambda _name: manager)
        success = Mock(return_value={"value": 1})

        self.assertEqual(
            server_module._run_model_job(success, context, {}),
            {"value": 1},
        )
        with self.assertRaisesRegex(RuntimeError, "invalid input"):
            server_module._run_model_job(
                Mock(side_effect=RuntimeError("invalid input")),
                context,
                {},
            )

        manager.clear.assert_not_called()

    def test_every_model_inference_job_uses_resource_failure_boundary(self):
        context = object()
        parameters = {"value": 1}
        jobs = (
            server_module.remove_background,
            server_module.upscale_image,
            server_module.generate_depth_plane_geometry,
            server_module.generate_cutout_artifacts,
            server_module.generate_panorama_geometry,
        )

        with patch.object(
            server_module,
            "_run_model_job",
            return_value={"result": True},
        ) as run:
            for job in jobs:
                self.assertEqual(job(context, parameters), {"result": True})

        self.assertEqual(run.call_count, len(jobs))
