# Upstream: https://github.com/dcm3c/tangle/tree/66221c398cd90f06a7beb0c0abf637b269313af3
# Original tangle.py SHA256: e53fe29bb9fe5174d1735f2d7060b1d7d14f1005666ef60bb93e27b4e0caa679
# Local changes: memory entry point, isolated numeric context, resource limits;
# removed CLI and file IO. Numerical meshing core retained under MIT.
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 David Meeker
"""
tangle
A 2D Delaunay triangulation tool compatible with Shewchuk's Triangle format.

Author: David Meeker
Generated with the assistance of Claude Code
Translated from tangle.cpp

Version 0.4.18
22 Aug 2026

MIT License

Copyright (c) 2026 David Meeker

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import sys
import math
import bisect
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from threading import RLock
from heapq import heappush, heappop

# Exact-predicate fallback precision.  orient2d/in_circle fall back to Decimal
# when the double filter is inconclusive; the products there need ~34 (orient2d)
# to ~51 (in_circle) significant digits to be exact, well above Decimal's default
# 28 (~93 bits, which is BELOW the float128 tangle.cpp found insufficient for
# mixed-scale coords -- see f0854c1, which moved C++ to float256 ~245 bits).
# 80 digits comfortably exceeds float256's precision; it only costs in the rare
# fallback (the double filter handles >99.9% of calls).
_CALL_LOCK = RLock()

# Base relative tolerance.  EPS is scaled to the bounding-box diagonal in
# build_delaunay(); EPS_SCALE controls that ratio and is also used directly
# for dimensionless comparisons.
EPS_SCALE = 1e-10
EPS = EPS_SCALE

# Relative tolerance for "too close" geometry: used both by cleanPSLG
# (merge nodes within bboxDiag * CLOSE_ENOUGH) and by quality refinement
# (reduce angle threshold for triangles with all edges < bboxDiag * CLOSE_ENOUGH).
CLOSE_ENOUGH = 1e-6

# Reduced minimum angle (degrees) for tiny triangles in locally dense
# regions where the full minimum angle is unachievable.
TINY_TRI_ANGLE = 15.0

# Hard cap on the requested minimum angle (degrees).  Delaunay refinement is
# only guaranteed to terminate below ~33.8 deg (Ruppert/Shewchuk); matches the
# ceiling FEMM enforces.  Under shortest-edge ordering refinement stays tame
# right up to this bound.
MINANGLE_MAX_VAL = 33.8


# ============================================================
# Options
# ============================================================

@dataclass
class Options:
    pslg: bool = False
    no_poly_out: bool = False
    jettison: bool = False
    quality: bool = False
    min_angle: float = 20.0
    edges: bool = False
    regions: bool = False
    area_limit: bool = False
    max_area: float = -1.0
    zero_indexed: bool = False
    quiet: bool = False
    suppress_iter: bool = False
    no_holes: bool = False
    no_steiner: bool = False
    neighbors: bool = False
    clean_pslg: bool = False
    clean_tol: float = -1.0  # -1 = auto (bboxDiag * 1e-6)
    reorder: bool = False  # reverse Cuthill-McKee bandwidth/profile reduction
    first_index: int = 1


# ============================================================
# Geometry primitives
# ============================================================

@dataclass
class Point:
    x: float
    y: float
    id: int = 0
    marker: int = 0
    attribs: list = field(default_factory=list)
    lfs: float = -1.0  # local feature size constraint (-1 = none)


@dataclass
class Segment:
    v0: int
    v1: int
    marker: int = 0
    lfs: float = -1.0  # per-segment LFS constraint (-1 = none)
    pbc_type: int = -1     # 0=periodic, 1=anti-periodic (-1 = none)
    no_split: bool = False # true for AGE chord segments (must stay uniformly spaced)
    pbc_side: int = -1     # 0/1: declared side of an (anti)periodic pair; -1 = n/a


@dataclass
class Hole:
    x: float
    y: float


@dataclass
class Region:
    x: float
    y: float
    attrib: float = 0.0
    max_area: float = -1.0


@dataclass
class Triangle:
    v: list = field(default_factory=lambda: [-1, -1, -1])
    neighbors: list = field(default_factory=lambda: [-1, -1, -1])
    region_attrib: float = 0.0
    region_max_area: float = -1.0
    marker: int = 0
    generation: int = 0


def orient2d_xy(ax, ay, bx, by, cx, cy):
    """orient2d on raw coordinates — avoids constructing a Point.
    Same exact-arithmetic fallback as orient2d."""
    Ax, Ay = bx - ax, by - ay
    Bx, By = cx - ax, cy - ay
    det = Ax * By - Bx * Ay
    M = max(abs(Ax), abs(Ay), abs(Bx), abs(By))
    if abs(det) > 6.662e-16 * M * M:
        return det
    fAx = Decimal(bx) - Decimal(ax)
    fAy = Decimal(by) - Decimal(ay)
    fBx = Decimal(cx) - Decimal(ax)
    fBy = Decimal(cy) - Decimal(ay)
    return float(fAx * fBy - fBx * fAy)


def orient2d(a, b, c):
    Ax, Ay = b.x - a.x, b.y - a.y
    Bx, By = c.x - a.x, c.y - a.y
    det = Ax * By - Bx * Ay

    # Error bound: det terms are O(M²), check if result is well above fp noise
    M = max(abs(Ax), abs(Ay), abs(Bx), abs(By))
    if abs(det) > 6.662e-16 * M * M:
        return det

    # Fall back to exact arithmetic via Decimal
    fAx = Decimal(b.x) - Decimal(a.x)
    fAy = Decimal(b.y) - Decimal(a.y)
    fBx = Decimal(c.x) - Decimal(a.x)
    fBy = Decimal(c.y) - Decimal(a.y)
    return float(fAx * fBy - fBx * fAy)


def in_circle(a, b, c, d):
    # 3x3 formulation: subtract d to eliminate one row
    Ax, Ay = a.x - d.x, a.y - d.y
    Bx, By = b.x - d.x, b.y - d.y
    Cx, Cy = c.x - d.x, c.y - d.y
    As = Ax * Ax + Ay * Ay
    Bs = Bx * Bx + By * By
    Cs = Cx * Cx + Cy * Cy

    det = (Ax * (By * Cs - Cy * Bs)
         - Ay * (Bx * Cs - Cx * Bs)
         + As * (Bx * Cy - Cx * By))

    # Error bound: det terms are O(M⁴), check if result is well above fp noise
    M = max(abs(Ax), abs(Ay), abs(Bx), abs(By),
            abs(Cx), abs(Cy))
    M4 = M * M * M * M
    if abs(det) > 1.333e-14 * M4:
        return det

    # Fall back to exact arithmetic via Decimal (standard 3x3 formulation)
    ax = Decimal(a.x) - Decimal(d.x)
    ay = Decimal(a.y) - Decimal(d.y)
    bx = Decimal(b.x) - Decimal(d.x)
    by = Decimal(b.y) - Decimal(d.y)
    cx = Decimal(c.x) - Decimal(d.x)
    cy = Decimal(c.y) - Decimal(d.y)
    cs = cx * cx + cy * cy
    bs = bx * bx + by * by
    fdet = (ax * (by * cs - cy * bs)
          - ay * (bx * cs - cx * bs)
          + (ax * ax + ay * ay) * (bx * cy - cx * by))
    return float(fdet)


def tri_area(a, b, c):
    return 0.5 * abs(orient2d(a, b, c))


def vertex_angle(a, b, c):
    abx, aby = b.x - a.x, b.y - a.y
    acx, acy = c.x - a.x, c.y - a.y
    dot = abx * acx + aby * acy
    cross = abx * acy - aby * acx
    return math.atan2(abs(cross), dot) * 180.0 / math.pi


def min_angle(a, b, c):
    la = math.sqrt((b.x-c.x)*(b.x-c.x)+(b.y-c.y)*(b.y-c.y))
    lb = math.sqrt((a.x-c.x)*(a.x-c.x)+(a.y-c.y)*(a.y-c.y))
    lc = math.sqrt((a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y))
    if la < EPS or lb < EPS or lc < EPS:
        return 0.0
    cos_a = max(-1.0, min(1.0, (lb * lb + lc * lc - la * la) / (2 * lb * lc)))
    cos_b = max(-1.0, min(1.0, (la * la + lc * lc - lb * lb) / (2 * la * lc)))
    cos_c = max(-1.0, min(1.0, (la * la + lb * lb - lc * lc) / (2 * la * lb)))
    return min(math.acos(cos_a), math.acos(cos_b), math.acos(cos_c)) * 180.0 / math.pi


def circumcenter(a, b, c):
    ax, ay = b.x - a.x, b.y - a.y
    bx, by = c.x - a.x, c.y - a.y
    D = 2.0 * (ax * by - ay * bx)
    if abs(D) < EPS:
        return (a.x + b.x + c.x) / 3.0, (a.y + b.y + c.y) / 3.0
    ux = (by * (ax * ax + ay * ay) - ay * (bx * bx + by * by)) / D
    uy = (ax * (bx * bx + by * by) - bx * (ax * ax + ay * ay)) / D
    return a.x + ux, a.y + uy


def point_on_segment(p, a, b):
    if orient2d(a, b, p) != 0:
        return False
    dx, dy = b.x - a.x, b.y - a.y
    if abs(dx) > EPS:
        t = (p.x - a.x) / dx
    elif abs(dy) > EPS:
        t = (p.y - a.y) / dy
    else:
        return False
    return -EPS_SCALE <= t <= 1 + EPS_SCALE  # dimensionless: fixed tolerance


def edge_key(a, b):
    return (min(a, b), max(a, b))


# ============================================================
# Mesh structure
# ============================================================

@dataclass
class PBCNodePair:
    node_a: int
    node_b: int
    type: int  # 0=periodic, 1=anti-periodic


class Mesh:
    def __init__(self):
        self.vertices = []
        self.triangles = []
        self.segments = []
        self.holes = []
        self.regions = []
        self.edges = []
        self.pbc_pairs = []      # list of PBCNodePair, filled after refinement
        self.pbc_twin = {}       # dict: node -> twin node (bidirectional)
        self.pbc_node_type = {}  # dict: node -> pbc type (0 or 1)
        self.pbc_defs = []       # PBC declarations: (marker_a, marker_b, type)

    def rebuild_adjacency(self):
        nt = len(self.triangles)
        edge_to_tri_edge = {}
        for t in self.triangles:
            t.neighbors = [-1, -1, -1]
        for i in range(nt):
            t = self.triangles[i]
            if t.v[0] < 0:
                continue
            for j in range(3):
                a, b = t.v[j], t.v[(j + 1) % 3]
                mn, mx = min(a, b), max(a, b)
                key = (mn << 32) | mx
                if key in edge_to_tri_edge:
                    packed = edge_to_tri_edge[key]
                    ot, oe = packed >> 2, packed & 3
                    self.triangles[i].neighbors[j] = ot
                    self.triangles[ot].neighbors[oe] = i
                    del edge_to_tri_edge[key]
                else:
                    edge_to_tri_edge[key] = (i << 2) | j

    def locate_triangle(self, px, py, hint=0):
        tris = self.triangles
        if not tris:
            return -1
        n = len(tris)
        if hint < 0 or hint >= n:
            hint = 0
        cur = hint
        verts = self.vertices
        for _ in range(n * 2):
            t = tris[cur]
            if t.v[0] < 0:
                cur = (cur + 1) % n
                continue
            v0, v1, v2 = verts[t.v[0]], verts[t.v[1]], verts[t.v[2]]
            o0 = orient2d_xy(v0.x, v0.y, v1.x, v1.y, px, py)
            o1 = orient2d_xy(v1.x, v1.y, v2.x, v2.y, px, py)
            o2 = orient2d_xy(v2.x, v2.y, v0.x, v0.y, px, py)
            if o0 >= -EPS and o1 >= -EPS and o2 >= -EPS:
                return cur
            worst, wv = -1, 0
            if o0 < wv:
                wv, worst = o0, 0
            if o1 < wv:
                wv, worst = o1, 1
            if o2 < wv:
                wv, worst = o2, 2
            if worst >= 0 and t.neighbors[worst] >= 0:
                cur = t.neighbors[worst]
            else:
                break
        # Fallback: linear scan
        for i in range(n):
            t = tris[i]
            if t.v[0] < 0:
                continue
            v0, v1, v2 = verts[t.v[0]], verts[t.v[1]], verts[t.v[2]]
            if (orient2d_xy(v0.x, v0.y, v1.x, v1.y, px, py) >= -EPS and
                orient2d_xy(v1.x, v1.y, v2.x, v2.y, px, py) >= -EPS and
                orient2d_xy(v2.x, v2.y, v0.x, v0.y, px, py) >= -EPS):
                return i
        return -1

    def has_edge(self, u, v, v2t):
        for ti in v2t[u]:
            t = self.triangles[ti]
            if t.v[0] < 0:
                continue
            for j in range(3):
                if (t.v[j] == u and t.v[(j + 1) % 3] == v) or \
                   (t.v[j] == v and t.v[(j + 1) % 3] == u):
                    return True
        return False


# ============================================================
# PSLG cleanup (-C flag)
# ============================================================

def clean_pslg(mesh, tol, quiet):
    pts = mesh.vertices
    segs = mesh.segments
    nv = len(pts)

    # Compute auto tolerance if not specified.  tol == -1 is the -C default
    # (bb_diag * CLOSE_ENOUGH); tol <= -2 is the always-on hygiene pass run for
    # every PSLG, with an essentially-exact tolerance (bb_diag * 1e-12, ~4 decimal
    # digits above double ULP) that merges only true duplicates and geometry no
    # refinement could ever resolve, while still splitting crossing segments (the
    # intersection test is tolerance-independent).
    if tol < 0:
        min_x = min(p.x for p in pts)
        max_x = max(p.x for p in pts)
        min_y = min(p.y for p in pts)
        max_y = max(p.y for p in pts)
        bb_diag = math.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        tol = bb_diag * (1e-12 if tol <= -2.0 else CLOSE_ENOUGH)
    tol2 = tol * tol

    merged_nodes = 0
    split_segs = 0
    removed_segs = 0

    # 1. Merge near-duplicate nodes (x-sorted sweep to avoid O(n²))
    remap = list(range(nv))
    xorder = sorted(range(nv), key=lambda k: pts[k].x)
    for ii in range(nv):
        i = xorder[ii]
        if remap[i] != i:
            continue
        for jj in range(ii + 1, nv):
            j = xorder[jj]
            if pts[j].x - pts[i].x > tol:
                break  # x-sorted: no more candidates
            if remap[j] != j:
                continue
            dx = pts[j].x - pts[i].x
            dy = pts[j].y - pts[i].y
            if dx * dx + dy * dy < tol2:
                remap[j] = i
                merged_nodes += 1

    # Apply remap to segments
    for s in segs:
        s.v0 = remap[s.v0]
        s.v1 = remap[s.v1]

    # 2. Remove degenerate segments
    good = [s for s in segs if s.v0 != s.v1]
    removed_segs += len(segs) - len(good)
    mesh.segments = good
    segs = mesh.segments

    # 3. Remove duplicate segments
    seen = set()
    good = []
    for s in segs:
        k = edge_key(s.v0, s.v1)
        if k not in seen:
            seen.add(k)
            good.append(s)
        else:
            removed_segs += 1
    mesh.segments = good
    segs = mesh.segments

    # Spatial grid shared by sections 4 and 5, replacing their O(S*N) / O(S^2)
    # brute-force scans. A segment's candidate points/segments are gathered from
    # the grid cells its supporting line passes through (sampled at <=1-cell
    # steps, each expanded to a 3x3 halo so anything within tol of the line is
    # covered) and processed lowest-index-first with the same tests as before,
    # so the output is identical -- just without the quadratic scan. Grid side
    # is capped at 1024, so cells >> tol always.
    def grid_dims():
        xmn = min(p.x for p in pts); xmx = max(p.x for p in pts)
        ymn = min(p.y for p in pts); ymx = max(p.y for p in pts)
        side = min(1024, max(1, int(math.sqrt(len(pts)))))
        cell = max((xmx - xmn) / side, (ymx - ymn) / side, 1e-30)
        return xmn, ymn, cell, int((xmx - xmn) / cell) + 1, int((ymx - ymn) / cell) + 1

    def seg_cells(x0, y0, x1, y1, gx0, gy0, cell, gnx, gny):
        # cells the segment's line passes through, each haloed 3x3 (deduped)
        cells = set()
        ns = max(1, int(math.hypot(x1 - x0, y1 - y0) / cell) + 1)
        for s in range(ns + 1):
            tt = s / ns
            cx = min(max(int((x0 + (x1 - x0) * tt - gx0) / cell), 0), gnx - 1)
            cy = min(max(int((y0 + (y1 - y0) * tt - gy0) / cell), 0), gny - 1)
            for ddx in (-1, 0, 1):
                for ddy in (-1, 0, 1):
                    mx, my = cx + ddx, cy + ddy
                    if 0 <= mx < gnx and 0 <= my < gny:
                        cells.add(mx * gny + my)
        return cells

    # 4. Split segments at near-coincident nodes (node lies on segment).
    # Points are not added in this section, so the point grid is built once.
    gx0, gy0, cell, gnx, gny = grid_dims()
    pgrid = {}
    for i in range(len(pts)):
        if i < nv and remap[i] != i:
            continue  # merged away
        cx = min(max(int((pts[i].x - gx0) / cell), 0), gnx - 1)
        cy = min(max(int((pts[i].y - gy0) / cell), 0), gny - 1)
        pgrid.setdefault(cx * gny + cy, []).append(i)
    changed = True
    while changed:
        changed = False
        for si in range(len(segs)):
            v0, v1 = segs[si].v0, segs[si].v1
            ax, ay = pts[v0].x, pts[v0].y
            bx, by = pts[v1].x, pts[v1].y
            dx, dy = bx - ax, by - ay
            len2 = dx * dx + dy * dy
            if len2 < tol2:
                continue
            sqrt_len = math.sqrt(len2)
            # segment bounding box (expanded by tol)
            sx0 = min(ax, bx) - tol
            sx1 = max(ax, bx) + tol
            sy0 = min(ay, by) - tol
            sy1 = max(ay, by) + tol
            # lowest-index point lying on this segment, from the cells it crosses
            best_i = -1
            for c in seg_cells(ax, ay, bx, by, gx0, gy0, cell, gnx, gny):
                for i in pgrid.get(c, ()):
                    if i == v0 or i == v1:
                        continue
                    if best_i >= 0 and i >= best_i:
                        continue
                    if i < nv and remap[i] != i:
                        continue
                    if pts[i].x < sx0 or pts[i].x > sx1 or pts[i].y < sy0 or pts[i].y > sy1:
                        continue
                    px, py = pts[i].x - ax, pts[i].y - ay
                    t = (dx * px + dy * py) / len2
                    if t <= tol / sqrt_len or t >= 1.0 - tol / sqrt_len:
                        continue
                    cross = dx * py - dy * px
                    if cross * cross > tol2 * len2:
                        continue
                    best_i = i
            if best_i >= 0:
                # Point best_i is on segment si — split it
                s2 = Segment(best_i, segs[si].v1, segs[si].marker, segs[si].lfs, segs[si].pbc_type, segs[si].no_split, segs[si].pbc_side)
                segs[si] = Segment(segs[si].v0, best_i, segs[si].marker, segs[si].lfs, segs[si].pbc_type, segs[si].no_split, segs[si].pbc_side)
                segs.append(s2)
                split_segs += 1
                changed = True

    # 5. Split segments at segment-segment intersections. Segments and points
    # change on every split, so the segment grid is rebuilt each pass; two
    # intersecting segments share the crossing cell, so each is a candidate for
    # the other.
    changed = True
    while changed:
        changed = False
        gx0, gy0, cell, gnx, gny = grid_dims()
        sgrid = {}
        for s in range(len(segs)):
            for c in seg_cells(pts[segs[s].v0].x, pts[segs[s].v0].y,
                               pts[segs[s].v1].x, pts[segs[s].v1].y,
                               gx0, gy0, cell, gnx, gny):
                sgrid.setdefault(c, []).append(s)
        for i in range(len(segs)):
            if changed:
                break
            ax, ay = pts[segs[i].v0].x, pts[segs[i].v0].y
            bx, by = pts[segs[i].v1].x, pts[segs[i].v1].y
            ax0, ax1 = min(ax, bx), max(ax, bx)
            ay0, ay1 = min(ay, by), max(ay, by)
            d1x, d1y = bx - ax, by - ay
            # lowest j>i whose segment intersects i, from the cells i crosses
            best_j = -1
            ix_best = iy_best = 0.0
            for c in seg_cells(ax, ay, bx, by, gx0, gy0, cell, gnx, gny):
                for j in sgrid.get(c, ()):
                    if j <= i:
                        continue
                    if best_j >= 0 and j >= best_j:
                        continue
                    # Skip if they share an endpoint
                    if (segs[i].v0 in (segs[j].v0, segs[j].v1) or
                        segs[i].v1 in (segs[j].v0, segs[j].v1)):
                        continue
                    # Bounding box pre-filter
                    bx0 = min(pts[segs[j].v0].x, pts[segs[j].v1].x)
                    bx1 = max(pts[segs[j].v0].x, pts[segs[j].v1].x)
                    if ax1 < bx0 or ax0 > bx1:
                        continue
                    by0 = min(pts[segs[j].v0].y, pts[segs[j].v1].y)
                    by1 = max(pts[segs[j].v0].y, pts[segs[j].v1].y)
                    if ay1 < by0 or ay0 > by1:
                        continue
                    cx, cy = pts[segs[j].v0].x, pts[segs[j].v0].y
                    d2x, d2y = pts[segs[j].v1].x, pts[segs[j].v1].y
                    ddx, ddy = d2x - cx, d2y - cy
                    denom = d1x * ddy - d1y * ddx
                    # Parallel-rejection must be SCALE-FREE: denom scales with the
                    # product of the segment lengths, so a fixed 1e-15 cutoff
                    # silently skipped genuine crossings between short near-parallel
                    # segments (and was needlessly far from underflow for long ones).
                    dmag = abs(d1x * ddy) + abs(d1y * ddx)
                    if dmag == 0.0 or abs(denom) < 1e-12 * dmag:
                        continue
                    t = ((cx - ax) * ddy - (cy - ay) * ddx) / denom
                    u = ((cx - ax) * d1y - (cy - ay) * d1x) / denom
                    if t <= 0 or t >= 1 or u <= 0 or u >= 1:
                        continue
                    best_j = j
                    ix_best, iy_best = ax + t * d1x, ay + t * d1y
            if best_j >= 0:
                j = best_j
                ix, iy = ix_best, iy_best
                # Check if intersection is near an existing node
                near_node = -1
                for k in range(len(pts)):
                    ex, ey = pts[k].x - ix, pts[k].y - iy
                    if ex * ex + ey * ey < tol2:
                        near_node = k
                        break
                if near_node < 0:
                    near_node = len(pts)
                    pts.append(Point(ix, iy, near_node, 0))
                # Split both segments
                s_i2 = Segment(near_node, segs[i].v1, segs[i].marker, segs[i].lfs, segs[i].pbc_type, segs[i].no_split, segs[i].pbc_side)
                segs[i] = Segment(segs[i].v0, near_node, segs[i].marker, segs[i].lfs, segs[i].pbc_type, segs[i].no_split, segs[i].pbc_side)
                segs.append(s_i2)
                s_j2 = Segment(near_node, segs[j].v1, segs[j].marker, segs[j].lfs, segs[j].pbc_type, segs[j].no_split, segs[j].pbc_side)
                segs[j] = Segment(segs[j].v0, near_node, segs[j].marker, segs[j].lfs, segs[j].pbc_type, segs[j].no_split, segs[j].pbc_side)
                segs.append(s_j2)
                split_segs += 2
                changed = True

    # Compact: remove merged-away vertices and re-index
    if merged_nodes > 0:
        new_idx = [-1] * len(pts)
        new_pts = []
        for i in range(len(pts)):
            target = remap[i] if i < nv else i
            if target != i:
                continue
            new_idx[i] = len(new_pts)
            pts[i].id = len(new_pts)
            new_pts.append(pts[i])
        for i in range(nv):
            if remap[i] != i:
                new_idx[i] = new_idx[remap[i]]
        for i in range(nv, len(pts)):
            if new_idx[i] < 0:
                new_idx[i] = len(new_pts)
                pts[i].id = len(new_pts)
                new_pts.append(pts[i])
        for s in segs:
            s.v0 = new_idx[s.v0]
            s.v1 = new_idx[s.v1]
        mesh.vertices = new_pts

    if not quiet and (merged_nodes > 0 or split_segs > 0 or removed_segs > 0):
        print(f"  PSLG cleanup: merged {merged_nodes} nodes, split "
              f"{split_segs} segments, removed {removed_segs} duplicates",
              file=sys.stderr)


# ============================================================
# Bowyer-Watson Delaunay triangulation
# ============================================================

def build_delaunay(mesh):
    pts = mesh.vertices
    n = len(pts)

    min_x = min(p.x for p in pts)
    max_x = max(p.x for p in pts)
    min_y = min(p.y for p in pts)
    max_y = max(p.y for p in pts)
    dx, dy = max_x - min_x, max_y - min_y
    d = max(dx, dy) * 10.0

    # Scale EPS to the bounding-box diagonal so tolerances stay meaningful
    # regardless of coordinate magnitude.
    global EPS
    bbox_diag = math.sqrt(dx*dx + dy*dy)
    EPS = bbox_diag * EPS_SCALE
    pts.append(Point(min_x - d, min_y - 3 * d, n, 0))
    pts.append(Point(min_x + 3 * d, min_y - d, n + 1, 0))
    pts.append(Point(min_x - d, min_y + 3 * d, n + 2, 0))

    tris = mesh.triangles
    tris.clear()
    tris.append(Triangle(v=[n, n + 1, n + 2], neighbors=[-1, -1, -1]))

    order = sorted(range(n), key=lambda i: (pts[i].x, pts[i].y))

    last_tri = 0
    visit_epoch = []
    epoch = 0
    skipped_pts = 0

    for ii in range(n):
        pidx = order[ii]
        p = pts[pidx]

        # Locate containing triangle by walking
        start_tri = -1
        cur = min(last_tri, len(tris) - 1)
        for _ in range(len(tris) * 2):
            t = tris[cur]
            if t.v[0] < 0:
                cur = 0
                continue
            o0 = orient2d(pts[t.v[0]], pts[t.v[1]], p)
            o1 = orient2d(pts[t.v[1]], pts[t.v[2]], p)
            o2 = orient2d(pts[t.v[2]], pts[t.v[0]], p)
            if o0 >= -EPS and o1 >= -EPS and o2 >= -EPS:
                start_tri = cur
                break
            w, wv = -1, 0
            if o0 < wv:
                wv, w = o0, 0
            if o1 < wv:
                wv, w = o1, 1
            if o2 < wv:
                wv, w = o2, 2
            if w >= 0 and t.neighbors[w] >= 0:
                cur = t.neighbors[w]
            else:
                break
        if start_tri < 0:
            for i in range(len(tris)):
                t = tris[i]
                if t.v[0] < 0:
                    continue
                if (orient2d(pts[t.v[0]], pts[t.v[1]], p) >= -EPS and
                    orient2d(pts[t.v[1]], pts[t.v[2]], p) >= -EPS and
                    orient2d(pts[t.v[2]], pts[t.v[0]], p) >= -EPS):
                    start_tri = i
                    break
        if start_tri < 0:
            skipped_pts += 1
            continue

        # Precise re-walk with exact orientation tests (the Bowyer-Watson
        # analogue of insert_point_lawson's exact refinement): the EPS-tolerant
        # walk above can stop at a triangle the point is actually just OUTSIDE
        # of, and near a vertex the circumcircle of that triangle can exclude the
        # point -- yielding a falsely empty cavity below.
        for _ in range(len(tris)):
            t = tris[start_tri]
            neg_edge = -1
            for j in range(3):
                if orient2d(pts[t.v[j]], pts[t.v[(j + 1) % 3]], p) < 0.0:
                    neg_edge = j
                    break
            if neg_edge < 0:
                break  # exact containment (or on edge)
            nb = t.neighbors[neg_edge]
            if nb < 0:
                break  # hull edge -- accept current
            start_tri = nb

        # BFS cavity (epoch-based visited to avoid per-point allocation)
        epoch += 1
        while len(visit_epoch) < len(tris):
            visit_epoch.append(0)
        bad = []
        stk = [start_tri]
        while stk:
            cur = stk.pop()
            if cur < 0 or cur >= len(tris) or visit_epoch[cur] == epoch:
                continue
            visit_epoch[cur] = epoch
            t = tris[cur]
            if t.v[0] < 0:
                continue
            if in_circle(pts[t.v[0]], pts[t.v[1]], pts[t.v[2]], p) > 0:
                bad.append(cur)
                for j in range(3):
                    if t.neighbors[j] >= 0 and visit_epoch[t.neighbors[j]] != epoch:
                        stk.append(t.neighbors[j])

        # Empty cavity: with exact predicates, a point strictly inside any
        # triangle is strictly inside its circumcircle, so an empty cavity means
        # the point coincides with an existing vertex (or the EPS walk mislocated
        # it).  Leave it unconnected, like Triangle's duplicate-vertex handling.
        # (A previous revision force-fanned the located triangle here, which
        # emitted zero-area triangles for exact duplicates and overlapping
        # triangles for mislocations -- a corrupted triangulation either way.)
        if not bad:
            skipped_pts += 1
            continue

        # Collect boundary polygon
        bad_set = set(bad)
        poly = []  # list of (v0, v1, outer_tri, outer_local_edge)
        for bi in bad:
            t = tris[bi]
            for j in range(3):
                nb = t.neighbors[j]
                if nb < 0 or nb not in bad_set:
                    oe = -1
                    if nb >= 0:
                        for k in range(3):
                            if tris[nb].neighbors[k] == bi:
                                oe = k
                                break
                    poly.append((t.v[j], t.v[(j + 1) % 3], nb, oe))

        # (A strict-CCW fan-refusal guard used to live here -- one orient2d per
        # cavity-boundary edge, refusing the insertion if any fan triangle came
        # out non-CCW.  With exact predicates the precise re-walk above guarantees
        # a correctly located point produces an all-CCW fan, so it refused 0
        # insertions suite-wide and was removed; outputs byte-identical without
        # it.  The empty-cavity skip above still catches exact duplicates.
        # tangle.cpp 0.4.3.)

        n_new = len(poly)
        bad.sort()
        slots = []
        for i in range(min(n_new, len(bad))):
            slots.append(bad[i])
        while len(slots) < n_new:
            slots.append(len(tris))
            tris.append(Triangle())
        for i in range(n_new, len(bad)):
            tris[bad[i]].v = [-1, -1, -1]
            tris[bad[i]].neighbors = [-1, -1, -1]

        for i in range(n_new):
            s = slots[i]
            tris[s].v = [poly[i][0], poly[i][1], pidx]
            tris[s].neighbors = [-1, -1, -1]
            tris[s].region_attrib = 0
            tris[s].region_max_area = -1
            tris[s].marker = 0
            # Strictly CCW by the fan guard above -- no orientation fix-up.

        # Wire outer adjacency
        for i in range(n_new):
            s = slots[i]
            if poly[i][2] < 0:
                continue
            for j in range(3):
                a, b = tris[s].v[j], tris[s].v[(j + 1) % 3]
                if (a == poly[i][0] and b == poly[i][1]) or \
                   (a == poly[i][1] and b == poly[i][0]):
                    tris[s].neighbors[j] = poly[i][2]
                    if poly[i][3] >= 0:
                        tris[poly[i][2]].neighbors[poly[i][3]] = s
                    break

        # Wire internal adjacency
        pidx_edges = {}
        for i in range(n_new):
            s = slots[i]
            for j in range(3):
                a, b = tris[s].v[j], tris[s].v[(j + 1) % 3]
                if a != pidx and b != pidx:
                    continue
                other = b if a == pidx else a
                if other in pidx_edges:
                    os, oe = pidx_edges[other]
                    tris[s].neighbors[j] = os
                    tris[os].neighbors[oe] = s
                    del pidx_edges[other]
                else:
                    pidx_edges[other] = (s, j)
        last_tri = slots[0]

    if skipped_pts > 0:
        sys.stderr.write(
            f"Warning: {skipped_pts} point{'' if skipped_pts == 1 else 's'} "
            "could not be inserted (duplicate or unlocatable); left unconnected.\n")

    # Remove dead triangles and super-triangle vertices
    keep = [False] * len(tris)
    for i in range(len(tris)):
        if tris[i].v[0] < 0:
            continue
        if tris[i].v[0] >= n or tris[i].v[1] >= n or tris[i].v[2] >= n:
            continue
        keep[i] = True
    remap = [-1] * len(tris)
    new_tris = []
    for i in range(len(tris)):
        if keep[i]:
            remap[i] = len(new_tris)
            new_tris.append(tris[i])
    for t in new_tris:
        for j in range(3):
            t.neighbors[j] = remap[t.neighbors[j]] if t.neighbors[j] >= 0 else -1
    mesh.triangles = new_tris
    del pts[n:]

    # Detect and re-insert orphaned vertices
    mesh.rebuild_adjacency()
    tris = mesh.triangles
    orphan_visit_epoch = []
    orphan_epoch = 0
    for retry in range(10):
        in_mesh = [False] * n
        for t in tris:
            if t.v[0] >= 0:
                for j in range(3):
                    if t.v[j] < n:
                        in_mesh[t.v[j]] = True
        orphans = [i for i in range(n) if not in_mesh[i]]
        if not orphans:
            break

        for pidx in orphans:
            p = pts[pidx]
            contain_tri = mesh.locate_triangle(p.x, p.y)
            if contain_tri < 0:
                continue

            # Skip if nearly coincident
            too_close = False
            for j in range(3):
                dx2 = pts[tris[contain_tri].v[j]].x - p.x
                dy2 = pts[tris[contain_tri].v[j]].y - p.y
                if dx2 * dx2 + dy2 * dy2 < EPS * EPS:
                    too_close = True
                    break
            if too_close:
                continue

            # Bowyer-Watson insertion with strict inCircle to avoid over-expanding
            # the cavity and orphaning nearby vertices
            orphan_epoch += 1
            while len(orphan_visit_epoch) < len(tris):
                orphan_visit_epoch.append(0)
            bad = []
            stk = [contain_tri]
            while stk:
                cur = stk.pop()
                if cur < 0 or cur >= len(tris) or orphan_visit_epoch[cur] == orphan_epoch:
                    continue
                orphan_visit_epoch[cur] = orphan_epoch
                t = tris[cur]
                if t.v[0] < 0:
                    continue
                if in_circle(pts[t.v[0]], pts[t.v[1]], pts[t.v[2]], p) > 0:
                    bad.append(cur)
                    for j in range(3):
                        if t.neighbors[j] >= 0 and orphan_visit_epoch[t.neighbors[j]] != orphan_epoch:
                            stk.append(t.neighbors[j])
            if not bad:
                bad.append(contain_tri)

            bad_set = set(bad)
            poly = []
            for bi in bad:
                t = tris[bi]
                for j in range(3):
                    nb = t.neighbors[j]
                    if nb < 0 or nb not in bad_set:
                        oe = -1
                        if nb >= 0:
                            for k in range(3):
                                if tris[nb].neighbors[k] == bi:
                                    oe = k
                                    break
                        poly.append((t.v[j], t.v[(j + 1) % 3], nb, oe))

            n_new = len(poly)
            bad.sort()
            slots = []
            for i in range(min(n_new, len(bad))):
                slots.append(bad[i])
            while len(slots) < n_new:
                slots.append(len(tris))
                tris.append(Triangle())
            for i in range(n_new, len(bad)):
                tris[bad[i]].v = [-1, -1, -1]
                tris[bad[i]].neighbors = [-1, -1, -1]

            for i in range(n_new):
                s = slots[i]
                tris[s].v = [poly[i][0], poly[i][1], pidx]
                tris[s].neighbors = [-1, -1, -1]
                tris[s].region_attrib = 0
                tris[s].region_max_area = -1
                tris[s].marker = 0
                if orient2d(pts[tris[s].v[0]], pts[tris[s].v[1]], pts[tris[s].v[2]]) < 0:
                    tris[s].v[0], tris[s].v[1] = tris[s].v[1], tris[s].v[0]

            # Wire outer adjacency
            for i in range(n_new):
                s = slots[i]
                if poly[i][2] < 0:
                    continue
                for j in range(3):
                    a, b = tris[s].v[j], tris[s].v[(j + 1) % 3]
                    if (a == poly[i][0] and b == poly[i][1]) or \
                       (a == poly[i][1] and b == poly[i][0]):
                        tris[s].neighbors[j] = poly[i][2]
                        if poly[i][3] >= 0:
                            tris[poly[i][2]].neighbors[poly[i][3]] = s
                        break

            # Wire internal adjacency
            pidx_edges = {}
            for i in range(n_new):
                s = slots[i]
                for j in range(3):
                    a, b = tris[s].v[j], tris[s].v[(j + 1) % 3]
                    if a != pidx and b != pidx:
                        continue
                    other = b if a == pidx else a
                    if other in pidx_edges:
                        os, oe = pidx_edges[other]
                        tris[s].neighbors[j] = os
                        tris[os].neighbors[oe] = s
                        del pidx_edges[other]
                    else:
                        pidx_edges[other] = (s, j)


# ============================================================
# CDT: enforce PSLG segments via cavity retriangulation
# ============================================================

def enforce_constraints(mesh, quiet):
    if not mesh.segments:
        return 0

    def build_v2t():
        v2t = [[] for _ in range(len(mesh.vertices))]
        for i, t in enumerate(mesh.triangles):
            if t.v[0] < 0:
                continue
            for j in range(3):
                v2t[t.v[j]].append(i)
        return v2t

    def ear_clip(poly_verts):
        # Strict ear clipping (mirrors C++ earClip): clip only well-formed empty
        # ears, and reject an ear when a vertex lies ON its new diagonal (the
        # >= 0 term) -- clipping it would orphan that vertex as a hanging node
        # (FEMM's near-collinear corner twins land exactly there). No relaxed
        # pass / fan fallback. On a stall it returns an INCOMPLETE result; the
        # caller checks the triangle count (a simple m-gon -> m-2 triangles) and
        # declines, routing the segment to the midpoint-split + rebuild fallback.
        result = []
        p = list(poly_verts)
        while len(p) > 3:
            clipped = False
            nn = len(p)
            for i in range(nn):
                prev_v = p[(i + nn - 1) % nn]
                cur_v = p[i]
                next_v = p[(i + 1) % nn]
                if orient2d(mesh.vertices[prev_v], mesh.vertices[cur_v],
                            mesh.vertices[next_v]) <= 0.0:
                    continue
                blocked = False
                for k in range(nn):
                    if k in ((i + nn - 1) % nn, i, (i + 1) % nn):
                        continue
                    vi = p[k]
                    if (orient2d(mesh.vertices[prev_v], mesh.vertices[cur_v],
                                 mesh.vertices[vi]) > 0 and
                        orient2d(mesh.vertices[cur_v], mesh.vertices[next_v],
                                 mesh.vertices[vi]) > 0 and
                        orient2d(mesh.vertices[next_v], mesh.vertices[prev_v],
                                 mesh.vertices[vi]) >= 0):
                        blocked = True
                        break
                if blocked:
                    continue
                result.append([prev_v, cur_v, next_v])
                p.pop(i)
                clipped = True
                break
            if not clipped:
                break
        if len(p) == 3:
            o = orient2d(mesh.vertices[p[0]], mesh.vertices[p[1]], mesh.vertices[p[2]])
            if o > 0:
                result.append([p[0], p[1], p[2]])
            elif o < 0:
                result.append([p[0], p[2], p[1]])
        return result

    v2t = build_v2t()

    # Split segments at collinear intermediate vertices
    # Sort vertex indices by x-coordinate for efficient range queries
    xorder = sorted(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].x)
    xsorted = [mesh.vertices[i].x for i in xorder]

    new_segs = []
    for seg in mesh.segments:
        su, sv = seg.v0, seg.v1
        sx, sy = mesh.vertices[su].x, mesh.vertices[su].y
        ddx, ddy = mesh.vertices[sv].x - sx, mesh.vertices[sv].y - sy
        len2 = ddx * ddx + ddy * ddy
        if len2 < EPS * EPS:
            new_segs.append(seg)
            continue
        eps2_len2 = EPS * EPS * len2  # squared collinearity threshold
        bxlo = min(sx, sx + ddx) - EPS
        bxhi = max(sx, sx + ddx) + EPS
        bylo = min(sy, sy + ddy) - EPS
        byhi = max(sy, sy + ddy) + EPS
        # Binary search for x-range [bxlo, bxhi]
        ilo = bisect.bisect_left(xsorted, bxlo)
        ihi = bisect.bisect_right(xsorted, bxhi)
        on_seg = []
        for ii in range(ilo, ihi):
            i = xorder[ii]
            if i == su or i == sv:
                continue
            vy = mesh.vertices[i].y
            if vy < bylo or vy > byhi:
                continue
            px, py = mesh.vertices[i].x - sx, vy - sy
            cross = ddx * py - ddy * px
            if cross * cross > eps2_len2:
                continue
            t_param = (ddx * px + ddy * py) / len2
            if t_param <= EPS_SCALE or t_param >= 1.0 - EPS_SCALE:
                continue
            on_seg.append((t_param, i))
        if not on_seg:
            new_segs.append(seg)
        else:
            on_seg.sort()
            prev_v = su
            for _, vi in on_seg:
                new_segs.append(Segment(prev_v, vi, seg.marker, seg.lfs, seg.pbc_type, seg.no_split, seg.pbc_side))
                prev_v = vi
            new_segs.append(Segment(prev_v, sv, seg.marker, seg.lfs, seg.pbc_type, seg.no_split, seg.pbc_side))
    if len(new_segs) != len(mesh.segments):
        if not quiet:
            print(f"  Split {len(mesh.segments)} segments into {len(new_segs)} sub-segments (collinear vertices)",
                  file=sys.stderr)
        mesh.segments = new_segs

    # Direct adjacency check: flip-based
    mesh.rebuild_adjacency()
    v2t = build_v2t()
    # Constrained-segment edges: a flip must never destroy one of these to
    # enforce another, or two crossing segments oscillate A<->B forever.
    seg_set = set()
    for s in mesh.segments:
        seg_set.add(edge_key(s.v0, s.v1))
    any_fixed = True
    # Hard cap: each segment needs only a handful of flips; the cap stops a
    # cocircular/collinear configuration from spinning. Segments not enforced
    # here fall through to the corridor + midpoint-split stages below.
    flip_passes = 2 * len(mesh.segments) + 16
    while any_fixed and flip_passes > 0:
        flip_passes -= 1
        any_fixed = False
        for seg in mesh.segments:
            su2, sv2 = seg.v0, seg.v1
            if mesh.has_edge(su2, sv2, v2t):
                continue
            found = False
            for ti in v2t[su2]:
                if mesh.has_edge(su2, sv2, v2t):
                    break
                t = mesh.triangles[ti]
                if t.v[0] < 0:
                    continue
                for j in range(3):
                    nb = t.neighbors[j]
                    if nb < 0:
                        continue
                    tn = mesh.triangles[nb]
                    has_sv = any(tn.v[k] == sv2 for k in range(3))
                    if not has_sv:
                        continue
                    a, b = t.v[j], t.v[(j + 1) % 3]
                    if a == su2 or b == su2 or a == sv2 or b == sv2:
                        continue
                    if edge_key(a, b) in seg_set:
                        continue  # never flip out a constrained segment
                    p_v, q_v = su2, sv2
                    o1 = orient2d(mesh.vertices[p_v], mesh.vertices[a], mesh.vertices[q_v])
                    o2 = orient2d(mesh.vertices[p_v], mesh.vertices[q_v], mesh.vertices[b])
                    if o1 < 0 or o2 < 0:
                        continue
                    # Do the flip
                    n_pa, n_bp = -1, -1
                    for k in range(3):
                        e0, e1 = t.v[k], t.v[(k + 1) % 3]
                        if (e0 == p_v and e1 == a) or (e0 == a and e1 == p_v):
                            n_pa = t.neighbors[k]
                        if (e0 == b and e1 == p_v) or (e0 == p_v and e1 == b):
                            n_bp = t.neighbors[k]
                    n_aq, n_qb = -1, -1
                    for k in range(3):
                        e0, e1 = tn.v[k], tn.v[(k + 1) % 3]
                        if (e0 == a and e1 == q_v) or (e0 == q_v and e1 == a):
                            n_aq = tn.neighbors[k]
                        if (e0 == q_v and e1 == b) or (e0 == b and e1 == q_v):
                            n_qb = tn.neighbors[k]
                    t.v = [p_v, a, q_v]
                    t.neighbors = [n_pa, n_aq, nb]
                    tn.v = [p_v, q_v, b]
                    tn.neighbors = [ti, n_qb, n_bp]
                    if n_aq >= 0:
                        for k in range(3):
                            if mesh.triangles[n_aq].neighbors[k] == nb:
                                mesh.triangles[n_aq].neighbors[k] = ti
                                break
                    if n_bp >= 0:
                        for k in range(3):
                            if mesh.triangles[n_bp].neighbors[k] == ti:
                                mesh.triangles[n_bp].neighbors[k] = nb
                                break
                    v2t = build_v2t()
                    any_fixed = True
                    found = True
                    break
                if found:
                    break

    # Cavity fallback for the few segments the flip block couldn't enforce
    def segs_cross(v1, v2, v3, v4):
        d1 = orient2d(mesh.vertices[v1], mesh.vertices[v2], mesh.vertices[v3])
        d2 = orient2d(mesh.vertices[v1], mesh.vertices[v2], mesh.vertices[v4])
        if d1 * d2 >= 0:
            return False
        d3 = orient2d(mesh.vertices[v3], mesh.vertices[v4], mesh.vertices[v1])
        d4 = orient2d(mesh.vertices[v3], mesh.vertices[v4], mesh.vertices[v2])
        if d3 * d4 >= 0:
            return False
        return True

    for seg in mesh.segments:
        su, sv = seg.v0, seg.v1
        if mesh.has_edge(su, sv, v2t):
            continue

        # Cavity-based fallback
        crossed_set = set()
        for ti in range(len(mesh.triangles)):
            t = mesh.triangles[ti]
            if t.v[0] < 0:
                continue
            for j in range(3):
                a, b = t.v[j], t.v[(j + 1) % 3]
                if segs_cross(su, sv, a, b):
                    crossed_set.add(ti)
                    break
        for vi in (su, sv):
            for ti in v2t[vi]:
                t = mesh.triangles[ti]
                if t.v[0] < 0:
                    continue
                for j in range(3):
                    if t.neighbors[j] in crossed_set:
                        for k in range(3):
                            a, b = t.v[k], t.v[(k + 1) % 3]
                            if segs_cross(su, sv, a, b):
                                crossed_set.add(ti)
                                break
                        break

        if crossed_set:
            bnd_edges_cav = []
            for ti in crossed_set:
                t = mesh.triangles[ti]
                for j in range(3):
                    nb = t.neighbors[j]
                    if nb < 0 or nb not in crossed_set:
                        bnd_edges_cav.append((t.v[j], t.v[(j + 1) % 3], nb))

            # Chain boundary edges
            adj_map = {}
            for i, be in enumerate(bnd_edges_cav):
                adj_map.setdefault(be[0], []).append((be[1], i))
            for v_key in adj_map:
                if len(adj_map[v_key]) > 1:
                    adj_map[v_key].sort(
                        key=lambda x: (math.atan2(
                            mesh.vertices[x[0]].y - mesh.vertices[v_key].y,
                            mesh.vertices[x[0]].x - mesh.vertices[v_key].x),
                            x[0]))  # deterministic tie-break on collinear edges

            poly_chain = []
            used_edges = set()
            start_v = bnd_edges_cav[0][0]
            cur_v = start_v
            prev_v = -1
            chain_ok = True

            for _ in range(len(bnd_edges_cav) + 1):
                poly_chain.append(cur_v)
                outs = adj_map.get(cur_v, [])
                best_idx = -1
                if len(outs) == 1 and outs[0][1] not in used_edges:
                    best_idx = 0
                elif prev_v >= 0:
                    in_dx = mesh.vertices[cur_v].x - mesh.vertices[prev_v].x
                    in_dy = mesh.vertices[cur_v].y - mesh.vertices[prev_v].y
                    in_angle = math.atan2(in_dy, in_dx)
                    best_turn = 1e30
                    for k in range(len(outs)):
                        if outs[k][1] in used_edges:
                            continue
                        ox = mesh.vertices[outs[k][0]].x - mesh.vertices[cur_v].x
                        oy = mesh.vertices[outs[k][0]].y - mesh.vertices[cur_v].y
                        out_angle = math.atan2(oy, ox)
                        turn = out_angle - in_angle
                        while turn <= 0:
                            turn += 2 * math.pi
                        # deterministic tie-break: on equal turn (collinear
                        # outgoing edges) prefer the lower target-vertex index
                        if turn < best_turn or \
                           (turn == best_turn and best_idx >= 0 and
                                outs[k][0] < outs[best_idx][0]):
                            best_turn = turn
                            best_idx = k
                else:
                    for k in range(len(outs)):
                        if outs[k][1] not in used_edges:
                            best_idx = k
                            break
                if best_idx < 0:
                    chain_ok = False
                    break
                used_edges.add(outs[best_idx][1])
                prev_v = cur_v
                cur_v = outs[best_idx][0]
                if cur_v == start_v and len(poly_chain) > 2:
                    break

            if len(poly_chain) >= 3 and cur_v != start_v:
                chain_ok = False

            new_tris_cav = []
            if chain_ok and len(poly_chain) >= 3:
                su_idx = sv_idx = -1
                for i in range(len(poly_chain)):
                    if poly_chain[i] == su:
                        su_idx = i
                    if poly_chain[i] == sv:
                        sv_idx = i
                if su_idx >= 0 and sv_idx >= 0:
                    nn = len(poly_chain)
                    poly1, poly2 = [], []
                    i = su_idx
                    while True:
                        poly1.append(poly_chain[i])
                        if i == sv_idx:
                            break
                        i = (i + 1) % nn
                    i = sv_idx
                    while True:
                        poly2.append(poly_chain[i])
                        if i == su_idx:
                            break
                        i = (i + 1) % nn
                    # Accept only COMPLETE triangulations (m-gon -> m-2 tris). A
                    # short count means ear_clip declined a degenerate cavity;
                    # leave new_tris_cav empty so the segment falls through to the
                    # midpoint-split + rebuild fallback.
                    t1, t2 = ear_clip(poly1), ear_clip(poly2)
                    if len(t1) == max(0, len(poly1) - 2) and len(t2) == max(0, len(poly2) - 2):
                        new_tris_cav = t1 + t2
                    else:
                        new_tris_cav = []
                else:
                    tt = ear_clip(poly_chain)
                    new_tris_cav = tt if len(tt) == max(0, len(poly_chain) - 2) else []

            if new_tris_cav:
                crossed_vec = sorted(crossed_set)
                total_new = len(new_tris_cav)
                total_old = len(crossed_vec)

                slots = []
                for i in range(min(total_old, total_new)):
                    slots.append(crossed_vec[i])
                while len(slots) < total_new:
                    slots.append(len(mesh.triangles))
                    mesh.triangles.append(Triangle())
                for i in range(total_new, total_old):
                    mesh.triangles[crossed_vec[i]].v = [-1, -1, -1]
                    mesh.triangles[crossed_vec[i]].neighbors = [-1, -1, -1]

                for i in range(total_new):
                    s = slots[i]
                    mesh.triangles[s].v = list(new_tris_cav[i])
                    mesh.triangles[s].neighbors = [-1, -1, -1]

                edge_map2 = {}
                for i in range(total_new):
                    s = slots[i]
                    t = mesh.triangles[s]
                    for j in range(3):
                        key = edge_key(t.v[j], t.v[(j + 1) % 3])
                        if key in edge_map2:
                            os, oe = edge_map2[key]
                            t.neighbors[j] = os
                            mesh.triangles[os].neighbors[oe] = s
                            del edge_map2[key]
                        else:
                            edge_map2[key] = (s, j)

                for be in bnd_edges_cav:
                    key = edge_key(be[0], be[1])
                    if key in edge_map2:
                        s, j = edge_map2[key]
                        mesh.triangles[s].neighbors[j] = be[2]
                        if be[2] >= 0:
                            ot = mesh.triangles[be[2]]
                            for k in range(3):
                                if ot.neighbors[k] in crossed_set:
                                    e0, e1 = ot.v[k], ot.v[(k + 1) % 3]
                                    if edge_key(e0, e1) == key:
                                        ot.neighbors[k] = s
                                        break
                v2t = build_v2t()

    # Count and return remaining missing segments
    miss = 0
    v2t = build_v2t()
    for s in mesh.segments:
        if not mesh.has_edge(s.v0, s.v1, v2t):
            miss += 1
            if not quiet:
                print(f"  UNENFORCED: v{s.v0} ({mesh.vertices[s.v0].x},{mesh.vertices[s.v0].y})"
                      f"->v{s.v1} ({mesh.vertices[s.v1].x},{mesh.vertices[s.v1].y})"
                      f" len={math.sqrt((mesh.vertices[s.v1].x-mesh.vertices[s.v0].x)*(mesh.vertices[s.v1].x-mesh.vertices[s.v0].x)+(mesh.vertices[s.v1].y-mesh.vertices[s.v0].y)*(mesh.vertices[s.v1].y-mesh.vertices[s.v0].y))}",
                      file=sys.stderr)
    if not quiet and miss > 0:
        print(f"Warning: {miss} of {len(mesh.segments)} segments could not be enforced.",
              file=sys.stderr)
    return miss


# ============================================================
# Flood-fill hole removal
# ============================================================

def remove_holes(mesh, opts):
    if opts.no_holes:
        return
    mesh.rebuild_adjacency()

    seg_edges = set()
    for s in mesh.segments:
        seg_edges.add(edge_key(s.v0, s.v1))

    remove = [False] * len(mesh.triangles)

    # Remove exterior: flood-fill from boundary triangles whose boundary
    # edge is not a constrained segment.
    q = deque()
    for i in range(len(mesh.triangles)):
        if remove[i]:
            continue
        t = mesh.triangles[i]
        for j in range(3):
            if t.neighbors[j] >= 0:
                continue
            key = edge_key(t.v[j], t.v[(j + 1) % 3])
            if key in seg_edges:
                continue
            if not remove[i]:
                remove[i] = True
                q.append(i)
            break
    while q:
        ti = q.popleft()
        t = mesh.triangles[ti]
        for j in range(3):
            nb = t.neighbors[j]
            if nb < 0 or remove[nb]:
                continue
            key = edge_key(t.v[j], t.v[(j + 1) % 3])
            if key in seg_edges:
                continue
            remove[nb] = True
            q.append(nb)

    # Remove explicit holes via flood fill from seed points
    for hole in mesh.holes:
        seed_tri = mesh.locate_triangle(hole.x, hole.y)
        if seed_tri < 0:
            continue
        q = deque([seed_tri])
        remove[seed_tri] = True
        while q:
            ti = q.popleft()
            t = mesh.triangles[ti]
            for j in range(3):
                nb = t.neighbors[j]
                if nb < 0 or remove[nb]:
                    continue
                key = edge_key(t.v[j], t.v[(j + 1) % 3])
                if key in seg_edges:
                    continue
                remove[nb] = True
                q.append(nb)

    kept = []
    remap = [-1] * len(mesh.triangles)
    for i in range(len(mesh.triangles)):
        if not remove[i]:
            remap[i] = len(kept)
            kept.append(mesh.triangles[i])
    for t in kept:
        for j in range(3):
            t.neighbors[j] = remap[t.neighbors[j]] if t.neighbors[j] >= 0 else -1
    mesh.triangles = kept


# ============================================================
# Flood-fill region assignment
# ============================================================

def assign_regions(mesh, opts):
    if not opts.regions or not mesh.regions:
        return
    mesh.rebuild_adjacency()

    seg_edges = set()
    for s in mesh.segments:
        seg_edges.add(edge_key(s.v0, s.v1))

    for t in mesh.triangles:
        t.region_attrib = 0
        t.region_max_area = -1

    for reg in mesh.regions:
        seed_tri = mesh.locate_triangle(reg.x, reg.y)
        if seed_tri < 0:
            continue
        q = deque([seed_tri])
        visited = [False] * len(mesh.triangles)
        visited[seed_tri] = True
        while q:
            ti = q.popleft()
            t = mesh.triangles[ti]
            t.region_attrib = reg.attrib
            t.region_max_area = reg.max_area
            for j in range(3):
                nb = t.neighbors[j]
                if nb < 0 or visited[nb]:
                    continue
                key = edge_key(t.v[j], t.v[(j + 1) % 3])
                if key in seg_edges:
                    continue
                visited[nb] = True
                q.append(nb)


# ============================================================
# Point insertion for quality refinement (Lawson flip-based)
# ============================================================

def insert_point_lawson(mesh, np, hint_tri, constrained_edges, affected, min_dist2=0.0):
    pidx = len(mesh.vertices)
    if len(mesh.vertices) >= mesh.max_vertices:
        raise ValueError("Cutout mesh vertex limit exceeded")
    mesh.vertices.append(np)

    ti = mesh.locate_triangle(np.x, np.y, hint_tri)
    if ti < 0:
        mesh.vertices.pop()
        return -1

    # Precise refinement: use exact orient2d_xy to walk from the approximate
    # triangle to the true containing triangle, à la Triangle's preciselocate().
    on_edge = -1
    for _ in range(len(mesh.triangles)):
        tr = mesh.triangles[ti]
        if tr.v[0] < 0:
            mesh.vertices.pop()
            return -1
        on_edge = -1
        neg_edge = -1
        for j in range(3):
            o = orient2d_xy(mesh.vertices[tr.v[j]].x, mesh.vertices[tr.v[j]].y,
                            mesh.vertices[tr.v[(j+1)%3]].x, mesh.vertices[tr.v[(j+1)%3]].y,
                            np.x, np.y)
            if o == 0.0:
                on_edge = j
            elif o < 0.0:
                neg_edge = j
        if neg_edge < 0:
            break  # all orient2d >= 0: point is inside (or on edge)
        nb = tr.neighbors[neg_edge]
        if nb < 0:
            break  # boundary — accept current triangle
        ti = nb
        on_edge = -1

    t = mesh.triangles[ti]

    # If precise refinement didn't detect on-edge (midpoint rounding),
    # fall back to EPS-based on-edge detection for segment midpoints.
    if on_edge < 0:
        for j in range(3):
            va, vb = t.v[j], t.v[(j + 1) % 3]
            edx = mesh.vertices[vb].x - mesh.vertices[va].x
            edy = mesh.vertices[vb].y - mesh.vertices[va].y
            o = orient2d_xy(mesh.vertices[va].x, mesh.vertices[va].y,
                            mesh.vertices[vb].x, mesh.vertices[vb].y, np.x, np.y)
            if o * o < EPS * EPS * (edx * edx + edy * edy):
                on_edge = j
                break

    # Check near-coincident with existing vertex. The reject radius is normally
    # EPS, but the quality-refinement caller passes min_dist2 = (0.5*shortest
    # edge)^2 as a too-close guard: an off-center/circumcenter landing within half
    # the bad triangle's shortest edge of an existing vertex is rejected (the
    # triangle is then tolerated). Stops the insertion radius collapsing on
    # near-degenerate geometry. No-op on well-conditioned meshes.
    rej_r2 = max(EPS * EPS, min_dist2)
    for j in range(3):
        dx = mesh.vertices[t.v[j]].x - np.x
        dy = mesh.vertices[t.v[j]].y - np.y
        if dx * dx + dy * dy < rej_r2:
            mesh.vertices.pop()
            return -1

    # Output-orientation validation (parity with tangle.cpp 156f54e): every
    # triangle a split creates must be strictly CCW (positive area). The locate
    # walk can accept a boundary triangle for a point actually OUTSIDE the domain;
    # splitting there manufactures an inverted triangle, and one invalid triangle
    # corrupts every circumcenter / flip / adjacency built on it. Refuse any such
    # split (the bad triangle is tolerated). Exact predicate => no inverted or
    # degenerate triangle can ever enter the mesh.
    def tri_ccw(a, b, c):
        return orient2d_xy(mesh.vertices[a].x, mesh.vertices[a].y,
                           mesh.vertices[b].x, mesh.vertices[b].y,
                           mesh.vertices[c].x, mesh.vertices[c].y) > 0.0

    # Inherit region from the containing triangle
    reg_attr = t.region_attrib
    reg_area = t.region_max_area

    flip_stack = []

    if on_edge < 0:
        # Interior: split triangle into 3
        v0, v1, v2 = t.v[0], t.v[1], t.v[2]
        if not (tri_ccw(v0, v1, pidx) and tri_ccw(v1, v2, pidx) and tri_ccw(v2, v0, pidx)):
            mesh.vertices.pop()
            return -1
        n0, n1, n2 = t.neighbors[0], t.neighbors[1], t.neighbors[2]

        t0 = ti
        t1 = len(mesh.triangles)
        mesh.triangles.append(Triangle())
        t2 = len(mesh.triangles)
        mesh.triangles.append(Triangle())

        mesh.triangles[t0] = Triangle(v=[v0, v1, pidx], neighbors=[n0, t1, t2],
                                      region_attrib=reg_attr, region_max_area=reg_area)
        mesh.triangles[t1] = Triangle(v=[v1, v2, pidx], neighbors=[n1, t2, t0],
                                      region_attrib=reg_attr, region_max_area=reg_area)
        mesh.triangles[t2] = Triangle(v=[v2, v0, pidx], neighbors=[n2, t0, t1],
                                      region_attrib=reg_attr, region_max_area=reg_area)

        if n1 >= 0:
            for k in range(3):
                if mesh.triangles[n1].neighbors[k] == ti:
                    mesh.triangles[n1].neighbors[k] = t1
                    break
        if n2 >= 0:
            for k in range(3):
                if mesh.triangles[n2].neighbors[k] == ti:
                    mesh.triangles[n2].neighbors[k] = t2
                    break

        flip_stack.extend([(t0, 0), (t1, 0), (t2, 0)])
        affected.extend([t0, t1, t2])
    else:
        # On edge: split 2 triangles into 4
        va = t.v[on_edge]
        vb = t.v[(on_edge + 1) % 3]
        vc = t.v[(on_edge + 2) % 3]
        n_ab = t.neighbors[on_edge]
        n_bvc = t.neighbors[(on_edge + 1) % 3]
        n_cva = t.neighbors[(on_edge + 2) % 3]

        if n_ab < 0:
            # Boundary edge: split 1 triangle into 2
            if not (tri_ccw(va, pidx, vc) and tri_ccw(pidx, vb, vc)):
                mesh.vertices.pop()
                return -1
            t0 = ti
            t1 = len(mesh.triangles)
            mesh.triangles.append(Triangle())

            mesh.triangles[t0] = Triangle(v=[va, pidx, vc], neighbors=[-1, t1, n_cva],
                                          region_attrib=reg_attr, region_max_area=reg_area)
            mesh.triangles[t1] = Triangle(v=[pidx, vb, vc], neighbors=[-1, n_bvc, t0],
                                          region_attrib=reg_attr, region_max_area=reg_area)

            if n_bvc >= 0:
                for k in range(3):
                    if mesh.triangles[n_bvc].neighbors[k] == ti:
                        mesh.triangles[n_bvc].neighbors[k] = t1
                        break

            flip_stack.extend([(t0, 2), (t1, 1)])
            affected.extend([t0, t1])
        else:
            # Both sides: split 2 triangles into 4
            tn = mesh.triangles[n_ab]
            je = -1
            for k in range(3):
                if tn.neighbors[k] == ti:
                    je = k
                    break
            if je < 0:
                mesh.vertices.pop()
                return -1

            vd = tn.v[(je + 2) % 3]
            # Coincidence check for the neighbor's apex: the on-edge split creates
            # edges to vd, but the rejection loop above only tested the CONTAINING
            # triangle's vertices.  A point within the reject radius of vd passed
            # that test, and the strict-CCW guard below accepts any sub-EPS-thin
            # but positively-oriented sliver -- a legal-but-degenerate triangle at vd.
            dxv = mesh.vertices[vd].x - np.x
            dyv = mesh.vertices[vd].y - np.y
            if dxv * dxv + dyv * dyv < rej_r2:
                mesh.vertices.pop()
                return -1
            if tn.v[je] == vb and tn.v[(je + 1) % 3] == va:
                n_avd = tn.neighbors[(je + 1) % 3]
                n_dvb = tn.neighbors[(je + 2) % 3]
            else:
                n_dvb = tn.neighbors[(je + 1) % 3]
                n_avd = tn.neighbors[(je + 2) % 3]

            if not (tri_ccw(va, pidx, vc) and tri_ccw(pidx, vb, vc) and
                    tri_ccw(vb, pidx, vd) and tri_ccw(pidx, va, vd)):
                mesh.vertices.pop()
                return -1
            # Inherit region from the neighbor triangle
            reg_attr2 = tn.region_attrib
            reg_area2 = tn.region_max_area

            t0 = ti
            t1 = len(mesh.triangles)
            mesh.triangles.append(Triangle())
            t2 = n_ab
            t3 = len(mesh.triangles)
            mesh.triangles.append(Triangle())

            mesh.triangles[t0] = Triangle(v=[va, pidx, vc], neighbors=[t3, t1, n_cva],
                                          region_attrib=reg_attr, region_max_area=reg_area)
            mesh.triangles[t1] = Triangle(v=[pidx, vb, vc], neighbors=[t2, n_bvc, t0],
                                          region_attrib=reg_attr, region_max_area=reg_area)
            mesh.triangles[t2] = Triangle(v=[vb, pidx, vd], neighbors=[t1, t3, n_dvb],
                                          region_attrib=reg_attr2, region_max_area=reg_area2)
            mesh.triangles[t3] = Triangle(v=[pidx, va, vd], neighbors=[t0, n_avd, t2],
                                          region_attrib=reg_attr2, region_max_area=reg_area2)

            if n_bvc >= 0:
                for k in range(3):
                    if mesh.triangles[n_bvc].neighbors[k] == ti:
                        mesh.triangles[n_bvc].neighbors[k] = t1
                        break
            if n_avd >= 0:
                for k in range(3):
                    if mesh.triangles[n_avd].neighbors[k] == n_ab:
                        mesh.triangles[n_avd].neighbors[k] = t3
                        break

            flip_stack.extend([(t0, 2), (t1, 1), (t2, 2), (t3, 1)])
            affected.extend([t0, t1, t2, t3])

    # Lawson flip loop
    while flip_stack:
        ft, fj = flip_stack.pop()
        tri = mesh.triangles[ft]
        if tri.v[0] < 0:
            continue
        fn = tri.neighbors[fj]
        if fn < 0:
            continue

        fa, fb, fp = tri.v[fj], tri.v[(fj + 1) % 3], tri.v[(fj + 2) % 3]

        if edge_key(fa, fb) in constrained_edges:
            continue

        tri_n = mesh.triangles[fn]
        if tri_n.v[0] < 0:
            continue
        fj2 = -1
        for k in range(3):
            if tri_n.neighbors[k] == ft:
                fj2 = k
                break
        if fj2 < 0:
            continue

        fq = tri_n.v[(fj2 + 2) % 3]

        if in_circle(mesh.vertices[fa], mesh.vertices[fb], mesh.vertices[fp],
                     mesh.vertices[fq]) <= 0:
            continue

        # No convexity check: with exact predicates, in_circle(fa,fb,fp,fq)>0
        # implies the quad (fa,fq,fb,fp) is convex, so both flipped triangles
        # come out CCW.  The belt-and-suspenders orient2d pair that lived here
        # rejected 0 of millions of flips suite-wide (byte-identical without it)
        # and was removed (tangle.cpp 0.4.3).

        n_fb_fp = tri.neighbors[(fj + 1) % 3]
        n_fp_fa = tri.neighbors[(fj + 2) % 3]
        n_ext1 = tri_n.neighbors[(fj2 + 1) % 3]
        n_ext2 = tri_n.neighbors[(fj2 + 2) % 3]

        if tri_n.v[fj2] != fb:
            n_ext1, n_ext2 = n_ext2, n_ext1

        ra, ra2 = tri.region_attrib, tri.region_max_area
        rb, rb2 = tri_n.region_attrib, tri_n.region_max_area

        mesh.triangles[ft] = Triangle(v=[fa, fq, fp], neighbors=[n_ext1, fn, n_fp_fa],
                                      region_attrib=ra, region_max_area=ra2)
        mesh.triangles[fn] = Triangle(v=[fb, fp, fq], neighbors=[n_fb_fp, ft, n_ext2],
                                      region_attrib=rb, region_max_area=rb2)

        if n_ext1 >= 0:
            for k in range(3):
                if mesh.triangles[n_ext1].neighbors[k] == fn:
                    mesh.triangles[n_ext1].neighbors[k] = ft
                    break
        if n_fb_fp >= 0:
            for k in range(3):
                if mesh.triangles[n_fb_fp].neighbors[k] == ft:
                    mesh.triangles[n_fb_fp].neighbors[k] = fn
                    break

        affected.extend([ft, fn])
        flip_stack.extend([(ft, 0), (fn, 2)])

    # Bump generation
    for ai in affected:
        if 0 <= ai < len(mesh.triangles):
            mesh.triangles[ai].generation += 1

    return pidx


# ============================================================
# Quality refinement
# ============================================================

def tri_metric(mesh, ti, min_ang_threshold, global_max_a, use_region_area,
               cos_min_ang=-1.0):
    t = mesh.triangles[ti]
    if t.v[0] < 0:
        return (0, False, False, 0, -1, 0, 0, 0, 0)
    a = mesh.vertices[t.v[0]]
    b = mesh.vertices[t.v[1]]
    c = mesh.vertices[t.v[2]]

    # Squared edge lengths (computed once, reused for both area and angle checks)
    la2 = (b.x-c.x)*(b.x-c.x) + (b.y-c.y)*(b.y-c.y)
    lb2 = (a.x-c.x)*(a.x-c.x) + (a.y-c.y)*(a.y-c.y)
    lc2 = (a.x-b.x)*(a.x-b.x) + (a.y-b.y)*(a.y-b.y)

    # Area via cross product (no orient2d exact-arithmetic overhead)
    cross = (b.x-a.x)*(c.y-a.y) - (b.y-a.y)*(c.x-a.x)
    area = 0.5 * abs(cross)

    effective_max_area = -1
    if use_region_area and t.region_max_area > 0:
        effective_max_area = t.region_max_area
    if global_max_a > 0:
        if effective_max_area > 0:
            effective_max_area = min(effective_max_area, global_max_a)
        else:
            effective_max_area = global_max_a
    # LFS constraint: if any vertex has lfs defined, impose area <= sqrt(3)/4 * lfs^2
    for j in range(3):
        vl = mesh.vertices[t.v[j]].lfs
        if vl > 0:
            lfs_area = 0.43301270189221932 * vl * vl  # sqrt(3)/4
            if effective_max_area > 0:
                effective_max_area = min(effective_max_area, lfs_area)
            else:
                effective_max_area = lfs_area
    area_viol = effective_max_area > 0 and area > effective_max_area + EPS

    # Fast angle check using cosine comparison (no hypot/acos)
    # Minimum angle < threshold iff maximum cosine > cosMinAng.
    # cos(angle_opposite_la) = (lb²+lc²-la²) / (2·sqrt(lb²·lc²))
    # Compare squared: (lb²+lc²-la²)² > cos²Threshold · 4·lb²·lc²
    ang_viol = False
    max_cos_ratio = 0.0
    if min_ang_threshold > 0 and cos_min_ang > -0.5:
        cos2t = cos_min_ang * cos_min_ang
        for num, prod in ((lb2 + lc2 - la2, lb2 * lc2),
                          (la2 + lc2 - lb2, la2 * lc2),
                          (la2 + lb2 - lc2, la2 * lb2)):
            if num > 0:
                denom = cos2t * 4.0 * prod
                if denom > 0:
                    ratio = num * num / denom
                    if ratio > 1.0:
                        ang_viol = True
                        if ratio > max_cos_ratio:
                            max_cos_ratio = ratio
    elif min_ang_threshold > 0:
        ang = min_angle(a, b, c)
        ang_viol = ang < min_ang_threshold - EPS
        if ang_viol:
            max_cos_ratio = (min_ang_threshold - ang) / min_ang_threshold + 1.0

    if not area_viol and not ang_viol:
        return (0, False, False, area, effective_max_area, la2, lb2, lc2, cross)
    metric = 0
    if area_viol:
        metric = area / (effective_max_area if effective_max_area > 0 else 1.0)
    if ang_viol:
        metric = max(metric, max_cos_ratio)
    return (metric, ang_viol, area_viol, area, effective_max_area, la2, lb2, lc2, cross)


def refine_quality(mesh, opts, n_input_verts):
    if not opts.quality and not opts.area_limit:
        return
    # Refine to exactly the requested angle.  (An earlier +0.1 deg overshoot
    # "for floating-point precision" only added needless triangles: the refiner
    # never stops at a triangle below the threshold it tests, so the output
    # minimum can fall short by at most rounding in the angle evaluation, orders
    # of magnitude below 0.1 deg.)
    min_ang_val = opts.min_angle if opts.quality else 0.0
    cos_min_ang = math.cos(min_ang_val * math.pi / 180.0) if min_ang_val > 0 else -1.0
    global_max_a = opts.max_area if opts.area_limit else -1.0
    use_region_area = opts.area_limit

    # Estimate final triangle count from CDT using LFS integral with
    # circle-of-influence model for refinement seed vertices.
    nv = len(mesh.vertices)
    nt = len(mesh.triangles)

    # Build vertex-to-triangle adjacency
    v2t = [[] for _ in range(nv)]
    for i in range(nt):
        t = mesh.triangles[i]
        if t.v[0] < 0:
            continue
        for j in range(3):
            v2t[t.v[j]].append(i)

    # Bounding box diagonal — used to cap degenerate circumradii
    gxmin = min(v.x for v in mesh.vertices)
    gxmax = max(v.x for v in mesh.vertices)
    gymin = min(v.y for v in mesh.vertices)
    gymax = max(v.y for v in mesh.vertices)
    bb_diag = math.sqrt((gxmax-gxmin)*(gxmax-gxmin) + (gymax-gymin)*(gymax-gymin))

    # Compute LFS at each vertex as min circumradius of incident CDT triangles
    lfs = [1e30] * nv
    for i in range(nt):
        t = mesh.triangles[i]
        if t.v[0] < 0:
            continue
        p0, p1, p2 = mesh.vertices[t.v[0]], mesh.vertices[t.v[1]], mesh.vertices[t.v[2]]
        area = tri_area(p0, p1, p2)
        e0 = math.sqrt((p1.x-p2.x)*(p1.x-p2.x)+(p1.y-p2.y)*(p1.y-p2.y))
        e1 = math.sqrt((p0.x-p2.x)*(p0.x-p2.x)+(p0.y-p2.y)*(p0.y-p2.y))
        e2 = math.sqrt((p0.x-p1.x)*(p0.x-p1.x)+(p0.y-p1.y)*(p0.y-p1.y))
        R = e0 * e1 * e2 / (4.0 * area) if area > 0 else 0
        if R > 0:
            R = min(R, bb_diag)
            for j in range(3):
                lfs[t.v[j]] = min(lfs[t.v[j]], R)

    # Fold in user-assigned LFS constraints
    for vi in range(nv):
        if mesh.vertices[vi].lfs > 0:
            lfs[vi] = min(lfs[vi], mesh.vertices[vi].lfs)

    # Compute background mesh size H at each vertex from area constraints
    # and median circumradius of incident CDT triangles
    bg_size = [1e30] * nv
    for vi in range(nv):
        # Area constraint contribution (only if area limiting is active)
        amax = global_max_a
        if use_region_area:
            for ti in v2t[vi]:
                t = mesh.triangles[ti]
                if t.v[0] < 0:
                    continue
                if t.region_max_area > 0:
                    amax = min(amax, t.region_max_area) if amax > 0 else t.region_max_area
        if amax > 0:
            bg_size[vi] = math.sqrt(4.0 * amax / math.sqrt(3.0))

        # Median circumradius of incident CDT triangles
        inc_r = []
        for ti in v2t[vi]:
            t = mesh.triangles[ti]
            if t.v[0] < 0:
                continue
            p0, p1, p2 = mesh.vertices[t.v[0]], mesh.vertices[t.v[1]], mesh.vertices[t.v[2]]
            a2 = tri_area(p0, p1, p2)
            ee0 = math.sqrt((p1.x-p2.x)*(p1.x-p2.x)+(p1.y-p2.y)*(p1.y-p2.y))
            ee1 = math.sqrt((p0.x-p2.x)*(p0.x-p2.x)+(p0.y-p2.y)*(p0.y-p2.y))
            ee2 = math.sqrt((p0.x-p1.x)*(p0.x-p1.x)+(p0.y-p1.y)*(p0.y-p1.y))
            R2 = ee0 * ee1 * ee2 / (4.0 * a2) if a2 > 0 else 0
            if R2 > 0:
                inc_r.append(min(R2, bb_diag))
        if inc_r:
            inc_r.sort()
            med_r = inc_r[len(inc_r) // 2]
            bg_size[vi] = min(bg_size[vi], med_r)

    # Pass 1: background mesh estimate from CDT triangles
    alpha = math.sqrt(3.0) / 4.0
    pi_over_alpha = math.pi / alpha
    cos_min_angle = math.cos(min_ang_val * math.pi / 180.0)

    est_background = 0.0
    n_cdt = 0
    n_bad_cdt = 0
    total_area = 0.0
    for i in range(nt):
        t = mesh.triangles[i]
        if t.v[0] < 0:
            continue
        n_cdt += 1
        p0, p1, p2 = mesh.vertices[t.v[0]], mesh.vertices[t.v[1]], mesh.vertices[t.v[2]]
        area = tri_area(p0, p1, p2)
        total_area += area
        H = (bg_size[t.v[0]] + bg_size[t.v[1]] + bg_size[t.v[2]]) / 3.0
        bg_est = area / (alpha * H * H)
        # Check for bad angle
        e0 = math.sqrt((p1.x-p2.x)*(p1.x-p2.x)+(p1.y-p2.y)*(p1.y-p2.y))
        e1 = math.sqrt((p0.x-p2.x)*(p0.x-p2.x)+(p0.y-p2.y)*(p0.y-p2.y))
        e2 = math.sqrt((p0.x-p1.x)*(p0.x-p1.x)+(p0.y-p1.y)*(p0.y-p1.y))
        cos_a0 = (e1*e1 + e2*e2 - e0*e0) / (2*e1*e2 + 1e-30)
        cos_a1 = (e0*e0 + e2*e2 - e1*e1) / (2*e0*e2 + 1e-30)
        cos_a2 = (e0*e0 + e1*e1 - e2*e2) / (2*e0*e1 + 1e-30)
        cos_max = max(cos_a0, cos_a1, cos_a2)
        is_bad = cos_max > cos_min_angle
        if is_bad:
            n_bad_cdt += 1
        # Angle-area interaction: 1.7x when area dominates on bad triangles
        if is_bad and bg_est > 6.0:
            est_background += bg_est * 1.7
        else:
            est_background += max(bg_est, 6.0)

    # Pass 2: refinement seed contributions (circle-of-influence model)
    est_seeds = 0.0
    n_seeds = 0
    for vi in range(nv):
        h = lfs[vi]
        H = bg_size[vi]
        if h >= 1e29 or h >= H * 0.5:
            continue
        n_seeds += 1
        ratio = H / h
        log_r = math.log(ratio)
        # Correction: Ruppert's geometric grading creates quadratically more
        # triangles than the linear grading model at high H/h ratios.
        seed_contrib = pi_over_alpha * (1.0 + 2.0 * log_r) * max(1.0, log_r)
        seed_contrib -= pi_over_alpha  # subtract background already counted
        if seed_contrib > 0:
            est_seeds += seed_contrib

    # Pass 3: segment LFS contributions
    # A segment with LFS constraint h generates a grading band on both sides.
    # Theoretical integral (linear grading) telescopes to 2*L/(alpha*h), but
    # Ruppert's geometric grading is ~3x denser, giving 6*L/(alpha*h).
    # NOTE: this assumes grading on both sides (interior segment).  Boundary
    # segments only grade on one side, so this overestimates by ~2x for them.
    # Conservative is fine for a safety cap; if a tighter estimate is ever
    # needed, halve the contribution for boundary segments (those with only
    # one incident triangle on the constrained edge).
    est_seg_lfs = 0
    for s in mesh.segments:
        if s.lfs <= 0:
            continue
        Ldx = mesh.vertices[s.v1].x - mesh.vertices[s.v0].x
        Ldy = mesh.vertices[s.v1].y - mesh.vertices[s.v0].y
        L = math.sqrt(Ldx*Ldx + Ldy*Ldy)
        est_seg_lfs += 6.0 * L / (alpha * s.lfs)

    est_total_tris = est_background + est_seeds + est_seg_lfs
    max_steiner = max(10000, int(est_total_tris * 5.0))
    if not opts.quiet:
        sys.stderr.write(f"  CDT: {n_cdt} tris ({n_bad_cdt} bad), area={total_area:.6g}, seeds: {n_seeds}\n")
        sys.stderr.write(f"  Est triangles: {int(est_total_tris)}, Steiner limit: {max_steiner}\n")
    steiner_count = [0]  # use list for mutability in closures

    constrained_edges = set()
    for s in mesh.segments:
        constrained_edges.add(edge_key(s.v0, s.v1))

    # Detect acute apices and initialize shell tracking (concentric shells)
    acute_apices = set()
    vert_segs = {}
    for si in range(len(mesh.segments)):
        for v in (mesh.segments[si].v0, mesh.segments[si].v1):
            vert_segs.setdefault(v, []).append(si)
    for vi, slist in vert_segs.items():
        if vi >= n_input_verts or len(slist) < 2:
            continue
        for i in range(len(slist)):
            for j in range(i + 1, len(slist)):
                oi = mesh.segments[slist[i]].v1 if mesh.segments[slist[i]].v0 == vi else mesh.segments[slist[i]].v0
                oj = mesh.segments[slist[j]].v1 if mesh.segments[slist[j]].v0 == vi else mesh.segments[slist[j]].v0
                dix = mesh.vertices[oi].x - mesh.vertices[vi].x
                diy = mesh.vertices[oi].y - mesh.vertices[vi].y
                djx = mesh.vertices[oj].x - mesh.vertices[vi].x
                djy = mesh.vertices[oj].y - mesh.vertices[vi].y
                dot = dix * djx + diy * djy
                cross = dix * djy - diy * djx
                if dot > 0 and abs(cross) < dot * 1.15:  # angle < ~60°
                    acute_apices.add(vi)
    shell_apex = [-1] * len(mesh.vertices)

    gxmin -= 1
    gymin -= 1
    gxmax += 1
    gymax += 1
    # Size the grid so each cell holds ~O(1) segments at the final mesh density,
    # not a fixed 50x50.  Estimate final segment count = (boundary length)/h,
    # h = sqrt(domArea/estTotalTris); target ~sqrt(estSegs) cells/side.  Floor 50
    # keeps low-segment meshes from over-building; cap 700 bounds memory.
    g_target = 50
    b_len = 0.0
    for s in mesh.segments:
        sa, sb = mesh.vertices[s.v0], mesh.vertices[s.v1]
        b_len += math.sqrt((sb.x - sa.x) ** 2 + (sb.y - sa.y) ** 2)
    dom_a = (gxmax - gxmin) * (gymax - gymin)
    h = math.sqrt(dom_a / max(1.0, est_total_tris))
    est_segs = b_len / h if h > 0 else 0.0
    g = int(math.sqrt(max(1.0, est_segs)))
    if g > g_target:
        g_target = g
    if g_target > 700:
        g_target = 700
    g_nx, g_ny = g_target, g_target
    gcell = max((gxmax - gxmin) / g_nx, (gymax - gymin) / g_ny)
    g_nx = int((gxmax - gxmin) / gcell) + 1
    g_ny = int((gymax - gymin) / gcell) + 1

    seg_grid = {}

    def grid_add_seg(si):
        s = mesh.segments[si]
        sa, sb = mesh.vertices[s.v0], mesh.vertices[s.v1]
        mx, my = (sa.x + sb.x) * 0.5, (sa.y + sb.y) * 0.5
        r = math.sqrt((sb.x-sa.x)*(sb.x-sa.x)+(sb.y-sa.y)*(sb.y-sa.y)) * 0.5
        cx0 = max(0, int((mx - r - gxmin) / gcell))
        cy0 = max(0, int((my - r - gymin) / gcell))
        cx1 = min(g_nx - 1, int((mx + r - gxmin) / gcell))
        cy1 = min(g_ny - 1, int((my + r - gymin) / gcell))
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                key = cx * g_ny + cy
                seg_grid.setdefault(key, []).append(si)

    def grid_remove_seg(si):
        s = mesh.segments[si]
        sa, sb = mesh.vertices[s.v0], mesh.vertices[s.v1]
        mx, my = (sa.x + sb.x) * 0.5, (sa.y + sb.y) * 0.5
        r = math.sqrt((sb.x-sa.x)*(sb.x-sa.x)+(sb.y-sa.y)*(sb.y-sa.y)) * 0.5
        cx0 = max(0, int((mx - r - gxmin) / gcell))
        cy0 = max(0, int((my - r - gymin) / gcell))
        cx1 = min(g_nx - 1, int((mx + r - gxmin) / gcell))
        cy1 = min(g_ny - 1, int((my + r - gymin) / gcell))
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                key = cx * g_ny + cy
                if key in seg_grid:
                    lst = seg_grid[key]
                    if si in lst:
                        lst.remove(si)

    # edge_to_seg map: edge_key -> segment index (for PBC partner lookup)
    edge_to_seg = {}
    for si in range(len(mesh.segments)):
        grid_add_seg(si)
        edge_to_seg[edge_key(mesh.segments[si].v0, mesh.segments[si].v1)] = si

    # Vertex -> constrained-subsegment neighbor vertices, maintained across
    # splits. Used by the corner-aligned split rule (split_fraction) below.
    seg_adj = [[] for _ in range(len(mesh.vertices))]
    for s in mesh.segments:
        seg_adj[s.v0].append(s.v1)
        seg_adj[s.v1].append(s.v0)

    def split_fraction(si):
        """Corner-aligned split position (anti-resonance rule).

        Pure midpoint splitting pins the innermost subsegment lengths of a
        corner's two arms to L1/2^k and L2/2^j: their folded ratio is fixed by
        the input, and the wedge triangle between the innermost rungs is
        self-similar under halving with an invariant min angle f(theta, ratio).
        If the quality bound exceeds that invariant and the corner angle is near
        ~100 deg (where the encroach-split ping-pong sustains), refinement
        cascades to the FP floor (MotorB tooth roots: theta=97.757, ratio 5.694
        -> invariant 32.77 deg; see corner_lab.py).

        Cure: when an endpoint is an input-vertex corner in the (88,108)-deg
        window and the folded-invariant wedge violates the bound, snap the split
        so this arm's corner-incident length equals the neighbor arm's innermost
        length (times a power of two, whichever lands in [1/3, 2/3]). Aligned
        arms make the wedge isoceles (min angle >= (180-theta)/2) so the
        resonance cannot form. Everywhere else: exact midpoint.
        """
        if min_ang_val <= 0.0:
            return 0.5   # no angle bound -> no resonance possible
        seg = mesh.segments[si]
        sa, sb = mesh.vertices[seg.v0], mesh.vertices[seg.v1]
        sx, sy = sb.x - sa.x, sb.y - sa.y
        l2seg = sx * sx + sy * sy
        if l2seg <= 0.0:
            return 0.5
        t, best_d = 0.5, 1e9
        for side in range(2):
            e = seg.v1 if side else seg.v0
            far = seg.v0 if side else seg.v1
            if e >= len(seg_adj):
                continue
            pe, pf = mesh.vertices[e], mesh.vertices[far]
            dx, dy = pf.x - pe.x, pf.y - pe.y
            for n in seg_adj[e]:
                if n == far:
                    continue
                pn = mesh.vertices[n]
                ox, oy = pn.x - pe.x, pn.y - pe.y
                r2 = ox * ox + oy * oy
                if r2 <= 0.0:
                    continue
                dot = dx * ox + dy * oy
                co = dot / math.sqrt(l2seg * r2)   # cos(corner angle theta)
                # THE guard: snap iff it flips the corner's limit state from
                # failing the bound to meeting it. Midpoint dynamics converge to
                # the folded-ratio wedge; snap dynamics converge to the aligned
                # isoceles wedge (min angle min(theta, (180-theta)/2)).
                # (a) The ALIGNED attractor must MEET the bound:
                #     min_ang <= theta <= 180 - 2*min_ang. This rejects acute
                #     corners (snapping cannot help; shell/give-up territory) and
                #     near-collinear junctions (arc-chord chains and every
                #     Steiner chain vertex), where aligning is meaningless.
                if co > cos_min_ang:                                  # theta < min_ang
                    continue
                if co < 1.0 - 2.0 * cos_min_ang * cos_min_ang:       # theta > 180-2*min_ang
                    continue
                # (b) The MIDPOINT attractor must FAIL the bound: fold the
                #     midpoint ratio (L/2)/r by octaves into [1/sqrt2, sqrt2)
                #     and test the invariant wedge (sides 1 and rho at theta).
                #     Transiently-bad-but-convergent states stay midpoint.
                rho = 0.5 * math.sqrt(l2seg / r2)
                while rho < 0.70710678118654752:
                    rho *= 2.0
                while rho >= 1.4142135623730951:
                    rho *= 0.5
                c2 = 1.0 + rho * rho - 2.0 * rho * co
                if c2 > 0.0:
                    c = math.sqrt(c2)
                    cos_a = (1.0 + c2 - rho * rho) / (2.0 * c)          # opposite rho
                    cos_b = (rho * rho + c2 - 1.0) / (2.0 * rho * c)    # opposite 1
                    if co <= cos_min_ang and cos_a <= cos_min_ang and cos_b <= cos_min_ang:
                        continue   # invariant wedge meets the bound: no snap
                f = math.sqrt(r2 / l2seg)   # neighbor arm length / this length
                for cand in (0.5 * f, f, 2.0 * f):
                    if cand < 1.0 / 3.0 or cand > 2.0 / 3.0:
                        continue
                    d = abs(cand - 0.5)
                    if d < best_d:
                        best_d = d
                        t = 1.0 - cand if side else cand
        return t

    def split_segment_core(si, out_affected, hint_tri=-1, t_frac=-1.0):
        """Split segment (corner-aligned fraction, or forced t_frac for PBC
        partner sync). Returns split-point index or -1 on failure."""
        seg = Segment(mesh.segments[si].v0, mesh.segments[si].v1,
                      mesh.segments[si].marker, mesh.segments[si].lfs,
                      mesh.segments[si].pbc_type, mesh.segments[si].no_split,
                      mesh.segments[si].pbc_side)
        sa, sb = mesh.vertices[seg.v0], mesh.vertices[seg.v1]
        t = t_frac if 0.0 < t_frac < 1.0 else split_fraction(si)
        mx, my = sa.x + (sb.x - sa.x) * t, sa.y + (sb.y - sa.y) * t
        mid = Point(mx, my, len(mesh.vertices), seg.marker, [], seg.lfs)

        ek = edge_key(seg.v0, seg.v1)
        constrained_edges.discard(ek)
        edge_to_seg.pop(ek, None)
        grid_remove_seg(si)

        mid_idx = insert_point_lawson(mesh, mid, hint_tri, constrained_edges, out_affected)
        if mid_idx < 0:
            constrained_edges.add(ek)
            edge_to_seg[ek] = si
            grid_add_seg(si)
            return -1
        steiner_count[0] += 1
        # Propagate shell membership for acute-angle wedge tracking
        while len(shell_apex) <= mid_idx:
            shell_apex.append(-1)
        a0 = seg.v0 if seg.v0 < n_input_verts else shell_apex[seg.v0]
        a1 = seg.v1 if seg.v1 < n_input_verts else shell_apex[seg.v1]
        if a0 >= 0 and a0 in acute_apices:
            shell_apex[mid_idx] = a0
        elif a1 >= 0 and a1 in acute_apices:
            shell_apex[mid_idx] = a1
        # Maintain the constrained-neighbor adjacency for split_fraction.
        while len(seg_adj) < len(mesh.vertices):
            seg_adj.append([])
        seg_adj[seg.v0] = [mid_idx if nb == seg.v1 else nb for nb in seg_adj[seg.v0]]
        seg_adj[seg.v1] = [mid_idx if nb == seg.v0 else nb for nb in seg_adj[seg.v1]]
        seg_adj[mid_idx] = [seg.v0, seg.v1]
        s1 = Segment(seg.v0, mid_idx, seg.marker, seg.lfs, seg.pbc_type, seg.no_split, seg.pbc_side)
        s2 = Segment(mid_idx, seg.v1, seg.marker, seg.lfs, seg.pbc_type, seg.no_split, seg.pbc_side)
        mesh.segments[si] = s1
        new_si = len(mesh.segments)
        mesh.segments.append(s2)
        ek1 = edge_key(s1.v0, s1.v1)
        ek2 = edge_key(s2.v0, s2.v1)
        constrained_edges.add(ek1)
        constrained_edges.add(ek2)
        edge_to_seg[ek1] = si
        edge_to_seg[ek2] = new_si
        grid_add_seg(si)
        grid_add_seg(new_si)
        return mid_idx

    def split_segment(si, out_affected, hint_tri=-1):
        """Split segment; for PBC segments, also split the partner."""
        seg = mesh.segments[si]  # read before split modifies it
        pbc_type = seg.pbc_type
        sv0, sv1 = seg.v0, seg.v1
        t_used = split_fraction(si)
        mid_idx = split_segment_core(si, out_affected, hint_tri, t_used)
        if mid_idx < 0:
            return False

        # Synchronized PBC partner split
        if pbc_type >= 0:
            tv0 = mesh.pbc_twin.get(sv0, -1)
            tv1 = mesh.pbc_twin.get(sv1, -1)
            if tv0 >= 0 and tv1 >= 0:
                pek = edge_key(tv0, tv1)
                partner_si = edge_to_seg.get(pek, -1)
                if partner_si >= 0:
                    partner_affected = []
                    # Split the partner at the SAME parametric position (oriented:
                    # partner may be stored with endpoints in either order) so the
                    # periodic boundaries keep matching node positions.
                    pt = t_used if mesh.segments[partner_si].v0 == tv0 else 1.0 - t_used
                    partner_mid = split_segment_core(partner_si, partner_affected, -1, pt)
                    if partner_mid >= 0:
                        mesh.pbc_twin[mid_idx] = partner_mid
                        mesh.pbc_twin[partner_mid] = mid_idx
                        mesh.pbc_node_type[mid_idx] = pbc_type
                        mesh.pbc_node_type[partner_mid] = pbc_type
                        # Add partner-affected triangles so the caller can
                        # queue them for quality checking.
                        out_affected.extend(partner_affected)
        return True

    def find_encroached(px, py):
        gcx = max(0, min(g_nx - 1, int((px - gxmin) / gcell)))
        gcy = max(0, min(g_ny - 1, int((py - gymin) / gcell)))
        for ddx in range(-1, 2):
            for ddy in range(-1, 2):
                cx, cy = gcx + ddx, gcy + ddy
                if cx < 0 or cx >= g_nx or cy < 0 or cy >= g_ny:
                    continue
                key = cx * g_ny + cy
                if key not in seg_grid:
                    continue
                for si in seg_grid[key]:
                    s = mesh.segments[si]
                    if s.no_split:
                        continue  # AGE chords must stay uniformly spaced
                    sa, sb = mesh.vertices[s.v0], mesh.vertices[s.v1]
                    mx2, my2 = (sa.x + sb.x) * 0.5, (sa.y + sb.y) * 0.5
                    sr2 = ((sb.x-sa.x)*(sb.x-sa.x)+(sb.y-sa.y)*(sb.y-sa.y)) * 0.25
                    dd2 = (px-mx2)*(px-mx2)+(py-my2)*(py-my2)
                    if dd2 < sr2:
                        return si
        return -1

    def walk_blocked(start_tri, px, py):
        """Walk straight from start_tri toward (px,py); return the segment index
        of the first CONSTRAINED edge the walk must cross (the candidate is
        hidden behind it and encroaches it, even one outside the domain), -1 if
        the point is reachable (visible), or -2 if the walk fails structurally
        (drop the candidate).  Without this, blocked candidates fail insertion
        and their bad triangles are silently dropped (e.g. a vertex a few microns
        off a constrained segment left a 0.107-degree sliver untouched)."""
        ti = start_tri
        for _ in range(len(mesh.triangles)):
            if ti < 0 or ti >= len(mesh.triangles):
                return -2
            t = mesh.triangles[ti]
            if t.v[0] < 0:
                return -2
            exit_edge = -1
            for j in range(3):
                va = t.v[j]
                vb = t.v[(j + 1) % 3]
                if orient2d_xy(mesh.vertices[va].x, mesh.vertices[va].y,
                               mesh.vertices[vb].x, mesh.vertices[vb].y,
                               px, py) < 0.0:
                    exit_edge = j
                    break
            if exit_edge < 0:
                return -1  # point inside (or on boundary of) ti: visible
            va = t.v[exit_edge]
            vb = t.v[(exit_edge + 1) % 3]
            if edge_key(va, vb) in constrained_edges:
                return edge_to_seg.get(edge_key(va, vb), -2)
            ti = t.neighbors[exit_edge]
            if ti < 0:
                return -2  # unconstrained hull edge (shouldn't happen in a PSLG)
        return -2

    # Priority queue (min-heap): order by SHORTEST EDGE first = smallest squared
    # edge length, the order under which off-center insertion guarantees growth
    # (Ungor).  Tuple = (key, idx, generation, retry).  (A scale-gated switch to
    # worst-angle ordering for tiny triangles used to live here; with the
    # circumcenter test below made scale-free it is unnecessary and actively
    # harmful -- it broke the smallest-first growth guarantee and carpeted
    # sub-tiny features at -q33.)
    REQUEUE_CAP = 4     # capped badIdx re-queue after an encroachment split
    GUARD_FACTOR = 0.5  # too-close-insertion guard: reject radius factor

    def prio_key(mr):
        return min(mr[5], mr[6], mr[7])  # shortest squared edge

    pq = []
    for i in range(len(mesh.triangles)):
        mr = tri_metric(mesh, i, min_ang_val, global_max_a, use_region_area, cos_min_ang)
        if mr[0] > 0:
            heappush(pq, (prio_key(mr), i, mesh.triangles[i].generation, 0))

    # Precompute off-center constant (loop-invariant)
    offconst = (0.475 * math.sqrt(
        (1.0 + math.cos(min_ang_val * math.pi / 180.0)) /
        (1.0 - math.cos(min_ang_val * math.pi / 180.0)))) if min_ang_val > 0 else 0

    dbg_encroach = dbg_insert = dbg_skip = dbg_fail = 0

    iterations = 0
    while pq and steiner_count[0] < max_steiner:
        iterations += 1
        if iterations > mesh.max_vertices * 20:
            raise ValueError("Cutout mesh refinement limit exceeded")
        _prio, bad_idx, gen, retry = heappop(pq)

        if bad_idx >= len(mesh.triangles):
            continue
        bt = mesh.triangles[bad_idx]
        if bt.v[0] < 0:
            continue
        if bt.generation != gen:
            continue
        tmr = tri_metric(mesh, bad_idx, min_ang_val, global_max_a, use_region_area, cos_min_ang)
        if tmr[0] <= 0:
            continue
        ang_viol, area_viol, area, _ = tmr[1], tmr[2], tmr[3], tmr[4]
        tmr_la2, tmr_lb2, tmr_lc2 = tmr[5], tmr[6], tmr[7]

        a = mesh.vertices[bt.v[0]]
        b = mesh.vertices[bt.v[1]]
        c = mesh.vertices[bt.v[2]]

        # Skip if both edges at smallest-angle vertex are segments
        if ang_viol and not area_viol:
            # Find vertex with smallest angle = vertex opposite the shortest edge
            # Use cached squared edge lengths from tri_metric
            la2, lb2, lc2 = tmr_la2, tmr_lb2, tmr_lc2
            min_v = 0  # opposite la (edge b-c)
            if lb2 < la2 and lb2 < lc2:
                min_v = 1  # opposite lb (edge a-c)
            elif lc2 < la2:
                min_v = 2  # opposite lc (edge a-b)
            va = bt.v[min_v]
            vb_v = bt.v[(min_v + 1) % 3]
            vc_v = bt.v[(min_v + 2) % 3]
            if (edge_key(va, vb_v) in constrained_edges and
                edge_key(va, vc_v) in constrained_edges):
                dbg_skip += 1
                continue
            # Check if worst-angle vertex is inside a small-angle shell.
            # Only skip if at least one edge at the vertex is constrained —
            # this limits suppression to triangles directly on the shell boundary.
            if va < len(shell_apex) and shell_apex[va] >= 0:
                if (edge_key(va, vb_v) in constrained_edges or
                    edge_key(va, vc_v) in constrained_edges):
                    dbg_skip += 1
                    continue
            # For tiny triangles (all edges < bb_diag * 1e-9, i.e. at the floor
            # where coordinates have ~7 ULPs of room left), accept a reduced
            # minimum angle.  This engages only for EXACTLY (or near-exactly)
            # coincident input geometry that splitting cannot resolve -- anything
            # with a representable gap is refined to full quality instead.
            tiny_len2 = bb_diag * 1e-9
            tiny_len2 *= tiny_len2
            if la2 < tiny_len2 and lb2 < tiny_len2 and lc2 < tiny_len2:
                ang = min_angle(a, b, c)
                if ang >= min(min_ang_val, TINY_TRI_ANGLE):
                    dbg_skip += 1
                    continue

        # Compute circumcenter or off-center
        if ang_viol:
            # Inline circumcenter using cached values from tri_metric
            xdo, ydo = b.x - a.x, b.y - a.y
            xao, yao = c.x - a.x, c.y - a.y
            D = 2.0 * (xdo * yao - ydo * xao)
            # Degenerate-circumcenter fallback must be SCALE-FREE: D scales like
            # edge^2, so an absolute EPS classified every triangle below ~sqrt(EPS)
            # as degenerate and inserted its centroid -> guaranteed insertion-radius
            # descent (a carpet) once refinement reaches small scales.
            d_mag = abs(xdo * yao) + abs(ydo * xao)
            if abs(D) < 1e-12 * d_mag or d_mag == 0.0:
                tcx, tcy = (a.x + b.x + c.x) / 3.0, (a.y + b.y + c.y) / 3.0
            else:
                # dodist=xdo²+ydo²=lc2, aodist=xao²+yao²=lb2 (from tri_metric)
                dodist_cc, aodist_cc = tmr_lc2, tmr_lb2
                tcx = a.x + (yao * dodist_cc - ydo * aodist_cc) / D
                tcy = a.y + (xdo * aodist_cc - xao * dodist_cc) / D
            dodist, aodist, dadist = tmr_lc2, tmr_lb2, tmr_la2
            ddx_cc, ddy_cc = tcx - a.x, tcy - a.y
            if dodist < aodist and dodist < dadist:
                dxoff = 0.5 * xdo - offconst * ydo
                dyoff = 0.5 * ydo + offconst * xdo
                if dxoff * dxoff + dyoff * dyoff < ddx_cc * ddx_cc + ddy_cc * ddy_cc:
                    tcx, tcy = a.x + dxoff, a.y + dyoff
            elif aodist < dadist:
                dxoff = 0.5 * xao + offconst * yao
                dyoff = 0.5 * yao - offconst * xao
                if dxoff * dxoff + dyoff * dyoff < ddx_cc * ddx_cc + ddy_cc * ddy_cc:
                    tcx, tcy = a.x + dxoff, a.y + dyoff
            else:
                dxoff = 0.5 * (c.x - b.x) - offconst * (c.y - b.y)
                dyoff = 0.5 * (c.y - b.y) + offconst * (c.x - b.x)
                if (dxoff * dxoff + dyoff * dyoff <
                    (ddx_cc - xdo) ** 2 + (ddy_cc - ydo) ** 2):
                    tcx, tcy = b.x + dxoff, b.y + dyoff
        else:
            tcx = (a.x + b.x + c.x) / 3.0
            tcy = (a.y + b.y + c.y) / 3.0

        # Pre-insertion encroachment check: if the circumcenter/off-center
        # encroaches a segment, or is hidden from its bad triangle behind a
        # constrained edge (walk-blocked, which also covers candidates outside
        # the domain), split that segment instead of inserting the point.
        enc_seg = find_encroached(tcx, tcy)
        if enc_seg < 0:
            blk = walk_blocked(bad_idx, tcx, tcy)
            if blk == -2:
                dbg_fail += 1
                continue
            if blk >= 0:
                if mesh.segments[blk].no_split:
                    dbg_skip += 1
                    continue
                enc_seg = blk
        if enc_seg >= 0 and opts.no_steiner and mesh.segments[enc_seg].marker != 0:
            continue
        if enc_seg >= 0:
            seg_aff = []
            if split_segment(enc_seg, seg_aff, bad_idx):
                dbg_encroach += 1
                # Triangles modified by the split are re-queued fresh (retry=0)
                # via seg_aff below.  If badIdx was NOT among them, the split left
                # it unchanged but may have removed the segment its circumcenter
                # encroached, making it fixable — so re-queue it too with an
                # incremented retry.  The cap stops the apex cascade.
                if (bad_idx not in seg_aff and retry + 1 < REQUEUE_CAP and
                        bad_idx < len(mesh.triangles) and
                        mesh.triangles[bad_idx].v[0] >= 0):
                    mrb = tri_metric(mesh, bad_idx, min_ang_val, global_max_a,
                                     use_region_area, cos_min_ang)
                    if mrb[0] > 0:
                        heappush(pq, (prio_key(mrb), bad_idx,
                                      mesh.triangles[bad_idx].generation, retry + 1))
                for ti2 in seg_aff:
                    if 0 <= ti2 < len(mesh.triangles) and mesh.triangles[ti2].v[0] >= 0:
                        mr2 = tri_metric(mesh, ti2, min_ang_val, global_max_a,
                                         use_region_area, cos_min_ang)
                        if mr2[0] > 0:
                            heappush(pq, (prio_key(mr2), ti2,
                                          mesh.triangles[ti2].generation, 0))
                        for k in range(3):
                            nb = mesh.triangles[ti2].neighbors[k]
                            if nb >= 0:
                                mr2 = tri_metric(mesh, nb, min_ang_val, global_max_a,
                                                 use_region_area, cos_min_ang)
                                if mr2[0] > 0:
                                    heappush(pq, (prio_key(mr2), nb,
                                                  mesh.triangles[nb].generation, 0))
            continue

        # Insert, with the too-close guard: reject an off-center/circumcenter
        # that would land within (GUARD_FACTOR * shortest edge of the bad
        # triangle) of an existing vertex.
        min_edge2 = min(tmr_la2, tmr_lb2, tmr_lc2)
        guard_dist2 = GUARD_FACTOR * GUARD_FACTOR * min_edge2
        np_pt = Point(tcx, tcy, len(mesh.vertices), 0)
        affected = []
        new_pt = insert_point_lawson(mesh, np_pt, bad_idx, constrained_edges,
                                     affected, guard_dist2)
        if new_pt < 0:
            # No -2 vertex-coincident fallback: with the walk-blocked
            # encroachment check above and the CDT empty-circumcircle property,
            # the circumcenter is at least one circumradius from every visible
            # vertex; a refused insertion just tolerates the bad triangle.
            dbg_fail += 1
            continue

        steiner_count[0] += 1
        dbg_insert += 1

        # Re-check only the affected triangles.  insert_point_lawson records every
        # modified triangle (split products + all flips) in `affected`, and a
        # triangle's metric depends only on its own 3 vertices, so unmodified
        # neighbors cannot have changed status — no neighbor sweep needed.
        for ti in sorted(set(affected)):
            if 0 <= ti < len(mesh.triangles):
                mr = tri_metric(mesh, ti, min_ang_val, global_max_a, use_region_area, cos_min_ang)
                if mr[0] > 0:
                    heappush(pq, (prio_key(mr), ti, mesh.triangles[ti].generation, 0))

    if pq:
        raise ValueError("Cutout mesh refinement limit exceeded")
    if not opts.quiet:
        print(f"Quality refinement: {dbg_insert} Steiner points, "
              f"{dbg_encroach} segment splits, {dbg_skip} skipped, "
              f"{dbg_fail} failed insertions", file=sys.stderr)


# ============================================================
# Edge extraction
# ============================================================


def build_mesh(points, segments, holes, max_area, *, max_vertices=50000):
    """Build a constrained mesh in memory, preserving segment markers."""
    global EPS
    if len(points) < 3 or len(points) > max_vertices:
        raise ValueError("Cutout mesh input exceeds vertex limits")
    if not math.isfinite(max_area) or max_area <= 0:
        raise ValueError("Cutout mesh area must be positive")
    if any(not math.isfinite(v) for p in points for v in p):
        raise ValueError("Cutout mesh coordinates must be finite")
    if any(a == b or min(a, b) < 0 or max(a, b) >= len(points) for a, b, _ in segments):
        raise ValueError("Cutout mesh segment is invalid")
    shift_x = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    shift_y = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
    mesh = Mesh()
    mesh.max_vertices = max_vertices
    mesh.vertices = [Point(x-shift_x, y-shift_y, i) for i, (x, y) in enumerate(points)]
    mesh.segments = [Segment(a, b, marker) for a, b, marker in segments]
    mesh.holes = [Hole(x-shift_x, y-shift_y) for x, y in holes]
    opts = Options(pslg=True, quality=True, min_angle=10., area_limit=True, max_area=max_area, quiet=True)
    with _CALL_LOCK, localcontext() as context:
        context.prec = 80
        previous_epsilon = EPS
        try:
            clean_pslg(mesh, -2.0, True)
            for attempt in range(11):
                if len(mesh.vertices) > max_vertices:
                    raise ValueError("Cutout mesh vertex limit exceeded")
                mesh.triangles.clear()
                build_delaunay(mesh)
                mesh.rebuild_adjacency()
                missing = enforce_constraints(mesh, True)
                if not missing:
                    break
                if attempt == 10:
                    raise ValueError("Cutout mesh could not enforce its constraints")
                users = [[] for _ in mesh.vertices]
                for i, triangle in enumerate(mesh.triangles):
                    if triangle.v[0] >= 0:
                        for v in triangle.v:
                            users[v].append(i)
                for i in range(len(mesh.segments)-1, -1, -1):
                    segment = mesh.segments[i]
                    if mesh.has_edge(segment.v0, segment.v1, users):
                        continue
                    a, b = mesh.vertices[segment.v0], mesh.vertices[segment.v1]
                    index = len(mesh.vertices)
                    mesh.vertices.append(Point((a.x+b.x)/2, (a.y+b.y)/2, index))
                    mesh.segments[i:i+1] = [Segment(segment.v0, index, segment.marker), Segment(index, segment.v1, segment.marker)]
            remove_holes(mesh, opts)
            if not mesh.triangles:
                raise ValueError("Cutout mesh encloses no area")
            refine_quality(mesh, opts, len(mesh.vertices))
        finally:
            EPS = previous_epsilon
    return (
        [(p.x+shift_x, p.y+shift_y) for p in mesh.vertices],
        [t.v for t in mesh.triangles if t.v[0] >= 0],
        [(s.v0, s.v1, s.marker) for s in mesh.segments],
    )
