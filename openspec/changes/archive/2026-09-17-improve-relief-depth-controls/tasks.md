## 1. Relief depth behavior

- [x] 1.1 Add the public `Depth Offset` distance input to `O Image Relief Plane`, with a default of one and signed range; expose `Depth Direction`, `Depth Offset`, and `Depth Scale` directly below `Thickness` in that order.
- [x] 1.2 Add `Depth Offset` to `Reference Depth` before `reference_plane_depth()`, then replace the thickness-dependent inward limit with a zero clamp after direction adjustment and `Depth Scale`, preserving fixed-base and side-layer weighting.

## 2. Behavior verification

- [x] 2.1 Update Relief Plane geometry tests to verify far depths stop at `Thickness`, positive depths remain unrestricted, and the fixed base and side interpolation remain valid.
- [x] 2.2 Add positive, negative, and zero `Depth Offset` tests, including direction adjustment, `Depth Scale = 0`, and checks that Depth Offset is scaled as part of the corrected relative depth while the depth-zero height remains fixed.
- [x] 2.3 Update the node-group interface inventory test for `Depth Direction` and `Depth Offset` names, order, panel placement, and old base-plane clamp behavior.

## 3. Node asset

- [x] 3.1 Run `uv run node-group build` to rebuild and validate `src/anyimage/assets/O_AnyImage.blend` from the updated source and tests.
- [x] 3.2 Run the relevant Relief Plane and plane-object tests, then inspect the final diff for stale inward-limit nodes or old behavior references.

## 4. Initial depth direction

- [x] 4.1 Extract the robust plane-direction fit into `common.depth` and reuse it from Cutout Symmetry calibration.
- [x] 4.2 Fit the complete valid Relief depth image in local plane coordinates and initialize the new Modifier's `Depth Direction`.
- [x] 4.3 Add sloped-depth initialization and shared calibration regression tests.
