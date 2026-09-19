## Why

Convert to Panorama currently rejects any image whose pixel dimensions are not exactly 2:1, so even a nearly compliant panorama cannot be processed. Panorama conversion should accept arbitrary static image aspect ratios by preparing a valid 2:1 input automatically while making the loss of edge content visible to the user.

## What Changes

- Accept static panorama source images regardless of their original aspect ratio.
- Center-crop the source to the largest integer-pixel 2:1 region before preparing both the AI analysis input and panorama color material.
- Report a warning when any rows or columns are removed, including the original and cropped dimensions.
- Preserve the existing behavior without a warning when the source dimensions are already exactly 2:1.
- Continue rejecting animated or unusably small images that cannot produce a positive 2:1 crop.

## Capabilities

### New Capabilities

- `panorama-input-cropping`: Defines validation, centered 2:1 crop selection, prepared panorama inputs, and user warning behavior.

### Modified Capabilities

None.

## Impact

- Affects the Blender-side Convert to Panorama operator and shared material color input preparation used by its job submission.
- Adds focused operator and image-preparation tests for wide, tall, odd-width, already-2:1, animated, and unusably small inputs.
- Does not change the panorama job protocol, server geometry pipeline, model dependencies, or node assets.
