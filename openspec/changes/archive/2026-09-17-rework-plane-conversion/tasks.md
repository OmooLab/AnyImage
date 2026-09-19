## 1. Center Plane Origins

- [x] 1.1 Refactor the shared Plane mesh placement so centered local vertices and the compensated object matrix preserve the source Image Empty rectangle in world space.
- [x] 1.2 Apply the centered placement to Convert to Plane and Convert to Depth Plane without changing their UV range, selection replacement, names, or custom shape markers.
- [x] 1.3 Add Blender tests for offset Image Empty bounds and transformed sources, verifying centered origins and unchanged world-space corners for both conversion paths.

## 2. Unify Plane Material Ownership

- [x] 2.1 Remove the `Material` interface, Group Input, and Set Material node from `O Mesh Plane`, leaving generated faces on material index `0`.
- [x] 2.2 Remove the `Material` interface and forwarding from `O Image Depth Plane`, and simplify runtime Modifier input assignment while keeping image materials in Mesh slot `0`.
- [x] 2.3 Update Plane, thickness block, Depth Plane, and clipboard Plane validations to prove evaluated faces resolve the Mesh slot `0` material without a Modifier material input.

## 3. Rebuild Depth Plane Geometry

- [x] 3.1 Replace the single-extrude Depth Plane graph with the `O Mesh Plane` thickness topology positioned from the original image plane toward the positive-normal displaced face.
- [x] 3.2 Implement Z Depth sampling, `Base Plane Depth` zero calibration, `Depth Scale`, and linear layer weighting from the fixed base to the fully displaced face.
- [x] 3.3 Clamp inward displacement before the fixed base with a nonzero safety gap, preserve unrestricted outward displacement, and retain a single displaced surface when Thickness is zero.
- [x] 3.4 Ensure positive Thickness produces adaptive intermediate side-wall rings with a minimum useful ring count and stable UV/material indices.

## 4. Replace Interfaces and Defaults

- [x] 4.1 Replace `Depth Amount` with `Depth Scale` and `Reference Depth` with `Base Plane Depth` across the node builder, runtime Modifier inputs, validators, and tests without compatibility aliases.
- [x] 4.2 Set Convert to Depth Plane and its generated job handoff to default `Subdivide` to `6`, while keeping ordinary Plane default `0` and Metadata-derived hidden data unchanged.
- [x] 4.3 Add evaluated-geometry tests for zero Depth Scale thickness, fixed base vertices, zero-plane calibration, displacement direction and scale, side-ring interpolation, negative non-crossing, and outward displacement beyond the base thickness.

## 5. Rebuild Assets and Documentation

- [x] 5.1 Update node interface and layout validations, then rebuild `src/anyimage/assets/O_AnyImage.blend` with the final `O Mesh Plane` and `O Image Depth Plane` graphs.
- [x] 5.2 Update the Plane conversion and node asset internal documentation to describe centered origins, Mesh-slot material ownership, terrain-block topology, and the final control names.
- [x] 5.3 Run the node asset build pipeline and complete test suite, fixing any interface, topology, packaging, registration, or documentation consistency failures.

## 6. Correct Material Transfer and Thickness Anchor

- [x] 6.1 Preserve the source Mesh material set in generated `O Mesh Plane` geometry by joining a captured source marker, setting material index `0`, and deleting the source geometry.
- [x] 6.2 Anchor the fixed Depth Plane base at the original image plane so `Thickness` only moves the displaced face and intermediate side-wall rings.
- [x] 6.3 Update evaluated-geometry tests, OpenSpec artifacts, and documentation, then rebuild the node asset and run the complete validation suite.

## 7. Add Depth Plane Material Normal

- [x] 7.1 Make the Depth Plane Job request Z Depth and Tangent Normal from one shared `generate_moge2_artifacts()` call, returning `z_depth`, `depth_metadata`, and `tangent_normal` without a second inference.
- [x] 7.2 Load and Pack the Tangent Normal as Non-Color data, connect it to the Depth Plane image material in Tangent Space, and clean up unused Depth and Normal images on failure.
- [x] 7.3 Add server and Blender tests for the combined artifacts, material node connection, default `Subdivide` value, and failure cleanup; update documentation, rebuild the node asset, and run the complete validation suite.
- [x] 7.4 Set the Depth Plane image material Principled IOR to `1.2`, matching Cutout, and update its response test and documentation.
