import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "trace_silhouette", pathlib.Path(__file__).parent.parent / "tools" / "trace_silhouette.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


def grid(rows):
    return [[ch == "#" for ch in row] for row in rows]


def test_trace_walks_the_outer_boundary_clockwise():
    mask = grid(["......",
                 ".###..",
                 ".####.",
                 ".###..",
                 "......"])
    pts = ts.trace(mask)
    assert pts[0] == (1, 1) and pts[1] == (2, 1)            # starts top-left, goes right first (clockwise)
    assert set(pts) == {(1, 1), (2, 1), (3, 1), (4, 2), (3, 3), (2, 3), (1, 3), (1, 2)}


def test_trace_edge_cases():
    assert ts.trace(grid(["...", "..."])) == []
    assert ts.trace(grid(["...", ".#.", "..."])) == [(1, 1)]


def test_outline_simplifies_and_scales():
    mask = [[True] * 20 for _ in range(10)]                 # 20x10 rectangle -> its 4 corners
    pts = ts.outline(mask, 40, 0.5)
    assert sorted(pts) == [(0, 0), (0, 18), (38, 0), (38, 18)]
