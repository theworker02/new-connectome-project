"""Dataset registry schema and loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DatasetRecord(BaseModel):
    dataset_id: str
    species: str | None = None
    taxonomic_order: str | None = None
    common_name: str | None = None
    specimen_id: str | None = None
    sex: str | None = None
    developmental_stage: str | None = None
    anatomical_region: str | None = None
    imaging_method: str | None = None
    voxel_size_nm: Any = None
    volume_dimensions: Any = None
    estimated_volume: Any = None
    source_repository: str | None = None
    source_URL_or_identifier: str | None = None
    publication: str | None = None
    DOI: str | None = None
    license: str | None = None
    access_status: str | None = None
    raw_data_available: bool | None = None
    segmentation_available: bool | str | None = None
    synapse_annotations_available: bool | str | None = None
    skeletons_available: bool | str | None = None
    cell_annotations_available: bool | str | None = None
    download_method: str | None = None
    estimated_download_size: Any = None
    checksum_information: Any = None
    connectomics_suitability: str | None = None
    processability_rank: int | None = None
    notes: str | None = None


class Registry(BaseModel):
    version: int
    audit_date: str
    notes: str | None = None
    datasets: list[DatasetRecord] = Field(default_factory=list)

    def by_id(self, dataset_id: str) -> DatasetRecord:
        for ds in self.datasets:
            if ds.dataset_id == dataset_id:
                return ds
        raise KeyError(dataset_id)

    def ranked(self) -> list[DatasetRecord]:
        return sorted(
            self.datasets,
            key=lambda d: d.processability_rank if d.processability_rank is not None else 10_000,
        )

    def processable(self) -> list[DatasetRecord]:
        return [
            d
            for d in self.ranked()
            if d.raw_data_available is True
            and d.access_status in {"PUBLIC_DOWNLOAD", "PUBLIC_STREAM"}
        ]


def default_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "registry" / "registry.yaml"


def load_registry(path: Path | None = None) -> Registry:
    path = path or default_registry_path()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Registry.model_validate(data)
