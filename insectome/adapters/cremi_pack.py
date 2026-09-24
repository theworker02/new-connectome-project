"""Import CREMI partner annotations as a LEVEL-1 connectome pack (no EM required for graph)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download

from insectome import __version__
from insectome.connectome.store import ConnectomeStore
from insectome.guards import DownloadEstimate, check_download
from insectome.schemas.states import CoverageClaim, EvidenceState
from insectome.storage.paths import utc_now


def _resolve_cremi_hdf(dataset_id: str = "cremi_sample_a", authorize_download: bool = False) -> Path:
    """Prefer existing local copy; otherwise download with guard (annotations use full file)."""
    from insectome.storage.paths import DataLayout

    layout = DataLayout()
    local = layout.dataset_dir("raw", dataset_id) / "sample_A.hdf"
    if local.exists():
        return local
    # HuggingFace file ~175 MB — under 1 GB warn threshold but still guarded for transparency
    estimate = DownloadEstimate(
        operation=f"cremi_import:{dataset_id}",
        expected_download_bytes=175 * 1024**2,
        expected_temporary_bytes=175 * 1024**2,
        expected_final_bytes=2 * 1024**2,  # we keep graph pack, not EM, long-term preferred
        estimated_runtime_sec=60,
        notes="CREMI HDF used only to extract annotation tables; raw EM not required for queries.",
    )
    check_download(estimate, authorize=authorize_download)
    cached = hf_hub_download(repo_id="MedOtter/CREMI", filename="train/sample_A.hdf", repo_type="dataset")
    return Path(cached)


def import_cremi_connectivity(
    dataset_id: str = "cremi_sample_a",
    connectome_id: str = "cremi_sample_a_v0.2",
    authorize_download: bool = False,
) -> ConnectomeStore:
    hdf = _resolve_cremi_hdf(dataset_id, authorize_download=authorize_download)
    with h5py.File(hdf, "r") as f:
        ann_ids = np.asarray(f["annotations/ids"][:])
        locs = np.asarray(f["annotations/locations"][:])
        type_key = "annotations/types" if "annotations/types" in f else "annotations/type"
        types = np.asarray(f[type_key][:])
        partners = np.asarray(f["annotations/presynaptic_site/partners"][:])
        res = np.asarray(f["volumes/raw"].attrs.get("resolution", [40, 4, 4]), float)
        neuron_ids = np.asarray(f["volumes/labels/neuron_ids"])

    id_to_idx = {int(i): idx for idx, i in enumerate(ann_ids.tolist())}

    def neuron_at(loc_nm: np.ndarray) -> int | None:
        z = int(round(loc_nm[0] / res[0]))
        y = int(round(loc_nm[1] / res[1]))
        x = int(round(loc_nm[2] / res[2]))
        if not (0 <= z < neuron_ids.shape[0] and 0 <= y < neuron_ids.shape[1] and 0 <= x < neuron_ids.shape[2]):
            return None
        val = int(neuron_ids[z, y, x])
        return val if val != 0 else None

    syn_rows = []
    for pre_id, post_id in partners.tolist():
        pre_id, post_id = int(pre_id), int(post_id)
        if pre_id not in id_to_idx or post_id not in id_to_idx:
            continue
        pre_loc = locs[id_to_idx[pre_id]]
        post_loc = locs[id_to_idx[post_id]]
        pre_n = neuron_at(pre_loc)
        post_n = neuron_at(post_loc)
        syn_rows.append(
            {
                "synapse_id": f"{dataset_id}:{pre_id}->{post_id}",
                "dataset_id": dataset_id,
                "z_nm": float(pre_loc[0]),
                "y_nm": float(pre_loc[1]),
                "x_nm": float(pre_loc[2]),
                "pre_neuron": pre_n,
                "post_neuron": post_n,
                "confidence": 1.0,
                "detector": "cremi_ground_truth_annotations",
                "verification_state": EvidenceState.SOURCE_DOCUMENTED,
            }
        )
    syn_df = pd.DataFrame(syn_rows)
    usable = syn_df.dropna(subset=["pre_neuron", "post_neuron"])
    usable = usable[usable["pre_neuron"] != usable["post_neuron"]]
    edges = (
        usable.groupby(["pre_neuron", "post_neuron"], as_index=False)
        .agg(synapse_count=("synapse_id", "count"), mean_confidence=("confidence", "mean"))
        .rename(columns={"pre_neuron": "pre_neuron_id", "post_neuron": "post_neuron_id"})
    )
    edges["dataset"] = dataset_id
    edges["specimen"] = "CREMI-A"
    edges["anatomical_region"] = "adult Drosophila brain ssTEM subvolume"
    edges["verification_status"] = EvidenceState.SOURCE_DOCUMENTED

    neuron_set = sorted(set(edges["pre_neuron_id"].astype(int)) | set(edges["post_neuron_id"].astype(int)))
    nodes = pd.DataFrame(
        {
            "neuron_id": neuron_set,
            "dataset": dataset_id,
            "specimen": "CREMI-A",
            "species": "Drosophila melanogaster",
            "anatomical_region": "adult Drosophila brain ssTEM subvolume",
            "evidence_state": str(EvidenceState.SOURCE_DOCUMENTED),
            "reconstruction_method": "CREMI curated labels (reused)",
        }
    )

    store = ConnectomeStore(connectome_id)
    store.save_tables(nodes, edges, syn_df)
    local_bytes = sum(p.stat().st_size for p in store.dir.glob("*") if p.is_file())
    store.write_manifest(
        {
            "species": "Drosophila melanogaster",
            "specimen": "CREMI-A",
            "dataset": dataset_id,
            "source": "CREMI / MedOtter HuggingFace mirror",
            "source_version": "sample_A",
            "connectome_version": "v0.2",
            "coverage_claim": CoverageClaim.PARTIAL_VOLUME,
            "neurons": {
                "source": "CREMI volumes/labels/neuron_ids at annotation sites",
                "count": int(len(nodes)),
                "reconstruction_method": "reused CREMI GT (no new segmentation)",
            },
            "synapses": {
                "source": "CREMI annotations/presynaptic_site/partners",
                "count": int(len(syn_df)),
                "detection_method": "SOURCE_DOCUMENTED import",
            },
            "annotations": {"source": "CREMI"},
            "raw_em": {
                "remote_location": "hf://datasets/MedOtter/CREMI/train/sample_A.hdf",
                "locally_stored": False,
                "note": "EM retained only if previously cached; not required for graph queries",
            },
            "new_computation": {
                "operations_performed": ["annotation_table_import", "neuron_id_lookup", "graph_normalize"]
            },
            "reuse_percentage": 95,
            "processing_level": 1,
            "storage": {
                "local_bytes": local_bytes,
                "remote_bytes_referenced": 175 * 1024**2,
            },
            "software_version": __version__,
            "created_at": utc_now(),
        }
    )
    return store
