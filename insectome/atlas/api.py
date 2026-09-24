"""FastAPI atlas data API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from insectome.atlas import service
from insectome.atlas.neuroglancer_export import export_neuroglancer
from insectome.connectome.store import ConnectomeStore, list_connectomes
from insectome.storage.paths import project_root

app = FastAPI(
    title="Insect Connectome Atlas API",
    version="0.4.0",
    description="Sparse, provenance-aware multi-species connectome atlas",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/species")
def species() -> list[dict[str, Any]]:
    return service.list_species_atlas()


@app.get("/api/species/{key}")
def species_one(key: str) -> dict[str, Any]:
    for s in service.list_species_atlas():
        if s["key"] == key:
            return s
    raise HTTPException(404, "species not found")


@app.get("/api/connectomes")
def connectomes() -> list[dict[str, Any]]:
    return service.atlas_status_rows()


@app.get("/api/connectomes/{connectome_id}")
def connectome(connectome_id: str) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    if not store.manifest_path.exists() and not (store.dir / "nodes.parquet").exists():
        raise HTTPException(404, "connectome not found")
    man = store.read_manifest() if store.manifest_path.exists() else {}
    status = next((r for r in service.atlas_status_rows() if r["connectome_id"] == connectome_id), {})
    return {"manifest": man, "status": status}


@app.get("/api/connectomes/{connectome_id}/neurons")
def neurons(
    connectome_id: str,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    idx = service.load_index(connectome_id).copy()
    # Prefer skeletoned, then high-degree — denser scientific browsing
    if "has_skeleton" in idx.columns:
        idx["_sk"] = idx["has_skeleton"].fillna(False).astype(bool)
    else:
        idx["_sk"] = False
    din = idx["degree_in"] if "degree_in" in idx.columns else 0
    dout = idx["degree_out"] if "degree_out" in idx.columns else 0
    idx["_deg"] = (
        (din.fillna(0).astype(int) if hasattr(din, "fillna") else 0)
        + (dout.fillna(0).astype(int) if hasattr(dout, "fillna") else 0)
    )
    idx = idx.sort_values(["_sk", "_deg"], ascending=[False, False], kind="mergesort")
    idx = idx.drop(columns=["_sk", "_deg"], errors="ignore")
    if q:
        ql = q.lower()
        mask = (
            idx["source_id"].astype(str).str.contains(ql)
            | idx.get("name", pd_series_empty(idx)).astype(str).str.lower().str.contains(ql)
            | idx.get("cell_type", pd_series_empty(idx)).astype(str).str.lower().str.contains(ql)
        )
        idx = idx[mask]
    total = len(idx)
    page = idx.iloc[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "neurons": page.to_dict(orient="records")}


def pd_series_empty(idx):
    import pandas as pd

    return pd.Series([""] * len(idx))


@app.get("/api/connectomes/{connectome_id}/neurons/{source_id}")
def neuron(connectome_id: str, source_id: int) -> dict[str, Any]:
    try:
        return service.neuron_detail(connectome_id, source_id)
    except KeyError:
        raise HTTPException(404, "neuron not found") from None


@app.get("/api/connectomes/{connectome_id}/neurons/{source_id}/partners")
def partners(connectome_id: str, source_id: int) -> dict[str, Any]:
    detail = service.neuron_detail(connectome_id, source_id)
    return {
        "upstream": detail["upstream"],
        "downstream": detail["downstream"],
        "partners": detail["partners"],
    }


@app.get("/api/connectomes/{connectome_id}/neurons/{source_id}/skeleton")
def skeleton(connectome_id: str, source_id: int, lod: bool = True) -> dict[str, Any]:
    try:
        return service.skeleton_payload(connectome_id, source_id, lod=lod)
    except FileNotFoundError:
        raise HTTPException(404, "skeleton not found") from None


@app.get("/api/connectomes/{connectome_id}/skeletons/batch")
def skeletons_batch(
    connectome_id: str,
    limit: int = Query(100, ge=1, le=2000),
    lod: bool = True,
) -> dict[str, Any]:
    return service.batch_skeletons(connectome_id, limit=limit, lod=lod)


@app.get("/api/connectomes/{connectome_id}/silhouettes")
def silhouettes(
    connectome_id: str,
    limit: int = Query(120, ge=1, le=500),
    size: int = Query(96, ge=48, le=256),
    ids: str | None = Query(None, description="Comma-separated source ids"),
) -> dict[str, Any]:
    from insectome.atlas.silhouettes import batch_silhouettes

    source_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    return batch_silhouettes(connectome_id, limit=limit, size=size, source_ids=source_ids)


@app.get("/api/connectomes/{connectome_id}/paths")
def paths(connectome_id: str, source: int, target: int, cutoff: int = 4) -> dict[str, Any]:
    return service.path_query(connectome_id, source, target, cutoff=cutoff)


@app.get("/api/connectomes/{connectome_id}/synapses")
def synapses(connectome_id: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    store = ConnectomeStore(connectome_id)
    syn = store.load_synapses()
    if syn is None or syn.empty:
        return {"total": 0, "synapses": []}
    return {
        "total": int(len(syn)),
        "synapses": syn.iloc[offset : offset + limit].to_dict(orient="records"),
    }


@app.get("/api/connectomes/{connectome_id}/synapses/{synapse_index}/em")
def synapse_em(connectome_id: str, synapse_index: int) -> dict[str, Any]:
    if not connectome_id.startswith("cremi"):
        raise HTTPException(400, "EM evidence cutouts currently wired for CREMI packs only")
    try:
        return service.cremi_em_cutout_b64(connectome_id, synapse_index)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/connectomes/{connectome_id}/export-neuroglancer")
def export_ng(connectome_id: str) -> dict[str, Any]:
    try:
        path = export_neuroglancer(connectome_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    return {"path": str(path)}


@app.get("/api/atlas/status")
def atlas_status() -> list[dict[str, Any]]:
    return service.atlas_status_rows()


@app.get("/api/storage")
def storage_status() -> dict[str, Any]:
    from insectome.storage.cache import InsectomeCache

    return InsectomeCache().status()


@app.post("/api/storage/limits")
def storage_limits(soft_gb: float | None = None, hard_gb: float | None = None, ram_mb: float | None = None) -> dict[str, Any]:
    from insectome.storage.cache import InsectomeCache

    c = InsectomeCache()
    c.set_limits(soft_gb=soft_gb, hard_gb=hard_gb, ram_mb=ram_mb)
    return c.status()


@app.post("/api/storage/clear")
def storage_clear(kinds: str | None = Query(None, description="Comma list: em_chunk,mesh_hi,mesh_lo,skeleton or omit for all")) -> dict[str, Any]:
    from insectome.storage.cache import InsectomeCache

    c = InsectomeCache()
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    result = c.clear(kinds=kind_list)
    result["status"] = c.status()
    return result


@app.get("/api/connectomes/{connectome_id}/streaming")
def streaming_manifest(connectome_id: str) -> dict[str, Any]:
    from insectome.atlas.streaming_manifest import build_streaming_manifest

    try:
        return build_streaming_manifest(connectome_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/telemetry")
def telemetry() -> dict[str, Any]:
    from insectome.storage.cache import InsectomeCache

    cache = InsectomeCache().status()
    return {
        "cache": cache,
        "architecture": "zero-storage-streaming",
        "note": "GPU/network live counters are UI-side; server reports cache + fetch queue.",
    }


@app.get("/api/autonomy/status")
def autonomy_status() -> dict[str, Any]:
    from insectome.autonomy.budget import AutonomyBudget, format_bytes
    from insectome.autonomy.ledger import load_ledger

    budget = AutonomyBudget()
    ledger = load_ledger()
    candidates = [c.model_dump(mode="json") for c in ledger.values()]
    by_status: dict[str, int] = {}
    for c in candidates:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    return {
        "pack_bytes": budget.used_bytes(),
        "pack_bytes_label": format_bytes(budget.used_bytes()),
        "soft_limit_bytes": budget.pack_soft_bytes,
        "hard_limit_bytes": budget.pack_hard_bytes,
        "candidate_count": len(candidates),
        "by_status": by_status,
        "candidates": sorted(candidates, key=lambda x: (-x.get("reuse_score", 0), x.get("candidate_id", ""))),
    }


@app.post("/api/autonomy/run")
def autonomy_run(auto_ingest: bool = True, rebuild_catalogs: bool = True) -> dict[str, Any]:
    from insectome.autonomy.cycle import run_autonomy_cycle

    try:
        return run_autonomy_cycle(auto_ingest=auto_ingest, rebuild_catalogs=rebuild_catalogs)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc


def _frontend_dir():
    return project_root() / "atlas" / "dist"


def mount_studio_ui(application: FastAPI) -> None:
    """Serve the built React studio (atlas/dist) with SPA fallback for client routes."""
    frontend = _frontend_dir()
    if not frontend.exists() or not (frontend / "index.html").exists():
        return

    assets = frontend / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=str(assets)), name="studio_assets")

    @application.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # Never shadow API — those routes are registered first, but guard anyway
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = (frontend / full_path).resolve()
        try:
            candidate.relative_to(frontend.resolve())
        except ValueError as exc:
            raise HTTPException(404, "not found") from exc
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend / "index.html")


mount_studio_ui(app)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run("insectome.atlas.api:app", host=host, port=port, reload=False)
