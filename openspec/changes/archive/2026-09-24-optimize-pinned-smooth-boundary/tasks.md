## 1. Shared smoothing implementation

- [x] 1.1 Replace separated boundary geometry lookup with normalized masked blur and share its denominator between Position and UV
- [x] 1.2 Compute and apply UV and Position updates from the same repeat geometry state
- [x] 1.3 Remove obsolete boundary sampling helpers and connections from the repeat graph

## 2. Behavior and structure verification

- [x] 2.1 Add focused equivalence coverage for normalized boundary targets and small out-of-range UV values
- [x] 2.2 Assert Depth Cutout shared smoothing contains no Separate Geometry, Sample Nearest, or Sample Index nodes
- [x] 2.3 Run related smoothing and Depth Cutout tests

## 3. Node asset validation

- [x] 3.1 Rebuild and validate all node assets
- [x] 3.2 Check final references, temporary attributes, and diff cleanliness

## 4. Disabled-work and repeat-field optimization

- [x] 4.1 Hoist the boundary mask and normalization out of the repeat zone and clean their temporary attributes
- [x] 4.2 Skip boundary-weight storage at zero Boundary Smooth and front-normal smoothing at zero Thickness
- [x] 4.3 Add structural and output-equivalence coverage for the lazy branches and cached fields
- [x] 4.4 Rebuild node assets and record before/after modifier execution timings

## 5. Merge simplification

- [x] 5.1 Remove the projection-stage connected merge and edge-length statistics
- [x] 5.2 Use a fixed `1e-6` final Merge by Distance and remove the dynamic parameter
- [x] 5.3 Update structural coverage and rebuild node assets
