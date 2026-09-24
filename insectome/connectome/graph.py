"""Connectome graph generation — sparse, provenance-preserving."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from insectome.schemas.states import EvidenceState
from insectome.synapses.records import SynapseRecord


def build_connectome_graph(
    synapses: list[SynapseRecord],
    dataset_id: str,
    specimen_id: str,
    anatomical_region: str,
    min_synapses: int = 1,
) -> tuple[nx.DiGraph, pd.DataFrame, pd.DataFrame]:
    """Aggregate synapses into directed edges. Drops edges lacking neuron IDs."""
    rows = []
    for s in synapses:
        if s.pre_neuron is None or s.post_neuron is None:
            continue
        if s.pre_neuron == s.post_neuron:
            # Keep as QC flag later; exclude from graph edges for now
            continue
        rows.append(
            {
                "pre_neuron_id": int(s.pre_neuron),
                "post_neuron_id": int(s.post_neuron),
                "synapse_id": s.synapse_id,
                "confidence": s.confidence,
                "verification_status": s.verification_state,
            }
        )
    syn_df = pd.DataFrame(rows)
    if syn_df.empty:
        edges = pd.DataFrame(
            columns=[
                "pre_neuron_id",
                "post_neuron_id",
                "synapse_count",
                "mean_confidence",
                "verification_status",
                "dataset",
                "specimen",
                "anatomical_region",
            ]
        )
        nodes = pd.DataFrame(columns=["neuron_id", "dataset", "specimen", "anatomical_region"])
        return nx.DiGraph(), nodes, edges

    grouped = (
        syn_df.groupby(["pre_neuron_id", "post_neuron_id"], as_index=False)
        .agg(
            synapse_count=("synapse_id", "count"),
            mean_confidence=("confidence", "mean"),
            verification_status=("verification_status", "first"),
        )
    )
    grouped = grouped[grouped["synapse_count"] >= min_synapses].copy()
    grouped["dataset"] = dataset_id
    grouped["specimen"] = specimen_id
    grouped["anatomical_region"] = anatomical_region

    neuron_ids = sorted(set(grouped["pre_neuron_id"]) | set(grouped["post_neuron_id"]))
    nodes = pd.DataFrame(
        {
            "neuron_id": neuron_ids,
            "dataset": dataset_id,
            "specimen": specimen_id,
            "anatomical_region": anatomical_region,
            "evidence_state": str(EvidenceState.SOURCE_DOCUMENTED),
        }
    )

    g = nx.DiGraph()
    for _, row in nodes.iterrows():
        attrs = {k: (str(v) if not isinstance(v, (int, float, bool)) else v) for k, v in row.to_dict().items()}
        g.add_node(int(row.neuron_id), **attrs)
    for _, row in grouped.iterrows():
        g.add_edge(
            int(row.pre_neuron_id),
            int(row.post_neuron_id),
            synapse_count=int(row.synapse_count),
            mean_confidence=float(row.mean_confidence),
            verification_status=str(row.verification_status),
            dataset=str(dataset_id),
            specimen=str(specimen_id),
            anatomical_region=str(anatomical_region),
        )
    return g, nodes, grouped


def export_connectome(
    graph: nx.DiGraph,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    synapses: pd.DataFrame,
    out_dir: Path,
    metadata: dict,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    graphml = out_dir / "connectome.graphml"
    nx.write_graphml(graph, graphml)
    paths["graphml"] = graphml
    nodes_p = out_dir / "nodes.parquet"
    edges_p = out_dir / "edges.parquet"
    syn_p = out_dir / "synapses.parquet"
    nodes.to_parquet(nodes_p, index=False)
    edges.to_parquet(edges_p, index=False)
    synapses.to_parquet(syn_p, index=False)
    paths["nodes"] = nodes_p
    paths["edges"] = edges_p
    paths["synapses"] = syn_p

    # Sparse adjacency for numeric neuron ids remapped to [0..n)
    if len(nodes):
        id_list = nodes["neuron_id"].astype(int).tolist()
        index = {nid: i for i, nid in enumerate(id_list)}
        n = len(id_list)
        mat = np.zeros((n, n), dtype=np.int32)
        for _, e in edges.iterrows():
            i = index[int(e.pre_neuron_id)]
            j = index[int(e.post_neuron_id)]
            mat[i, j] = int(e.synapse_count)
        adj_path = out_dir / "adjacency_sparse.npz"
        # Store dense-but-small ROI matrix sparsely
        from scipy import sparse

        sparse.save_npz(adj_path, sparse.csr_matrix(mat))
        paths["adjacency"] = adj_path
        metadata = {**metadata, "neuron_id_order": id_list}

    meta_path = out_dir / "metadata.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    paths["metadata"] = meta_path
    return paths
