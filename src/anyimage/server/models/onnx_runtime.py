"""Shared ONNX Runtime session helpers."""

CUDA_PROVIDER_OPTIONS = {
    "arena_extend_strategy": "kSameAsRequested",
}
RESOURCE_ERROR_TOKENS = (
    "out of memory",
    "bad allocation",
    "bad_alloc",
    "failed to allocate",
    "not enough memory",
    "insufficient memory",
)


class OnnxResourceError(RuntimeError):
    """ONNX Runtime could not allocate or report provider resources."""


def _raise_runtime_error(error, action, stage):
    if isinstance(error, UnicodeDecodeError):
        message = (
            f"ONNX Runtime could not report why model {stage} failed; "
            "GPU or system memory may be exhausted"
        )
        exception_type = OnnxResourceError
    elif isinstance(error, MemoryError) or any(
        token in str(error).lower() for token in RESOURCE_ERROR_TOKENS
    ):
        message = (
            f"Unable to {action} ONNX model because GPU or system memory "
            "was exhausted"
        )
        exception_type = OnnxResourceError
    else:
        message = f"Unable to {action} ONNX model: {error}"
        exception_type = RuntimeError
    raise exception_type(message) from error


def select_providers(requested, available):
    available = set(available)
    providers_for_device = {
        "cuda": "CUDAExecutionProvider",
        "directml": "DmlExecutionProvider",
        "coreml": "CoreMLExecutionProvider",
        "cpu": "CPUExecutionProvider",
    }
    if requested != "auto":
        provider = providers_for_device[requested]
        if provider not in available:
            raise RuntimeError(
                f"{requested.upper()} was requested but the ONNX Runtime "
                f"provider {provider} is not available"
            )
        providers = [provider]
        if (
            provider == "CoreMLExecutionProvider"
            and "CPUExecutionProvider" in available
        ):
            providers.append("CPUExecutionProvider")
        return providers
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
    try:
        session = onnxruntime.InferenceSession(
            str(path),
            providers=configured_providers,
            enable_fallback=requested_device == "auto",
            **session_options,
        )
    except Exception as error:
        _raise_runtime_error(error, "load", "loading")
    if requested_device != "auto" and providers[0] not in session.get_providers():
        raise RuntimeError(
            f"{requested_device.upper()} was requested but the ONNX Runtime "
            f"provider {providers[0]} could not be initialized"
        )
    return session


def run_session(
    session,
    output_names,
    input_feed,
    *,
    release_memory=True,
):
    run_options = None
    if release_memory and "CUDAExecutionProvider" in session.get_providers():
        import onnxruntime

        run_options = onnxruntime.RunOptions()
        run_options.add_run_config_entry(
            "memory.enable_memory_arena_shrinkage",
            "gpu:0",
        )
    try:
        if run_options is None:
            return session.run(output_names, input_feed)
        return session.run(output_names, input_feed, run_options=run_options)
    except Exception as error:
        _raise_runtime_error(error, "run", "execution")
