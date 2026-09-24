## ADDED Requirements

### Requirement: Fill smoothing follows Fill Sides lazily

`O Image Cutout Symmetry` SHALL evaluate Fill smoothing only when Fill Sides is enabled. Disabling Fill Sides MUST bypass the complete Fill repeat while retaining Seam smoothing and seam welding.

#### Scenario: Fill Sides disabled at high Smooth

- **WHEN** Fill Sides is disabled and Smooth is positive
- **THEN** Seam smoothing still uses Smooth
- **AND** Fill influence, Position Blur, UV Blur, and repeat iterations are not evaluated

### Requirement: Symmetry smoothing interface stays minimal

`O Image Cutout Symmetry` MUST NOT expose Smooth UV or Merge Distance. UV SHALL smooth automatically for at most four iterations, and plane classification, snapping, and merge SHALL use a fixed `1e-6` distance.

#### Scenario: Inspect interface and merge

- **WHEN** the Symmetry group is built
- **THEN** its inputs contain Fill Sides and Smooth but not Smooth UV or Merge Distance
- **AND** its Merge by Distance uses an unlinked `1e-6` Distance
