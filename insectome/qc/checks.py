"""Automatic QC — flag issues; never silently rewrite biology."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass
class QCFinding:
    code: str
    severity: str
    message: str
    object_id: str | None = None


def run_qc(
    labels: np.ndarray,
    synapses: pd.DataFrame,
    edges: pd.DataFrame,
) -> list[QCFinding]:
    findings: list[QCFinding] = []
    n_labels = int(labels.max()) if labels.size else 0
    counts = np.bincount(labels.ravel()) if labels.size else np.array([0])
    if len(counts) > 1:
        largest = int(counts[1:].max())
        if largest > 0.5 * labels.size:
            findings.append(
                QCFinding(
                    code="IMPLAUSIBLY_LARGE_MERGE",
                    severity="high",
                    message=f"Largest object covers {largest / labels.size:.1%} of ROI voxels",
                )
            )
        tiny = int(np.sum(counts[1:] < 10))
        if tiny:
            findings.append(
                QCFinding(
                    code="ISOLATED_FRAGMENTS",
                    severity="low",
                    message=f"{tiny} objects with <10 voxels",
                )
            )

    if not synapses.empty and {"pre_neuron", "post_neuron"}.issubset(synapses.columns):
        self_links = synapses[synapses["pre_neuron"] == synapses["post_neuron"]]
        if len(self_links):
            findings.append(
                QCFinding(
                    code="SELF_CONNECTIONS",
                    severity="medium",
                    message=f"{len(self_links)} self-connection synapse records",
                )
            )
        outside = synapses[synapses["pre_neuron"].isna() | synapses["post_neuron"].isna()]
        if len(outside):
            findings.append(
                QCFinding(
                    code="SYNAPSE_OUTSIDE_SEGMENTATION",
                    severity="medium",
                    message=f"{len(outside)} synapses could not be assigned to neuron labels in ROI",
                )
            )

    if not edges.empty and "synapse_count" in edges.columns:
        dense = edges[edges["synapse_count"] > 50]
        if len(dense):
            findings.append(
                QCFinding(
                    code="DENSE_SYNAPSE_CLUSTER",
                    severity="low",
                    message=f"{len(dense)} edges with >50 synapses (inspect manually)",
                )
            )

    findings.append(
        QCFinding(
            code="LABEL_COUNT",
            severity="info",
            message=f"Segmentation contains {max(n_labels, 0)} positive label ids",
        )
    )
    return findings


def findings_to_dataframe(findings: list[QCFinding]) -> pd.DataFrame:
    return pd.DataFrame([asdict(f) for f in findings])
