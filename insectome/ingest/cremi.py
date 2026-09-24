"""CREMI HDF5 ingestion with ROI cutouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from huggingface_hub import hf_hub_download

from insectome import __version__
from insectome.schemas.states import CoverageClaim, EvidenceState, ProcessingState
from insectome.storage.paths import ArtifactManifest, DataLayout, sha256_file, utc_now

CREMI_HF = {
    "cremi_sample_a": "train/sample_A.hdf",
    "cremi_sample_b": "train/sample_B.hdf",
    "cremi_sample_c": "train/sample_C.hdf",
}


@dataclass
class CremiVolume:
    dataset_id: str
    raw: np.ndarray
    neuron_ids: np.ndarray | None
    clefts: np.ndarray | None
    resolution_zyx_nm: tuple[float, float, float]
    origin_zyx: tuple[int, int, int]
    annotation_ids: np.ndarray | None = None
    annotation_locations_nm: np.ndarray | None = None
    annotation_types: np.ndarray | None = None
    partners: np.ndarray | None = None
    source_path: str = ""


def download_cremi(dataset_id: str = "cremi_sample_a", layout: DataLayout | None = None) -> Path:
    if dataset_id not in CREMI_HF:
        raise KeyError(f"Unsupported CREMI id: {dataset_id}")
    layout = layout or DataLayout()
    layout.ensure()
    cached = hf_hub_download(
        repo_id="MedOtter/CREMI",
        filename=CREMI_HF[dataset_id],
        repo_type="dataset",
    )
    dest_dir = layout.dataset_dir("raw", dataset_id)
    dest = dest_dir / Path(cached).name
    if not dest.exists():
        dest.write_bytes(Path(cached).read_bytes())
    digest = sha256_file(dest)
    ArtifactManifest(
        dataset_id=dataset_id,
        artifact_type="raw_hdf5",
        path=str(dest),
        processing_state=ProcessingState.RAW,
        evidence_state=EvidenceState.SOURCE_DOCUMENTED,
        created_at=utc_now(),
        software_version=__version__,
        parameters={"source": "huggingface:MedOtter/CREMI", "filename": CREMI_HF[dataset_id]},
        sha256=digest,
        coverage_claim=CoverageClaim.PARTIAL_VOLUME,
    ).write(dest_dir / "manifest.json")
    return dest


def _read_resolution(dset) -> tuple[float, float, float]:
    res = dset.attrs.get("resolution", None)
    if res is None:
        return (40.0, 4.0, 4.0)
    arr = np.asarray(res, dtype=float).ravel()
    return float(arr[0]), float(arr[1]), float(arr[2])


def load_cremi_roi(
    hdf_path: Path,
    dataset_id: str,
    z0: int = 0,
    y0: int = 0,
    x0: int = 0,
    size: int = 64,
    include_annotations: bool = True,
) -> CremiVolume:
    """Load a cubic ROI. Missing labels remain None — never fabricated."""
    with h5py.File(hdf_path, "r") as f:
        raw_ds = f["volumes/raw"]
        shape = raw_ds.shape
        z1 = min(z0 + size, shape[0])
        y1 = min(y0 + size, shape[1])
        x1 = min(x0 + size, shape[2])
        sl = (slice(z0, z1), slice(y0, y1), slice(x0, x1))
        raw = np.asarray(raw_ds[sl])
        resolution = _read_resolution(raw_ds)

        neuron_ids = None
        clefts = None
        if "volumes/labels/neuron_ids" in f:
            neuron_ids = np.asarray(f["volumes/labels/neuron_ids"][sl])
        if "volumes/labels/clefts" in f:
            clefts = np.asarray(f["volumes/labels/clefts"][sl])

        ann_ids = locs = types = partners = None
        if include_annotations and "annotations" in f:
            ann_ids = np.asarray(f["annotations/ids"][:])
            locs = np.asarray(f["annotations/locations"][:])  # nm z,y,x
            type_key = "annotations/types" if "annotations/types" in f else "annotations/type"
            types = np.asarray(f[type_key][:])
            if "annotations/presynaptic_site/partners" in f:
                partners = np.asarray(f["annotations/presynaptic_site/partners"][:])

    return CremiVolume(
        dataset_id=dataset_id,
        raw=raw,
        neuron_ids=neuron_ids,
        clefts=clefts,
        resolution_zyx_nm=resolution,
        origin_zyx=(z0, y0, x0),
        annotation_ids=ann_ids,
        annotation_locations_nm=locs,
        annotation_types=types,
        partners=partners,
        source_path=str(hdf_path),
    )


def save_roi_npz(volume: CremiVolume, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    raw_path = out_dir / "raw.npy"
    np.save(raw_path, volume.raw)
    paths["raw"] = raw_path
    meta: dict[str, Any] = {
        "dataset_id": volume.dataset_id,
        "origin_zyx": volume.origin_zyx,
        "shape_zyx": list(volume.raw.shape),
        "resolution_zyx_nm": list(volume.resolution_zyx_nm),
        "source_path": volume.source_path,
    }
    if volume.neuron_ids is not None:
        p = out_dir / "neuron_ids_gt.npy"
        np.save(p, volume.neuron_ids)
        paths["neuron_ids_gt"] = p
    if volume.clefts is not None:
        p = out_dir / "clefts_gt.npy"
        np.save(p, volume.clefts)
        paths["clefts_gt"] = p
    import json

    meta_path = out_dir / "roi_meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    paths["meta"] = meta_path
    return paths
