## Context

Convert to Panorama currently validates `width == height * 2` before it exports the source color image. The shared color-input helper already accepts pixel bounds and uses the resulting file for both material color and AI analysis, so the crop can be applied once at the Blender boundary without changing the server job or duplicating image processing.

## Goals / Non-Goals

**Goals:**

- Derive a deterministic, centered, exact 2:1 integer-pixel crop from any usable static source image.
- Use the same cropped pixels for AI analysis and the generated panorama material.
- Warn users whenever the prepared input omits source pixels.
- Keep exact 2:1 inputs unchanged.

**Non-Goals:**

- Padding, stretching, resampling, or content-aware crop positioning.
- Repairing an image that is not actually an equirectangular panorama.
- Changing server inference, panorama fusion, output metadata, or node groups.

## Decisions

### Compute the largest centered exact 2:1 pixel rectangle

Let `crop_height = min(source_height, source_width // 2)` and `crop_width = crop_height * 2`. Center these dimensions independently within the source using integer offsets. This retains the maximum possible source area, handles both wide and tall images, and removes one unavoidable column from odd-width inputs. Integer floor placement gives deterministic bounds when the discarded pixels cannot be split equally.

Padding would preserve all pixels but introduce artificial panorama regions. Resizing would distort the projection. Both are less faithful than an explicit crop.

### Select bounds before preparing the shared color input

Add a small reusable image-bound calculation in the appropriate `common` image module, then pass those bounds to `prepare_material_color_input`. `material_analysis_input` will continue to derive its input from that exported color file. This guarantees that inference and the material see identical framing while retaining existing HDR, color-space, alpha, temporary-file, and cleanup behavior.

Cropping only the analysis preview was rejected because the generated material and inferred geometry would then use different angular content.

### Warn at the public operator boundary

`ConvertToPanorama` will emit one Blender `WARNING` report after determining that the crop differs from the source. The message will state original and cropped pixel dimensions. Exact 2:1 sources will not report a warning. Animated images and inputs for which the computed crop has zero width or height remain errors.

The warning belongs at the public operator boundary because that is where source dimensions and user feedback are both available; it does not need to become part of the job protocol.

## Risks / Trade-offs

- [Centered cropping can remove important edge content] → Make the crop explicit through a warning with dimensions; interactive crop selection remains outside this change.
- [Odd discarded pixel counts make perfect geometric centering impossible] → Use stable integer floor offsets and test the exact bounds.
- [Very narrow images cannot yield a positive 2:1 integer crop] → Keep a clear validation error for widths below two pixels or otherwise invalid dimensions.
- [Warning timing could imply success before setup or submission later fails] → Report the warning as part of input preparation, while preserving normal error reporting for subsequent failures.
