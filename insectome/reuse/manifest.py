"""Reuse manifest schema, gap analysis, and reuse scoring."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field

from insectome.schemas.states import Suitability


class ProcessingLevel(IntEnum):
    COMPLETE_CONNECTOME = 0
    CONNECTIVITY_EXISTS = 1
    SYNAPSES_AND_SEGMENTATION = 2
    SEGMENTATION_EXISTS = 3
    SKELETONS_EXIST = 4
    PARTIAL_RECONSTRUCTION = 5
    RAW_EM_ONLY = 6
    INACCESSIBLE = 99


class Availability(str):
    AVAILABLE = "AVAILABLE"
    AVAILABLE_REMOTE = "AVAILABLE_REMOTE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    OPTIONAL = "OPTIONAL"
    REQUIRED = "REQUIRED"
    UNKNOWN = "UNKNOWN"
    INACCESSIBLE = "INACCESSIBLE"


class GapItem(BaseModel):
    component: str
    status: str
    notes: str | None = None


class RequiredNewWork(BaseModel):
    segmentation: bool = False
    skeletonization: bool = False
    synapse_detection: bool = False
    graph_construction: bool = False
    normalization: bool = True
    comparative_mapping: bool = False
    notes: str | None = None


class ReuseManifest(BaseModel):
    dataset_id: str
    species: str | None = None
    processing_level: int
    reuse_score: int = Field(ge=0, le=100)
    raw_em_available: bool | str = False
    segmentation_available: bool | str = False
    segmentation_proofread: bool | str = False
    skeletons_available: bool | str = False
    synapses_available: bool | str = False
    connectivity_available: bool | str = False
    cell_types_available: bool | str = False
    meshes_available: bool | str = False
    annotations_available: bool | str = False
    neurotransmitters_available: bool | str = False
    gaps: list[GapItem] = Field(default_factory=list)
    required_new_work: RequiredNewWork = Field(default_factory=RequiredNewWork)
    remote_raw_bytes_estimate: int | None = None
    local_required_bytes_estimate: int | None = None
    offline_pack_bytes_estimate: int | None = None
    sources: list[str] = Field(default_factory=list)
    notes: str | None = None


def score_reuse(
    *,
    connectivity: bool,
    synapses: bool,
    segmentation: bool,
    segmentation_proofread: bool,
    skeletons: bool,
    cell_types: bool,
    annotations: bool,
    raw_only: bool,
    inaccessible: bool,
) -> tuple[int, ProcessingLevel]:
    if inaccessible:
        return 0, ProcessingLevel.INACCESSIBLE
    if connectivity and (synapses or skeletons or segmentation_proofread):
        score = 100
        if not cell_types:
            score = 92
        if not annotations:
            score = min(score, 90)
        return score, ProcessingLevel.COMPLETE_CONNECTOME
    if connectivity:
        return 90, ProcessingLevel.CONNECTIVITY_EXISTS
    if synapses and segmentation:
        return 75, ProcessingLevel.SYNAPSES_AND_SEGMENTATION
    if segmentation:
        return 60, ProcessingLevel.SEGMENTATION_EXISTS
    if skeletons:
        return 50, ProcessingLevel.SKELETONS_EXIST
    if any([synapses, segmentation, skeletons, annotations]):
        return 30, ProcessingLevel.PARTIAL_RECONSTRUCTION
    if raw_only:
        return 0, ProcessingLevel.RAW_EM_ONLY
    return 0, ProcessingLevel.RAW_EM_ONLY


def _truthy(v: Any) -> bool:
    return v is True


def build_reuse_manifest(dataset: Any) -> ReuseManifest:
    """Build evidence-based reuse manifest from a registry DatasetRecord."""
    inaccessible = dataset.access_status == "INACCESSIBLE" or dataset.connectomics_suitability == Suitability.INACCESSIBLE
    connectivity = _truthy(dataset.synapse_annotations_available) and dataset.dataset_id.startswith("cremi")
    # CREMI has partner annotations => connectivity without our segmentation
    if dataset.dataset_id.startswith("cremi"):
        connectivity = True
        synapses = True
        segmentation = True
        skeletons = False
        cell_types = False
        annotations = True
        proofread = True  # CREMI challenge labels are curated GT
        meshes = False
        nt = False
        raw = True
        sources = ["CREMI HDF5 annotations + neuron_ids"]
        remote_raw = 175 * 1024**2
        local_req = 2 * 1024**2
        pack = 500 * 1024
        notes = "LEVEL 1+: import partner annotations as graph; raw EM optional for evidence only."
    elif dataset.dataset_id.startswith("heinze"):
        return ReuseManifest(
            dataset_id=dataset.dataset_id,
            species=dataset.species,
            processing_level=int(ProcessingLevel.INACCESSIBLE),
            reuse_score=0,
            raw_em_available=False,
            gaps=[GapItem(component="raw_em", status=Availability.INACCESSIBLE)],
            required_new_work=RequiredNewWork(
                segmentation=False,
                synapse_detection=False,
                graph_construction=False,
                normalization=False,
                notes="Await public deposit / collaboration access.",
            ),
            sources=[str(dataset.source_URL_or_identifier)],
            notes="No verified public reconstruction products.",
        )
    elif dataset.dataset_id == "bombus_cx_projectome_sayre2021":
        connectivity = False
        synapses = False
        segmentation = False
        skeletons = True
        cell_types = True
        annotations = True
        proofread = False
        meshes = False
        nt = False
        raw = False
        sources = ["Insect Brain Database projectome"]
        remote_raw = None
        local_req = 50 * 1024**2
        pack = 50 * 1024**2
        notes = "Morphology/projectome only — not synaptic connectome."
    elif dataset.dataset_id in {"hemibrain_neuprint", "flywire_codex"}:
        connectivity = True
        synapses = True
        segmentation = True
        skeletons = True
        cell_types = True
        annotations = True
        proofread = True
        meshes = True
        nt = dataset.dataset_id == "flywire_codex"
        raw = True
        sources = (
            ["neuPrint hemibrain API"]
            if dataset.dataset_id == "hemibrain_neuprint"
            else ["FlyWire / Codex / CAVE"]
        )
        remote_raw = 26 * 1024**4  # ~26 TB EM cited for hemibrain scale (estimate)
        local_req = 50 * 1024**2
        pack = 300 * 1024**2
        notes = "LEVEL 0 — reuse complete published connectome; never download full EM."
    elif dataset.dataset_id == "aedes_antennal_lobe_bao2025":
        connectivity = False
        synapses = False  # published paper has reconstruction; public BossDB channel is EM-only (verified)
        segmentation = False
        skeletons = False
        cell_types = False
        annotations = False
        proofread = False
        meshes = False
        nt = False
        raw = True
        sources = ["BossDB bao_alford2025 EM channel; paper reconstruction not verified as public API"]
        remote_raw = 5 * 1024**4  # unknown; large ssTEM — estimate marked as such
        local_req = 5 * 1024**2
        pack = None
        notes = "LEVEL 6 raw EM streamable; published circuit exists but reuse channel UNKNOWN."
    elif dataset.dataset_id == "banc_drosophila_2025":
        connectivity = True  # published connectome effort — treat connectivity as available via project
        synapses = True
        segmentation = True
        skeletons = True
        cell_types = False
        annotations = False
        proofread = True
        meshes = False
        nt = False
        raw = True
        sources = ["BossDB BANC project / publication"]
        remote_raw = 50 * 1024**4  # estimate UNKNOWN scale
        local_req = 100 * 1024**2
        pack = 500 * 1024**2
        notes = "Existing CNS connectome — reuse/benchmark only; do not re-segment wholesale."
    else:
        connectivity = False
        synapses = _truthy(dataset.synapse_annotations_available)
        segmentation = _truthy(dataset.segmentation_available)
        skeletons = _truthy(dataset.skeletons_available)
        cell_types = _truthy(dataset.cell_annotations_available)
        annotations = cell_types
        proofread = False
        meshes = False
        nt = False
        raw = _truthy(dataset.raw_data_available)
        sources = [str(dataset.source_URL_or_identifier)]
        remote_raw = None
        local_req = None
        pack = None
        notes = "Generic registry-derived estimate; verify before compute."

    score, level = score_reuse(
        connectivity=connectivity,
        synapses=synapses,
        segmentation=segmentation,
        segmentation_proofread=proofread,
        skeletons=skeletons,
        cell_types=cell_types,
        annotations=annotations,
        raw_only=raw and not any([connectivity, synapses, segmentation, skeletons]),
        inaccessible=False,
    )

    gaps = [
        GapItem(component="connectivity", status=Availability.AVAILABLE if connectivity else Availability.MISSING),
        GapItem(component="synapses", status=Availability.AVAILABLE if synapses else Availability.MISSING),
        GapItem(component="segmentation", status=Availability.AVAILABLE if segmentation else Availability.MISSING),
        GapItem(component="skeletons", status=Availability.AVAILABLE if skeletons else Availability.MISSING),
        GapItem(component="cell_types", status=Availability.PARTIAL if cell_types else Availability.MISSING),
        GapItem(
            component="raw_em",
            status=Availability.AVAILABLE_REMOTE if raw else Availability.MISSING,
        ),
        GapItem(
            component="neurotransmitters",
            status=Availability.PARTIAL if nt else Availability.MISSING,
        ),
    ]

    need_graph = not connectivity
    req = RequiredNewWork(
        segmentation=not segmentation and level >= ProcessingLevel.RAW_EM_ONLY,
        skeletonization=not skeletons and need_graph,
        synapse_detection=not synapses and need_graph,
        graph_construction=need_graph,
        normalization=True,
        comparative_mapping=False,
        notes="Prefer import/normalize over reconstruction.",
    )
    if level <= ProcessingLevel.CONNECTIVITY_EXISTS:
        req.segmentation = False
        req.skeletonization = False
        req.synapse_detection = False
        req.graph_construction = False

    return ReuseManifest(
        dataset_id=dataset.dataset_id,
        species=dataset.species,
        processing_level=int(level),
        reuse_score=score,
        raw_em_available=raw,
        segmentation_available=segmentation,
        segmentation_proofread=proofread,
        skeletons_available=skeletons,
        synapses_available=synapses,
        connectivity_available=connectivity,
        cell_types_available=cell_types,
        meshes_available=meshes,
        annotations_available=annotations,
        neurotransmitters_available=nt,
        gaps=gaps,
        required_new_work=req,
        remote_raw_bytes_estimate=remote_raw,
        local_required_bytes_estimate=local_req,
        offline_pack_bytes_estimate=pack,
        sources=sources,
        notes=notes,
    )


def analyze_registry(datasets: list[Any]) -> list[ReuseManifest]:
    manifests = [build_reuse_manifest(d) for d in datasets]
    return sorted(manifests, key=lambda m: (-m.reuse_score, m.processing_level, m.dataset_id))
