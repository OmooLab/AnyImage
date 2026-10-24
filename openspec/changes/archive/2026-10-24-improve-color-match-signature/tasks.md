## 1. Adaptive Color Signature

- [x] 1.1 Implement deterministic spatial candidate extraction, saliency weights, real-pixel representatives, and adaptive 8–16 anchor selection.
- [x] 1.2 Implement rectangular weighted color transport and smooth full-image chroma application while retaining the independent lightness path.
- [x] 1.3 Derive a dynamic 3–7 color display palette with merged weights from the same reference signature.
- [x] 1.4 Increase the effective weight of small coherent saturated regions and select higher-chroma real pixels as signature representatives.

## 2. Blender Panel Integration

- [x] 2.1 Store dynamic palette count, colors, and weights in `AnyImageSettings`, update them with the reference, and draw proportional color blocks in `ColorMatchPanel`.
- [x] 2.2 Keep at least three display colors for non-degenerate signatures and render palette controls without Blender's disabled gray appearance.
- [x] 2.3 Preserve the more chromatic real representative when similar palette groups merge.

## 3. Verification

- [x] 3.1 Add focused tests for spatial accents, adaptive and unequal anchor counts, deterministic matching, dynamic palette merging, clearing, and proportional Panel drawing.
- [x] 3.2 Run the related color-matching, property, Panel, operator, and registration tests; inspect performance and the final diff for unrelated changes.
- [x] 3.3 Add regression coverage for the three-color floor and enabled true-color palette presentation, then rerun related tests.
- [x] 3.4 Add regression coverage for small saturated accents and vivid representatives, then rerun related tests.
