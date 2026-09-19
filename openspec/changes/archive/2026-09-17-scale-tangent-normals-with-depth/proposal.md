## Why

Tangent-space normal maps describe the full-depth surface.  When a geometry node reduces its `Depth Scale`, its shape becomes flatter but the material normal remains at full strength, making surface detail appear too strong.

## What Changes

- Reuse the existing `o_normal_reduction` geometry attribute as the material-to-geometry contract for tangent-space normal strength.
- Make tangent-normal depth geometry write `1 - Depth Scale` to that attribute, so the material normal strength follows the displayed geometric depth.
- Extend the existing `O Image Layer` behavior without changing its attribute lookup or fallback semantics.
- Make Object Space normal strength follow the same geometry reduction contract.
- Reuse the existing `o_normal_reduction` contract for additional Tangent-normal depth geometry.

## Capabilities

### New Capabilities
- `depth-scaled-tangent-normals`: Keep tangent-space material normal strength consistent with geometry depth scaling.

### Modified Capabilities

None.

## Impact

- Tangent-normal geometry-group builders, especially Relief Plane.
- Normal-scale node tests; saved node assets must be rebuilt with `uv run node-group build`.
- No server inference format, user-facing modifier socket, or dependency changes.
