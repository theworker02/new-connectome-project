"""neuPrint adapter — LEVEL 0 reuse when NEUPRINT_APPLICATION_CREDENTIALS is set."""

from __future__ import annotations

import os
from typing import Any


def neuprint_available() -> bool:
    return bool(os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN"))


def import_neuprint_subgraph(
    neuron_type_regex: str,
    *,
    dataset: str = "hemibrain:v1.2.1",
    connectome_id: str,
    species_label: str = "Drosophila melanogaster",
    anatomical_region: str = "central brain",
    fetch_edges: bool = True,
    min_weight: int = 1,
    catalog_only: bool = True,
) -> Any:
    """Import a typed subgraph from neuPrint — graph/index only, no raw EM.

    catalog_only packs store nodes (+ optional edges) and rebuild neuron_index
    without downloading skeletons/meshes. This is the dense/space-efficient path.
    """
    if not neuprint_available():
        raise RuntimeError(
            "neuPrint token required. Set NEUPRINT_APPLICATION_CREDENTIALS "
            "(obtain from https://neuprint.janelia.org account page)."
        )
    from neuprint import Client, NeuronCriteria as NC, fetch_adjacencies, fetch_neurons
    import pandas as pd

    from insectome import __version__
    from insectome.connectome.store import ConnectomeStore
    from insectome.schemas.states import CoverageClaim, EvidenceState
    from insectome.storage.paths import utc_now

    token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
    client = Client("neuprint.janelia.org", dataset=dataset, token=token)
    criteria = NC(type=neuron_type_regex, regex=True)
    neurons, _ = fetch_neurons(criteria, client=client)
    if neurons.empty:
        raise RuntimeError(f"No neurons matched type regex {neuron_type_regex!r} in {dataset}")

    if fetch_edges:
        neuron_df, conn_df = fetch_adjacencies(criteria, criteria, client=client)
        if "weight" in conn_df.columns and min_weight > 1:
            conn_df = conn_df[conn_df["weight"] >= min_weight]
    else:
        neuron_df = neurons
        conn_df = pd.DataFrame(columns=["bodyId_pre", "bodyId_post", "weight"])

    dataset_id = dataset.split(":")[0].replace("-", "_")
    nodes = pd.DataFrame(
        {
            "neuron_id": neuron_df["bodyId"].astype(int),
            "type": neuron_df.get("type"),
            "instance": neuron_df.get("instance"),
            "dataset": dataset_id,
            "specimen": dataset,
            "species": species_label,
            "anatomical_region": anatomical_region,
            "evidence_state": str(EvidenceState.SOURCE_DOCUMENTED),
            "reconstruction_method": f"neuPrint {dataset} reuse (no local EM)",
            "graph_layer": "OBSERVED_SYNAPTIC",
        }
    )
    if conn_df is not None and len(conn_df):
        edges = conn_df.rename(
            columns={"bodyId_pre": "pre_neuron_id", "bodyId_post": "post_neuron_id", "weight": "synapse_count"}
        )
        edges = edges[["pre_neuron_id", "post_neuron_id", "synapse_count"]].copy()
        edges["dataset"] = dataset_id
        edges["specimen"] = dataset
        edges["anatomical_region"] = anatomical_region
        edges["verification_status"] = EvidenceState.SOURCE_DOCUMENTED
        edges["graph_layer"] = "OBSERVED_SYNAPTIC"
    else:
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
            "species": species_label,
            "specimen": dataset,
            "dataset": dataset_id,
            "source": f"neuPrint {dataset}",
            "source_version": dataset,
            "connectome_version": "v0.1",
            "coverage_claim": CoverageClaim.BRAIN_REGION,
            "coverage_map": {
                "claim": str(CoverageClaim.BRAIN_REGION),
                "region": anatomical_region,
                "labels": ["catalog_only" if catalog_only else "subgraph", "neuprint", "no_local_em"],
            },
            "graph_layers": {
                "OBSERVED_MORPHOLOGY": False,
                "OBSERVED_SYNAPTIC": bool(len(edges)),
                "INFERRED_CIRCUIT": False,
            },
            "neurons": {
                "source": "neuPrint",
                "count": int(len(nodes)),
                "reconstruction_method": "reused proofread connectome",
                "filter": neuron_type_regex,
            },
            "synapses": {
                "source": "neuPrint adjacency weights",
                "count": int(len(edges)),
                "detection_method": "reused",
            },
            "raw_em": {
                "remote_location": "remote EM via neuPrint/Neuroglancer ecosystem — do not bulk download",
                "locally_stored": False,
            },
            "atlas": {
                "catalog_only": catalog_only,
                "skeletons_local": False,
                "em_evidence": False,
            },
            "new_computation": {"operations_performed": ["neuprint_query", "normalize", "catalog_index"]},
            "reuse_percentage": 100,
            "processing_level": 0,
            "storage": {"local_bytes": local_bytes, "remote_bytes_referenced": None},
            "software_version": __version__,
            "created_at": utc_now(),
        }
    )
    (store.dir / "CONNECTOME_CARD.md").write_text(
        f"# Connectome card — {connectome_id}\n\n"
        f"- Dataset: {dataset}\n"
        f"- Filter: `{neuron_type_regex}`\n"
        f"- Neurons: {len(nodes)}\n"
        f"- Edges: {len(edges)}\n"
        f"- Layer: OBSERVED_SYNAPTIC (reused)\n"
        f"- Catalog-only (no local skeletons): {catalog_only}\n"
        f"- Local bytes: {local_bytes}\n"
        f"- Raw EM locally stored: false\n",
        encoding="utf-8",
    )
    return store


def import_hemibrain_subgraph(
    neuron_type_regex: str = "PEN_a.*",
    dataset: str = "hemibrain:v1.2.1",
    connectome_id: str = "hemibrain_pen_a_v0.1",
    species_label: str = "Drosophila melanogaster",
    anatomical_region: str = "central brain",
) -> Any:
    """Import a small typed subgraph from neuPrint — no raw EM."""
    return import_neuprint_subgraph(
        neuron_type_regex,
        dataset=dataset,
        connectome_id=connectome_id,
        species_label=species_label,
        anatomical_region=anatomical_region,
        fetch_edges=True,
        catalog_only=True,
    )
