# panorama-input-cropping Specification

## Purpose
TBD - created by archiving change auto-crop-panorama-input. Update Purpose after archive.
## Requirements
### Requirement: Panorama input uses an exact centered 2:1 crop
The system SHALL prepare panorama conversion from the largest centered integer-pixel rectangle whose width is exactly twice its height. The prepared color material and AI analysis input MUST use the same cropped pixels without stretching, padding, or aspect-ratio resampling.

#### Scenario: Source is wider than 2:1
- **WHEN** a user converts a usable static image whose width is greater than twice its height
- **THEN** the system crops columns equally where possible from the left and right and prepares an exact 2:1 input at the source height

#### Scenario: Source is narrower than 2:1
- **WHEN** a user converts a usable static image whose width is less than twice its height
- **THEN** the system crops rows equally where possible from the top and bottom and prepares the largest exact 2:1 input at or below the source width

#### Scenario: Source width is odd
- **WHEN** a usable static source has an odd width that cannot be part of an exact integer-pixel 2:1 rectangle
- **THEN** the system omits the unmatched column as part of its deterministic centered crop

#### Scenario: Source is already 2:1
- **WHEN** a user converts a usable static image whose width is exactly twice its height
- **THEN** the system prepares the full source image without removing pixels

### Requirement: Panorama crop is disclosed to the user
The system SHALL issue one warning whenever panorama input preparation removes source pixels, and the warning MUST identify both the original and cropped pixel dimensions.

#### Scenario: Conversion requires cropping
- **WHEN** the computed 2:1 bounds differ from the source bounds
- **THEN** the system reports a warning containing the source width and height and the cropped width and height

#### Scenario: Conversion does not require cropping
- **WHEN** the source bounds already form an exact 2:1 image
- **THEN** the system does not report a crop warning

### Requirement: Unsupported panorama sources remain rejected
The system MUST reject animated images and images too small to produce a positive integer-pixel 2:1 crop before submitting panorama generation.

#### Scenario: Source is animated
- **WHEN** a user attempts to convert an animated image
- **THEN** the system reports an error and does not submit panorama generation

#### Scenario: Source cannot produce a positive crop
- **WHEN** a source image cannot provide at least a 2-pixel-wide by 1-pixel-high crop
- **THEN** the system reports an error and does not submit panorama generation

