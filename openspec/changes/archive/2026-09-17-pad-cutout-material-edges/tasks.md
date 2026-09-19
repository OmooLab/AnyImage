## 1. Boundary Padding setting

- [x] 1.1 Add the Cutout Tool `Boundary Padding` preference with default 2 px, range 1–4 px and a clamped reader.
- [x] 1.2 Capture the configured value when each Cutout operation starts so synchronous and asynchronous responses use the same operation value.

## 2. Structural inward mapping

- [x] 2.1 Build a pure array mapping from the final threshold Mask that carries each boundary-band location along one local structural inward direction to the configured internal distance.
- [x] 2.2 Bound thin-structure rays to their last same-direction internal position and leave undefined directions unchanged without donor thresholds or fallback searches.
- [x] 2.3 Cover outer outlines, holes, concave corners, thin structures, scaled target resolutions and zero bypass.

## 3. Client-side image processing

- [x] 3.1 Apply the mapping to independent material Color RGBA for synchronous and AI Cutouts while preserving the source Image and AI input.
- [x] 3.2 Apply the mapping to Depth Z and validity, reconstruct target X/Y from Metadata intrinsics, and preserve reference depth.
- [x] 3.3 Update and repack processed Color and Depth Images before object consumption while preserving byte, float/HDR and CHANNEL_PACKED interpretation and cleanup.

## 4. Raw server artifacts

- [x] 4.1 Stop enabling server-side depth edge extension for Cutout and remove the unused extension path if no real caller remains.
- [x] 4.2 Update server tests to require raw MoGe Depth and unchanged Metadata generation.

## 5. Integration and validation

- [x] 5.1 Cover preference capture, synchronous/AI parity, unmodified geometry and UV, correct target-ray Depth projection, Normal isolation, packed ownership and failure cleanup.
- [x] 5.2 Run related tests, validate OpenSpec strictly, and inspect the final diff and stale references without rebuilding node assets or extension packages.
