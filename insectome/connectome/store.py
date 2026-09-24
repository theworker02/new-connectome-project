"""Federated connectome store — graph-first, sparse, compact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from insectome.storage.paths import project_root


def connectomes_root() -> Path:
    return project_root() / "data" / "connectomes"


class ConnectomeStore:
    def __init__(self, connectome_id: str, root: Path | None = None):
        self.connectome_id = connectome_id
        self.dir = (root or connectomes_root()) / connectome_id
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def manifest_path(self) -> Path:
        return self.dir / "connectome_manifest.json"

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def read_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def save_tables(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        synapses: pd.DataFrame | None = None,
    ) -> None:
        nodes.to_parquet(self.dir / "nodes.parquet", index=False)
        edges.to_parquet(self.dir / "edges.parquet", index=False)
        if synapses is not None and len(synapses):
            synapses.to_parquet(self.dir / "synapses.parquet", index=False)
        g = nx.DiGraph()
        for _, row in nodes.iterrows():
            g.add_node(int(row["neuron_id"]), **{k: str(v) for k, v in row.items() if k != "neuron_id"})
        for _, row in edges.iterrows():
            g.add_edge(
                int(row["pre_neuron_id"]),
                int(row["post_neuron_id"]),
                weight=int(row.get("synapse_count", 1)),
                **{k: str(v) for k, v in row.items() if k not in {"pre_neuron_id", "post_neuron_id"}},
            )
        nx.write_graphml(g, self.dir / "connectome.graphml")

    def load_nodes(self) -> pd.DataFrame:
        return pd.read_parquet(self.dir / "nodes.parquet")

    def load_edges(self) -> pd.DataFrame:
        return pd.read_parquet(self.dir / "edges.parquet")

    def load_synapses(self) -> pd.DataFrame | None:
        p = self.dir / "synapses.parquet"
        return pd.read_parquet(p) if p.exists() else None

    def neuron(self, neuron_id: int) -> dict | None:
        nodes = self.load_nodes()
        hit = nodes[nodes["neuron_id"] == neuron_id]
        if hit.empty:
            return None
        return hit.iloc[0].to_dict()

    def partners(self, neuron_id: int) -> pd.DataFrame:
        edges = self.load_edges()
        out = edges[edges["pre_neuron_id"] == neuron_id].copy()
        out["direction"] = "out"
        incoming = edges[edges["post_neuron_id"] == neuron_id].copy()
        incoming["direction"] = "in"
        return pd.concat([out, incoming], ignore_index=True)

    def path(self, source: int, target: int, cutoff: int = 4) -> list[int] | None:
        edges = self.load_edges()
        g = nx.DiGraph()
        for _, row in edges.iterrows():
            g.add_edge(int(row.pre_neuron_id), int(row.post_neuron_id))
        try:
            return nx.shortest_path(g, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None


def list_connectomes(root: Path | None = None) -> list[str]:
    base = root or connectomes_root()
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "connectome_manifest.json").exists() or (p / "nodes.parquet").exists())
