## ADDED Requirements

### Requirement: Internal Cutout attributes use the `_o_` prefix

Attributes that exist only inside the Cutout geometry node lifecycle and are removed before output SHALL use the `_o_` prefix. The system SHALL NOT use the previous `.o_anyimage_*` prefix for new internal attributes.

#### Scenario: Split marker is stored as an internal attribute

- **WHEN** Depth Cutout or another depth surface stores the split marker during edge separation
- **THEN** the stored name starts with `_o_` and is removed before the node group output

#### Scenario: Old internal marker names are not emitted

- **WHEN** a Cutout node group is evaluated
- **THEN** no `.o_anyimage_depth_cut` or `.o_anyimage_original_boundary` attribute remains on the output geometry

### Requirement: Public Cutout attributes keep the `o_` prefix

Attributes that are part of the Cutout shape, normal, or material protocol SHALL keep the `o_` prefix and SHALL NOT be removed by internal cleanup.

#### Scenario: Public shape and normal attributes survive cleanup

- **WHEN** Cutout or Depth Cutout outputs geometry
- **THEN** `o_balloon`, `o_normal_reduction`, and existing `o_depth_*` public protocol attributes remain available according to their current contracts

#### Scenario: UVMap and user attributes survive cleanup

- **WHEN** input geometry contains UVMap and user attributes
- **THEN** internal cleanup preserves those attributes without renaming them

### Requirement: Internal attributes are removed by a single wildcard operation

Each depth surface group SHALL remove its `_o_*` internal attributes with one `Remove Named Attribute` node using wildcard mode before output. It SHALL NOT remove internal attributes one by one.

#### Scenario: Wildcard cleanup removes all internal attributes

- **WHEN** a depth surface group evaluates with Split or Thickness enabled
- **THEN** every `_o_*` attribute is absent from the output geometry

#### Scenario: Wildcard cleanup is safe when no internal attribute exists

- **WHEN** a depth surface group evaluates with the corresponding internal path disabled
- **THEN** the wildcard removal produces no missing-attribute warning and leaves public attributes unchanged

