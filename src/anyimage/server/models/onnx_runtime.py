"""Shared ONNX Runtime session helpers."""

CUDA_PROVIDER_OPTIONS = {
    "arena_extend_strategy": "kSameAsRequested",
}


def select_providers(requested, available):
    available = set(available)
    providers_for_device = {
        "cuda": ("CUDAExecutionProvider", "DmlExecutionProvider"),
        "directml": ("DmlExecutionProvider",),
        "coreml": ("CoreMLExecutionProvider",),
        "cpu": ("CPUExecutionProvider",),
    }
    if requested != "auto":
        candidates = providers_for_device[requested]
        for provider in candidates:
            if provider in available:
                providers = [provider]
                if (
                    provider == "CoreMLExecutionProvider"
                    and "CPUExecutionProvider" in available
                ):
                    providers.append("CPUExecutionProvider")
                return providers
        if "CPUExecutionProvider" in available:
            return ["CPUExecutionProvider"]
        raise RuntimeError(
            f"{requested.upper()} was requested but the ONNX Runtime "
            f"providers {', '.join(candidates)} are not available"
        )
    priorities = (
        "CUDAExecutionProvider",
        "CoreMLExecutionProvider",
        "DmlExecutionProvider",
        "OpenVINOExecutionProvider",
        "CPUExecutionProvider",
    )
    providers = [provider for provider in priorities if provider in available]
    if not providers:
        raise RuntimeError("ONNX Runtime has no usable execution provider")
    return providers


def create_session(
    path,
    requested_device="auto",
    *,
    coreml_options=None,
):
    import onnxruntime

    providers = select_providers(
        requested_device,
        onnxruntime.get_available_providers(),
    )
    configured_providers = []
    for provider in providers:
        if provider == "CUDAExecutionProvider":
            provider = (provider, dict(CUDA_PROVIDER_OPTIONS))
        elif provider == "CoreMLExecutionProvider" and coreml_options:
            provider = (provider, dict(coreml_options))
        configured_providers.append(provider)
    session_options = {}
    if "DmlExecutionProvider" in providers:
        options = onnxruntime.SessionOptions()
        options.enable_mem_pattern = False
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
        session_options["sess_options"] = options
    return onnxruntime.InferenceSession(
        str(path),
        providers=configured_providers,
        **session_options,
    )


def run_session(
    session,
    output_names,
    input_feed,
    *,
    release_memory=True,
):
    if not release_memory or "CUDAExecutionProvider" not in (
        session.get_providers()
    ):
        return session.run(output_names, input_feed)

    import onnxruntime

    run_options = onnxruntime.RunOptions()
    run_options.add_run_config_entry(
        "memory.enable_memory_arena_shrinkage",
        "gpu:0",
    )
    return session.run(output_names, input_feed, run_options=run_options)
