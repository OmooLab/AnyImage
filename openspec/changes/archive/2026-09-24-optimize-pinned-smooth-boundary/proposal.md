## Why

`pinned_smooth` currently builds separate boundary meshes and spatial/index lookups for both Position and UV during every repeat iteration. These topology and sampling operations dominate a path whose boundary target can be expressed directly as normalized masked attribute blur on the unchanged mesh topology.

## What Changes

- Replace repeat-local boundary geometry separation and lookup with normalized boundary-mask blur.
- Share the boundary normalization field between Position and UV while retaining separate value blurs.
- Evaluate Position and UV targets from the same repeat state and apply the same final weight.
- Preserve existing boundary pinning, sharpness, influence, UV, topology, and zero-iteration behavior.
- Hoist topology-invariant boundary fields out of the repeat zone and remove their temporary attributes after smoothing.
- Skip boundary-weight work when Boundary Smooth is zero and skip smoothed-normal work when Thickness is zero.
- Remove the projection-stage connected merge and use a fixed `1e-6` distance for the final Merge by Distance.
- Add structural and behavioral regression coverage for the simplified repeat graph.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pinned-geometry-smoothing`: Define normalized masked blur as the shared boundary target implementation for Position and UV.
- `cutout-geometry-node-efficiency`: Require Depth Cutout boundary smoothing to avoid repeat-local geometry separation and spatial/index sampling.

## Impact

- `nodes/common/smoothing.py`
- Boundary smoothing and Depth Cutout node tests
- Generated node asset validation
- No public input, dependency, or file-format changes
