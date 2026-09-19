## Context

`O Image Layer` currently reads `o_normal_reduction` and calculates Tangent and Object Normal Map strengths from `1 - attribute`. Its absence evaluates as zero, preserving full strength. `O Image Relief Plane` changes surface displacement with `Depth Scale` but supplies no matching material attribute, so its normal map remains visually over-strong at lower values.

The current Depth Plane and Depth Cutout conversion paths request Object Space normals. The panorama material is shadeless. Relief Plane is the only current Depth Scale geometry path that supplies a reduction attribute, and the shared material already applies that attribute in both normal spaces.

## Goals / Non-Goals

**Goals:**

- Reuse the existing `o_normal_reduction` attribute contract for Tangent Normal strength.
- Keep Tangent Normal strength numerically equal to the geometry's current `Depth Scale` on Relief Plane.
- Preserve full strength for material users and geometry that do not provide the attribute.
- Rebuild and verify the node asset and its rendered behavior.

**Non-Goals:**

- Alter Object Space normal-color transformation.
- Change Depth Scale ranges, geometry projection, normal-map generation, or user-facing sockets.
- Add a new normal-scale attribute or alter the existing material attribute lookup.

## Decisions

### Reuse the reduction attribute

`O Image Layer` already calculates the normal multiplier as `1 - o_normal_reduction`. Relief Plane therefore writes `1 - Depth Scale` to its final geometry. This produces a normal multiplier equal to `Depth Scale`, including zero and values greater than one, without changing the established shader contract.

Alternative: introduce a second scale attribute and alter the shader to use it. This duplicates an existing contract and would require migration of current geometry producers without improving the resulting calculation.

### Preserve the existing missing-attribute fallback

An absent float attribute evaluates as zero, and the existing `1 - o_normal_reduction` expression therefore evaluates to one. No material-node change is required to preserve ordinary image-material strength.

Alternative: add an existence switch in the material. It would replicate behavior that the current expression already provides.

### Apply the reduction in both normal spaces

`O Image Layer` already supplies the same `Normal Scale × (1 - o_normal_reduction)` strength field to both Tangent and Object Normal Map nodes. Relief Plane will use that established shared behavior, so both normal spaces follow its displayed geometry depth.

Alternative: split the material paths and limit the factor to Tangent Space. This would introduce an inconsistent interpretation of the existing shared attribute and require a separate Object Space policy.

## Risks / Trade-offs

- [Relief geometry writes the reduction on an inappropriate domain] → Store the field where the material evaluates it and add rendered POINT/FACE-domain coverage.
- [Missing attributes disable unrelated normal maps] → Test the explicit missing-attribute fallback on both Tangent and Object paths.
- [A later Tangent Depth Scale group omits the contract] → Treat `o_normal_reduction = 1 - Depth Scale` as the required output attribute whenever a Tangent-normal geometry group exposes `Depth Scale`.
- [Object Space visual response differs from Tangent Space] → Render and compare both paths at zero, fractional, unit, and extrapolated scales.

## Migration Plan

1. Update relevant Tangent-normal geometry builders to write `1 - Depth Scale` as `o_normal_reduction`.
2. Extend rendered node tests with Relief Plane depth-scale coverage.
3. Run focused node tests, then `uv run node-group build` to regenerate and verify `src/anyimage/assets/O_AnyImage.blend`.
4. Roll back by restoring the previous asset and source together.
