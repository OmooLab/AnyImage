## Why

`O Image Cutout Symmetry` runs Seam and Fill smoothing as serial repeat zones, and high Smooth values spend substantial time re-evaluating the Fill influence and smoothing UVs. Fill work should be skipped when no wall is requested, and UV work should remain bounded without adding more public controls.

## What Changes

- Cache Fill smoothing influence once on both Point and Corner domains before its repeat zone.
- Fully bypass Fill smoothing when Fill Sides is disabled.
- Limit shared `pinned_smooth` UV relaxation to the first four repeat iterations while Position continues for the full requested count.
- Remove the Symmetry `Smooth UV` and `Merge Distance` inputs; UV smoothing remains automatic and merge distance is fixed to `1e-6`.
- Add structural, behavior, and representative-image performance verification.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pinned-geometry-smoothing`: Allow cached Point/Corner influence fields and cap UV relaxation at four iterations.
- `cutout-symmetry-seam`: Require Fill Sides off to bypass Fill smoothing and simplify the public interface.

## Impact

- `nodes/common/smoothing.py`
- `nodes/groups/image_cutout_symmetry.py`
- Symmetry node tests and interface inventory
- Generated node asset validation
- No dependency or file-format changes
