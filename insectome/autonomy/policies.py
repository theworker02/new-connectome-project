"""Auto-ingest eligibility policies (evidence + budget + no-EM)."""

from __future__ import annotations

from insectome.autonomy.budget import AutonomyBudget, EM_REFUSE_BYTES
from insectome.autonomy.models import Candidate, CandidateStatus, EvidenceKind, IngestPlan
from insectome.connectome.store import list_connectomes


# Pre-approved dense catalog recipes: graph/index only, no skeletons.
CATALOG_RECIPES: list[dict] = [
    {
        "candidate_id": "neuprint:hemibrain:cx_catalog",
        "title": "Hemibrain central complex catalog (graph)",
        "species": "Drosophila melanogaster",
        "connectome_id": "hemibrain_cx_catalog_v0.1",
        "dataset": "hemibrain:v1.2.1",
        "type_regex": r"^(EPG|PEN|PEG|Delta7|PFN|PFL|EL|ER|ExR|LNO).*",
        "anatomical_region": "central complex",
        "tags": ["catalog", "CX", "synaptic", "dense"],
        "reuse_score": 95,
        "processing_level": 0,
        # ~950 neurons + edges ≈ a few MB
        "estimated_final_bytes": 12 * 1024**2,
        "min_weight": 1,
    },
    {
        "candidate_id": "neuprint:hemibrain:mb_catalog",
        "title": "Hemibrain mushroom body catalog (graph)",
        "species": "Drosophila melanogaster",
        "connectome_id": "hemibrain_mb_catalog_v0.1",
        "dataset": "hemibrain:v1.2.1",
        "type_regex": r"^(KC|MBON|DAN|APL).*",
        "anatomical_region": "mushroom body",
        "tags": ["catalog", "MB", "synaptic", "dense"],
        "reuse_score": 92,
        "processing_level": 0,
        "estimated_final_bytes": 80 * 1024**2,
        "min_weight": 3,
    },
    {
        "candidate_id": "neuprint:optic-lobe:motion_catalog",
        "title": "Optic lobe motion detectors catalog (graph)",
        "species": "Drosophila melanogaster",
        "connectome_id": "optic_lobe_motion_catalog_v0.1",
        "dataset": "optic-lobe:v1.1",
        "type_regex": r"^(T4|T5).*",
        "anatomical_region": "optic lobe",
        "tags": ["catalog", "vision", "synaptic", "dense"],
        "reuse_score": 93,
        "processing_level": 0,
        # ~6.8k T4/T5 — keep edges sparse via min_weight
        "estimated_final_bytes": 120 * 1024**2,
        "min_weight": 5,
    },
]


WATCHLIST_CANDIDATES: list[dict] = [
    {
        "candidate_id": "registry:flywire_codex",
        "title": "FlyWire Codex whole-brain connectome",
        "species": "Drosophila melanogaster",
        "source_system": "registry",
        "reuse_score": 88,
        "processing_level": 0,
        "tags": ["watch", "LEVEL-0", "pending_adapter"],
        "notes": "Adapter pending — do not auto-ingest. Track public Codex API / dumps.",
        "url": "https://codex.flywire.ai/",
    },
    {
        "candidate_id": "registry:banc_drosophila_2025",
        "title": "BANC brain-and-nerve-cord connectome",
        "species": "Drosophila melanogaster",
        "source_system": "registry",
        "reuse_score": 80,
        "processing_level": 0,
        "tags": ["watch", "benchmark", "no_wholesale_recon"],
        "notes": "Benchmark / comparative reference only — not a reconstruction target.",
        "url": "https://bossdb.org/projects",
    },
    {
        "candidate_id": "neuprint:male-cns",
        "title": "neuPrint male CNS (brain + VNC)",
        "species": "Drosophila melanogaster",
        "source_system": "neuprint",
        "reuse_score": 90,
        "processing_level": 0,
        "tags": ["watch", "neuprint", "male-cns"],
        "notes": "Live neuPrint dataset — candidate for typed subgraph catalogs after sampling size.",
        "url": "https://neuprint.janelia.org/?dataset=male-cns:v1.0",
    },
    {
        "candidate_id": "ibdb:apis_mellifera",
        "title": "IBdb Apis mellifera morphology",
        "species": "Apis mellifera",
        "source_system": "ibdb",
        "reuse_score": 70,
        "processing_level": 4,
        "tags": ["watch", "ibdb", "morphology"],
        "notes": "~68 IBdb reconstructions — morphology layer; verify experiment files before ingest.",
        "url": "https://insectbraindb.org/",
    },
]


def plan_for_recipe(recipe: dict, budget: AutonomyBudget) -> IngestPlan:
    pack_id = recipe["connectome_id"]
    already = pack_id in list_connectomes()
    est = int(recipe.get("estimated_final_bytes") or 0)
    ok, reason = budget.may_auto_ingest(est)
    if already:
        return IngestPlan(
            method="neuprint_subgraph",
            connectome_id=pack_id,
            dataset=recipe["dataset"],
            type_regex=recipe["type_regex"],
            species_label=recipe.get("species"),
            anatomical_region=recipe.get("anatomical_region"),
            fetch_edges=True,
            min_weight=int(recipe.get("min_weight") or 1),
            include_skeletons=False,
            estimated_final_bytes=est,
            auto_eligible=False,
            block_reason="already_local",
        )
    return IngestPlan(
        method="neuprint_subgraph",
        connectome_id=pack_id,
        dataset=recipe["dataset"],
        type_regex=recipe["type_regex"],
        species_label=recipe.get("species"),
        anatomical_region=recipe.get("anatomical_region"),
        fetch_edges=True,
        min_weight=int(recipe.get("min_weight") or 1),
        include_skeletons=False,
        estimated_final_bytes=est,
        auto_eligible=ok,
        block_reason=None if ok else reason,
    )


def apply_policy(candidate: Candidate, budget: AutonomyBudget) -> Candidate:
    """Mutate status / plan based on evidence and budget."""
    c = candidate.model_copy(deep=True)
    packs = set(list_connectomes())

    if c.local_pack_id and c.local_pack_id in packs:
        c.status = CandidateStatus.AUTO_INGESTED
        return c

    if c.plan and c.plan.connectome_id and c.plan.connectome_id in packs:
        c.status = CandidateStatus.AUTO_INGESTED
        c.local_pack_id = c.plan.connectome_id
        return c

    kinds = {e.kind for e in c.evidence}
    has_live = bool(
        kinds
        & {
            EvidenceKind.NEUPRINT_DATASET,
            EvidenceKind.NEUPRINT_TYPE_COUNT,
            EvidenceKind.IBDB_SPECIES,
            EvidenceKind.IBDB_EXPERIMENT,
            EvidenceKind.REGISTRY_RECORD,
        }
    )
    if has_live and c.status == CandidateStatus.DISCOVERED:
        c.status = CandidateStatus.EVIDENCE_VERIFIED

    if c.plan is None:
        c.status = CandidateStatus.NEEDS_REVIEW
        return c

    if c.plan.include_skeletons:
        c.plan.auto_eligible = False
        c.plan.block_reason = "skeletons_not_auto"
        c.status = CandidateStatus.NEEDS_REVIEW
        return c

    if c.plan.estimated_final_bytes >= EM_REFUSE_BYTES:
        c.plan.auto_eligible = False
        c.plan.block_reason = "em_or_huge"
        c.status = CandidateStatus.BLOCKED
        return c

    if c.plan.method != "neuprint_subgraph":
        c.plan.auto_eligible = False
        c.plan.block_reason = c.plan.block_reason or "method_needs_review"
        c.status = CandidateStatus.NEEDS_REVIEW
        return c

    ok, reason = budget.may_auto_ingest(c.plan.estimated_final_bytes)
    c.plan.auto_eligible = ok and not c.plan.block_reason
    if not ok:
        c.plan.block_reason = reason
        c.status = CandidateStatus.BLOCKED
    elif c.plan.auto_eligible:
        c.status = CandidateStatus.QUEUED
    else:
        c.status = CandidateStatus.NEEDS_REVIEW
    return c
