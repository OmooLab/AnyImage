import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from tests.anyimage.server.runtime_support import ServerTestCase

class ModelManagerTest(ServerTestCase):
    def test_background_cache_switches_model_directory_and_device_and_closes(self):
        from server.models import background

        cache = self.create_cache()
        loads = []

        def create(directory, device):
            result = object()
            loads.append((str(directory), device, result))
            return result

        with patch.object(background, "model_adapter", return_value=SimpleNamespace(create_session=create)):
            first, _ = cache.get_background("a/birefnet-lite", "cpu")
            assert cache.get_background("a/birefnet-lite", "cpu") == (first, 0.0)
            second, _ = cache.get_background("a/BEN2-ONNX", "cpu")
            third, _ = cache.get_background("a/birefnet-hr-matting", "cpu")
            fourth, _ = cache.get_background("b/birefnet-hr-matting", "cpu")
            assert cache.get_background("b/birefnet-hr-matting", "directml") == (fourth, 0.0)
            fifth, _ = cache.get_background("b/birefnet-lite", "directml")
        assert len(loads) == 5
        assert len({id(item) for item in (first, second, third, fourth, fifth)}) == 5
        assert cache.snapshot()["background"] == "birefnet-lite"
        assert loads[2][1] == loads[3][1] == "cpu"
        cache.close()
        assert cache.background_model is None
        assert cache.snapshot()["background"] == ""

    def test_required_model_download_skips_ready_model(self):
        manager = self.ModelManager(Path("."))
        downloads = []
        context = SimpleNamespace(progress=lambda *_args: None)
        with (
            patch.object(
                manager,
                "ready",
                side_effect=lambda key: key == "BEN2_BASE",
            ),
            patch.object(
                manager,
                "_download",
                side_effect=lambda _context, key, _progress: downloads.append(key),
            ),
        ):
            result = manager.download_missing(
                context,
                ("MOGE2_VITS_NORMAL", "BEN2_BASE"),
            )

        self.assertEqual(downloads, ["MOGE2_VITS_NORMAL"])
        self.assertEqual(result, {"downloaded": ["MOGE2_VITS_NORMAL"]})


    def test_models_are_owned_by_the_server_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.ModelManager(Path(directory))
            snapshot = manager.snapshot()
        self.assertEqual(
            snapshot,
            {
                "loaded": {
                    "background": "",
                    "geometry": "",
                    "upscale": "",
                }
            },
        )
        self.assertIn("server.model_catalog", sys.modules)


    def test_background_model_is_reused_for_matching_runtime_key(self):
        loads = []

        ben2 = ModuleType("server.models.onnx_ben2")
        ben2.create_session = lambda model_dir, device: (
            loads.append((model_dir, device)) or object()
        )
        cache = self.create_cache()
        device = SimpleNamespace(type="cuda")
        with patch.dict(sys.modules, {"server.models.onnx_ben2": ben2}):
            first, _load_ms = cache.get_background("BEN2-ONNX", device)
            second, cached_load_ms = cache.get_background("BEN2-ONNX", device)

        self.assertIs(first, second)
        self.assertEqual(loads, [("BEN2-ONNX", "cuda")])
        self.assertEqual(cache.snapshot()["background"], "BEN2-ONNX")
        self.assertEqual(cached_load_ms, 0.0)


    def test_model_cache_keeps_three_categories(self):
        cache = self.create_cache()
        ben2 = object()
        old_moge = object()
        upscale = object()
        cache.background_model = ben2
        cache.background_key = ("ben2", "cuda")
        cache.moge_model = old_moge
        cache.moge_key = ("old-moge", "cuda")
        cache.upscale_model = upscale
        cache.upscale_key = ("upscale", "cuda")
        new_moge = object()
        fake_moge = ModuleType("server.models.onnx_moge2")
        fake_moge.create_session = lambda _model_dir, _device: new_moge
        with patch.dict(sys.modules, {"server.models.onnx_moge2": fake_moge}):
            self.assertIs(cache.get_moge("new-moge", "cuda"), new_moge)

        self.assertIs(cache.background_model, ben2)
        self.assertIs(cache.upscale_model, upscale)
        self.assertEqual(cache.snapshot()["geometry"], "new-moge")


    def test_upscale_model_is_reused_for_matching_runtime_key(self):
        loads = []
        upscale = ModuleType("server.models.onnx_upscale")
        upscale.create_session = lambda model_dir, device: (
            loads.append((model_dir, device)) or object()
        )
        cache = self.create_cache()

        with patch.dict(
            sys.modules,
            {"server.models.onnx_upscale": upscale},
        ):
            first = cache.get_upscale("model", "cpu")
            second = cache.get_upscale("model", "cpu")

        self.assertIs(first, second)
        self.assertEqual(loads, [("model", "cpu")])
        self.assertEqual(cache.snapshot()["upscale"], "model")


    def test_inference_cleanup_keeps_every_cached_session(self):
        class Session:
            def get_providers(self):
                return ["CUDAExecutionProvider"]

            def run(self, _names, _feeds, run_options=None):
                self.run_options = run_options
                return [object()]

        class RunOptions:
            def add_run_config_entry(self, _key, _value):
                return None

        runtime = ModuleType("onnxruntime")
        runtime.RunOptions = RunOptions
        sessions = {
            "ben2": Session(),
            "moge2": Session(),
            "upscale": Session(),
        }
        ben2 = ModuleType("server.models.onnx_ben2")
        ben2.create_session = lambda _directory, _device: sessions["ben2"]
        moge2 = ModuleType("server.models.onnx_moge2")
        moge2.create_session = lambda _directory, _device: sessions["moge2"]
        upscale = ModuleType("server.models.onnx_upscale")
        upscale.create_session = lambda _directory, _device: sessions["upscale"]
        cache = self.create_cache()

        def assert_reused(first, getter, release_name):
            with (
                patch.dict(sys.modules, {"onnxruntime": runtime}),
                patch.object(
                    cache,
                    release_name,
                    wraps=getattr(cache, release_name),
                ) as release,
            ):
                self.onnx_runtime.run_session(first, ["output"], {"input": 1})
                second = getter()
            self.assertIs(first, second)
            release.assert_not_called()

        with patch.dict(
            sys.modules,
            {
                "server.models.onnx_ben2": ben2,
                "server.models.onnx_moge2": moge2,
                "server.models.onnx_upscale": upscale,
            },
        ):
            first_ben2, _load_ms = cache.get_background("BEN2-ONNX", "cuda")
            assert_reused(
                first_ben2,
                lambda: cache.get_background("BEN2-ONNX", "cuda")[0],
                "release_background",
            )

            first_moge2 = cache.get_moge("moge2", "cuda")
            assert_reused(
                first_moge2,
                lambda: cache.get_moge("moge2", "cuda"),
                "release_geometry",
            )

            first_upscale = cache.get_upscale("upscale", "cuda")
            assert_reused(
                first_upscale,
                lambda: cache.get_upscale("upscale", "cuda"),
                "release_upscale",
            )
