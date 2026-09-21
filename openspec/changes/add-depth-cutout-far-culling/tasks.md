## 1. Depth statistics and creation defaults

- [x] 1.1 Add a shared selected-depth median calculation that reuses the reference depth validity, mask, and fallback rules; cover valid, masked, and empty selections with focused tests.
- [x] 1.2 Compute the 1.2-times-median object-space depth limit during Depth Cutout creation and assign it to Depth Solid and the upstream Depth Symmetry modifier.
- [x] 1.3 Extend Cutout object creation tests to verify `Depth Limit`, including its `Reference Depth` and `Uniform Scale` conversion.

## 2. Depth Cutout node behavior

- [x] 2.1 Add the non-negative `Depth Limit` DISTANCE input directly below `Depth Split` in the `O Image Depth Cutout` root interface and inventory expectations.
- [x] 2.2 Classify far faces from their projected face-center depth, delete them before boundary smoothing, and merge the new boundary into the Depth Split cut field.
- [x] 2.3 Add node behavior tests for the threshold boundary, Reference Depth and Depth Scale interaction, zero and positive thickness, profile taper, and absence of geometry derived from culled faces.

## 3. Asset and verification

- [x] 3.1 Run the focused common depth, Cutout object, node inventory, and Depth Cutout behavior tests.
- [x] 3.2 Run `uv run --group blender node-group build` to regenerate and verify the node asset.
- [x] 3.3 Re-run affected tests against the saved asset, search for stale interface assumptions, and review the final diff.

## 4. Depth Split boundary integration

- [x] 4.1 Move `Depth Limit` directly below `Depth Split` outside Options and classify limited geometry from the shared face-center camera sample.
- [x] 4.2 Merge the limit boundary into the Depth Split cut marker before profile taper, smoothing, normals, and thickness construction.
- [x] 4.3 Add regression coverage for closed positive-thickness limit edges, rebuild the node asset, and re-run affected tests.

## 5. Depth limit range

- [x] 5.1 Set the `Depth Limit` minimum to `-1` and verify the saved interface value.
- [x] 5.2 Remove the Point Delete interface and deletion branch, rebuild the node asset, and verify affected tests.
