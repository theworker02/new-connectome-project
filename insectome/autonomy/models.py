"""Candidate and cycle report models for autonomous ingestion."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CandidateStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    QUEUED = "QUEUED"
    AUTO_INGESTED = "AUTO_INGESTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class EvidenceKind(str, Enum):
    NEUPRINT_DATASET = "NEUPRINT_DATASET"
    NEUPRINT_TYPE_COUNT = "NEUPRINT_TYPE_COUNT"
    IBDB_SPECIES = "IBDB_SPECIES"
    IBDB_EXPERIMENT = "IBDB_EXPERIMENT"
    REGISTRY_RECORD = "REGISTRY_RECORD"
    PUBLICATION_DOI = "PUBLICATION_DOI"
    LOCAL_PACK = "LOCAL_PACK"


class EvidenceItem(BaseModel):
    kind: EvidenceKind
    source: str
    detail: str | None = None
    url: str | None = None
    observed_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IngestPlan(BaseModel):
    """How to materialize a candidate as a local pack (graph/index only)."""

    method: str  # neuprint_subgraph | ibdb_morphology | none
    connectome_id: str | None = None
    dataset: str | None = None
    type_regex: str | None = None
    species_label: str | None = None
    anatomical_region: str | None = None
    fetch_edges: bool = True
    min_weight: int = 1
    include_skeletons: bool = False
    estimated_final_bytes: int = 0
    auto_eligible: bool = False
    block_reason: str | None = None


class Candidate(BaseModel):
    candidate_id: str
    title: str
    species: str | None = None
    source_system: str
    status: CandidateStatus = CandidateStatus.DISCOVERED
    reuse_score: int = Field(ge=0, le=100, default=0)
    processing_level: int | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    plan: IngestPlan | None = None
    local_pack_id: str | None = None
    notes: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    last_action: str | None = None
    tags: list[str] = Field(default_factory=list)


class CycleReport(BaseModel):
    started_at: str
    finished_at: str | None = None
    budget_used_bytes: int = 0
    budget_soft_bytes: int = 0
    budget_hard_bytes: int = 0
    probes_run: list[str] = Field(default_factory=list)
    candidates_new: int = 0
    candidates_updated: int = 0
    auto_ingested: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    catalogs_rebuilt: list[str] = Field(default_factory=list)
    notes: str | None = None
