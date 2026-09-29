## 1. Adjustable Color Transform

- [x] 1.1 Add bounded Color and Lightness parameters to the color transform.
- [x] 1.2 Add proxy resizing and preview-quality execution that omits final-only byte processing.
- [x] 1.3 Add algorithm tests for parameter bounds, independent transfer axes, unchanged Alpha, deterministic defaults, and proxy dimensions/performance.

## 2. Preview Transaction

- [x] 2.1 Add a temporary preview binding transaction for Image Empty and Image Texture targets, including shared object material isolation.
- [x] 2.2 Restore original bindings without overwriting external target changes and clean all temporary Image and Material data on every exit path.
- [x] 2.3 Add transaction tests for direct, shared-image, shared-material, cancellation, confirmation preparation, and changed-target cases.

## 3. Modal Match Operator

- [x] 3.1 Convert `MatchColorReference` to invoke a Modal session with initial Color and Lightness 50%, bounded mouse mapping, Shift precision, and overlay feedback.
- [x] 3.2 Throttle mouse preview refreshes, confirm with one full-resolution `ImageEditTarget` commit, and cancel with lossless restoration.
- [x] 3.3 Add Modal tests for mouse controls, preview throttling, left-click and Enter confirmation, right-click and Esc cancellation, cleanup, and one-step undo/redo.

## 4. Verification

- [x] 4.1 Run the related color-match, image-target, menu, registration, Alpha, and Undo tests and fix failures.
- [x] 4.2 Run the full test suite, measure representative proxy refresh time, and inspect the final diff for persistent tuning properties, AI coupling, stale temporary resources, and unrelated changes.

## 5. Current Image Semantics

- [x] 5.1 Keep no persistent color baseline and make Set and Match use the current Image.
- [x] 5.2 Verify repeated matching accumulates from current pixels while shared-target isolation remains stable.
- [x] 5.3 Run related and full-suite verification, then inspect for stale baseline state.

## 6. Centered Preview Overlay

- [x] 6.1 Replace temporary target bindings with a Rectify-style centered GPU preview while keeping the target unchanged during the Modal.
- [x] 6.2 Draw Color, Lightness, adjustment, confirmation, and cancellation guidance around the centered preview.
- [x] 6.3 Update Modal cleanup and interaction tests, run related tests, and inspect for stale preview-binding code.

## 7. Independent Transfer Axes

- [x] 7.1 Use independent Color and Lightness transfer strengths from 0% to 100%.
- [x] 7.2 Start both axes at 50%, remove hidden transfer multipliers, and update the centered guidance.
- [x] 7.3 Update algorithm and Modal tests, run related and full-suite verification, and inspect for stale control names.

## 8. Reference Statistics

- [x] 8.1 Keep the existing sample cap while moderately emphasizing visible chromatic reference pixels.
- [x] 8.2 Add deterministic palette extraction from the same reference weighting for Panel feedback.
- [x] 8.3 Run related tests and inspect range, default, palette, and stale extrapolation references.
