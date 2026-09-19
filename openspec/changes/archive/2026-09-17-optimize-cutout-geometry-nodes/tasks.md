## 1. Internal attribute naming and wildcard cleanup

- [x] 1.1 Rename `CUT_ATTRIBUTE` from `.o_anyimage_depth_cut` to `_o_anyimage_depth_cut` and update `depth_surface.py`, `image_depth_panorama.py`, and asset checks.
- [x] 1.2 Replace the internal split-marker removal path with one wildcard `Remove Named Attribute` matching `_o_*` before each depth surface output.
- [x] 1.3 Update `tests/tools/nodes/test_temporary_attributes.py`, `test_depth_surface_split.py`, and `tools/nodes/check.py` to assert the new prefix and remove stale `.o_anyimage_*` expectations.

## 2. Reuse the projected outline field

- [x] 2.1 Change `build_volume_fields`, `original_boundary_field`, and `smooth_cut_boundary` to accept an already-evaluated boundary field instead of creating their own `edge_boundary_field`.
- [x] 2.2 In `_build_depth_surface`, compute the post-cleanup outline once and pass it to projection-time consumers and boundary smoothing.
- [x] 2.3 Add a node-count or evaluation-equivalence test proving the projected outline consumers share one field on the same topology.

## 3. Derive center from shared low-frequency fields

- [x] 3.1 Restructure `build_volume_fields` and `build_front_fields` so `depth_slow` and `profile_slow` are computed once with the existing blur settings.
- [x] 3.2 Replace the direct `blur(depth - profile)` center computation with `depth_slow - profile_slow`.
- [x] 3.3 Add a regression test comparing derived center values and Balloon geometry to the previous behavior within floating-point tolerance.

## 4. Use triangle-only strip cleanup in Depth Cutout

- [x] 4.1 Split `_remove_strip_faces` or add a triangle-only helper so quad cleanup nodes are built only for non-triangle callers.
- [x] 4.2 Update `split_depth_surface` callers so `O Image Depth Cutout` uses the triangle-only path while Depth Plane and Depth Panorama keep the existing quad path.
- [x] 4.3 Update strip cleanup tests to cover both paths and verify Depth Cutout output is unchanged.

## 5. Short-circuit zero-thickness branches

- [x] 5.1 In `image_cutout.py`, gate `_build_balloon` and `_build_shell` so thickness below the existing zero threshold returns the original surface before extrusion or Repeat.
- [x] 5.2 In `image_depth_cutout.py`, return the projected front surface when the selected thickness is zero, and only build `thicken_depth_surface` plus shell field sampling for positive thickness.
- [x] 5.3 Add tests verifying zero-thickness modes produce the single surface, preserve UV/public attributes, and emit no thickness-related node warnings.

## 6. Rebuild assets and run regression

- [x] 6.1 Run the focused Cutout and Depth Cutout test files and fix any behavioral differences.
- [x] 6.2 Run `uv run node-group build` to rebuild and validate `O_AnyImage.blend`.
- [x] 6.3 Run the full `uv run pytest` suite and confirm normal exit with no new expected failures.
- [x] 6.4 Review `git diff --check` and the final node/attribute inventory to confirm no stale `.o_anyimage_*` references remain.
