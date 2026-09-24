"""Phase 2 storage and compute-savings reports."""

from __future__ import annotations

from pathlib import Path

from insectome.guards import format_bytes
from insectome.reuse.manifest import analyze_registry
from insectome.schemas.dataset import load_registry
from insectome.storage.paths import project_root


def write_phase2_reports() -> dict[str, str]:
    root = project_root()
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    manifests = analyze_registry(load_registry().datasets)

    storage_lines = [
        "# Storage report",
        "",
        "Objective: a multi-TB remote dataset should require only MB–low-GB locally.",
        "",
        "| dataset_id | reuse % | level | remote raw (est.) | local required (est.) | offline pack (est.) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for m in manifests:
        storage_lines.append(
            "| {id} | {ru} | {lv} | {rem} | {loc} | {pack} |".format(
                id=m.dataset_id,
                ru=m.reuse_score,
                lv=m.processing_level,
                rem=format_bytes(m.remote_raw_bytes_estimate or 0) if m.remote_raw_bytes_estimate else "UNKNOWN",
                loc=format_bytes(m.local_required_bytes_estimate or 0) if m.local_required_bytes_estimate else "UNKNOWN",
                pack=format_bytes(m.offline_pack_bytes_estimate or 0) if m.offline_pack_bytes_estimate else "UNKNOWN",
            )
        )
    storage_lines += [
        "",
        "## Notes",
        "",
        "- Estimates marked UNKNOWN when publishers do not state sizes.",
        "- `local required` assumes reuse-first import (graph/metadata), not full EM.",
        "- Cache hard limit default: 10 GB (`~/.insectome/cache`).",
        "",
    ]
    storage_path = reports / "STORAGE_REPORT.md"
    storage_path.write_text("\n".join(storage_lines), encoding="utf-8")

    compute_lines = [
        "# Compute savings (estimates)",
        "",
        "Values are order-of-magnitude estimates for planning — not audited billing figures.",
        "",
        "| dataset_id | if reconstructed from EM (est.) | reuse-based path | avoided work |",
        "|---|---|---|---|",
    ]
    for m in manifests:
        if m.processing_level >= 99:
            avoided = "N/A — inaccessible"
            full = "N/A"
            reuse = "wait for deposit"
        elif m.reuse_score >= 90:
            full = "weeks–months GPU/CPU + multi-TB I/O (ESTIMATE)"
            reuse = "seconds–minutes API/HDF annotation import"
            avoided = "segmentation + synapse detection + proofreading"
        elif m.reuse_score >= 60:
            full = "days–weeks (ESTIMATE)"
            reuse = "hours on missing stages only"
            avoided = "re-segmentation of existing labels"
        elif m.reuse_score == 0 and m.raw_em_available:
            full = "ROI-first days (ESTIMATE); full volume last resort"
            reuse = "none yet — gap fill only"
            avoided = "0% until partial products appear"
        else:
            full = "UNKNOWN"
            reuse = "UNKNOWN"
            avoided = "UNKNOWN"
        compute_lines.append(f"| {m.dataset_id} | {full} | {reuse} | {avoided} |")
    compute_lines += [
        "",
        "## Principle",
        "",
        "Ideal operation: **zero new EM segmentation**.",
        "Second-best: tiny unresolved ROI.",
        "Full-volume reconstruction: absolute last resort.",
        "",
    ]
    compute_path = reports / "COMPUTE_SAVINGS.md"
    compute_path.write_text("\n".join(compute_lines), encoding="utf-8")
    return {"storage": str(storage_path), "compute": str(compute_path)}
