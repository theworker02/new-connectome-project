"""Storage paths and manifests — every artifact retains dataset_id."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass
class DataLayout:
    root: Path = field(default_factory=project_root)

    @property
    def data(self) -> Path:
        return self.root / "data"

    def ensure(self) -> None:
        for name in (
            "registry",
            "raw",
            "cache",
            "normalized",
            "aligned",
            "segmentation",
            "synapses",
            "skeletons",
            "annotations",
            "connectomes",
        ):
            (self.data / name).mkdir(parents=True, exist_ok=True)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)

    def dataset_dir(self, kind: str, dataset_id: str) -> Path:
        path = self.data / kind / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass
class ArtifactManifest:
    dataset_id: str
    artifact_type: str
    path: str
    processing_state: str
    evidence_state: str
    created_at: str
    software_version: str
    parameters: dict[str, Any]
    sha256: str | None = None
    parent_artifacts: list[str] = field(default_factory=list)
    coverage_claim: str = "ROI"

    def write(self, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
