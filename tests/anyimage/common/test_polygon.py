"""Verify scanline preview coverage and active-edge work bounds."""

import math
import random

import pytest

from anyimage.common import polygon


@pytest.mark.parametrize("step", (0.5, 2.0, 7.0))
def test_active_edges_match_full_scan_with_crossings_and_repeated_vertices(step):
    randomizer = random.Random(42)
    paths = [
        ((0, 0), (4, 4), (0, 4), (4, 0)),
        ((0, 0), (4, 0), (4, 4), (0, 4), (0, 0)) * 2,
        ((0, 0), (4, 0), (4, 1), (0, 1), (0, 0), (0, 0)),
        tuple((randomizer.uniform(-100, 100), randomizer.uniform(-100, 100))
              for _ in range(80)),
    ]
    for path in paths:
        edges = tuple(zip(path, (*path[1:], path[0])))
        for bottom, top, intervals in polygon.scanline_fill_bands(path, step):
            assert intervals == polygon._scanline_intervals(edges, (bottom + top) / 2)


def test_preview_scan_visits_only_edges_crossing_the_row(monkeypatch):
    path = tuple((900 * math.cos(i * math.tau / 800),
                  500 * math.sin(i * math.tau / 800)) for i in range(800))
    original = polygon._scanline_intervals
    visited = []

    def scan(edges, sample_y):
        visited.append(len(edges))
        return original(edges, sample_y)

    monkeypatch.setattr(polygon, "_scanline_intervals", scan)
    bands = polygon.scanline_fill_bands(path)

    assert len(bands) == 500
    assert visited == [2] * 500
    assert all(len(intervals) == 1 for _, _, intervals in bands)
