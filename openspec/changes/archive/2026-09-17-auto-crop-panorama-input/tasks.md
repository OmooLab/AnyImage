## 1. Crop Bounds

- [x] 1.1 Add a common helper that returns the largest deterministic centered exact 2:1 integer-pixel bounds and rejects dimensions that cannot produce a positive crop
- [x] 1.2 Add focused tests for exact, wide, tall, odd-width, uneven-margin, and unusably small dimension cases

## 2. Panorama Conversion

- [x] 2.1 Update Convert to Panorama to keep animated-image validation, compute the crop bounds, and pass them into the shared material color input preparation
- [x] 2.2 Report one crop warning with original and cropped dimensions only when pixels are removed
- [x] 2.3 Update panorama operator tests to verify arbitrary aspect ratios submit cropped color and analysis inputs, exact 2:1 input stays unchanged, and unsupported sources remain rejected

## 3. Verification

- [x] 3.1 Run the related common image and panorama conversion test suites and confirm they pass
- [x] 3.2 Inspect the final diff and search the panorama conversion path to confirm the strict 2:1 rejection and stale expectations are removed
