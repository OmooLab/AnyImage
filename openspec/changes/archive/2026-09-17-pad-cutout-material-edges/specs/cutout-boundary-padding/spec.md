## ADDED Requirements

### Requirement: Cutout boundary mapping follows the structural interior
The system SHALL derive one local inward direction from the final Cutout threshold Mask without selecting among content-based donor candidates. For each boundary location it SHALL sample at Boundary Padding pixels along that inward direction and transport the sample through the inner boundary band, boundary and outer padding band.

#### Scenario: Outer and hole boundaries
- **WHEN** the final Cutout Mask contains an outer outline or a hole
- **THEN** its mapping points from that boundary into the adjacent filled Mask region

#### Scenario: Thin structure
- **WHEN** the configured inward distance would leave the current Mask along the same ray
- **THEN** the mapping stops at the last position inside that Mask without changing direction or searching another donor

#### Scenario: Undefined local direction
- **WHEN** a boundary-band location has no finite nonzero local inward direction
- **THEN** that location remains unchanged

### Requirement: Material and depth share the Cutout boundary mapping
The system SHALL apply the same structural mapping to the independent Cutout material Color Image and optional Depth Image after raw AI artifacts return and before material or geometry consumption. It SHALL scale the mapping to each target image resolution.

#### Scenario: Material padding
- **WHEN** Boundary Padding is positive
- **THEN** the material boundary band receives complete RGBA from its mapped internal location

#### Scenario: Depth padding
- **WHEN** a Depth Cutout has positive Boundary Padding
- **THEN** its boundary band receives camera Z and validity from the mapped internal location and camera X/Y are reconstructed for each target pixel from the original intrinsics

#### Scenario: Different resolutions
- **WHEN** material and Depth images have different dimensions
- **THEN** both mappings represent the same normalized Cutout boundary and proportional padding width

### Requirement: Boundary processing is isolated from source and AI data
The system SHALL preserve the source Image, original Cutout Mask, mesh geometry, UV coordinates, MoGe input, Normal output, intrinsics and reference depth. The server SHALL generate raw Cutout Depth without edge extension.

#### Scenario: AI Cutout
- **WHEN** Cutout requests Depth or Normal generation
- **THEN** MoGe processes the unpadded input and only the returned Color and Depth images receive client-side boundary processing

#### Scenario: Existing depth calibration
- **WHEN** client-side Depth padding changes boundary pixels
- **THEN** the original Metadata reference depth remains the Cutout calibration reference

### Requirement: Boundary Padding is configurable
The system SHALL expose `Boundary Padding` in Preferences under Cutout Tool as a pixel distance with a default of 2, a minimum of 1 and a maximum of 4. Each Cutout operation SHALL capture the current value and existing objects SHALL remain unchanged.

#### Scenario: Asynchronous preference change
- **WHEN** the preference changes after an AI Cutout starts
- **THEN** its response uses the value captured when that operation started

### Requirement: Processed images preserve their lifecycle
The system SHALL preserve existing Color and Depth precision, interpretation, ownership and cleanup behavior after client-side boundary processing.

#### Scenario: Successful creation
- **WHEN** a padded Cutout is created successfully
- **THEN** its processed independent Color and optional Depth Images are packed with their updated pixels

#### Scenario: Failed creation
- **WHEN** Cutout creation fails after loading either image
- **THEN** unowned Blender Images and temporary files are released by the existing cleanup path
