## ADDED Requirements

### Requirement: Fill influence caches both consumer domains

Shared pinned smoothing SHALL support caching a fixed influence before the repeat as separate Point and Corner internal attributes. Position SHALL consume the Point value, UV SHALL consume the Corner value, and both attributes MUST be removed after the repeat.

#### Scenario: Cached Fill smoothing preserves output

- **WHEN** `O Image Cutout Symmetry` applies Fill smoothing
- **THEN** cached and uncached results have identical Position, UV, topology, and loop order

### Requirement: UV relaxation is capped at four iterations

Shared pinned smoothing SHALL update UV only during the first four repeat iterations. Position smoothing SHALL continue for the full requested iteration count.

#### Scenario: High smoothing count

- **WHEN** the requested smoothing count is greater than four
- **THEN** UV Store Named Attribute evaluates exactly four times
- **AND** later repeat iterations update Position without updating UV
