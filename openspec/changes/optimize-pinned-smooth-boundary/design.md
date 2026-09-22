## Context

`pinned_smooth` updates Position and `UVMap` in one repeat zone. Each value currently creates its own temporary boundary geometry, nearest-point lookup, and index sample. The UV path additionally converts UV to temporary positions. Topology does not change inside the repeat, and both targets use the same point-domain boundary mask.

The boundary-only one-step blur with weight `0.5` can be evaluated on the full topology as normalized masked blur:

`boundary_target(value) = Blur(boundary * value, 0.5) / Blur(boundary, 0.5)`

For a boundary point, the common full-topology normalization factor cancels, leaving the same self and boundary-neighbor weighted average as blurring the separated boundary mesh.

## Goals / Non-Goals

**Goals:**

- Remove repeat-local Separate Geometry, Sample Nearest, and Sample Index nodes from shared pinned smoothing.
- Share one blurred boundary denominator between Position and UV.
- Evaluate both targets from the same repeat state and final weight.
- Preserve output behavior within floating-point tolerance.

**Non-Goals:**

- Change public smoothing controls, influence bands, pin sharp behavior, topology, or UV domain.
- Add Panorama-specific UV handling.
- Change non-pinned Fill Smooth target semantics.

## Decisions

### 1. Normalize masked values on the unchanged topology

The implementation blurs the float boundary mask once per iteration. Position and point-domain UV are multiplied by the mask, blurred independently with the existing boundary weight, and divided by the shared blurred mask. Only boundary points consume these normalized targets.

This replaces topology extraction and spatial lookup with adjacency blur. Connecting the boundary mask directly to Blur Weight is not equivalent because Weight controls the receiving element's blur strength rather than excluding non-boundary neighbor values.

### 2. Compute Position and UV targets before either update

Both general and boundary targets are fields on the current repeat geometry. UV is stored before Set Position, then Position is updated. Storing UV does not change topology or normals, so both consumers evaluate the shared sharpness and influence weight in the same geometric state.

### 3. Cache topology-invariant boundary fields before the repeat

The boundary boolean field and its blurred denominator do not change while the repeat updates only Position and UV. Store both once before the repeat, read them inside every iteration, and remove the temporary attributes immediately after the repeat. The attributes remain private implementation details and do not escape the helper.

### 4. Let geometry switches gate expensive optional fields

Depth Cutout routes the unmodified projection around the boundary-weight store when Boundary Smooth is zero. It also routes the projection around the 256-iteration normal-direction store when Thickness is zero. Geometry switches keep those branches lazy while preserving the existing public output and cleanup protocol.

### 5. Verify structure and behavior

Tests compare boundary targets and public output behavior, assert zero repeat-local geometry separation and sampling nodes in the shared smoothing path, and retain the existing node asset build validation.

### 6. Keep only the final fixed-distance weld

The projected surface no longer runs a connected merge. The final front/rear/side assembly retains one ALL Merge by Distance with an unlinked `1e-6` Distance. This removes edge-length statistics and the dynamic weld-distance parameter while avoiding premature welding of very thin front and rear leaves.

## Risks / Trade-offs

- [Normalization divides by zero away from the boundary] → Clamp the denominator to a small positive value; only boundary points select the result.
- [Masked blur differs from separated blur] → Add a focused irregular-boundary equivalence test with floating-point tolerance.
- [Temporary smoothing attributes leak into output] → Remove both immediately after the repeat and assert the public result contains neither name.
- [A disabled branch still evaluates] → Benchmark evaluated modifiers with alternating inputs and compare zero/positive control values.
