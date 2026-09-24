"""BossDB cutout ingest via intern (optional dependency)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from insectome import __version__
from insectome.schemas.states import CoverageClaim, EvidenceState, ProcessingState
from insectome.storage.paths import ArtifactManifest, DataLayout, utc_now

AEDES_URI = "bossdb://bao_alford2025/aedes/em_rechunked"


@dataclass
class BossCutout:
    dataset_id: str
    uri: str
    raw: np.ndarray
    origin_zyx: tuple[int, int, int]
    shape_zyx: tuple[int, int, int]


def fetch_bossdb_cutout(
    uri: str = AEDES_URI,
    dataset_id: str = "aedes_antennal_lobe_bao2025",
    z0: int = 4000,
    y0: int = 56000,
    x0: int = 88000,
    size_z: int = 32,
    size_y: int = 256,
    size_x: int = 256,
    layout: DataLayout | None = None,
    authorize: bool = False,
) -> BossCutout:
    """Stream a small BossDB ROI. Never downloads the full volume."""
    from insectome.guards import DownloadEstimate, check_download

    nbytes = int(size_z * size_y * size_x)
    check_download(
        DownloadEstimate(
            operation="bossdb_cutout",
            expected_download_bytes=nbytes,
            expected_temporary_bytes=nbytes,
            expected_final_bytes=nbytes,
            notes=f"ROI only from {uri}; full volume forbidden by default",
        ),
        authorize=authorize,
    )
    if nbytes > 50 * 1024**2 and not authorize:
        raise RuntimeError("BossDB cutout >50 MB requires authorize=True")
    try:
        from intern import array
    except ImportError as exc:
        raise ImportError(
            "BossDB ingest requires optional dependency: pip install insectome[bossdb]"
        ) from exc

    layout = layout or DataLayout()
    layout.ensure()
    channel = array(uri)
    z1, y1, x1 = z0 + size_z, y0 + size_y, x0 + size_x
    raw = np.asarray(channel[z0:z1, y0:y1, x0:x1])
    out_dir = layout.dataset_dir("raw", dataset_id) / f"roi_z{z0}_y{y0}_x{x0}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "raw.npy"
    np.save(out_path, raw)
    ArtifactManifest(
        dataset_id=dataset_id,
        artifact_type="bossdb_cutout",
        path=str(out_path),
        processing_state=ProcessingState.RAW,
        evidence_state=EvidenceState.SOURCE_DOCUMENTED,
        created_at=utc_now(),
        software_version=__version__,
        parameters={
            "uri": uri,
            "origin_zyx": [z0, y0, x0],
            "shape_zyx": list(raw.shape),
        },
        coverage_claim=CoverageClaim.ROI,
    ).write(out_dir / "manifest.json")
    return BossCutout(
        dataset_id=dataset_id,
        uri=uri,
        raw=raw,
        origin_zyx=(z0, y0, x0),
        shape_zyx=tuple(raw.shape),
    )
