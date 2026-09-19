## 1. Shared reference depth

- [x] 1.1 Add `reference_depth(image, mask=None)` to `src/anyimage/common/depth.py`: take the 95th percentile of camera Z over pixels whose Depth texture Alpha is greater than `0.95` and whose depth is finite and positive, and return model units.
- [x] 1.2 Drop `reference_depth` from `load_depth_metadata()` and change `depth_uniform_scale()` to take the computed reference depth instead of reading it from metadata.
- [x] 1.3 Move the base-shape direction fit into `common/depth.py` as `fit_symmetry_depth_direction()` beside `fit_depth_direction()`, then delete `src/anyimage/operators/cutout_tool/depth_calibration.py`.
- [x] 1.4 Delete `selection_calibration()` from `src/anyimage/operators/cutout_tool/geometry.py` and remove its test.
- [x] 1.5 Drop reference samples farther than `REFERENCE_DEPTH_RANGE_FACTOR` times the median before the percentile, and return `REFERENCE_DEPTH_BASELINE` when there is no valid pixel at all.
- [x] 1.6 Return the flat canonical direction from `fit_depth_direction()` when no sample is usable, and delete the caller-side `try/except` in plane conversion.

## 2. Server artifacts

- [x] 2.1 Remove the `reference_valid` argument and the `reference_depth` field from `write_depth_metadata()` in `src/anyimage/server/geometry/depth_texture.py`.
- [x] 2.2 Drop `alpha_threshold` from `generate_moge_artifacts()` and the cutout job parameters in `src/anyimage/server/jobs/cutout.py`.
- [x] 2.3 Update the server metadata and artifact tests to expect a `depth.json` with only `image_size` and `intrinsics`.

## 3. Depth shape initialization

- [x] 3.1 Compute the reference depth in `create_depth_plane_object()` and `create_shape_object()`; pass the cutout selection as the reference mask and use the whole depth image for plane conversion.
- [x] 3.2 Delete the transparency gate, `DEFAULT_DEPTH_BASELINE`, `DEFAULT_DEPTH_DIRECTION` fallback usage, and the adaptive calibration branch from the Cutout object creation path.
- [x] 3.3 Update the operator and shared support fixtures so depth metadata no longer carries a reference depth and Cutout depth shapes build from the shared reference.
- [x] 3.4 Add regression coverage that a skewed depth field returns the 95th percentile and that a selection mask narrows the reference domain.

## 4. Relief base plane

- [x] 4.1 Change the `Depth Offset` default to `0` in `tools/nodes/groups/image_relief_plane.py`.
- [x] 4.2 Run `uv run node-group build` to rebuild and validate `src/anyimage/assets/O_AnyImage.blend`.
- [x] 4.3 Update the Relief Plane node tests and interface inventory for the new default and the reference-depth-driven base plane.

## 5. Verification

- [x] 5.1 Run the affected `pytest` modules for `common.depth`, server artifacts, plane conversion, and cutout operators.
- [x] 5.2 Search for stale `reference_depth` metadata reads, `depth_calibration` imports, and fixed-baseline references, then review the final diff.
