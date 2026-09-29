## 1. Color Reference State

- [x] 1.1 Add the current Scene color-reference Image property and helpers that validate static readable references without fallback.
- [x] 1.2 Implement and register `SetColorReference` with context-target resolution, reference replacement, and undo-safe state updates.
- [x] 1.3 Add tests for setting, replacing, persisting, removing, and rejecting animated color references from each supported image context.

## 2. Deterministic Color Matching

- [x] 2.1 Add a focused color-matching module that samples large inputs, converts interpreted RGB to the perceptual working representation, and computes Alpha-weighted reference and whole-target statistics.
- [x] 2.2 Implement the monotonic sparse-anchor luminance transform and regularized, gain-limited chroma transform at fixed complete strength.
- [x] 2.3 Implement low-frequency adjustment-field application across all target RGB, smooth chroma gamut compression, deterministic byte dithering, and float-precision output without changing dimensions or Alpha.
- [x] 2.4 Add synthetic unit tests for deterministic output, Alpha-weighted reference extraction, hidden target RGB migration with unchanged Alpha, no-Alpha whole-image processing, smooth gradients, compressed edge noise, gamut bounds, and constant or degenerate color inputs.
- [x] 2.5 Measure representative byte-image processing time and peak intermediate memory, then keep sampling and array allocation within an interactive local-edit budget.

## 3. Match Operator and Menus

- [x] 3.1 Implement and register `MatchColorReference` with polling for one valid distinct reference and target, local non-AI execution, result creation, and cleanup on failure.
- [x] 3.2 Commit matching results through `ImageEditTarget` so Image Empty, AnyImage Mesh Color Image, and material Image Texture targets preserve identity or isolate shared Image and Material data as required.
- [x] 3.3 Add `Set Color Reference` and `Match Color Reference` to all three existing image-action menus, with Match disabled when the Scene has no valid reference.
- [x] 3.4 Add operator and menu tests covering absent or invalid references, same-Image rejection, context isolation, target changes, shared users, full source names, color interpretation, and one-step undo/redo.

## 4. Verification

- [x] 4.1 Run the related color-matching, image-target, menu, image-result, Alpha, and registration tests and fix all failures.
- [x] 4.2 Run the full test suite and inspect the final diff for accidental AI-environment coupling, user-visible tuning properties, background special cases, stale registrations, and temporary resources.
