"""Neuroglancer-compatible export (skeletons + annotations + viewer state)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from insectome.atlas.skeletons import line_segments, read_skeleton_bin
from insectome.connectome.store import ConnectomeStore
from insectome.storage.paths import project_root


def export_neuroglancer(connectome_id: str, out_dir: Path | None = None) -> Path:
    """Export LOD skeletons + annotation table + Neuroglancer state JSON.

    Full sharded precomputed volumes are out of scope until EM is granted;
    this export is skeleton/annotation oriented and hostable via static HTTP.
    """
    store = ConnectomeStore(connectome_id)
    root = out_dir or (project_root() / "data" / "neuroglancer" / connectome_id)
    sk_out = root / "skeletons"
    ann_out = root / "annotations"
    props_out = root / "properties"
    for p in (sk_out, ann_out, props_out):
        p.mkdir(parents=True, exist_ok=True)

    index_path = store.dir / "neuron_index.parquet"
    if not index_path.exists():
        raise RuntimeError(f"{connectome_id} has no neuron_index.parquet — run atlas enrich first")
    import pandas as pd

    index = pd.read_parquet(index_path)
    # Skeleton source info (simplified Neuroglancer precomputed skeleton metadata)
    sk_info = {
        "@type": "neuroglancer_skeletons",
        "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        "vertex_attributes": [{"id": "radius", "data_type": "float32", "num_components": 1}],
        "segment_properties": "properties",
    }
    (sk_out / "info").write_text(json.dumps(sk_info, indent=2), encoding="utf-8")

    props = {
        "@type": "neuroglancer_segment_properties",
        "inline": {
            "ids": [str(int(x)) for x in index["source_id"]],
            "properties": [
                {
                    "id": "label",
                    "type": "label",
                    "values": [str(x) for x in index.get("name", index["source_id"])],
                },
                {
                    "id": "cell_type",
                    "type": "label",
                    "values": [str(x) if x is not None else "" for x in index.get("cell_type", [])],
                },
            ],
        },
    }
    (props_out / "info").write_text(json.dumps(props, indent=2), encoding="utf-8")

    # Write per-segment JSON skeletons (portable; binary NG format can be added later)
    segments = []
    for _, row in index.iterrows():
        sid = int(row["source_id"])
        lod = store.dir / "skeletons" / f"{sid}.lod.skbin"
        full = store.dir / "skeletons" / f"{sid}.skbin"
        path = lod if lod.exists() else full
        if not path.exists():
            continue
        verts, links, meta = read_skeleton_bin(path)
        segs = line_segments(verts, links)
        payload = {
            "segment_id": sid,
            "global_id": row["global_id"],
            "verticesXYZR": verts.reshape(-1).tolist(),
            "links": links.tolist(),
            "line_segments": segs.reshape(-1).tolist(),
            "meta": meta,
        }
        (sk_out / f"{sid}.json").write_text(json.dumps(payload), encoding="utf-8")
        segments.append(sid)

    # Annotation points from somata
    annotations = []
    for _, row in index.iterrows():
        if pd.isna(row.get("soma_x")):
            continue
        annotations.append(
            {
                "id": str(row["global_id"]),
                "type": "point",
                "point": [float(row["soma_x"]), float(row["soma_y"]), float(row["soma_z"])],
                "props": {"source_id": int(row["source_id"]), "label": str(row.get("name") or row["source_id"])},
            }
        )
    (ann_out / "soma_annotations.json").write_text(json.dumps(annotations, indent=2), encoding="utf-8")

    man = store.read_manifest() if store.manifest_path.exists() else {}
    center = None
    if len(index) and not index["soma_x"].isna().all():
        center = [
            float(index["soma_x"].mean()),
            float(index["soma_y"].mean()),
            float(index["soma_z"].mean()),
        ]
    state = {
        "connectome_id": connectome_id,
        "title": f"Insectome — {connectome_id}",
        "dimensions": {"x": [8e-9, "m"], "y": [8e-9, "m"], "z": [8e-9, "m"]},
        "position": center,
        "layers": [
            {
                "type": "segmentation",
                "name": "neurons",
                "source": f"insectome://skeletons/{connectome_id}",
                "segments": [str(s) for s in segments[:50]],
            }
        ],
        "layout": "4panel",
        "notes": (
            "Skeleton/annotation export for Neuroglancer-compatible hosting. "
            "Raw EM precomputed volumes are not included (remote-only policy)."
        ),
        "manifest_coverage": man.get("coverage_map"),
        "how_to_host": (
            "Serve data/neuroglancer/<id> over HTTP and open the JSON skeletons "
            "in the Insectome atlas, or convert to sharded precomputed with "
            "cloudvolume/tensorstore when EM access exists."
        ),
    }
    (root / "viewer_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (root / "README.md").write_text(
        "\n".join(
            [
                f"# Neuroglancer export — {connectome_id}",
                "",
                "Contents:",
                "- `skeletons/` — per-neuron JSON skeletons (LOD)",
                "- `annotations/soma_annotations.json`",
                "- `properties/` — segment property metadata",
                "- `viewer_state.json` — shareable atlas/Neuroglancer-oriented state",
                "",
                "Raw EM imagery is intentionally omitted.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return root
