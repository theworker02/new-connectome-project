"""Export a compact static site dataset for GitHub Pages.

Writes JSON under atlas/public/data/ so the Vite build can ship without FastAPI.
Raw connectome packs stay local; only catalog indexes + sparse LOD skeletons ship.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from insectome.atlas import service
from insectome.atlas.skeletons import line_segments, read_skeleton_bin
from insectome.autonomy.budget import format_bytes
from insectome.autonomy.ledger import load_ledger
from insectome.autonomy.budget import AutonomyBudget
from insectome.connectome.store import ConnectomeStore, list_connectomes
from insectome.storage.paths import project_root, utc_now

# Keep the published site well under GitHub Pages practical limits.
MAX_SKELETONS_PER_PACK = 48
MAX_LOD_VERTICES = 320
MAX_PARTNER_NEURONS = 96
MAX_PARTNERS_PER_SIDE = 40
MAX_EDGE_EXPORT = 80_000
SOFT_SITE_WARN_BYTES = 180 * 1024**2


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if pd.isna(obj):
        return None
    return str(obj)


def _write_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_jsonable(payload), separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def static_data_root() -> Path:
    return project_root() / "atlas" / "public" / "data"


def _neuron_index_records(connectome_id: str) -> list[dict[str, Any]]:
    idx = service.load_index(connectome_id)
    if idx.empty:
        return []
    keep = [
        c
        for c in (
            "source_id",
            "global_id",
            "name",
            "cell_type",
            "has_skeleton",
            "pre_count",
            "post_count",
            "degree_in",
            "degree_out",
            "soma_x",
            "soma_y",
            "soma_z",
        )
        if c in idx.columns
    ]
    df = idx[keep].copy()
    # Prefer skeletons / high degree at the front for UI defaults
    if "has_skeleton" in df.columns:
        df["_sk"] = df["has_skeleton"].fillna(False).astype(int)
    else:
        df["_sk"] = 0
    deg = 0
    if "degree_out" in df.columns:
        deg = deg + df["degree_out"].fillna(0)
    if "degree_in" in df.columns:
        deg = deg + df["degree_in"].fillna(0)
    df["_deg"] = deg
    df = df.sort_values(["_sk", "_deg"], ascending=[False, False]).drop(columns=["_sk", "_deg"])
    return df.to_dict(orient="records")


def _skeleton_entry(store: ConnectomeStore, source_id: int) -> dict[str, Any] | None:
    path = store.dir / "skeletons" / f"{source_id}.lod.skbin"
    if not path.exists():
        path = store.dir / "skeletons" / f"{source_id}.skbin"
    if not path.exists():
        return None
    verts, links, meta = read_skeleton_bin(path)
    # Extra downsample for Pages payload
    n = len(verts)
    if n > MAX_LOD_VERTICES:
        stride = int(np.ceil(n / MAX_LOD_VERTICES))
        keep = np.zeros(n, dtype=bool)
        keep[0] = True
        keep[::stride] = True
        keep[-1] = True
        roots = np.where(links < 0)[0]
        keep[roots] = True
        idx = np.where(keep)[0]
        old_to_new = -np.ones(n, dtype=np.int32)
        old_to_new[idx] = np.arange(len(idx), dtype=np.int32)
        new_verts = verts[idx]
        new_links = np.empty(len(idx), dtype=np.int32)
        for ni, oi in enumerate(idx):
            parent = int(links[oi])
            while parent >= 0 and old_to_new[parent] < 0:
                parent = int(links[parent])
            new_links[ni] = -1 if parent < 0 else int(old_to_new[parent])
        verts, links = new_verts, new_links
    segs = line_segments(verts, links).reshape(-1).tolist()
    return {
        "source_id": int(source_id),
        "global_id": meta.get("global_id"),
        "line_segments": [round(float(x), 2) for x in segs],
        "n_vertices": int(len(verts)),
        "name": None,
    }


def _partner_maps(store: ConnectomeStore, neuron_ids: list[int]) -> dict[int, dict[str, list]]:
    wanted = set(int(x) for x in neuron_ids)
    out: dict[int, dict[str, list]] = {i: {"upstream": [], "downstream": []} for i in wanted}
    edges_path = store.dir / "edges.parquet"
    if not edges_path.exists() or not wanted:
        return out
    edges = store.load_edges()
    if edges.empty:
        return out
    # Filter to rows touching wanted neurons
    pre = edges["pre_neuron_id"].astype(int)
    post = edges["post_neuron_id"].astype(int)
    mask = pre.isin(wanted) | post.isin(wanted)
    sub = edges.loc[mask]
    if "synapse_count" not in sub.columns:
        sub = sub.assign(synapse_count=1)
    for _, row in sub.iterrows():
        a, b = int(row["pre_neuron_id"]), int(row["post_neuron_id"])
        w = int(row.get("synapse_count", 1) or 1)
        rec_out = {"partner_id": b, "synapse_count": w, "direction": "out", "pre_neuron_id": a, "post_neuron_id": b}
        rec_in = {"partner_id": a, "synapse_count": w, "direction": "in", "pre_neuron_id": a, "post_neuron_id": b}
        if a in out and len(out[a]["downstream"]) < MAX_PARTNERS_PER_SIDE:
            out[a]["downstream"].append(rec_out)
        if b in out and len(out[b]["upstream"]) < MAX_PARTNERS_PER_SIDE:
            out[b]["upstream"].append(rec_in)
    return out


def _export_pack(connectome_id: str, out_root: Path) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    pack_dir = out_root / "packs" / connectome_id
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    pack_dir.mkdir(parents=True)

    status_rows = {r["connectome_id"]: r for r in service.atlas_status_rows()}
    status = status_rows.get(connectome_id, {"connectome_id": connectome_id})
    manifest = store.read_manifest() if store.manifest_path.exists() else {}

    neurons = _neuron_index_records(connectome_id)
    _write_json(pack_dir / "neurons.json", {"total": len(neurons), "neurons": neurons})
    _write_json(pack_dir / "manifest.json", {"manifest": manifest, "status": status})
    _write_json(pack_dir / "status.json", status)

    # Skeleton batch: prefer has_skeleton rows already sorted
    sk_candidates = [int(r["source_id"]) for r in neurons if r.get("has_skeleton")]
    if not sk_candidates:
        sk_candidates = [int(r["source_id"]) for r in neurons[:MAX_SKELETONS_PER_PACK]]
    sk_ids = sk_candidates[:MAX_SKELETONS_PER_PACK]
    name_map = {int(r["source_id"]): r.get("name") for r in neurons}
    batch_neurons: list[dict[str, Any]] = []
    sk_dir = pack_dir / "skeletons"
    for sid in sk_ids:
        entry = _skeleton_entry(store, sid)
        if not entry:
            continue
        entry["name"] = name_map.get(sid)
        batch_neurons.append(entry)
        _write_json(sk_dir / f"{sid}.json", entry)
    _write_json(
        pack_dir / "skeletons" / "batch.json",
        {"connectome_id": connectome_id, "count": len(batch_neurons), "neurons": batch_neurons},
    )

    partner_ids = sk_ids[:MAX_PARTNER_NEURONS]
    # Also include first catalog page for partner lookups when no skeletons
    if len(partner_ids) < 24:
        for r in neurons[:24]:
            sid = int(r["source_id"])
            if sid not in partner_ids:
                partner_ids.append(sid)
    partners = _partner_maps(store, partner_ids)
    for sid, payload in partners.items():
        _write_json(pack_dir / "partners" / f"{sid}.json", payload)

    # Sparse edges for pathfinding on small packs only
    edges_meta: dict[str, Any] = {"exported": False, "count": 0}
    edges_path = store.dir / "edges.parquet"
    if edges_path.exists():
        edges = store.load_edges()
        n_edges = int(len(edges))
        edges_meta["count"] = n_edges
        if 0 < n_edges <= MAX_EDGE_EXPORT:
            cols = ["pre_neuron_id", "post_neuron_id"]
            if "synapse_count" in edges.columns:
                cols.append("synapse_count")
            rows = edges[cols].head(MAX_EDGE_EXPORT).to_dict(orient="records")
            _write_json(pack_dir / "edges.json", {"edges": rows})
            edges_meta["exported"] = True
            edges_meta["exported_count"] = len(rows)

    # Neuron detail stubs for partner IDs (identity without full partners list)
    for r in neurons:
        sid = int(r["source_id"])
        if sid not in partners and sid not in sk_ids[:20]:
            continue
        detail = {
            "connectome_id": connectome_id,
            "neuron": {"neuron_id": sid, "name": r.get("name"), "type": r.get("cell_type")},
            "index": r,
            "partners": [],
            "upstream": partners.get(sid, {}).get("upstream", []),
            "downstream": partners.get(sid, {}).get("downstream", []),
            "provenance": {
                "source": manifest.get("source"),
                "source_version": manifest.get("source_version"),
                "specimen": manifest.get("specimen"),
                "coverage_map": manifest.get("coverage_map"),
            },
            "graph_layers": manifest.get("graph_layers"),
        }
        _write_json(pack_dir / "neurons" / f"{sid}.json", detail)

    pack_bytes = sum(p.stat().st_size for p in pack_dir.rglob("*") if p.is_file())
    return {
        "connectome_id": connectome_id,
        "neurons": len(neurons),
        "skeletons_exported": len(batch_neurons),
        "partners_exported": len(partners),
        "edges": edges_meta,
        "bytes": pack_bytes,
    }


def export_static_site(*, clean: bool = True) -> dict[str, Any]:
    """Materialize atlas/public/data for a fully static GitHub Pages build."""
    out = static_data_root()
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    # Ensure indexes cover all nodes before export
    for cid in list_connectomes():
        try:
            service.rebuild_full_neuron_catalog(cid)
        except Exception:  # noqa: BLE001
            pass

    pack_summaries = []
    for cid in list_connectomes():
        if not (ConnectomeStore(cid).dir / "nodes.parquet").exists():
            continue
        pack_summaries.append(_export_pack(cid, out))

    connectomes = service.atlas_status_rows()
    # Only include packs we exported
    exported_ids = {p["connectome_id"] for p in pack_summaries}
    connectomes = [c for c in connectomes if c["connectome_id"] in exported_ids]
    species = service.list_species_atlas()

    budget = AutonomyBudget()
    ledger = load_ledger()
    candidates = [c.model_dump(mode="json") for c in ledger.values()]
    by_status: dict[str, int] = {}
    for c in candidates:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    autonomy = {
        "pack_bytes": budget.used_bytes(),
        "pack_bytes_label": format_bytes(budget.used_bytes()),
        "soft_limit_bytes": budget.pack_soft_bytes,
        "hard_limit_bytes": budget.pack_hard_bytes,
        "candidate_count": len(candidates),
        "by_status": by_status,
        "candidates": sorted(candidates, key=lambda x: (-x.get("reuse_score", 0), x.get("candidate_id", ""))),
        "static": True,
        "note": "Read-only snapshot. Run `insectome autonomy run` locally to refresh.",
    }

    storage = {
        "total_bytes": sum(p["bytes"] for p in pack_summaries),
        "soft_limit_bytes": budget.pack_soft_bytes,
        "hard_limit_bytes": budget.pack_hard_bytes,
        "ram_bytes": 0,
        "breakdown_bytes": {"static_site": sum(p["bytes"] for p in pack_summaries)},
        "root": "static://atlas/public/data",
        "static": True,
    }

    meta = {
        "generated_at": utc_now(),
        "mode": "github_pages_static",
        "packs": pack_summaries,
        "total_bytes": sum(p["bytes"] for p in pack_summaries),
        "warn_over_soft": sum(p["bytes"] for p in pack_summaries) > SOFT_SITE_WARN_BYTES,
    }

    _write_json(out / "connectomes.json", connectomes)
    _write_json(out / "species.json", species)
    _write_json(out / "autonomy.json", autonomy)
    _write_json(out / "storage.json", storage)
    _write_json(out / "meta.json", meta)
    _write_json(
        out / "health.json",
        {"ok": True, "mode": "static", "generated_at": meta["generated_at"], "packs": len(pack_summaries)},
    )

    # 404 helper content note for SPA — actual 404.html written at build time
    readme = out / "README.md"
    readme.write_text(
        "# Static Insectome data\n\n"
        "Generated by `insectome pages export` for GitHub Pages.\n"
        "Do not hand-edit; regenerate from local connectome packs.\n",
        encoding="utf-8",
    )

    return meta
