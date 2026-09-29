## 1. Adjustable Color Transform

- [x] 1.1 Add bounded Match and low-frequency Contrast parameters to the color transform while preserving existing default output behavior.
- [x] 1.2 Add proxy resizing and preview-quality execution that omits final-only byte processing.
- [x] 1.3 Add algorithm tests for parameter bounds, stronger tonal range, unchanged Alpha, deterministic defaults, and proxy dimensions/performance.

## 2. Preview Transaction

- [x] 2.1 Add a temporary preview binding transaction for Image Empty and Image Texture targets, including shared object material isolation.
- [x] 2.2 Restore original bindings without overwriting external target changes and clean all temporary Image and Material data on every exit path.
- [x] 2.3 Add transaction tests for direct, shared-image, shared-material, cancellation, confirmation preparation, and changed-target cases.

## 3. Modal Match Operator

- [x] 3.1 Convert `MatchColorReference` to invoke a Modal session with initial Match 100% and Contrast 0%, bounded mouse mapping, Shift precision, and Header feedback.
- [x] 3.2 Throttle mouse preview refreshes, confirm with one full-resolution `ImageEditTarget` commit, and cancel with lossless restoration.
- [x] 3.3 Add Modal tests for mouse controls, preview throttling, left-click and Enter confirmation, right-click and Esc cancellation, cleanup, and one-step undo/redo.

## 4. Verification

- [x] 4.1 Run the related color-match, image-target, menu, registration, Alpha, and Undo tests and fix failures.
- [x] 4.2 Run the full test suite, measure representative proxy refresh time, and inspect the final diff for persistent tuning properties, AI coupling, stale temporary resources, and unrelated changes.

## 5. Current Image Semantics

- [x] 5.1 Keep no persistent color baseline and make Set and Match use the current Image.
- [x] 5.2 Verify repeated matching accumulates from current pixels while shared-target isolation remains stable.
- [x] 5.3 Run related and full-suite verification, then inspect for stale baseline state.
