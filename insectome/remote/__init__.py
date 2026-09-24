"""RemoteVolume — federation layer for huge sources without local copies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class RemotePointer:
    """WHERE data lives — never a silent substitute for another biological dataset."""

    provider: str
    uri: str | None = None
    object_id: str | int | None = None
    dataset: str | None = None
    coordinates: list[float] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class VolumeMeta:
    provider: str
    dataset: str
    remote_raw_bytes: int | None
    resolution_nm: list[float] | None = None
    bounds: list[int] | None = None
    notes: str = ""
    healthy: bool = True


class RemoteVolume(ABC):
    provider: str

    @abstractmethod
    def get_metadata(self) -> VolumeMeta: ...

    def get_chunk(self, bounds: tuple[int, int, int, int, int, int], resolution: int = 0) -> np.ndarray:
        raise NotImplementedError(f"{self.provider} does not expose volume chunks")

    def get_skeleton(self, neuron_id: int | str) -> dict[str, Any]:
        raise NotImplementedError(f"{self.provider} does not expose skeletons")

    def get_mesh(self, neuron_id: int | str, lod: int = 2) -> dict[str, Any] | None:
        return None

    def get_synapses(self, neuron_id: int | str) -> list[dict[str, Any]]:
        return []

    def get_em_cutout(self, bounds: tuple[int, int, int, int, int, int]) -> np.ndarray:
        return self.get_chunk(bounds, resolution=0)

    def health(self) -> dict[str, Any]:
        try:
            meta = self.get_metadata()
            return {"provider": self.provider, "healthy": meta.healthy, "dataset": meta.dataset}
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.provider, "healthy": False, "error": str(exc)}


# Known remote magnitudes (authoritative public figures / published estimates)
HEMIBRAIN_REMOTE_BYTES = 26 * 1024**4  # ~26 TB published EM ecosystem (not downloaded)
FAFB_REMOTE_BYTES = 100 * 1024**4  # order-of-magnitude whole-brain EM class
CREMI_SAMPLE_A_BYTES = 175 * 1024**2
