"""Persistent candidate ledger under data/autonomy/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from insectome.autonomy.models import Candidate, CycleReport
from insectome.storage.paths import project_root, utc_now


def autonomy_dir() -> Path:
    path = project_root() / "data" / "autonomy"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_path() -> Path:
    return autonomy_dir() / "candidates.json"


def history_path() -> Path:
    return autonomy_dir() / "cycle_history.jsonl"


def load_ledger() -> dict[str, Candidate]:
    path = ledger_path()
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Candidate] = {}
    for item in raw.get("candidates", []):
        c = Candidate.model_validate(item)
        out[c.candidate_id] = c
    return out


def save_ledger(candidates: dict[str, Candidate], *, meta: dict[str, Any] | None = None) -> Path:
    path = ledger_path()
    payload = {
        "version": 1,
        "updated_at": utc_now(),
        "meta": meta or {},
        "candidates": [c.model_dump(mode="json") for c in sorted(candidates.values(), key=lambda x: x.candidate_id)],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def append_cycle_report(report: CycleReport) -> Path:
    path = history_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report.model_dump(mode="json")) + "\n")
    return path


def merge_candidate(existing: Candidate | None, incoming: Candidate) -> Candidate:
    """Preserve first_seen / status progression; refresh evidence and scores."""
    now = utc_now()
    if existing is None:
        incoming.first_seen = incoming.first_seen or now
        incoming.last_seen = now
        return incoming

    merged = existing.model_copy(deep=True)
    merged.last_seen = now
    merged.title = incoming.title or merged.title
    merged.species = incoming.species or merged.species
    merged.reuse_score = max(merged.reuse_score, incoming.reuse_score)
    if incoming.processing_level is not None:
        merged.processing_level = incoming.processing_level
    if incoming.plan is not None:
        merged.plan = incoming.plan
    if incoming.notes:
        merged.notes = incoming.notes
    # Deduplicate evidence by kind+source+detail
    seen = {(e.kind, e.source, e.detail) for e in merged.evidence}
    for e in incoming.evidence:
        key = (e.kind, e.source, e.detail)
        if key not in seen:
            merged.evidence.append(e)
            seen.add(key)
    for tag in incoming.tags:
        if tag not in merged.tags:
            merged.tags.append(tag)
    # Don't downgrade terminal statuses unless new evidence upgrades
    from insectome.autonomy.models import CandidateStatus

    if existing.status in {CandidateStatus.AUTO_INGESTED, CandidateStatus.REJECTED}:
        pass
    elif incoming.status != CandidateStatus.DISCOVERED:
        merged.status = incoming.status
    return merged
