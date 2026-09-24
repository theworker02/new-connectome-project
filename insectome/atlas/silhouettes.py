"""2D skeleton silhouettes for visual neuron browsing."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from insectome.atlas.skeletons import line_segments, read_skeleton_bin
from insectome.connectome.store import ConnectomeStore


def _project_xy(segs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return Nx2 endpoints flattened as polyline pairs in XY (drop Z)."""
    if segs.size == 0:
        return np.zeros((0, 2)), np.zeros((0, 2))
    a = segs[:, 0:2]
    b = segs[:, 3:5]
    return a, b


def segments_to_svg(
    segs: np.ndarray,
    *,
    size: int = 120,
    stroke: str = "#4fd4b0",
    stroke_width: float = 1.35,
    pad: float = 0.08,
) -> str:
    """Orthographic XY silhouette as a compact SVG string."""
    if segs is None or len(segs) == 0:
        return _empty_svg(size)
    a, b = _project_xy(np.asarray(segs, dtype=np.float64).reshape(-1, 6))
    pts = np.vstack([a, b])
    lo = pts.min(axis=0)
    hi = pts.max(axis=0)
    span = np.maximum(hi - lo, 1e-6)
    scale = (1.0 - 2 * pad) * size / float(span.max())
    # center in square
    mid = (lo + hi) / 2.0
    origin = size / 2.0

    def tx(x: float, y: float) -> tuple[float, float]:
        return (origin + (x - mid[0]) * scale, origin - (y - mid[1]) * scale)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">',
        f'<rect width="100%" height="100%" fill="#0a1410"/>',
    ]
    # subsample long skeletons for thumbnail weight
    step = max(1, len(a) // 400)
    for i in range(0, len(a), step):
        x1, y1 = tx(float(a[i, 0]), float(a[i, 1]))
        x2, y2 = tx(float(b[i, 0]), float(b[i, 1]))
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" stroke-linecap="round"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _empty_svg(size: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f'<rect width="100%" height="100%" fill="#0a1410"/>'
        f'<circle cx="{size/2}" cy="{size/2}" r="6" fill="#24352e"/>'
        f"</svg>"
    )


def _skeleton_path(store: ConnectomeStore, source_id: int) -> Path | None:
    sk = store.dir / "skeletons"
    for name in (f"{source_id}.lod.skbin", f"{source_id}.skbin"):
        p = sk / name
        if p.exists():
            return p
    return None


@lru_cache(maxsize=4096)
def silhouette_svg(connectome_id: str, source_id: int, size: int = 120) -> str | None:
    store = ConnectomeStore(connectome_id)
    path = _skeleton_path(store, source_id)
    if path is None:
        return None
    verts, links, _meta = read_skeleton_bin(path)
    segs = line_segments(verts, links)
    return segments_to_svg(segs, size=size)


def batch_silhouettes(
    connectome_id: str,
    *,
    limit: int = 120,
    size: int = 96,
    source_ids: list[int] | None = None,
) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    from insectome.atlas.service import load_index

    index = load_index(connectome_id)
    if source_ids:
        want = set(int(x) for x in source_ids)
        rows = index[index["source_id"].astype(int).isin(want)]
    else:
        if "has_skeleton" in index.columns:
            rows = index[index["has_skeleton"] == True]  # noqa: E712
        else:
            rows = index
        rows = rows.head(limit)

    out: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        sid = int(row["source_id"])
        svg = silhouette_svg(connectome_id, sid, size=size)
        if not svg:
            continue
        out.append(
            {
                "source_id": sid,
                "name": row.get("name"),
                "cell_type": row.get("cell_type"),
                "svg": svg,
            }
        )
    return {"connectome_id": connectome_id, "count": len(out), "silhouettes": out}
