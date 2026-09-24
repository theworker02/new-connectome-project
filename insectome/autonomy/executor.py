"""Execute safe auto-ingest jobs from the candidate ledger."""

from __future__ import annotations

from typing import Any

from insectome.adapters.neuprint_adapter import import_neuprint_subgraph, neuprint_available
from insectome.atlas.service import rebuild_full_neuron_catalog
from insectome.autonomy.budget import AutonomyBudget
from insectome.autonomy.models import Candidate, CandidateStatus
from insectome.connectome.store import list_connectomes
from insectome.storage.paths import utc_now


def execute_candidate(candidate: Candidate, budget: AutonomyBudget) -> dict[str, Any]:
    """Run one queued candidate. Returns action report; mutates candidate in place."""
    plan = candidate.plan
    if plan is None or not plan.auto_eligible:
        return {"candidate_id": candidate.candidate_id, "ok": False, "reason": "not_eligible"}

    ok, reason = budget.may_auto_ingest(plan.estimated_final_bytes)
    if not ok:
        candidate.status = CandidateStatus.BLOCKED
        plan.block_reason = reason
        candidate.last_action = f"blocked:{reason}"
        return {"candidate_id": candidate.candidate_id, "ok": False, "reason": reason}

    if plan.connectome_id and plan.connectome_id in list_connectomes():
        candidate.status = CandidateStatus.AUTO_INGESTED
        candidate.local_pack_id = plan.connectome_id
        candidate.last_action = "already_local"
        return {"candidate_id": candidate.candidate_id, "ok": True, "reason": "already_local"}

    if plan.method != "neuprint_subgraph":
        candidate.status = CandidateStatus.NEEDS_REVIEW
        candidate.last_action = "method_unsupported"
        return {"candidate_id": candidate.candidate_id, "ok": False, "reason": "method_unsupported"}

    if not neuprint_available():
        candidate.status = CandidateStatus.BLOCKED
        candidate.last_action = "neuprint_token_missing"
        return {"candidate_id": candidate.candidate_id, "ok": False, "reason": "neuprint_token_missing"}

    if not plan.connectome_id or not plan.type_regex or not plan.dataset:
        candidate.status = CandidateStatus.BLOCKED
        candidate.last_action = "incomplete_plan"
        return {"candidate_id": candidate.candidate_id, "ok": False, "reason": "incomplete_plan"}

    store = import_neuprint_subgraph(
        plan.type_regex,
        dataset=plan.dataset,
        connectome_id=plan.connectome_id,
        species_label=plan.species_label or "Drosophila melanogaster",
        anatomical_region=plan.anatomical_region or "brain",
        fetch_edges=plan.fetch_edges,
        min_weight=int(plan.min_weight or 1),
        catalog_only=not plan.include_skeletons,
    )
    catalog = rebuild_full_neuron_catalog(plan.connectome_id)
    local_bytes = sum(p.stat().st_size for p in store.dir.rglob("*") if p.is_file())
    candidate.status = CandidateStatus.AUTO_INGESTED
    candidate.local_pack_id = plan.connectome_id
    candidate.last_action = f"ingested:{utc_now()}"
    candidate.notes = (candidate.notes or "") + f" | local_bytes={local_bytes}"
    return {
        "candidate_id": candidate.candidate_id,
        "ok": True,
        "connectome_id": plan.connectome_id,
        "neurons": catalog.get("neurons"),
        "local_bytes": local_bytes,
    }
