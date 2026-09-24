"""Phase B orchestration: CREMI ROI → preprocess → segment → synapses → graph → QC."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from rich.console import Console

from insectome import __version__
from insectome.connectome.graph import build_connectome_graph, export_connectome
from insectome.ingest.cremi import download_cremi, load_cremi_roi, save_roi_npz
from insectome.preprocessing.normalize import contrast_normalize
from insectome.qc.checks import findings_to_dataframe, run_qc
from insectome.schemas.dataset import load_registry
from insectome.schemas.states import CoverageClaim, EvidenceState, ProcessingState
from insectome.segmentation.baseline import adapted_rand, baseline_watershed, variation_of_information
from insectome.storage.paths import ArtifactManifest, DataLayout, utc_now
from insectome.synapses.records import records_to_dataframe, synapses_from_cremi_annotations

console = Console()


def estimate_compute_plan(roi_size: int = 64) -> dict:
    voxels = roi_size**3
    return {
        "mode": "LOCAL",
        "dataset_id": "cremi_sample_a",
        "roi_size": roi_size,
        "voxels": voxels,
        "download_size": "~175 MB (full sample A; ROI is subset)",
        "ram_estimate_mb": max(256, voxels * 8 // (1024 * 1024) + 128),
        "vram_estimate_mb": 0,
        "notes": "Phase B validation ROI — no multi-month job.",
    }


def run_phase_b(
    roi_size: int = 64,
    z0: int = 0,
    y0: int = 256,
    x0: int = 960,
    root: Path | None = None,
) -> dict:
    layout = DataLayout(root=root) if root else DataLayout()
    layout.ensure()
    registry = load_registry()
    ds = registry.by_id("cremi_sample_a")

    plan = estimate_compute_plan(roi_size)
    plan_path = layout.root / "reports" / "COMPUTE_PLAN.md"
    plan_path.write_text(
        "# Compute plan — Phase B (CREMI Sample A ROI)\n\n"
        + "\n".join(f"- **{k}**: `{v}`" for k, v in plan.items())
        + "\n",
        encoding="utf-8",
    )

    console.print("[bold]Phase B[/bold]: download CREMI Sample A")
    hdf = download_cremi("cremi_sample_a", layout=layout)

    console.print(f"Load ROI z={z0} y={y0} x={x0} size={roi_size}")
    vol = load_cremi_roi(hdf, "cremi_sample_a", z0=z0, y0=y0, x0=x0, size=roi_size)
    roi_dir = layout.dataset_dir("raw", "cremi_sample_a") / f"roi_{roi_size}_z{z0}_y{y0}_x{x0}"
    save_roi_npz(vol, roi_dir)

    console.print("Preprocess (contrast normalize)")
    prep = contrast_normalize(vol.raw)
    norm_dir = layout.dataset_dir("normalized", "cremi_sample_a") / roi_dir.name
    norm_dir.mkdir(parents=True, exist_ok=True)
    np.save(norm_dir / "raw_norm.npy", prep.image)
    if prep.missing_mask is not None:
        np.save(norm_dir / "missing_slices.npy", prep.missing_mask)

    console.print("Baseline watershed segmentation (MODEL_PREDICTED)")
    seg = baseline_watershed(prep.image)
    seg_dir = layout.dataset_dir("segmentation", "cremi_sample_a") / roi_dir.name
    seg_dir.mkdir(parents=True, exist_ok=True)
    np.save(seg_dir / "labels_model.npy", seg.labels)
    ArtifactManifest(
        dataset_id="cremi_sample_a",
        artifact_type="segmentation",
        path=str(seg_dir / "labels_model.npy"),
        processing_state=ProcessingState.SEGMENTED,
        evidence_state=EvidenceState.MODEL_PREDICTED,
        created_at=utc_now(),
        software_version=__version__,
        parameters=seg.parameters | {"method": seg.method},
        coverage_claim=CoverageClaim.ROI,
    ).write(seg_dir / "manifest_model.json")

    metrics = {}
    if vol.neuron_ids is not None:
        vi, split_vi, merge_vi = variation_of_information(seg.labels, vol.neuron_ids)
        arand = adapted_rand(seg.labels, vol.neuron_ids)
        metrics = {
            "variation_of_information": vi,
            "vi_split": split_vi,
            "vi_merge": merge_vi,
            "adapted_rand_error": arand,
            "gt_neuron_count": int(len(np.unique(vol.neuron_ids)) - (1 if 0 in vol.neuron_ids else 0)),
            "pred_label_count": int(seg.labels.max()),
        }
        # Also persist GT labels for provenance (SOURCE_DOCUMENTED)
        np.save(seg_dir / "labels_gt.npy", vol.neuron_ids)

    console.print("Build SOURCE_DOCUMENTED synapses from CREMI annotations in ROI")
    gt_labels = vol.neuron_ids if vol.neuron_ids is not None else seg.labels
    syn_records = []
    if (
        vol.annotation_ids is not None
        and vol.annotation_locations_nm is not None
        and vol.annotation_types is not None
        and vol.partners is not None
    ):
        syn_records = synapses_from_cremi_annotations(
            dataset_id="cremi_sample_a",
            annotation_ids=vol.annotation_ids,
            locations_nm=vol.annotation_locations_nm,
            types=vol.annotation_types,
            partners=vol.partners,
            neuron_labels=gt_labels,
            resolution_zyx_nm=vol.resolution_zyx_nm,
            origin_zyx=vol.origin_zyx,
            roi_shape=tuple(vol.raw.shape),
        )
    syn_df = records_to_dataframe(syn_records)
    syn_dir = layout.dataset_dir("synapses", "cremi_sample_a") / roi_dir.name
    syn_dir.mkdir(parents=True, exist_ok=True)
    syn_path = syn_dir / "synapses.parquet"
    syn_df.to_parquet(syn_path, index=False)

    console.print("Generate connectome graph (independent ROI graph)")
    graph, nodes, edges = build_connectome_graph(
        syn_records,
        dataset_id="cremi_sample_a",
        specimen_id=str(ds.specimen_id),
        anatomical_region=str(ds.anatomical_region),
    )
    conn_dir = layout.dataset_dir("connectomes", "cremi_sample_a") / roi_dir.name
    export_connectome(
        graph,
        nodes,
        edges,
        syn_df,
        conn_dir,
        metadata={
            "dataset_id": "cremi_sample_a",
            "specimen_id": ds.specimen_id,
            "species": ds.species,
            "coverage_claim": CoverageClaim.ROI,
            "roi_origin_zyx": list(vol.origin_zyx),
            "roi_shape_zyx": list(vol.raw.shape),
            "software_version": __version__,
            "created_at": utc_now(),
            "edge_evidence": EvidenceState.SOURCE_DOCUMENTED,
            "limitations": [
                "ROI only — not a whole-brain connectome",
                "Baseline watershed is MODEL_PREDICTED and not used for published edges",
                "Edges derived from CREMI partner annotations intersecting this ROI",
            ],
        },
    )

    findings = run_qc(seg.labels, syn_df, edges)
    qc_df = findings_to_dataframe(findings)
    qc_path = layout.root / "reports" / f"QC_REPORT_cremi_roi_{roi_size}.md"
    lines = [
        "# QC report — CREMI Sample A ROI",
        "",
        f"- Coverage claim: `{CoverageClaim.ROI}`",
        f"- Dataset: `cremi_sample_a`",
        f"- ROI origin (z,y,x): `{vol.origin_zyx}`",
        f"- ROI shape: `{vol.raw.shape}`",
        f"- SOURCE_DOCUMENTED synapses in ROI: `{len(syn_records)}`",
        f"- Graph nodes: `{graph.number_of_nodes()}`",
        f"- Graph edges: `{graph.number_of_edges()}`",
        "",
        "## Segmentation metrics vs CREMI neuron_ids (baseline watershed)",
        "",
    ]
    if metrics:
        for k, v in metrics.items():
            lines.append(f"- **{k}**: `{v}`")
    else:
        lines.append("- No GT neuron labels in ROI load (unexpected).")
    lines += ["", "## Findings", ""]
    for f in findings:
        lines.append(f"- `{f.severity}` **{f.code}**: {f.message}")
    lines += [
        "",
        "## Integrity notes",
        "",
        "- Baseline segmentation is `MODEL_PREDICTED` and is **not** claimed as proofread biology.",
        "- Connectome edges use CREMI `SOURCE_DOCUMENTED` partner annotations only.",
        "- Proximity was never used to invent synapses.",
        "",
    ]
    qc_path.write_text("\n".join(lines), encoding="utf-8")
    qc_df.to_parquet(syn_dir / "qc_findings.parquet", index=False)

    summary = {
        "dataset_id": "cremi_sample_a",
        "roi": {"origin_zyx": list(vol.origin_zyx), "shape": list(vol.raw.shape)},
        "metrics": metrics,
        "n_synapses_documented": len(syn_records),
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "reports": {"qc": str(qc_path), "compute_plan": str(plan_path)},
        "connectome_dir": str(conn_dir),
    }
    summary_path = layout.root / "reports" / "PHASE_B_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console.print(f"[green]Done.[/green] Summary: {summary_path}")
    return summary
