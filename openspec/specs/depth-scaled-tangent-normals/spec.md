# depth-scaled-tangent-normals Specification

## Purpose
TBD - created by archiving change scale-tangent-normals-with-depth. Update Purpose after archive.
## Requirements
### Requirement: Normal strength follows geometry depth scale
When a Geometry Nodes group both exposes `Depth Scale` and is rendered with a normal map, it SHALL store `1 - Depth Scale` as the `o_normal_reduction` float attribute on its final geometry. `O Image Layer` SHALL calculate Tangent and Object Normal Map Strength as its `Normal Scale` input multiplied by `1 - o_normal_reduction`.

#### Scenario: Reduced relief depth reduces Tangent normal strength
- **WHEN** an O Image Relief Plane uses a Tangent normal map and `Depth Scale` is set to 0.5
- **THEN** the Tangent Normal Map Strength is one half of the value produced at `Depth Scale` 1 with the same `Normal Scale` input

#### Scenario: Zero relief depth disables Tangent normal detail
- **WHEN** an O Image Relief Plane uses a Tangent normal map and `Depth Scale` is set to 0
- **THEN** the Tangent Normal Map Strength is zero

#### Scenario: Depth extrapolation is preserved
- **WHEN** an eligible Tangent-normal geometry group uses `Depth Scale` greater than 1
- **THEN** `o_normal_reduction` is negative by the corresponding amount and the Tangent Normal Map Strength retains the extrapolated value without clamping

### Requirement: Reduction attribute retains its material fallback
`O Image Layer` SHALL use a factor of 1 for its Tangent Normal Map Strength when `o_normal_reduction` is absent. The existing `o_normal_reduction` material contract SHALL remain unchanged.

#### Scenario: Ordinary image material has no normal-scale attribute
- **WHEN** an object using O Image Layer has no `o_normal_reduction` attribute
- **THEN** its Tangent Normal Map Strength equals the `Normal Scale` input

#### Scenario: Object Space normal strength follows the reduction
- **WHEN** O Image Layer is configured for an Object Space normal map and its geometry has any `o_normal_reduction` value
- **THEN** the Object Space Normal Map Strength equals the `Normal Scale` input multiplied by `1 - o_normal_reduction`

