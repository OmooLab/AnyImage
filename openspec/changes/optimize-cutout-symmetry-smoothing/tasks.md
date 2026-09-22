## 1. Shared smoothing

- [x] 1.1 Add opt-in Point/Corner influence caching and exact cleanup to pinned smoothing
- [x] 1.2 Add a lazy UV geometry branch without changing Position smoothing

## 2. Symmetry integration

- [x] 2.1 Connect shared UV smoothing behavior to both smoothing stages
- [x] 2.2 Replace the zero-iteration Fill control with a Fill Sides geometry bypass
- [x] 2.3 Enable dual-domain influence caching for Fill smoothing

## 3. Verification

- [x] 3.1 Add interface, structure, output-equivalence, and UV-bypass tests
- [x] 3.2 Benchmark the supplied heart image across baseline and cached-region cases
- [x] 3.3 Rebuild and validate all node assets

## 4. Fixed UV and merge limits

- [x] 4.1 Gate shared pinned UV smoothing to the first four repeat iterations
- [x] 4.2 Remove Symmetry Smooth UV and Merge Distance inputs and fix merge distance to `1e-6`
- [x] 4.3 Update structure and behavior tests, benchmark the supplied image, and rebuild node assets
