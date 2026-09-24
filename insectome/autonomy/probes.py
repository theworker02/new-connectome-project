"""Live probes of public connectome / morphology sources."""

from __future__ import annotations

import os
from typing import Any

import requests

from insectome.autonomy.models import (
    Candidate,
    CandidateStatus,
    EvidenceItem,
    EvidenceKind,
    IngestPlan,
)
from insectome.autonomy.policies import CATALOG_RECIPES, WATCHLIST_CANDIDATES, plan_for_recipe
from insectome.autonomy.budget import AutonomyBudget
from insectome.connectome.store import list_connectomes
from insectome.discovery.sources import list_sources
from insectome.schemas.dataset import load_registry
from insectome.storage.paths import utc_now


def probe_neuprint_datasets() -> list[Candidate]:
    """List live neuPrint datasets and emit candidates for new ones."""
    token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
    if not token:
        return []
    now = utc_now()
    try:
        r = requests.get(
            "https://neuprint.janelia.org/api/dbmeta/datasets",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        return [
            Candidate(
                candidate_id="neuprint:probe_error",
                title="neuPrint probe failed",
                source_system="neuprint",
                status=CandidateStatus.BLOCKED,
                notes=str(exc),
                first_seen=now,
                last_seen=now,
            )
        ]

    keys = list(data.keys()) if isinstance(data, dict) else [str(x) for x in data]
    out: list[Candidate] = []
    known_local_hints = ("hemibrain", "manc", "optic-lobe", "optic_lobe")
    for ds in keys:
        cid = f"neuprint:dataset:{ds}"
        already_hint = any(h in ds.lower().replace(":", "_") for h in known_local_hints)
        out.append(
            Candidate(
                candidate_id=cid,
                title=f"neuPrint dataset {ds}",
                species="Drosophila melanogaster",
                source_system="neuprint",
                status=CandidateStatus.EVIDENCE_VERIFIED,
                reuse_score=90 if "manc" in ds or "hemibrain" in ds or "optic" in ds else 75,
                processing_level=0,
                evidence=[
                    EvidenceItem(
                        kind=EvidenceKind.NEUPRINT_DATASET,
                        source="neuprint.janelia.org/api/dbmeta/datasets",
                        detail=ds,
                        url=f"https://neuprint.janelia.org/?dataset={ds}",
                        observed_at=now,
                        payload={"dataset": ds},
                    )
                ],
                plan=IngestPlan(
                    method="none" if already_hint else "neuprint_subgraph",
                    dataset=ds,
                    fetch_edges=True,
                    include_skeletons=False,
                    estimated_final_bytes=50 * 1024**2,
                    auto_eligible=False,
                    block_reason="dataset_watch_only" if not already_hint else "covered_by_catalog_recipes",
                ),
                notes="Live neuPrint dataset. Prefer typed catalog recipes over full-dataset dumps.",
                tags=["neuprint", "live", "dataset"],
                first_seen=now,
                last_seen=now,
            )
        )
    return out


def probe_catalog_recipes(budget: AutonomyBudget) -> list[Candidate]:
    now = utc_now()
    token_ok = bool(os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN"))
    out: list[Candidate] = []
    for recipe in CATALOG_RECIPES:
        plan = plan_for_recipe(recipe, budget)
        evidence = [
            EvidenceItem(
                kind=EvidenceKind.NEUPRINT_TYPE_COUNT,
                source=recipe["dataset"],
                detail=recipe["type_regex"],
                url=f"https://neuprint.janelia.org/?dataset={recipe['dataset']}",
                observed_at=now,
                payload={"estimated_final_bytes": recipe.get("estimated_final_bytes")},
            )
        ]
        status = CandidateStatus.QUEUED if plan.auto_eligible else CandidateStatus.NEEDS_REVIEW
        if plan.block_reason == "already_local":
            status = CandidateStatus.AUTO_INGESTED
        elif not token_ok:
            status = CandidateStatus.BLOCKED
            plan.auto_eligible = False
            plan.block_reason = "neuprint_token_missing"
        out.append(
            Candidate(
                candidate_id=recipe["candidate_id"],
                title=recipe["title"],
                species=recipe.get("species"),
                source_system="neuprint",
                status=status,
                reuse_score=int(recipe.get("reuse_score", 90)),
                processing_level=int(recipe.get("processing_level", 0)),
                evidence=evidence,
                plan=plan,
                local_pack_id=plan.connectome_id if plan.block_reason == "already_local" else None,
                tags=list(recipe.get("tags") or []),
                first_seen=now,
                last_seen=now,
            )
        )
    return out


def probe_ibdb_species() -> list[Candidate]:
    now = utc_now()
    try:
        r = requests.get("https://insectbraindb.org/api/v2/species/", timeout=60)
        r.raise_for_status()
        species_list = r.json()
    except Exception as exc:  # noqa: BLE001
        return [
            Candidate(
                candidate_id="ibdb:probe_error",
                title="IBdb probe failed",
                source_system="ibdb",
                status=CandidateStatus.BLOCKED,
                notes=str(exc),
                first_seen=now,
                last_seen=now,
            )
        ]

    local = set(list_connectomes())
    # Species we already cover locally (substring match on pack names / known ids)
    covered_names = {
        "megalopta",
        "schistocerca",
        "rhyparobia",
        "bombus",
        "drosophila",
    }
    out: list[Candidate] = []
    for s in species_list:
        sid = s.get("id")
        name = s.get("scientific_name") or s.get("name") or f"species_{sid}"
        try:
            nr = requests.get(
                "https://insectbraindb.org/api/v2/neuron/",
                params={"species": sid},
                timeout=45,
            )
            neurons = nr.json() if nr.ok else []
            n_count = len(neurons) if isinstance(neurons, list) else 0
        except Exception:  # noqa: BLE001
            n_count = 0
        if n_count <= 0:
            continue
        low = name.lower()
        if any(c in low for c in covered_names):
            continue
        # Skip if a pack already mentions this taxon
        if any(name.split()[0].lower() in p for p in local):
            continue
        cid = f"ibdb:species:{sid}"
        out.append(
            Candidate(
                candidate_id=cid,
                title=f"IBdb {name} ({n_count} reconstructions)",
                species=name,
                source_system="ibdb",
                status=CandidateStatus.EVIDENCE_VERIFIED,
                reuse_score=min(85, 40 + n_count),
                processing_level=4,
                evidence=[
                    EvidenceItem(
                        kind=EvidenceKind.IBDB_SPECIES,
                        source="insectbraindb.org/api/v2/species",
                        detail=f"species_id={sid}; neurons={n_count}",
                        url="https://insectbraindb.org/",
                        observed_at=now,
                        payload={"species_id": sid, "neuron_count": n_count, "raw": {"id": sid, "name": name}},
                    )
                ],
                plan=IngestPlan(
                    method="ibdb_morphology",
                    species_label=name,
                    include_skeletons=True,
                    estimated_final_bytes=max(5, n_count) * 2 * 1024**2,
                    auto_eligible=False,
                    block_reason="ibdb_needs_review",
                ),
                notes="Morphology-layer candidate. Confirm experiment skeleton files before importing.",
                tags=["ibdb", "morphology", "candidate"],
                first_seen=now,
                last_seen=now,
            )
        )
    return out


def probe_registry_gaps() -> list[Candidate]:
    now = utc_now()
    local = set(list_connectomes())
    out: list[Candidate] = []
    try:
        reg = load_registry()
    except Exception as exc:  # noqa: BLE001
        return [
            Candidate(
                candidate_id="registry:probe_error",
                title="Registry probe failed",
                source_system="registry",
                status=CandidateStatus.BLOCKED,
                notes=str(exc),
                first_seen=now,
                last_seen=now,
            )
        ]

    for ds in reg.datasets:
        # Skip if any local pack mentions dataset_id stem
        stem = ds.dataset_id.split("_")[0]
        if any(stem in p or ds.dataset_id in p for p in local):
            continue
        if ds.connectomics_suitability in {"INACCESSIBLE"}:
            status = CandidateStatus.BLOCKED
        elif ds.access_status in {"PUBLIC_DOWNLOAD", "PUBLIC_STREAM"} and ds.raw_data_available:
            status = CandidateStatus.NEEDS_REVIEW
        else:
            status = CandidateStatus.DISCOVERED
        out.append(
            Candidate(
                candidate_id=f"registry:{ds.dataset_id}",
                title=ds.publication or ds.dataset_id,
                species=ds.species,
                source_system="registry",
                status=status,
                reuse_score=max(0, 100 - 5 * (ds.processability_rank or 20)),
                processing_level=None,
                evidence=[
                    EvidenceItem(
                        kind=EvidenceKind.REGISTRY_RECORD,
                        source="registry/registry.yaml",
                        detail=ds.dataset_id,
                        url=ds.source_URL_or_identifier,
                        observed_at=now,
                        payload={
                            "access_status": ds.access_status,
                            "suitability": ds.connectomics_suitability,
                            "rank": ds.processability_rank,
                        },
                    )
                ],
                plan=IngestPlan(
                    method="none",
                    auto_eligible=False,
                    block_reason="registry_watch",
                    estimated_final_bytes=0,
                ),
                notes=ds.notes,
                tags=["registry", str(ds.connectomics_suitability or "UNKNOWN")],
                first_seen=now,
                last_seen=now,
            )
        )
    return out


def probe_watchlist() -> list[Candidate]:
    now = utc_now()
    out: list[Candidate] = []
    for item in WATCHLIST_CANDIDATES:
        out.append(
            Candidate(
                candidate_id=item["candidate_id"],
                title=item["title"],
                species=item.get("species"),
                source_system=item.get("source_system", "watch"),
                status=CandidateStatus.NEEDS_REVIEW,
                reuse_score=int(item.get("reuse_score", 50)),
                processing_level=item.get("processing_level"),
                evidence=[
                    EvidenceItem(
                        kind=EvidenceKind.PUBLICATION_DOI
                        if "doi" in (item.get("url") or "").lower()
                        else EvidenceKind.REGISTRY_RECORD,
                        source=item.get("source_system", "watch"),
                        detail=item.get("notes"),
                        url=item.get("url"),
                        observed_at=now,
                    )
                ],
                plan=IngestPlan(method="none", auto_eligible=False, block_reason="watchlist"),
                notes=item.get("notes"),
                tags=list(item.get("tags") or []),
                first_seen=now,
                last_seen=now,
            )
        )
    # Seed discovery sources as long-lived watch notes
    for src in list_sources():
        out.append(
            Candidate(
                candidate_id=f"discovery:{src['name'].lower().replace(' ', '_')}",
                title=src["name"],
                source_system="discovery",
                status=CandidateStatus.NEEDS_REVIEW,
                reuse_score=40,
                evidence=[
                    EvidenceItem(
                        kind=EvidenceKind.PUBLICATION_DOI,
                        source=src["name"],
                        detail=src.get("method"),
                        url=src.get("url"),
                        observed_at=now,
                    )
                ],
                plan=IngestPlan(method="none", auto_eligible=False, block_reason="discovery_seed"),
                notes=src.get("method"),
                tags=["discovery_seed"],
                first_seen=now,
                last_seen=now,
            )
        )
    return out


def run_all_probes(budget: AutonomyBudget) -> tuple[list[Candidate], list[str], list[str]]:
    """Return candidates, probe names, errors."""
    probes: list[tuple[str, Any]] = [
        ("catalog_recipes", lambda: probe_catalog_recipes(budget)),
        ("neuprint_datasets", probe_neuprint_datasets),
        ("ibdb_species", probe_ibdb_species),
        ("registry_gaps", probe_registry_gaps),
        ("watchlist", probe_watchlist),
    ]
    all_c: list[Candidate] = []
    names: list[str] = []
    errors: list[str] = []
    for name, fn in probes:
        names.append(name)
        try:
            all_c.extend(fn())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    return all_c, names, errors
