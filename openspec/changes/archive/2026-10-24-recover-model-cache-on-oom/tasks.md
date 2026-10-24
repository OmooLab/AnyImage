## 1. Session Load Recovery

- [x] 1.1 Add cache tests for first-load resource failure, successful one-time retry, repeated resource failure, and ordinary load failure.
- [x] 1.2 Route all three model categories through one Session factory helper that clears every slot and retries once only for `OnnxResourceError`.

## 2. Inference Failure Cleanup

- [x] 2.1 Add Server Job tests proving inference resource failures clear all cached Sessions while success and ordinary failures preserve them.
- [x] 2.2 Wrap all model inference Jobs in one shared resource-failure boundary that clears the model manager and re-raises without retrying inference.

## 3. Manual Cache Control

- [x] 3.1 Add `ClearModels.poll()` for the READY state and expose `Unload Models` through the shared AnyImage image action menu.
- [x] 3.2 Update menu and Server panel tests for the shared Operator and its READY, BUSY and STOPPED behavior.

## 4. Verification

- [x] 4.1 Run the related ONNX Runtime, model manager, Server Job, menu, panel and registration tests.
- [x] 4.2 Review the final diff for retry loops, non-resource cache eviction, duplicated cleanup handlers and unintended changes to the three-slot policy.
