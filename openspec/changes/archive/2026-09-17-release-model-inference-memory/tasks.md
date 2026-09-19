## 1. Shared ONNX Runtime Memory Policy

- [x] 1.1 Extend the shared ONNX Session creation path with CUDA `kSameAsRequested` arena configuration, and verify CUDA, CoreML and plain Provider configurations with runtime helper tests.
- [x] 1.2 Add the Provider-aware shared Session run entry that applies `memory.enable_memory_arena_shrinkage=gpu:0` only to a completing CUDA run, and verify CUDA cleanup, intermediate run, fallback Provider and output passthrough scenarios with unit tests.
- [x] 1.3 Add an ONNX Runtime 1.24 API smoke test for constructing the required `RunOptions` entry, and verify it runs without requiring a CUDA device.

## 2. Model Adapter Integration

- [x] 2.1 Migrate BEN2 ONNX inference to the shared run entry with an explicit completion flag, and verify preprocessing, alpha output and cleanup-enabled output remain unchanged in `test_model_ben2_onnx.py`.
- [x] 2.2 Migrate DA3 ONNX inference to the shared run entry with an explicit completion flag, and verify joint prediction fields, attention validation and completion forwarding in `test_model_da3_onnx.py`.
- [x] 2.3 Migrate MoGe-2 ONNX inference to the shared run entry with an explicit completion flag, and verify prediction fields, Provider selection and completion forwarding in `test_model_moge2_onnx.py`.
- [x] 2.4 Migrate Upscale tile inference to the shared run entry and mark only the final requested tile as completing, and verify multi-tile call order, output equality and existing resource-error conversion in `test_model_upscale_onnx.py`.

## 3. Business Inference Boundaries

- [x] 3.1 Propagate the completion flag through BEN2 single-image, multi-frame, Selection and Debug flows, and verify only the final frame requests cleanup while single-image flows still request it.
- [x] 3.2 Propagate the completion flag through DA3 joint/per-frame and MoGe-2 single/multi-image production and Debug flows, and verify each complete operation records exactly one cleanup request on its final model run.
- [x] 3.3 Propagate the completion flag through production and Debug Upscale frame loops so only the final frame's final tile requests cleanup, and verify single-frame, multi-frame and multi-tile sequences in Server Job tests.

## 4. Lifecycle and Project Verification

- [x] 4.1 Extend ModelManager lifecycle tests to prove BEN2, DA3, MoGe-2 and Upscale cleanup does not call their Session release paths and a matching subsequent request returns the same cached Session.
- [x] 4.2 Update `docs/internals/runtime.md` to describe cached Session ownership and end-of-operation temporary arena cleanup, and verify the model lifecycle section matches all four model families and Provider limitations.
- [x] 4.3 Run `uv run pytest` and verify the complete test suite passes without changes to Job protocols, model outputs or existing Upscale OOM behavior.
