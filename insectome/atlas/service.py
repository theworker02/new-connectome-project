"""Atlas service layer over connectome packs."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from insectome.atlas.skeletons import line_segments, read_skeleton_bin, skeleton_to_json
from insectome.connectome.store import ConnectomeStore, list_connectomes
from insectome.phase3.catalog import SPECIES_CATALOG, available_packs_for


_INDEX_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}
_INDEX_TTL_S = 120.0


def _pick_name(nodes: pd.DataFrame) -> pd.Series:
    for col in ("name", "instance", "type", "cell_type"):
        if col in nodes.columns:
            return nodes[col]
    return nodes["neuron_id"].astype(str)


def _pick_type(nodes: pd.DataFrame) -> pd.Series:
    for col in ("type", "cell_type", "name"):
        if col in nodes.columns:
            return nodes[col]
    return pd.Series([None] * len(nodes))


def rebuild_full_neuron_catalog(connectome_id: str) -> dict[str, Any]:
    """Write neuron_index.parquet covering ALL pack neurons, merging skeleton geometry."""
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    if nodes.empty:
        return {"connectome_id": connectome_id, "neurons": 0}
    edges_path = store.dir / "edges.parquet"
    edges = pd.read_parquet(edges_path) if edges_path.exists() else pd.DataFrame()

    base = pd.DataFrame(
        {
            "source_id": nodes["neuron_id"].astype(int),
            "name": _pick_name(nodes).values,
            "cell_type": _pick_type(nodes).values,
            "species": nodes["species"].values if "species" in nodes.columns else None,
            "specimen": nodes["specimen"].values if "specimen" in nodes.columns else None,
            "dataset": nodes["dataset"].values if "dataset" in nodes.columns else None,
            "region": nodes["anatomical_region"].values if "anatomical_region" in nodes.columns else None,
            "graph_layer": nodes["graph_layer"].values if "graph_layer" in nodes.columns else None,
            "has_skeleton": False,
        }
    )
    if "global_id" in nodes.columns:
        base["global_id"] = nodes["global_id"].values
    else:
        base["global_id"] = base["source_id"].astype(str)

    sk_path = store.dir / "neuron_index.parquet"
    if sk_path.exists():
        prev = pd.read_parquet(sk_path)
        if "source_id" in prev.columns:
            sk = prev.set_index("source_id")
            for col in (
                "soma_x",
                "soma_y",
                "soma_z",
                "n_skeleton_vertices",
                "n_lod_vertices",
                "has_skeleton",
            ):
                if col in sk.columns:
                    mapped = base["source_id"].map(sk[col])
                    if col == "has_skeleton":
                        base[col] = mapped.fillna(False).astype(bool)
                    else:
                        base[col] = mapped
            for col in ("global_id", "name", "cell_type"):
                if col in sk.columns and col in base.columns:
                    mapped = base["source_id"].map(sk[col])
                    base[col] = mapped.where(mapped.notna(), base[col])

    sk_dir = store.dir / "skeletons"
    if sk_dir.exists():
        sk_ids: set[int] = set()
        for p in sk_dir.glob("*.lod.skbin"):
            try:
                sk_ids.add(int(p.name.split(".", 1)[0]))
            except ValueError:
                continue
        for p in sk_dir.glob("*.skbin"):
            if ".lod." in p.name:
                continue
            try:
                sk_ids.add(int(p.stem))
            except ValueError:
                continue
        base["has_skeleton"] = base["source_id"].isin(sk_ids)

    if not edges.empty and "pre_neuron_id" in edges.columns:
        out_n = edges.groupby("pre_neuron_id").size()
        in_n = edges.groupby("post_neuron_id").size()
        if "synapse_count" in edges.columns:
            out_w = edges.groupby("pre_neuron_id")["synapse_count"].sum()
            in_w = edges.groupby("post_neuron_id")["synapse_count"].sum()
        else:
            out_w, in_w = out_n, in_n
        base["degree_out"] = base["source_id"].map(out_n).fillna(0).astype(int)
        base["degree_in"] = base["source_id"].map(in_n).fillna(0).astype(int)
        base["pre_count"] = base["source_id"].map(out_w).fillna(0).astype(int)
        base["post_count"] = base["source_id"].map(in_w).fillna(0).astype(int)
    else:
        for c in ("degree_out", "degree_in", "pre_count", "post_count"):
            if c not in base.columns:
                base[c] = 0

    base.to_parquet(store.dir / "neuron_index.parquet", index=False)
    _INDEX_CACHE.pop(connectome_id, None)
    n_sk = int(base["has_skeleton"].sum()) if "has_skeleton" in base.columns else 0
    return {"connectome_id": connectome_id, "neurons": int(len(base)), "skeletons": n_sk}


def load_index(connectome_id: str, *, force: bool = False) -> pd.DataFrame:
    now = time.time()
    cached = _INDEX_CACHE.get(connectome_id)
    if not force and cached and now - cached[0] < _INDEX_TTL_S:
        return cached[1].copy()

    store = ConnectomeStore(connectome_id)
    nodes_path = store.dir / "nodes.parquet"
    idx_path = store.dir / "neuron_index.parquet"
    if not nodes_path.exists():
        return pd.DataFrame()

    nodes = store.load_nodes()
    n_nodes = len(nodes)

    if idx_path.exists():
        idx = pd.read_parquet(idx_path)
        if "source_id" not in idx.columns and "neuron_id" in idx.columns:
            idx = idx.rename(columns={"neuron_id": "source_id"})
        if len(idx) < n_nodes:
            rebuild_full_neuron_catalog(connectome_id)
            idx = pd.read_parquet(idx_path)
    else:
        rebuild_full_neuron_catalog(connectome_id)
        idx = pd.read_parquet(idx_path)

    _INDEX_CACHE[connectome_id] = (now, idx)
    return idx.copy()


def atlas_status_rows() -> list[dict[str, Any]]:
    rows = []
    for cid in list_connectomes():
        store = ConnectomeStore(cid)
        man = store.read_manifest() if store.manifest_path.exists() else {}
        nodes = store.load_nodes() if (store.dir / "nodes.parquet").exists() else pd.DataFrame()
        edges = store.load_edges() if (store.dir / "edges.parquet").exists() else pd.DataFrame()
        syn = store.load_synapses()
        idx_path = store.dir / "neuron_index.parquet"
        n_sk = 0
        if idx_path.exists():
            idx = pd.read_parquet(idx_path)
            n_sk = int(idx["has_skeleton"].sum()) if "has_skeleton" in idx.columns else int(len(idx))
        else:
            sk_dir = store.dir / "skeletons"
            if sk_dir.exists():
                n_sk = len(list(sk_dir.glob("*.lod.skbin"))) or len(list(sk_dir.glob("*.skbin")))
        cov = man.get("coverage_map") or {}
        layers = man.get("graph_layers") or {}
        rows.append(
            {
                "connectome_id": cid,
                "species": man.get("species") or (None if nodes.empty else nodes.iloc[0].get("species")),
                "region": cov.get("region") or man.get("neurons", {}).get("filter") or "",
                "neurons": int(len(nodes)),
                "synapses": 0 if syn is None else int(len(syn)),
                "edges": int(len(edges)),
                "morphology_coverage": bool(layers.get("OBSERVED_MORPHOLOGY") or n_sk),
                "synaptic_coverage": bool(layers.get("OBSERVED_SYNAPTIC")),
                "skeletons": n_sk,
                "em_availability": "remote/evidence"
                if man.get("atlas", {}).get("em_evidence")
                else man.get("raw_em", {}).get("remote_location"),
                "atlas_status": (
                    "VIEWER_3D_READY"
                    if n_sk
                    else ("GRAPH_READY" if (layers.get("OBSERVED_SYNAPTIC") and len(edges)) else "PACK_ONLY")
                ),
                "coverage_claim": cov.get("claim") or man.get("coverage_claim"),
                "labels": cov.get("labels") or [],
            }
        )
    return rows


def list_species_atlas() -> list[dict[str, Any]]:
    out = []
    for entry in SPECIES_CATALOG.values():
        packs = available_packs_for(entry)
        pack_rows = [r for r in atlas_status_rows() if r["connectome_id"] in packs]
        out.append(
            {
                "key": entry.key,
                "scientific": entry.scientific,
                "common": entry.common,
                "heinze_2026": entry.heinze_2026_status,
                "packs": packs,
                "total_neurons": sum(p["neurons"] for p in pack_rows),
                "total_edges": sum(p["edges"] for p in pack_rows),
                "total_skeletons": sum(p["skeletons"] for p in pack_rows),
                "atlas_ready": any(p["atlas_status"] in {"VIEWER_3D_READY", "READY"} for p in pack_rows),
                "notes": entry.notes,
            }
        )
    return out


def neuron_detail(connectome_id: str, source_id: int) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    hit = nodes[nodes["neuron_id"] == source_id]
    if hit.empty:
        raise KeyError(source_id)
    row = hit.iloc[0].to_dict()
    partners = store.partners(source_id)
    index = load_index(connectome_id)
    ix = index[index["source_id"] == source_id]
    man = store.read_manifest() if store.manifest_path.exists() else {}
    return {
        "connectome_id": connectome_id,
        "neuron": row,
        "index": None if ix.empty else ix.iloc[0].to_dict(),
        "partners": partners.to_dict(orient="records"),
        "upstream": partners[partners["direction"] == "in"].to_dict(orient="records")
        if "direction" in partners
        else [],
        "downstream": partners[partners["direction"] == "out"].to_dict(orient="records")
        if "direction" in partners
        else [],
        "provenance": {
            "source": man.get("source"),
            "source_version": man.get("source_version"),
            "specimen": man.get("specimen"),
            "coverage_map": man.get("coverage_map"),
            "limitations": man.get("limitations", []),
        },
        "graph_layers": man.get("graph_layers"),
    }


def skeleton_payload(connectome_id: str, source_id: int, lod: bool = True, as_segments: bool = True) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    path = store.dir / "skeletons" / (f"{source_id}.lod.skbin" if lod else f"{source_id}.skbin")
    if not path.exists():
        alt = store.dir / "skeletons" / f"{source_id}.skbin"
        if alt.exists():
            path = alt
        else:
            raise FileNotFoundError(source_id)
    verts, links, meta = read_skeleton_bin(path)
    payload = skeleton_to_json(verts, links, max_vertices=2000 if lod else 20000)
    payload["meta"] = meta
    payload["source_id"] = source_id
    payload["connectome_id"] = connectome_id
    if as_segments:
        payload["line_segments"] = line_segments(verts, links).reshape(-1).tolist()
    return payload


def batch_skeletons(connectome_id: str, limit: int = 200, lod: bool = True) -> dict[str, Any]:
    index = load_index(connectome_id)
    if "has_skeleton" in index.columns:
        index = index[index["has_skeleton"] == True]  # noqa: E712
    if "degree_out" in index.columns or "degree_in" in index.columns:
        deg = (
            (index["degree_out"].fillna(0).astype(int) if "degree_out" in index.columns else 0)
            + (index["degree_in"].fillna(0).astype(int) if "degree_in" in index.columns else 0)
        )
        index = index.assign(_deg=deg).sort_values("_deg", ascending=False)
    neurons = []
    for sid in index["source_id"].astype(int).head(limit):
        try:
            sk = skeleton_payload(connectome_id, int(sid), lod=lod, as_segments=True)
            neurons.append(
                {
                    "source_id": int(sid),
                    "global_id": sk["meta"].get("global_id"),
                    "line_segments": sk["line_segments"],
                    "n_vertices": sk["n_vertices"],
                    "name": None,
                }
            )
        except FileNotFoundError:
            continue
    name_map = {int(r["source_id"]): r.get("name") for r in index.to_dict(orient="records")}
    for n in neurons:
        n["name"] = name_map.get(n["source_id"])
    return {"connectome_id": connectome_id, "count": len(neurons), "neurons": neurons}


def path_query(connectome_id: str, source: int, target: int, cutoff: int = 4) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    path = store.path(source, target, cutoff=cutoff)
    return {"from": source, "to": target, "path": path, "found": path is not None}


def cremi_em_cutout_b64(connectome_id: str, synapse_index: int = 0) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    syn = store.load_synapses()
    if syn is None or syn.empty:
        raise RuntimeError("No synapses")
    row = syn.iloc[int(synapse_index)]
    from insectome.adapters.cremi_pack import _resolve_cremi_hdf
    from insectome.evidence.cutout import cremi_evidence_cutout

    hdf = _resolve_cremi_hdf(authorize_download=False)
    cut = cremi_evidence_cutout(float(row.z_nm), float(row.y_nm), float(row.x_nm), Path(hdf))
    mid = cut[cut.shape[0] // 2]
    m = mid.astype(np.float32)
    m = (255 * (m - m.min()) / (m.ptp() + 1e-6)).astype(np.uint8)
    return {
        "synapse": row.to_dict(),
        "shape": list(cut.shape),
        "mid_slice_shape": list(m.shape),
        "mid_slice_b64": base64.b64encode(m.tobytes()).decode("ascii"),
        "dtype": "uint8",
        "note": "Evidence ROI mid-slice only — not full EM volume",
    }
