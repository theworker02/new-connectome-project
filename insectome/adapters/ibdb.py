"""Insect Brain Database public artifact recovery (skeletons / projectomes)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd
import requests

from insectome import __version__
from insectome.connectome.store import ConnectomeStore
from insectome.guards import DownloadEstimate, check_download, format_bytes
from insectome.schemas.states import CoverageClaim, EvidenceState
from insectome.storage.paths import project_root, utc_now

BASE = "https://insectbraindb.org"


def list_experiment_files(experiment_id: int) -> list[dict]:
    r = requests.get(f"{BASE}/api/v2/experiment/{experiment_id}/file/", timeout=60)
    r.raise_for_status()
    return r.json()


def list_neurons(species_id: int) -> list[dict]:
    r = requests.get(f"{BASE}/api/v2/neuron/", params={"species": species_id}, timeout=60)
    r.raise_for_status()
    return r.json()


def neuron_reconstructions(neuron_id: int) -> list[dict]:
    r = requests.get(f"{BASE}/api/v2/neuron/reconstruction", params={"neuron": neuron_id}, timeout=60)
    r.raise_for_status()
    return r.json()


def import_bombus_cx_projectome(
    connectome_id: str = "bombus_terrestris_cx_projectome_v0.1",
    experiment_id: int = 61,
) -> ConnectomeStore:
    """Sayre et al. bumblebee CX projectome skeletons from IBdb experiment 61.

    This is an OBSERVED MORPHOLOGY / PROJECTOME layer — not a synaptic connectome.
    """
    files = list_experiment_files(experiment_id)
    sk_files = [f for f in files if "skeleton" in f.get("file_name", "").lower()]
    if not sk_files:
        raise RuntimeError(f"No skeleton files for IBdb experiment {experiment_id}")
    url = sk_files[0]["url"]
    # Unknown exact size; guard with soft estimate (~50–200 MB typical)
    check_download(
        DownloadEstimate(
            operation="ibdb_bombus_skeletons",
            expected_download_bytes=80 * 1024**2,
            expected_temporary_bytes=100 * 1024**2,
            expected_final_bytes=30 * 1024**2,
            notes="IBdb Bombus CX projectome skeletons (Sayre 2021)",
        ),
        authorize=False,
    )
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    raw = resp.content
    # Filename may say .gz even when payload is plain JSON
    if raw[:2] == b"\x1f\x8b":
        data = json.loads(gzip.decompress(raw).decode("utf-8"))
    else:
        data = json.loads(raw.decode("utf-8"))

    # CATMAID-style export: data is list of neurons with skeletons
    neurons = data.get("data", data if isinstance(data, list) else [])
    rows = []
    skeleton_dir = project_root() / "data" / "connectomes" / connectome_id / "skeletons"
    skeleton_dir.mkdir(parents=True, exist_ok=True)
    for i, neuron in enumerate(neurons):
        name = neuron.get("name") or neuron.get("neuron_name") or f"neuron_{i}"
        nid = int(neuron.get("id") or neuron.get("skeleton_id") or i + 1)
        skels = neuron.get("skeletons") or []
        n_nodes = 0
        for j, sk in enumerate(skels):
            swc_rows = sk.get("data") or []
            n_nodes += len(swc_rows)
            # persist compact json summary only (avoid huge SWC dump by default)
            (skeleton_dir / f"{nid}_{j}.meta.json").write_text(
                json.dumps({"neuron_id": nid, "name": name, "n_nodes": len(swc_rows)}, indent=2),
                encoding="utf-8",
            )
        rows.append(
            {
                "neuron_id": nid,
                "name": name,
                "dataset": "bombus_cx_projectome_sayre2021",
                "specimen": "Bombus terrestris CX SBEM",
                "species": "Bombus terrestris",
                "anatomical_region": "central complex",
                "evidence_state": str(EvidenceState.SOURCE_DOCUMENTED),
                "reconstruction_method": "CATMAID skeleton projectome (IBdb EIN-0000061)",
                "graph_layer": "OBSERVED_MORPHOLOGY",
                "n_skeleton_nodes": n_nodes,
            }
        )
    nodes = pd.DataFrame(rows)
    edges = pd.DataFrame(
        columns=[
            "pre_neuron_id",
            "post_neuron_id",
            "synapse_count",
            "dataset",
            "specimen",
            "anatomical_region",
            "verification_status",
            "graph_layer",
        ]
    )
    store = ConnectomeStore(connectome_id)
    store.save_tables(nodes, edges, None)
    local_bytes = sum(p.stat().st_size for p in store.dir.rglob("*") if p.is_file())
    store.write_manifest(
        {
            "species": "Bombus terrestris",
            "specimen": "Bombus CX SBEM (Sayre et al. 2021)",
            "dataset": "bombus_cx_projectome_sayre2021",
            "source": f"Insect Brain Database experiment {experiment_id}",
            "source_version": "EIN-0000061.1",
            "connectome_version": "v0.1",
            "coverage_claim": CoverageClaim.BRAIN_REGION,
            "graph_layers": {
                "OBSERVED_MORPHOLOGY": True,
                "OBSERVED_SYNAPTIC": False,
                "INFERRED_CIRCUIT": False,
            },
            "neurons": {
                "source": "IBdb CATMAID skeleton export",
                "count": int(len(nodes)),
                "reconstruction_method": "reused projectome skeletons",
            },
            "synapses": {
                "source": None,
                "count": 0,
                "detection_method": "NOT_AVAILABLE_PUBLICLY",
            },
            "raw_em": {"remote_location": "NOT_PUBLICLY_VERIFIED", "locally_stored": False},
            "new_computation": {"operations_performed": ["ibdb_skeleton_import", "normalize"]},
            "reuse_percentage": 100,
            "processing_level": 4,
            "storage": {"local_bytes": local_bytes, "remote_bytes_referenced": None},
            "limitations": [
                "PROJECTOME / morphology only — no public synaptic edge table",
                "Not the 2026 multi-species Heinze EM volumes",
            ],
            "software_version": __version__,
            "created_at": utc_now(),
        }
    )
    # CONNECTOME CARD
    card = store.dir / "CONNECTOME_CARD.md"
    card.write_text(
        "\n".join(
            [
                "# Connectome card — Bombus terrestris central complex projectome",
                "",
                "- Species: Bombus terrestris",
                "- Region: central complex",
                "- Graph layer: OBSERVED_MORPHOLOGY only",
                f"- Neurons: {len(nodes)}",
                "- Synapses / edges: 0 (not publicly released as synaptic connectome)",
                "- Source: Insect Brain Database experiment 61 (Sayre et al. eLife 2021)",
                "- Reuse: 100% (no new EM segmentation)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return store


def import_ibdb_species_morphology(
    species_id: int,
    species_name: str,
    connectome_id: str,
    anatomical_region: str = "central complex / brain (IBdb morphologies)",
) -> ConnectomeStore:
    """Import publicly listed IBdb neurons as morphology nodes (SWC metadata).

    These are typically dye-fill / light-level reconstructions unless otherwise noted.
    No synaptic edges are invented.
    """
    neurons = list_neurons(species_id)
    rows = []
    for n in neurons:
        nid = int(n["id"])
        recs = neuron_reconstructions(nid)
        swc_count = 0
        for rec in recs:
            for vf in rec.get("viewer_files") or []:
                if str(vf.get("file_name", "")).lower().endswith(".swc"):
                    swc_count += 1
        rows.append(
            {
                "neuron_id": nid,
                "name": n.get("name") or n.get("short_name"),
                "dataset": f"ibdb_species_{species_id}",
                "specimen": "UNKNOWN",
                "species": species_name,
                "anatomical_region": anatomical_region,
                "evidence_state": str(EvidenceState.SOURCE_DOCUMENTED),
                "reconstruction_method": "IBdb public neuron record (+ SWC if present)",
                "graph_layer": "OBSERVED_MORPHOLOGY",
                "n_swc_files": swc_count,
                "publication": str(n.get("publications")),
            }
        )
    nodes = pd.DataFrame(rows)
    edges = pd.DataFrame(
        columns=[
            "pre_neuron_id",
            "post_neuron_id",
            "synapse_count",
            "dataset",
            "specimen",
            "anatomical_region",
            "verification_status",
            "graph_layer",
        ]
    )
    store = ConnectomeStore(connectome_id)
    store.save_tables(nodes, edges, None)
    local_bytes = sum(p.stat().st_size for p in store.dir.glob("*") if p.is_file())
    store.write_manifest(
        {
            "species": species_name,
            "specimen": "UNKNOWN / mixed IBdb records",
            "dataset": f"ibdb_species_{species_id}",
            "source": "https://insectbraindb.org",
            "source_version": "api/v2",
            "connectome_version": "v0.1",
            "coverage_claim": CoverageClaim.PARTIAL_VOLUME,
            "graph_layers": {
                "OBSERVED_MORPHOLOGY": True,
                "OBSERVED_SYNAPTIC": False,
                "INFERRED_CIRCUIT": False,
            },
            "neurons": {"source": "IBdb", "count": int(len(nodes)), "reconstruction_method": "reused public morphologies"},
            "synapses": {"source": None, "count": 0, "detection_method": "NOT_IN_PUBLIC_IBDB_RECORD"},
            "raw_em": {"remote_location": None, "locally_stored": False},
            "new_computation": {"operations_performed": ["ibdb_neuron_catalog_import"]},
            "reuse_percentage": 100,
            "processing_level": 4,
            "storage": {"local_bytes": local_bytes},
            "limitations": [
                "Morphology catalog / projectome-like records — NOT observed synaptic connectome",
                "Not a substitute for unpublished Heinze 2026 EM CX reconstructions",
            ],
            "software_version": __version__,
            "created_at": utc_now(),
        }
    )
    (store.dir / "CONNECTOME_CARD.md").write_text(
        f"# Connectome card — {species_name} (IBdb morphologies)\n\n"
        f"- Neurons: {len(nodes)}\n"
        f"- Synaptic edges: 0\n"
        f"- Layer: OBSERVED_MORPHOLOGY only\n"
        f"- Local bytes: {format_bytes(local_bytes)}\n",
        encoding="utf-8",
    )
    return store
