"""Enrich connectome packs with real skeleton geometry for the atlas."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from insectome.atlas.canonical import make_global_id
from insectome.atlas.skeletons import (
    downsample_skeleton,
    skeleton_from_catmaid_swc_rows,
    skeleton_from_neuprint_df,
    skeleton_from_swc_text,
    write_skeleton_bin,
)
from insectome.connectome.store import ConnectomeStore
from insectome.storage.paths import project_root, utc_now


def enrich_hemibrain_epg_skeletons(
    connectome_id: str = "hemibrain_epg_v0.1",
    dataset: str = "hemibrain:v1.2.1",
    max_vertices_lod: int = 900,
) -> dict:
    """Fetch neuPrint skeletons for all neurons in the EPG pack."""
    from neuprint import Client, fetch_skeleton

    token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
    if not token:
        raise RuntimeError("NEUPRINT_APPLICATION_CREDENTIALS required")
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    client = Client("neuprint.janelia.org", dataset=dataset, token=token)
    sk_dir = store.dir / "skeletons"
    sk_dir.mkdir(parents=True, exist_ok=True)
    index_rows = []
    species = str(nodes.iloc[0]["species"])
    specimen = str(nodes.iloc[0].get("specimen", dataset))
    dataset_id = str(nodes.iloc[0]["dataset"])
    for _, row in nodes.iterrows():
        bid = int(row["neuron_id"])
        sk = fetch_skeleton(bid, client=client)
        verts, links = skeleton_from_neuprint_df(sk)
        lod_v, lod_l = downsample_skeleton(verts, links, max_vertices=max_vertices_lod)
        gid = make_global_id(species, specimen, dataset_id, bid)
        write_skeleton_bin(
            sk_dir / f"{bid}.skbin",
            verts,
            links,
            meta={"global_id": gid, "source_id": bid, "lod": "full", "source": "neuPrint"},
        )
        write_skeleton_bin(
            sk_dir / f"{bid}.lod.skbin",
            lod_v,
            lod_l,
            meta={"global_id": gid, "source_id": bid, "lod": "display", "source": "neuPrint"},
        )
        soma = None
        if "somaLocation" in row and isinstance(row.get("somaLocation"), (list, tuple)):
            soma = list(row["somaLocation"])
        elif len(verts):
            # approximate soma as largest-radius node
            soma = verts[int(verts[:, 3].argmax()), :3].tolist()
        index_rows.append(
            {
                "global_id": gid,
                "source_id": bid,
                "species": species,
                "specimen": specimen,
                "dataset": dataset_id,
                "region": row.get("anatomical_region"),
                "name": row.get("instance") or row.get("type"),
                "cell_type": row.get("type"),
                "soma_x": None if soma is None else float(soma[0]),
                "soma_y": None if soma is None else float(soma[1]),
                "soma_z": None if soma is None else float(soma[2]),
                "has_skeleton": True,
                "n_skeleton_vertices": int(len(verts)),
                "n_lod_vertices": int(len(lod_v)),
                "graph_layer": row.get("graph_layer", "OBSERVED_SYNAPTIC"),
            }
        )
    index = pd.DataFrame(index_rows)
    # attach degree stats from edges
    edges = store.load_edges()
    out_deg = edges.groupby("pre_neuron_id")["synapse_count"].sum()
    in_deg = edges.groupby("post_neuron_id")["synapse_count"].sum()
    out_n = edges.groupby("pre_neuron_id").size()
    in_n = edges.groupby("post_neuron_id").size()
    index["pre_count"] = index["source_id"].map(out_deg).fillna(0).astype(int)
    index["post_count"] = index["source_id"].map(in_deg).fillna(0).astype(int)
    index["degree_out"] = index["source_id"].map(out_n).fillna(0).astype(int)
    index["degree_in"] = index["source_id"].map(in_n).fillna(0).astype(int)
    index.to_parquet(store.dir / "neuron_index.parquet", index=False)
    # update nodes with global ids
    nodes = nodes.copy()
    nodes["global_id"] = [
        make_global_id(species, specimen, dataset_id, int(i)) for i in nodes["neuron_id"]
    ]
    nodes["has_skeleton"] = True
    store.save_tables(nodes, edges, store.load_synapses())
    man = store.read_manifest()
    man["graph_layers"]["OBSERVED_MORPHOLOGY"] = True
    man["atlas"] = {
        "skeletons": True,
        "neuron_index": True,
        "enriched_at": utc_now(),
        "skeleton_source": "neuPrint fetch_skeleton",
        "primary_milestone": True,
    }
    man["coverage_map"] = {
        "region": "central complex / ellipsoid body–protocerebral bridge (EPG)",
        "claim": "LOCAL_SYNAPTIC_CONNECTOME",
        "labels": ["SYNAPTIC_CONNECTOME", "HIGH_CONFIDENCE_RECONSTRUCTION", "PARTIAL_RECONSTRUCTION"],
        "notes": "Typed EPG subgraph of hemibrain — not whole-brain",
    }
    store.write_manifest(man)
    card = store.dir / "CONNECTOME_CARD.md"
    card.write_text(
        "\n".join(
            [
                "# Connectome card — hemibrain EPG (atlas primary)",
                "",
                "- Species: Drosophila melanogaster",
                "- Specimen: hemibrain:v1.2.1",
                "- Region: central complex (EPG cell class)",
                "- Coverage claim: LOCAL SYNAPTIC CONNECTOME / PARTIAL",
                f"- Neurons: {len(nodes)}",
                f"- Edges: {len(edges)}",
                "- Skeletons: neuPrint (observed morphology)",
                "- Graph layers: OBSERVED_MORPHOLOGY + OBSERVED_SYNAPTIC",
                "- EM: remote via neuPrint/Neuroglancer — not stored locally",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"connectome_id": connectome_id, "neurons": int(len(index)), "skeletons": int(len(index))}


def enrich_bombus_skeletons_from_ibdb(
    connectome_id: str = "bombus_terrestris_cx_projectome_v0.1",
    experiment_id: int = 61,
    max_neurons: int | None = None,
    max_vertices_lod: int = 600,
) -> dict:
    """Re-fetch IBdb Bombus projectome and persist real skeleton XYZ."""
    import gzip

    import requests

    from insectome.adapters.ibdb import list_experiment_files

    files = list_experiment_files(experiment_id)
    sk_files = [f for f in files if "skeleton" in f.get("file_name", "").lower()]
    if not sk_files:
        raise RuntimeError("No Bombus skeleton file on IBdb")
    resp = requests.get(sk_files[0]["url"], timeout=300)
    resp.raise_for_status()
    raw = resp.content
    if raw[:2] == b"\x1f\x8b":
        data = json.loads(gzip.decompress(raw).decode("utf-8"))
    else:
        data = json.loads(raw.decode("utf-8"))
    neurons = data.get("data", data if isinstance(data, list) else [])
    if max_neurons:
        neurons = neurons[:max_neurons]
    store = ConnectomeStore(connectome_id)
    sk_dir = store.dir / "skeletons"
    sk_dir.mkdir(parents=True, exist_ok=True)
    # clear old meta-only files
    for p in sk_dir.glob("*.meta.json"):
        p.unlink()
    index_rows = []
    species = "Bombus terrestris"
    specimen = "Bombus terrestris CX SBEM"
    dataset_id = "bombus_cx_projectome_sayre2021"
    for i, neuron in enumerate(neurons):
        name = neuron.get("name") or neuron.get("neuron_name") or f"neuron_{i}"
        nid = int(neuron.get("id") or neuron.get("skeleton_id") or i + 1)
        skels = neuron.get("skeletons") or []
        if not skels:
            continue
        # merge first skeleton
        rows = skels[0].get("data") or []
        verts, links = skeleton_from_catmaid_swc_rows(rows)
        if len(verts) == 0:
            continue
        lod_v, lod_l = downsample_skeleton(verts, links, max_vertices=max_vertices_lod)
        gid = make_global_id(species, specimen, dataset_id, nid)
        write_skeleton_bin(
            sk_dir / f"{nid}.skbin",
            verts,
            links,
            meta={"global_id": gid, "source_id": nid, "name": name, "source": "IBdb"},
        )
        write_skeleton_bin(
            sk_dir / f"{nid}.lod.skbin",
            lod_v,
            lod_l,
            meta={"global_id": gid, "source_id": nid, "name": name, "lod": "display"},
        )
        soma = verts[int(verts[:, 3].argmax()), :3].tolist()
        index_rows.append(
            {
                "global_id": gid,
                "source_id": nid,
                "species": species,
                "specimen": specimen,
                "dataset": dataset_id,
                "region": "central complex",
                "name": name,
                "cell_type": name.split("_")[0] if "_" in name else name,
                "soma_x": float(soma[0]),
                "soma_y": float(soma[1]),
                "soma_z": float(soma[2]),
                "has_skeleton": True,
                "n_skeleton_vertices": int(len(verts)),
                "n_lod_vertices": int(len(lod_v)),
                "graph_layer": "OBSERVED_MORPHOLOGY",
                "pre_count": 0,
                "post_count": 0,
                "degree_in": 0,
                "degree_out": 0,
            }
        )
    index = pd.DataFrame(index_rows)
    index.to_parquet(store.dir / "neuron_index.parquet", index=False)
    nodes = store.load_nodes()
    nodes = nodes.copy()
    nodes["global_id"] = [
        make_global_id(species, specimen, dataset_id, int(i)) for i in nodes["neuron_id"]
    ]
    nodes["has_skeleton"] = nodes["neuron_id"].isin(set(index["source_id"]))
    store.save_tables(nodes, store.load_edges(), None)
    man = store.read_manifest()
    man["atlas"] = {
        "skeletons": True,
        "neuron_index": True,
        "enriched_at": utc_now(),
        "skeleton_source": "IBdb CATMAID SWC",
        "primary_milestone": False,
        "comparison_milestone": True,
    }
    man["coverage_map"] = {
        "region": "central complex",
        "claim": "MORPHOLOGY_ONLY / CENTRAL-COMPLEX PROJECTOME",
        "labels": ["MORPHOLOGY_ONLY", "PARTIAL_RECONSTRUCTION"],
        "notes": "No public synaptic edges",
    }
    store.write_manifest(man)
    return {"connectome_id": connectome_id, "neurons": int(len(index))}


def enrich_neuprint_pack(
    connectome_id: str,
    dataset: str,
    *,
    max_n: int | None = None,
    region: str = "central brain",
    max_lod: int = 700,
    claim: str = "LOCAL_SYNAPTIC_CONNECTOME",
    labels: list[str] | None = None,
) -> dict:
    """Fetch neuPrint skeletons for neurons in an arbitrary pack."""
    from neuprint import Client, fetch_skeleton

    token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
    if not token:
        raise RuntimeError("NEUPRINT_APPLICATION_CREDENTIALS required")
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    if max_n:
        nodes = nodes.head(max_n)
    client = Client("neuprint.janelia.org", dataset=dataset, token=token)
    sk_dir = store.dir / "skeletons"
    sk_dir.mkdir(parents=True, exist_ok=True)
    species = str(nodes.iloc[0]["species"])
    specimen = str(nodes.iloc[0].get("specimen", dataset))
    dataset_id = str(nodes.iloc[0]["dataset"])
    index_rows = []
    for _, row in nodes.iterrows():
        bid = int(row["neuron_id"])
        sk = fetch_skeleton(bid, client=client)
        verts, links = skeleton_from_neuprint_df(sk)
        lod_v, lod_l = downsample_skeleton(verts, links, max_vertices=max_lod)
        gid = make_global_id(species, specimen, dataset_id, bid)
        write_skeleton_bin(
            sk_dir / f"{bid}.skbin",
            verts,
            links,
            meta={"global_id": gid, "source_id": bid, "source": "neuPrint"},
        )
        write_skeleton_bin(
            sk_dir / f"{bid}.lod.skbin",
            lod_v,
            lod_l,
            meta={"global_id": gid, "source_id": bid, "lod": "display"},
        )
        soma = verts[int(verts[:, 3].argmax()), :3].tolist() if len(verts) else None
        index_rows.append(
            {
                "global_id": gid,
                "source_id": bid,
                "species": species,
                "specimen": specimen,
                "dataset": dataset_id,
                "region": row.get("anatomical_region", region),
                "name": row.get("instance") or row.get("type"),
                "cell_type": row.get("type"),
                "soma_x": None if soma is None else float(soma[0]),
                "soma_y": None if soma is None else float(soma[1]),
                "soma_z": None if soma is None else float(soma[2]),
                "has_skeleton": True,
                "n_skeleton_vertices": int(len(verts)),
                "n_lod_vertices": int(len(lod_v)),
                "graph_layer": row.get("graph_layer", "OBSERVED_SYNAPTIC"),
            }
        )
    index = pd.DataFrame(index_rows)
    edges = store.load_edges()
    out_deg = edges.groupby("pre_neuron_id")["synapse_count"].sum()
    in_deg = edges.groupby("post_neuron_id")["synapse_count"].sum()
    out_n = edges.groupby("pre_neuron_id").size()
    in_n = edges.groupby("post_neuron_id").size()
    index["pre_count"] = index["source_id"].map(out_deg).fillna(0).astype(int)
    index["post_count"] = index["source_id"].map(in_deg).fillna(0).astype(int)
    index["degree_out"] = index["source_id"].map(out_n).fillna(0).astype(int)
    index["degree_in"] = index["source_id"].map(in_n).fillna(0).astype(int)
    index.to_parquet(store.dir / "neuron_index.parquet", index=False)
    nodes_all = store.load_nodes().copy()
    sk_ids = set(index["source_id"])
    nodes_all["global_id"] = [
        make_global_id(species, specimen, dataset_id, int(i)) for i in nodes_all["neuron_id"]
    ]
    nodes_all["has_skeleton"] = nodes_all["neuron_id"].isin(sk_ids)
    store.save_tables(nodes_all, edges, store.load_synapses())
    man = store.read_manifest()
    man.setdefault("graph_layers", {})["OBSERVED_MORPHOLOGY"] = True
    man["atlas"] = {
        "skeletons": True,
        "neuron_index": True,
        "enriched_at": utc_now(),
        "skeleton_source": "neuPrint fetch_skeleton",
        "n_skeletons": len(index),
    }
    man["coverage_map"] = {
        "region": region,
        "claim": claim,
        "labels": labels or ["SYNAPTIC_CONNECTOME", "PARTIAL_RECONSTRUCTION"],
    }
    store.write_manifest(man)
    return {"connectome_id": connectome_id, "skeletons": int(len(index))}


def enrich_ibdb_species_swc(
    connectome_id: str,
    *,
    max_n: int | None = None,
    max_vertices_lod: int = 700,
) -> dict:
    """Download public IBdb SWC files for a morphology pack and write atlas skeletons."""
    import requests

    from insectome.adapters.ibdb import neuron_reconstructions

    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    if "n_swc_files" in nodes.columns:
        candidates = nodes[nodes["n_swc_files"].fillna(0).astype(int) > 0]
    else:
        candidates = nodes
    if max_n:
        candidates = candidates.head(max_n)
    sk_dir = store.dir / "skeletons"
    sk_dir.mkdir(parents=True, exist_ok=True)
    species = str(nodes.iloc[0]["species"]) if len(nodes) else "Unknown"
    specimen = str(nodes.iloc[0].get("specimen", "IBdb"))
    dataset_id = str(nodes.iloc[0]["dataset"]) if len(nodes) else connectome_id
    index_rows = []
    skipped = 0
    for _, row in candidates.iterrows():
        nid = int(row["neuron_id"])
        try:
            recs = neuron_reconstructions(nid)
        except Exception:
            skipped += 1
            continue
        swc_url = None
        for rec in recs:
            for vf in rec.get("viewer_files") or []:
                if str(vf.get("file_name", "")).lower().endswith(".swc"):
                    swc_url = vf.get("url")
                    break
            if swc_url:
                break
        if not swc_url:
            skipped += 1
            continue
        try:
            resp = requests.get(swc_url, timeout=120)
            resp.raise_for_status()
            verts, links = skeleton_from_swc_text(resp.text)
        except Exception:
            skipped += 1
            continue
        if len(verts) == 0:
            skipped += 1
            continue
        lod_v, lod_l = downsample_skeleton(verts, links, max_vertices=max_vertices_lod)
        gid = make_global_id(species, specimen, dataset_id, nid)
        write_skeleton_bin(
            sk_dir / f"{nid}.skbin",
            verts,
            links,
            meta={"global_id": gid, "source_id": nid, "source": "IBdb SWC"},
        )
        write_skeleton_bin(
            sk_dir / f"{nid}.lod.skbin",
            lod_v,
            lod_l,
            meta={"global_id": gid, "source_id": nid, "lod": "display", "source": "IBdb SWC"},
        )
        soma = verts[int(verts[:, 3].argmax()), :3].tolist()
        index_rows.append(
            {
                "global_id": gid,
                "source_id": nid,
                "species": species,
                "specimen": specimen,
                "dataset": dataset_id,
                "region": row.get("anatomical_region") or "IBdb morphology",
                "name": row.get("name"),
                "cell_type": str(row.get("name") or "").split("-")[0] or None,
                "soma_x": float(soma[0]),
                "soma_y": float(soma[1]),
                "soma_z": float(soma[2]),
                "has_skeleton": True,
                "n_skeleton_vertices": int(len(verts)),
                "n_lod_vertices": int(len(lod_v)),
                "graph_layer": "OBSERVED_MORPHOLOGY",
                "pre_count": 0,
                "post_count": 0,
                "degree_in": 0,
                "degree_out": 0,
            }
        )
    if not index_rows:
        return {"connectome_id": connectome_id, "skeletons": 0, "skipped": skipped}
    index = pd.DataFrame(index_rows)
    index.to_parquet(store.dir / "neuron_index.parquet", index=False)
    nodes_all = store.load_nodes().copy()
    sk_ids = set(index["source_id"])
    nodes_all["global_id"] = [
        make_global_id(species, specimen, dataset_id, int(i)) for i in nodes_all["neuron_id"]
    ]
    nodes_all["has_skeleton"] = nodes_all["neuron_id"].isin(sk_ids)
    store.save_tables(nodes_all, store.load_edges(), None)
    man = store.read_manifest()
    man.setdefault("graph_layers", {})["OBSERVED_MORPHOLOGY"] = True
    man["atlas"] = {
        "skeletons": True,
        "neuron_index": True,
        "enriched_at": utc_now(),
        "skeleton_source": "IBdb public SWC",
        "n_skeletons": len(index),
        "skipped": skipped,
    }
    man["coverage_map"] = {
        "region": man.get("coverage_map", {}).get("region")
        if isinstance(man.get("coverage_map"), dict)
        else "mixed IBdb morphologies",
        "claim": "MORPHOLOGY_ONLY / LIGHT-LEVEL OR REGISTERED SWC",
        "labels": ["MORPHOLOGY_ONLY", "PARTIAL_RECONSTRUCTION", "IBDB_REUSE"],
        "notes": "Public Insect Brain Database SWC — not Heinze 2026 SBEM CX volumes",
    }
    store.write_manifest(man)
    return {"connectome_id": connectome_id, "skeletons": int(len(index)), "skipped": skipped}


def enrich_manc_high_degree_sample(
    connectome_id: str = "manc_sample_v0.1",
    dataset: str = "manc:v1.2.1",
    max_n: int = 60,
    max_lod: int = 600,
) -> dict:
    """Fetch neuPrint skeletons for the highest-degree MANC neurons (sampled morphology)."""
    from neuprint import Client, fetch_skeleton

    token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
    if not token:
        raise RuntimeError("NEUPRINT_APPLICATION_CREDENTIALS required")
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    edges = store.load_edges()
    deg = edges.groupby("pre_neuron_id").size().add(edges.groupby("post_neuron_id").size(), fill_value=0)
    ranked = nodes.copy()
    ranked["_deg"] = ranked["neuron_id"].map(deg).fillna(0)
    ranked = ranked.sort_values("_deg", ascending=False).head(max_n)
    client = Client("neuprint.janelia.org", dataset=dataset, token=token)
    sk_dir = store.dir / "skeletons"
    sk_dir.mkdir(parents=True, exist_ok=True)
    species = str(ranked.iloc[0]["species"])
    specimen = str(ranked.iloc[0].get("specimen", dataset))
    dataset_id = str(ranked.iloc[0]["dataset"])
    index_rows = []
    errors = 0
    for _, row in ranked.iterrows():
        bid = int(row["neuron_id"])
        try:
            sk = fetch_skeleton(bid, client=client)
            verts, links = skeleton_from_neuprint_df(sk)
        except Exception:
            errors += 1
            continue
        lod_v, lod_l = downsample_skeleton(verts, links, max_vertices=max_lod)
        gid = make_global_id(species, specimen, dataset_id, bid)
        write_skeleton_bin(
            sk_dir / f"{bid}.skbin",
            verts,
            links,
            meta={"global_id": gid, "source_id": bid, "source": "neuPrint"},
        )
        write_skeleton_bin(
            sk_dir / f"{bid}.lod.skbin",
            lod_v,
            lod_l,
            meta={"global_id": gid, "source_id": bid, "lod": "display"},
        )
        soma = verts[int(verts[:, 3].argmax()), :3].tolist() if len(verts) else None
        index_rows.append(
            {
                "global_id": gid,
                "source_id": bid,
                "species": species,
                "specimen": specimen,
                "dataset": dataset_id,
                "region": row.get("anatomical_region", "VNC"),
                "name": row.get("instance") or row.get("type"),
                "cell_type": row.get("type"),
                "soma_x": None if soma is None else float(soma[0]),
                "soma_y": None if soma is None else float(soma[1]),
                "soma_z": None if soma is None else float(soma[2]),
                "has_skeleton": True,
                "n_skeleton_vertices": int(len(verts)),
                "n_lod_vertices": int(len(lod_v)),
                "graph_layer": "OBSERVED_SYNAPTIC",
            }
        )
    if not index_rows:
        return {"connectome_id": connectome_id, "skeletons": 0, "errors": errors}
    index = pd.DataFrame(index_rows)
    out_deg = edges.groupby("pre_neuron_id")["synapse_count"].sum()
    in_deg = edges.groupby("post_neuron_id")["synapse_count"].sum()
    out_n = edges.groupby("pre_neuron_id").size()
    in_n = edges.groupby("post_neuron_id").size()
    index["pre_count"] = index["source_id"].map(out_deg).fillna(0).astype(int)
    index["post_count"] = index["source_id"].map(in_deg).fillna(0).astype(int)
    index["degree_out"] = index["source_id"].map(out_n).fillna(0).astype(int)
    index["degree_in"] = index["source_id"].map(in_n).fillna(0).astype(int)
    index.to_parquet(store.dir / "neuron_index.parquet", index=False)
    nodes_all = store.load_nodes().copy()
    sk_ids = set(index["source_id"])
    nodes_all["global_id"] = [
        make_global_id(species, specimen, dataset_id, int(i)) for i in nodes_all["neuron_id"]
    ]
    nodes_all["has_skeleton"] = nodes_all["neuron_id"].isin(sk_ids)
    store.save_tables(nodes_all, edges, store.load_synapses())
    man = store.read_manifest()
    man.setdefault("graph_layers", {})["OBSERVED_MORPHOLOGY"] = True
    man["atlas"] = {
        "skeletons": True,
        "neuron_index": True,
        "enriched_at": utc_now(),
        "skeleton_source": "neuPrint fetch_skeleton",
        "n_skeletons": len(index),
        "sample": f"top{max_n}_by_degree",
        "errors": errors,
    }
    man["coverage_map"] = {
        "region": "VNC",
        "claim": "LOCAL_SYNAPTIC_CONNECTOME / SAMPLED_MORPHOLOGY",
        "labels": ["SYNAPTIC_CONNECTOME", "PARTIAL_RECONSTRUCTION", "VNC"],
        "notes": "Full MANC edge table retained; 3D skeletons are a high-degree sample only",
    }
    store.write_manifest(man)
    return {"connectome_id": connectome_id, "skeletons": int(len(index)), "errors": errors}


def enrich_cremi_synapse_geometry(connectome_id: str = "cremi_sample_a_v0.2") -> dict:
    """Build per-neuron centroid + synapse point cloud from CREMI annotations (not EM morph)."""
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes()
    syn = store.load_synapses()
    if syn is None or syn.empty:
        raise RuntimeError("CREMI pack has no synapses")
    sk_dir = store.dir / "skeletons"
    sk_dir.mkdir(parents=True, exist_ok=True)
    species = "Drosophila melanogaster"
    specimen = "CREMI-A"
    dataset_id = "cremi_sample_a"
    index_rows = []
    import numpy as np

    for _, row in nodes.iterrows():
        nid = int(row["neuron_id"])
        pre = syn[syn["pre_neuron"] == nid][["x_nm", "y_nm", "z_nm"]]
        post = syn[syn["post_neuron"] == nid][["x_nm", "y_nm", "z_nm"]]
        pts = pd.concat([pre, post], ignore_index=True)
        if pts.empty:
            continue
        # star skeleton: centroid to each synapse site (geometry derived from synapse loci)
        c = pts.mean().to_numpy(dtype=np.float32)
        verts = [np.array([c[0], c[1], c[2], 20.0], dtype=np.float32)]
        links = [-1]
        for _, p in pts.iterrows():
            verts.append(np.array([p.x_nm, p.y_nm, p.z_nm, 8.0], dtype=np.float32))
            links.append(0)
        v = np.stack(verts)
        l = np.asarray(links, dtype=np.int32)
        gid = make_global_id(species, specimen, dataset_id, nid)
        write_skeleton_bin(
            sk_dir / f"{nid}.lod.skbin",
            v,
            l,
            meta={
                "global_id": gid,
                "geometry_kind": "SYNAPSE_SITE_STAR",
                "warning": "Not EM morphology — links synapse loci to centroid",
            },
        )
        index_rows.append(
            {
                "global_id": gid,
                "source_id": nid,
                "species": species,
                "specimen": specimen,
                "dataset": dataset_id,
                "region": "CREMI sample A ROI",
                "name": str(nid),
                "cell_type": None,
                "soma_x": float(c[0]),
                "soma_y": float(c[1]),
                "soma_z": float(c[2]),
                "has_skeleton": True,
                "n_skeleton_vertices": int(len(v)),
                "n_lod_vertices": int(len(v)),
                "graph_layer": "OBSERVED_SYNAPTIC",
                "geometry_kind": "SYNAPSE_SITE_STAR",
            }
        )
    index = pd.DataFrame(index_rows)
    edges = store.load_edges()
    out_deg = edges.groupby("pre_neuron_id")["synapse_count"].sum()
    in_deg = edges.groupby("post_neuron_id")["synapse_count"].sum()
    index["pre_count"] = index["source_id"].map(out_deg).fillna(0).astype(int)
    index["post_count"] = index["source_id"].map(in_deg).fillna(0).astype(int)
    index["degree_out"] = index["source_id"].map(edges.groupby("pre_neuron_id").size()).fillna(0).astype(int)
    index["degree_in"] = index["source_id"].map(edges.groupby("post_neuron_id").size()).fillna(0).astype(int)
    index.to_parquet(store.dir / "neuron_index.parquet", index=False)
    man = store.read_manifest()
    man["atlas"] = {
        "skeletons": True,
        "geometry_kind": "SYNAPSE_SITE_STAR",
        "em_evidence": True,
        "enriched_at": utc_now(),
    }
    man["coverage_map"] = {
        "region": "CREMI sample A partial volume",
        "claim": "PARTIAL_VOLUME / LOCAL_SYNAPTIC_CONNECTOME",
        "labels": ["SYNAPTIC_CONNECTOME", "PARTIAL_RECONSTRUCTION"],
    }
    store.write_manifest(man)
    # write synapse index for atlas
    syn2 = syn.copy()
    syn2["global_pre"] = [make_global_id(species, specimen, dataset_id, int(x)) for x in syn2["pre_neuron"]]
    syn2["global_post"] = [make_global_id(species, specimen, dataset_id, int(x)) for x in syn2["post_neuron"]]
    syn2.to_parquet(store.dir / "synapses.parquet", index=False)
    return {"connectome_id": connectome_id, "neurons": int(len(index)), "synapses": int(len(syn2))}
