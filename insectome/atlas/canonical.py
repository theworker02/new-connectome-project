"""Canonical neuron identity and atlas data model."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return s or "unknown"


def make_global_id(species: str, specimen: str, dataset: str, source_id: int | str) -> str:
    return f"{slug(species)}/{slug(specimen)}/{slug(dataset)}/{source_id}"


class NeuronCanonical(BaseModel):
    global_id: str
    source_id: int | str
    species: str
    specimen: str | None = None
    dataset: str
    region: str | None = None
    name: str | None = None
    cell_type: str | None = None
    hemisphere: str | None = None
    soma: list[float] | None = None
    reconstruction_state: str | None = None
    proofreading_state: str | None = None
    confidence: float | None = None
    graph_layer: str | None = None
    coverage_claim: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    pre_count: int = 0
    post_count: int = 0
    degree_in: int = 0
    degree_out: int = 0
    has_skeleton: bool = False
    has_mesh: bool = False
    n_skeleton_vertices: int = 0


COVERAGE_LABELS = (
    "COMPLETE_OR_PUBLISHED",
    "HIGH_CONFIDENCE_RECONSTRUCTION",
    "PARTIAL_RECONSTRUCTION",
    "MORPHOLOGY_ONLY",
    "SYNAPTIC_CONNECTOME",
    "EM_AVAILABLE_UNPROCESSED",
    "INSUFFICIENT_RESOLUTION",
    "NO_PUBLIC_DATA",
    "UNKNOWN",
)
