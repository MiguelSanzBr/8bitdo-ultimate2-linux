"""Trace the outline of a controller picture into a polygon for ``gui/geometry.py``.

Only the alpha channel is used (the shape of the product), never colours or artwork, and the picture is read from a
local path given on the command line: nothing from it is copied into the repository except the printed coordinates.

    python3 tools/trace_silhouette.py picture.png [--width 440] [--tolerance 1.5]
"""
import argparse

NEIGHBOURS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]   # clockwise on screen


def trace(mask):
    """Outer boundary pixels of the first shape in ``mask`` (rows of truthy values), clockwise (Moore neighbour)."""
    h, w = len(mask), len(mask[0])
    inside = lambda x, y: 0 <= x < w and 0 <= y < h and mask[y][x]
    start = next(((x, y) for y in range(h) for x in range(w) if mask[y][x]), None)
    if start is None:
        return []
    out, cur, d = [start], start, 6            # entered from the left, so start searching up
    while True:
        for k in range(8):
            nd = (d + 6 + k) % 8               # begin 90° counter-clockwise of the last move
            nx, ny = cur[0] + NEIGHBOURS[nd][0], cur[1] + NEIGHBOURS[nd][1]
            if inside(nx, ny):
                cur, d = (nx, ny), nd
                break
        else:
            return out                         # single pixel
        if cur == start:
            return out
        out.append(cur)


def simplify(pts, tol):
    """Ramer-Douglas-Peucker on a closed outline."""
    def rdp(seg):
        (ax, ay), (bx, by) = seg[0], seg[-1]
        ln = ((bx - ax) ** 2 + (by - ay) ** 2) ** .5 or 1
        far, idx = 0, 0
        for i, (px, py) in enumerate(seg[1:-1], 1):
            dist = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / ln
            if dist > far:
                far, idx = dist, i
        return rdp(seg[:idx + 1])[:-1] + rdp(seg[idx:]) if far > tol else [seg[0], seg[-1]]
    half = len(pts) // 2
    return rdp(pts[:half + 1])[:-1] + rdp(pts[half:] + pts[:1])[:-1]


def outline(mask, width, tol):
    """Simplified outline scaled so the shape is ``width`` units wide, origin at its top-left corner."""
    pts = trace(mask)
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    k = width / (max(p[0] for p in pts) - x0 + 1)
    return [(round((x - x0) * k), round((y - y0) * k)) for x, y in simplify(pts, tol / k)]


def main(argv=None):  # pragma: no cover - needs Pillow and a picture
    from PIL import Image
    ap = argparse.ArgumentParser()
    ap.add_argument("picture")
    ap.add_argument("--width", type=int, default=440)
    ap.add_argument("--tolerance", type=float, default=1.5, help="max deviation, in output units")
    a = ap.parse_args(argv)
    alpha = Image.open(a.picture).getchannel("A")
    w, h = alpha.size
    px = alpha.load()
    mask = [[px[x, y] > 128 for x in range(w)] for y in range(h)]
    print(outline(mask, a.width, a.tolerance))


if __name__ == "__main__":  # pragma: no cover
    main()
