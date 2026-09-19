## 1. Reuse the geometry-to-material contract

- [x] 1.1 Update O Image Relief Plane to store `1 - Depth Scale` as `o_normal_reduction` on final geometry.
- [x] 1.2 Confirm O Image Layer's existing `1 - o_normal_reduction` Tangent and Object-strength paths and its absent-attribute fallback need no code change.
- [x] 1.3 Confirm existing O Image Cutout and O Image Depth Cutout attribute uses retain their current geometry and material behavior.

## 2. Verification and assets

- [x] 2.1 Update definition and rendered node tests for absent, zero, fractional, and greater-than-one `o_normal_reduction` values in both normal spaces.
- [x] 2.2 Run the relevant node tests and fix regressions.
- [x] 2.3 Run `uv run node-group build` and verify the regenerated `O_AnyImage.blend` asset and inventory tests.
