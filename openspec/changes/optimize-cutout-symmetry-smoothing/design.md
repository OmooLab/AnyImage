## Context

`O Image Cutout Symmetry` applies one pinned Seam repeat before mirroring and one non-boundary Fill repeat after joining the mirrored result. Both repeat zones update Position and corner UV. The Fill influence is a fixed four-ring field, but without an explicit domain anchor it is evaluated as Point data for Position and Corner data for UV in every repeat context.

## Goals / Non-Goals

**Goals:**

- Evaluate the fixed Fill influence once per domain before its repeat.
- Make Fill Sides false a geometry-level lazy bypass around Fill smoothing.
- Limit UV relaxation cost independently from Position iteration count.
- Remove smoothing and merge controls that no longer need user tuning.

**Non-Goals:**

- Split the shared Smooth count into separate Seam and Fill controls.
- Smooth only an extracted band or introduce repeat-local geometry separation.
- Change Pin Sharp, pin-boundary behavior, or wall topology.

## Decisions

### 1. Cache Fill influence on Point and Corner domains

Extend shared pinned smoothing with an opt-in cached-region mode. It stores the incoming influence as two private attributes before the repeat: Point for Position weight and Corner for UV weight. The repeat reads the matching attribute and removes both after completion.

A single Point attribute is insufficient because it changes the existing Corner-domain UV interpolation. Keeping both domains was verified in an in-memory prototype to preserve Position, UV, topology, and loop order exactly.

### 2. Bypass the complete Fill repeat with Fill Sides

Use a geometry switch after the seam weld: false returns the welded geometry directly; true evaluates Fill smoothing with the shared Smooth count. The Fill repeat no longer needs an integer switch that merely changes its iteration count to zero.

### 3. Limit UV work from the repeat iteration index

Shared pinned smoothing compares the Repeat Input iteration index with `4`. The UV Store Named Attribute branch runs only while the index is below four; later iterations pass the current geometry directly to Set Position. Position targets and weights continue for every requested iteration.

### 4. Fix Symmetry merge distance internally

Remove the public Smooth UV and Merge Distance sockets. UV relaxation is automatic for up to four iterations, and all plane classification, snapping, and welding use a fixed `1e-6` distance.

### 5. Benchmark the supplied image through the real node chain

Use the supplied heart image to create the same image/depth geometry path used by the product, then measure evaluated modifier execution with alternating inputs. Report median timings for representative Smooth values, Fill Sides states, and capped versus uncapped UV work.

## Risks / Trade-offs

- [Cached fields change domain adaptation] → Store separate Point and Corner values and assert exact Position/UV equivalence through the fourth iteration.
- [UV continues beyond the cap] → Assert both repeat zones gate their UV stores from the paired Repeat Input iteration index with a strict threshold of four.
- [Image generation path introduces unrelated model time] → Benchmark only Blender modifier evaluation after input geometry exists.
