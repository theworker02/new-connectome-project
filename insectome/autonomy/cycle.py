"""One autonomy cycle: probe → score → auto-ingest → rebuild catalogs → ledger."""

from __future__ import annotations

from typing import Any

from insectome.atlas.service import rebuild_full_neuron_catalog
from insectome.autonomy.budget import AutonomyBudget, format_bytes
from insectome.autonomy.executor import execute_candidate
from insectome.autonomy.ledger import (
    append_cycle_report,
    load_ledger,
    merge_candidate,
    save_ledger,
)
from insectome.autonomy.models import CandidateStatus, CycleReport
from insectome.autonomy.policies import apply_policy
from insectome.autonomy.probes import run_all_probes
from insectome.connectome.store import list_connectomes
from insectome.storage.paths import project_root, utc_now


def run_autonomy_cycle(
    *,
    auto_ingest: bool = True,
    rebuild_catalogs: bool = True,
    budget: AutonomyBudget | None = None,
) -> dict[str, Any]:
    """Run a full discovery + optional ingest cycle.

    Returns a JSON-serializable summary suitable for CLI / API / studio.
    """
    budget = budget or AutonomyBudget()
    started = utc_now()
    report = CycleReport(
        started_at=started,
        budget_used_bytes=budget.used_bytes(),
        budget_soft_bytes=budget.pack_soft_bytes,
        budget_hard_bytes=budget.pack_hard_bytes,
    )

    ledger = load_ledger()
    probed, probe_names, probe_errors = run_all_probes(budget)
    report.probes_run = probe_names
    report.errors.extend(probe_errors)

    new_count = 0
    updated = 0
    for incoming in probed:
        prior = ledger.get(incoming.candidate_id)
        merged = merge_candidate(prior, incoming)
        merged = apply_policy(merged, budget)
        if prior is None:
            new_count += 1
        else:
            updated += 1
        ledger[incoming.candidate_id] = merged

    report.candidates_new = new_count
    report.candidates_updated = updated

    ingested: list[str] = []
    if auto_ingest:
        queued = [
            c
            for c in ledger.values()
            if c.status == CandidateStatus.QUEUED and c.plan and c.plan.auto_eligible
        ]
        # Prefer higher reuse_score
        queued.sort(key=lambda c: c.reuse_score, reverse=True)
        for cand in queued:
            # Refresh budget between jobs
            try:
                result = execute_candidate(cand, budget)
                ledger[cand.candidate_id] = cand
                if result.get("ok"):
                    ingested.append(cand.local_pack_id or cand.candidate_id)
                    report.auto_ingested.append(cand.candidate_id)
                elif cand.status == CandidateStatus.BLOCKED:
                    report.blocked.append(cand.candidate_id)
                else:
                    report.needs_review.append(cand.candidate_id)
            except Exception as exc:  # noqa: BLE001
                cand.status = CandidateStatus.BLOCKED
                cand.last_action = f"error:{exc}"
                ledger[cand.candidate_id] = cand
                report.errors.append(f"ingest {cand.candidate_id}: {exc}")
                report.blocked.append(cand.candidate_id)

    for c in ledger.values():
        if c.status == CandidateStatus.NEEDS_REVIEW and c.candidate_id not in report.needs_review:
            report.needs_review.append(c.candidate_id)

    rebuilt: list[str] = []
    if rebuild_catalogs:
        for cid in list_connectomes():
            try:
                rebuild_full_neuron_catalog(cid)
                rebuilt.append(cid)
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"catalog {cid}: {exc}")
    report.catalogs_rebuilt = rebuilt

    report.finished_at = utc_now()
    report.budget_used_bytes = budget.used_bytes()
    report.notes = (
        f"packs={format_bytes(report.budget_used_bytes)} / "
        f"soft={format_bytes(report.budget_soft_bytes)} / "
        f"hard={format_bytes(report.budget_hard_bytes)}; "
        f"auto_ingested={len(report.auto_ingested)}"
    )

    save_ledger(
        ledger,
        meta={
            "last_cycle": report.model_dump(mode="json"),
            "pack_bytes": report.budget_used_bytes,
        },
    )
    append_cycle_report(report)

    # Human-readable snapshot
    md_path = project_root() / "reports" / "AUTONOMY_STATUS.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Autonomy status",
        "",
        f"- Last cycle: `{report.finished_at}`",
        f"- Pack footprint: **{format_bytes(report.budget_used_bytes)}** "
        f"(soft {format_bytes(report.budget_soft_bytes)}, hard {format_bytes(report.budget_hard_bytes)})",
        f"- Probes: {', '.join(report.probes_run)}",
        f"- New candidates: {report.candidates_new}",
        f"- Auto-ingested: {', '.join(report.auto_ingested) or '—'}",
        f"- Needs review: {len(report.needs_review)}",
        f"- Blocked: {len(report.blocked)}",
        "",
        "## Candidates",
        "",
        "| Status | Score | ID | Species | Pack |",
        "|---|---:|---|---|---|",
    ]
    for c in sorted(ledger.values(), key=lambda x: (-x.reuse_score, x.candidate_id)):
        lines.append(
            f"| {c.status.value} | {c.reuse_score} | `{c.candidate_id}` | "
            f"{c.species or '—'} | `{c.local_pack_id or (c.plan.connectome_id if c.plan else '—')}` |"
        )
    if report.errors:
        lines.extend(["", "## Errors", ""])
        for e in report.errors:
            lines.append(f"- {e}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from insectome.autonomy.ledger import ledger_path

    return {
        "report": report.model_dump(mode="json"),
        "candidates": [c.model_dump(mode="json") for c in ledger.values()],
        "ledger_path": str(ledger_path()),
        "status_md": str(md_path),
        "ingested_packs": ingested,
    }
