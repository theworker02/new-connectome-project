"""CREMI local/remote evidence adapter — ROI cutouts only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from insectome.remote import CREMI_SAMPLE_A_BYTES, RemoteVolume, VolumeMeta
from insectome.storage.cache import InsectomeCache


class CremiRemote(RemoteVolume):
    provider = "cremi"

    def __init__(self, hdf_path: Path | None = None, cache: InsectomeCache | None = None):
        self.hdf_path = hdf_path
        self.cache = cache or InsectomeCache()

    def _resolve(self) -> Path:
        if self.hdf_path and self.hdf_path.exists():
            return self.hdf_path
        from insectome.adapters.cremi_pack import _resolve_cremi_hdf

        return Path(_resolve_cremi_hdf(authorize_download=False))

    def get_metadata(self) -> VolumeMeta:
        try:
            p = self._resolve()
            healthy = p.exists()
        except Exception:
            healthy = False
        return VolumeMeta(
            provider=self.provider,
            dataset="cremi_sample_a",
            remote_raw_bytes=CREMI_SAMPLE_A_BYTES,
            resolution_nm=[40.0, 4.0, 4.0],
            notes="Challenge volume — stream cutouts only; graph pack is local Tier-0.",
            healthy=healthy,
        )

    def get_chunk(self, bounds: tuple[int, int, int, int, int, int], resolution: int = 0) -> np.ndarray:
        z0, z1, y0, y1, x0, x1 = bounds
        key = f"cremi:chunk:{z0}:{z1}:{y0}:{y1}:{x0}:{x1}"
        cached = self.cache.get_bytes(key)
        if cached is not None:
            # shape prefix: 3x int32 then payload
            shape = np.frombuffer(cached[:12], dtype=np.int32)
            return np.frombuffer(cached[12:], dtype=np.uint8).reshape(tuple(shape))
        import h5py

        hdf = self._resolve()
        with h5py.File(hdf, "r") as f:
            raw = f["volumes/raw"]
            cut = np.asarray(raw[z0:z1, y0:y1, x0:x1])
        payload = np.asarray(cut.shape, dtype=np.int32).tobytes() + cut.astype(np.uint8).tobytes()
        self.cache.put_bytes(key, payload, kind="em_chunk", source=str(hdf))
        return cut

    def get_em_cutout(self, bounds: tuple[int, int, int, int, int, int]) -> np.ndarray:
        return self.get_chunk(bounds)
