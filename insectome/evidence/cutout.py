"""On-demand remote/local EM evidence cutouts around synapses."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from insectome.guards import DownloadEstimate, check_download
from insectome.storage.cache import InsectomeCache


def cremi_evidence_cutout(
    synapse_z_nm: float,
    synapse_y_nm: float,
    synapse_x_nm: float,
    hdf_path: Path,
    half_xy: int = 128,
    half_z: int = 4,
) -> np.ndarray:
    """Return a small EM cube around a synapse. Does not load the full volume into RAM."""
    import h5py

    with h5py.File(hdf_path, "r") as f:
        raw = f["volumes/raw"]
        res = np.asarray(raw.attrs.get("resolution", [40, 4, 4]), float)
        z = int(round(synapse_z_nm / res[0]))
        y = int(round(synapse_y_nm / res[1]))
        x = int(round(synapse_x_nm / res[2]))
        z0, z1 = max(0, z - half_z), min(raw.shape[0], z + half_z + 1)
        y0, y1 = max(0, y - half_xy), min(raw.shape[1], y + half_xy + 1)
        x0, x1 = max(0, x - half_xy), min(raw.shape[2], x + half_xy + 1)
        # Guard: cutout size
        nbytes = (z1 - z0) * (y1 - y0) * (x1 - x0)
        check_download(
            DownloadEstimate(
                operation="cremi_evidence_cutout",
                expected_download_bytes=nbytes,  # already local / chunked
                expected_temporary_bytes=nbytes,
                expected_final_bytes=nbytes,
                notes="Evidence ROI only",
            ),
            authorize=False,
        )
        cut = np.asarray(raw[z0:z1, y0:y1, x0:x1])
    cache = InsectomeCache()
    key = f"evidence:cremi:{z0}:{y0}:{x0}:{cut.shape}"
    cache.put_bytes(key, cut.tobytes(), kind="em_evidence")
    return cut


def bossdb_evidence_cutout(
    uri: str,
    z0: int,
    y0: int,
    x0: int,
    size_z: int = 8,
    size_y: int = 256,
    size_x: int = 256,
    authorize: bool = False,
) -> np.ndarray:
    nbytes = size_z * size_y * size_x
    check_download(
        DownloadEstimate(
            operation="bossdb_evidence_cutout",
            expected_download_bytes=nbytes,
            expected_temporary_bytes=nbytes,
            expected_final_bytes=nbytes,
            notes=f"BossDB ROI from {uri}",
        ),
        authorize=authorize,
    )
    if nbytes > 50 * 1024**2 and not authorize:
        raise RuntimeError("Evidence cutout >50 MB requires authorize=True")
    from insectome.ingest.bossdb import fetch_bossdb_cutout

    cut = fetch_bossdb_cutout(uri=uri, z0=z0, y0=y0, x0=x0, size_z=size_z, size_y=size_y, size_x=size_x)
    return cut.raw
