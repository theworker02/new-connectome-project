"""Compact skeleton I/O for atlas streaming."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pandas as pd


MAGIC = b"ISK1"  # Insectome Skeleton v1


def downsample_skeleton(vertices: np.ndarray, links: np.ndarray, max_vertices: int = 800) -> tuple[np.ndarray, np.ndarray]:
    """Decimate by stride while preserving tree links approximately."""
    n = len(vertices)
    if n <= max_vertices:
        return vertices, links
    stride = int(np.ceil(n / max_vertices))
    keep = np.zeros(n, dtype=bool)
    keep[0] = True
    keep[::stride] = True
    keep[-1] = True
    # always keep roots (link < 0)
    roots = np.where(links < 0)[0]
    keep[roots] = True
    idx = np.where(keep)[0]
    old_to_new = -np.ones(n, dtype=np.int32)
    old_to_new[idx] = np.arange(len(idx), dtype=np.int32)
    new_verts = vertices[idx]
    new_links = np.empty(len(idx), dtype=np.int32)
    for ni, oi in enumerate(idx):
        parent = int(links[oi])
        while parent >= 0 and old_to_new[parent] < 0:
            parent = int(links[parent])
        new_links[ni] = -1 if parent < 0 else int(old_to_new[parent])
    return new_verts, new_links


def skeleton_from_neuprint_df(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Convert neuPrint fetch_skeleton DataFrame to vertices (N,4) and parent links (N,)."""
    # neuPrint: rowId is 1-indexed; link is parent rowId or -1
    order = df["rowId"].to_numpy()
    id_to_i = {int(r): i for i, r in enumerate(order)}
    verts = np.column_stack(
        [
            df["x"].to_numpy(dtype=np.float32),
            df["y"].to_numpy(dtype=np.float32),
            df["z"].to_numpy(dtype=np.float32),
            df["radius"].to_numpy(dtype=np.float32),
        ]
    )
    links = np.empty(len(df), dtype=np.int32)
    for i, parent_row in enumerate(df["link"].to_numpy()):
        p = int(parent_row)
        links[i] = -1 if p < 0 else id_to_i.get(p, -1)
    return verts, links


def skeleton_from_swc_text(text: str) -> tuple[np.ndarray, np.ndarray]:
    """Parse standard SWC (id type x y z radius parent) into vertices + parent links."""
    rows: list[list[float]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.replace(",", " ").split()
        if len(parts) < 7:
            continue
        try:
            rows.append(
                [
                    float(parts[0]),
                    float(parts[1]),
                    float(parts[2]),
                    float(parts[3]),
                    float(parts[4]),
                    float(parts[5]),
                    float(parts[6]),
                ]
            )
        except ValueError:
            continue
    return skeleton_from_catmaid_swc_rows(rows)


def skeleton_from_catmaid_swc_rows(rows: list) -> tuple[np.ndarray, np.ndarray]:
    """CATMAID SWC-like rows: often [id, type, x, y, z, radius, parent]."""
    if not rows:
        return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.int32)
    sample = rows[0]
    if isinstance(sample, dict):
        ids = [int(r.get("id") or r.get("node_id") or i) for i, r in enumerate(rows)]
        xs = [float(r.get("x", 0)) for r in rows]
        ys = [float(r.get("y", 0)) for r in rows]
        zs = [float(r.get("z", 0)) for r in rows]
        rs = [float(r.get("radius", r.get("r", 1.0))) for r in rows]
        parents = [int(r.get("parent_id", r.get("parent", -1))) for r in rows]
    else:
        # list/tuple SWC
        ids = [int(r[0]) for r in rows]
        xs = [float(r[2]) for r in rows]
        ys = [float(r[3]) for r in rows]
        zs = [float(r[4]) for r in rows]
        rs = [float(r[5]) if len(r) > 5 and r[5] is not None else 1.0 for r in rows]
        parents = []
        for r in rows:
            if len(r) <= 6 or r[6] is None:
                parents.append(-1)
            else:
                parents.append(int(r[6]))
    id_to_i = {i: n for n, i in enumerate(ids)}
    verts = np.column_stack([xs, ys, zs, rs]).astype(np.float32)
    links = np.array([-1 if p < 0 else id_to_i.get(p, -1) for p in parents], dtype=np.int32)
    return verts, links


def write_skeleton_bin(path: Path, vertices: np.ndarray, links: np.ndarray, meta: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    verts = np.asarray(vertices, dtype=np.float32).reshape(-1, 4)
    ln = np.asarray(links, dtype=np.int32).reshape(-1)
    assert len(verts) == len(ln)
    meta_bytes = json.dumps(meta or {}, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<II", len(verts), len(meta_bytes)))
        f.write(meta_bytes)
        f.write(verts.tobytes(order="C"))
        f.write(ln.tobytes(order="C"))


def read_skeleton_bin(path: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    with path.open("rb") as f:
        magic = f.read(4)
        if magic != MAGIC:
            raise ValueError(f"Bad skeleton magic in {path}")
        n_verts, n_meta = struct.unpack("<II", f.read(8))
        meta = json.loads(f.read(n_meta).decode("utf-8") or "{}")
        verts = np.frombuffer(f.read(n_verts * 16), dtype=np.float32).reshape(n_verts, 4).copy()
        links = np.frombuffer(f.read(n_verts * 4), dtype=np.int32).copy()
    return verts, links, meta


def skeleton_to_json(vertices: np.ndarray, links: np.ndarray, max_vertices: int = 1200) -> dict:
    v, l = downsample_skeleton(vertices, links, max_vertices=max_vertices)
    return {
        "n_vertices": int(len(v)),
        "n_original": int(len(vertices)),
        "downsampled": bool(len(v) < len(vertices)),
        "vertices": v.reshape(-1).tolist(),  # xyzr flat
        "links": l.tolist(),
    }


def line_segments(vertices: np.ndarray, links: np.ndarray) -> np.ndarray:
    """Return Nx6 array of line segment endpoints for batched rendering."""
    segs = []
    for i, p in enumerate(links):
        if p < 0:
            continue
        a = vertices[i, :3]
        b = vertices[int(p), :3]
        segs.append([a[0], a[1], a[2], b[0], b[1], b[2]])
    if not segs:
        return np.zeros((0, 6), dtype=np.float32)
    return np.asarray(segs, dtype=np.float32)
