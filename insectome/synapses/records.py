"""Synapse records — never promote proximity to verified biology."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from insectome.schemas.states import EvidenceState


@dataclass
class SynapseRecord:
    synapse_id: str
    dataset_id: str
    z: float
    y: float
    x: float
    pre_neuron: int | None
    post_neuron: int | None
    confidence: float
    detector: str
    detector_version: str
    verification_state: str
    coordinate_space: str = "voxel_roi"
    source_partner_ids: tuple[int, int] | None = None


def _nm_to_voxel(
    loc_nm: np.ndarray,
    resolution_zyx_nm: tuple[float, float, float],
    origin_zyx: tuple[int, int, int],
) -> tuple[float, float, float]:
    z = loc_nm[0] / resolution_zyx_nm[0] - origin_zyx[0]
    y = loc_nm[1] / resolution_zyx_nm[1] - origin_zyx[1]
    x = loc_nm[2] / resolution_zyx_nm[2] - origin_zyx[2]
    return float(z), float(y), float(x)


def _lookup_neuron(labels: np.ndarray, z: float, y: float, x: float) -> int | None:
    zi, yi, xi = int(round(z)), int(round(y)), int(round(x))
    if not (0 <= zi < labels.shape[0] and 0 <= yi < labels.shape[1] and 0 <= xi < labels.shape[2]):
        return None
    val = int(labels[zi, yi, xi])
    return val if val != 0 else None


def synapses_from_cremi_annotations(
    dataset_id: str,
    annotation_ids: np.ndarray,
    locations_nm: np.ndarray,
    types: np.ndarray,
    partners: np.ndarray,
    neuron_labels: np.ndarray,
    resolution_zyx_nm: tuple[float, float, float],
    origin_zyx: tuple[int, int, int],
    roi_shape: tuple[int, int, int],
) -> list[SynapseRecord]:
    """Map CREMI pre→post partners into ROI. SOURCE_DOCUMENTED evidence only."""
    id_to_idx = {int(i): idx for idx, i in enumerate(annotation_ids.tolist())}
    def _as_text(v: object) -> str:
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return str(v)

    type_map = {int(annotation_ids[i]): _as_text(types[i]).lower() for i in range(len(annotation_ids))}
    records: list[SynapseRecord] = []
    for pre_id, post_id in partners.tolist():
        pre_id, post_id = int(pre_id), int(post_id)
        if pre_id not in id_to_idx or post_id not in id_to_idx:
            continue
        pre_loc = locations_nm[id_to_idx[pre_id]]
        z, y, x = _nm_to_voxel(pre_loc, resolution_zyx_nm, origin_zyx)
        if not (0 <= z < roi_shape[0] and 0 <= y < roi_shape[1] and 0 <= x < roi_shape[2]):
            continue
        # Prefer documented types; do not invent. Partner table already encodes pre→post.
        pre_type = type_map.get(pre_id, "")
        if pre_type and "pre" not in pre_type:
            continue
        pre_n = _lookup_neuron(neuron_labels, z, y, x)
        post_loc = locations_nm[id_to_idx[post_id]]
        pz, py, px = _nm_to_voxel(post_loc, resolution_zyx_nm, origin_zyx)
        post_n = _lookup_neuron(neuron_labels, pz, py, px)
        records.append(
            SynapseRecord(
                synapse_id=f"{dataset_id}:cremi:{pre_id}->{post_id}",
                dataset_id=dataset_id,
                z=z,
                y=y,
                x=x,
                pre_neuron=pre_n,
                post_neuron=post_n,
                confidence=1.0,
                detector="cremi_ground_truth_annotations",
                detector_version="cremi_hdf5",
                verification_state=EvidenceState.SOURCE_DOCUMENTED,
                coordinate_space="voxel_roi",
                source_partner_ids=(pre_id, post_id),
            )
        )
    return records


def records_to_dataframe(records: list[SynapseRecord]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for r in records:
        d = asdict(r)
        if d["source_partner_ids"] is not None:
            d["source_partner_ids"] = list(d["source_partner_ids"])
        rows.append(d)
    return pd.DataFrame(rows)
