## 1. Shared ONNX Runtime Boundary

- [x] 1.1 Add focused tests for Session creation and inference failures, covering explicit OOM messages, Unicode decode failures, and ordinary ONNX Runtime errors.
- [x] 1.2 Implement one shared error conversion path around `InferenceSession` creation and `session.run`, preserving the original exception chain and distinguishing load from execution.
- [x] 1.3 Update Provider selection so `auto` retains fallback behavior while unavailable explicit devices fail clearly.

## 2. Remove Duplicate Model Handling

- [x] 2.1 Remove Upscale's duplicate Provider resource-error detection and use the shared Runtime behavior.
- [x] 2.2 Keep and test Upscale's separate handling for Python/NumPy allocation failure of the complete output image.

## 3. Verification

- [x] 3.1 Run the ONNX Runtime, MoGe, BEN2, BiRefNet, Upscale, and model-manager AI tests.
- [x] 3.2 Review the final diff for duplicate error logic, unintended cache or release changes, and stale fallback expectations.
