## ADDED Requirements

### Requirement: Depth Cutout reuses the projected outline field

`O Image Depth Cutout` SHALL calculate the POINT/BOOLEAN outline field once on the post-split, pre-projection topology and reuse it for boundary-sensitive consumers on the same topology after projection. It SHALL NOT create separate Edge Neighbors and Vertex Neighbors fields for each consumer in the same topology stage.

#### Scenario: Same topology boundary consumers share the field

- **WHEN** Depth Cutout builds volume fields, original boundary sampling, and boundary smoothing after depth projection
- **THEN** these consumers read the same projected outline field, and the output geometry matches the prior implementation for zero and positive thickness

#### Scenario: Topology changes still receive a fresh boundary field

- **WHEN** Split Edges or boundary triangle cleanup changes topology before projection
- **THEN** the shared outline field is evaluated after that topology change, not reused across the destructive operation

### Requirement: Center field derives from shared low-frequency fields

`O Image Depth Cutout` SHALL compute the smoothed depth and profile fields with the existing 256-iteration interior-weighted blur, and SHALL derive the center field as `depth_slow - profile_slow` instead of running an additional equivalent blur on `depth - profile`.

#### Scenario: Center field is equivalent to the direct blur

- **WHEN** Depth Cutout evaluates a Balloon input with nonzero `o_balloon` and positive Thickness
- **THEN** the derived center values are equal to the prior direct center blur values within floating-point tolerance

#### Scenario: Uniform surface keeps the same center behavior

- **WHEN** Depth Cutout evaluates a zero-profile uniform surface
- **THEN** the derived center field produces the same front and rear positions as the prior implementation

### Requirement: Depth Cutout uses triangle-only strip cleanup

`O Image Depth Cutout` SHALL build only the triangle strip cleanup path because its input is triangulated. It SHALL NOT construct the quad strip cleanup branch used by other depth surfaces.

#### Scenario: Triangular strips are cleaned without quad nodes

- **WHEN** Depth Cutout receives a triangulated cutout mesh with thin boundary strips
- **THEN** strip faces are removed and the remaining geometry matches the prior triangle cleanup result

#### Scenario: Other depth surfaces keep their existing cleanup path

- **WHEN** Depth Plane or Depth Panorama evaluates a quad mesh
- **THEN** their existing quad strip cleanup behavior is unchanged

### Requirement: Zero thickness short-circuits shell construction

Both `O Image Cutout` and `O Image Depth Cutout` SHALL return the original single-surface geometry when the selected thickness input is below the existing zero threshold, without evaluating shell extrusion or thickness field sampling.

#### Scenario: Cutout Balloon and Shell remain single surface at zero

- **WHEN** Mode is Balloon or Shell and the selected Thickness or Shell Thickness is zero
- **THEN** the output is the original Cutout surface with no shell faces, and no thickness-related node warnings occur

#### Scenario: Depth Cutout keeps the projected front at zero thickness

- **WHEN** Depth Cutout has zero selected thickness
- **THEN** the output is the projected front surface, and thickness-only fields and shell geometry are not evaluated

### Requirement: Node graph optimization preserves Cutout geometry

The boundary reuse, center derivation, triangle-only cleanup, and zero-thickness short-circuit SHALL NOT change the finite output geometry, face order, UVMap, or public attributes for supported Cutout and Depth Cutout combinations.

#### Scenario: Representative mode and thickness matrix is equivalent

- **WHEN** Cutout and Depth Cutout are evaluated with Balloon/Shell modes, zero and positive thickness, Depth Split zero and positive, and representative input shapes
- **THEN** vertex positions and face topology are equivalent to the prior implementation within the existing test tolerance

#### Scenario: High-density mesh remains closed with thickness

- **WHEN** Depth Cutout uses a mesh with more than 4096 source vertices and positive thickness
- **THEN** the thickened shell remains finite and closed with no non-manifold boundary

