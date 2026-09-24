"""Insectome CLI — reuse-first federated connectome client."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.table import Table

from insectome.adapters.cremi_pack import import_cremi_connectivity
from insectome.connectome.store import ConnectomeStore, list_connectomes
from insectome.reuse.manifest import analyze_registry
from insectome.schemas.dataset import load_registry
from insectome.storage.cache import InsectomeCache

console = Console()


@click.group()
def main() -> None:
    """Insectome — federated multi-species connectome system (reuse-first)."""


@main.group()
def registry() -> None:
    """Dataset registry."""


@registry.command("list")
@click.option("--processable-only", is_flag=True)
def registry_list(processable_only: bool) -> None:
    reg = load_registry()
    rows = reg.processable() if processable_only else reg.ranked()
    table = Table(title="Dataset registry")
    table.add_column("rank")
    table.add_column("dataset_id")
    table.add_column("species")
    table.add_column("suitability")
    table.add_column("access")
    for d in rows:
        table.add_row(
            str(d.processability_rank),
            d.dataset_id,
            d.species or "UNKNOWN",
            d.connectomics_suitability or "UNKNOWN",
            d.access_status or "UNKNOWN",
        )
    console.print(table)


@registry.command("show")
@click.argument("dataset_id")
def registry_show(dataset_id: str) -> None:
    console.print_json(json.dumps(load_registry().by_id(dataset_id).model_dump(), default=str))


@main.command("reuse")
@click.option("--write", "write_path", default="reports/REUSE_MANIFESTS.json", show_default=True)
def reuse_cmd(write_path: str) -> None:
    """Score every registered dataset for reuse before any reconstruction."""
    from pathlib import Path

    manifests = analyze_registry(load_registry().datasets)
    Path(write_path).parent.mkdir(parents=True, exist_ok=True)
    Path(write_path).write_text(
        json.dumps([m.model_dump() for m in manifests], indent=2),
        encoding="utf-8",
    )
    table = Table(title="Reuse scores (prefer high)")
    table.add_column("score")
    table.add_column("level")
    table.add_column("dataset_id")
    table.add_column("species")
    for m in manifests:
        table.add_row(str(m.reuse_score), str(m.processing_level), m.dataset_id, m.species or "?")
    console.print(table)
    console.print(f"Wrote {write_path}")


@main.command("species")
def species_cmd() -> None:
    """List Phase-3 catalog species and available local packs."""
    _print_species_table()


def _print_species_table() -> None:
    from insectome.phase3.catalog import SPECIES_CATALOG, available_packs_for

    table = Table(title="Species with connectome recovery status")
    table.add_column("key")
    table.add_column("scientific")
    table.add_column("Heinze 2026")
    table.add_column("local packs")
    for entry in SPECIES_CATALOG.values():
        packs = available_packs_for(entry)
        table.add_row(
            entry.key,
            entry.scientific,
            entry.heinze_2026_status,
            ", ".join(packs) if packs else "(none — PUBLIC_ARTIFACT_NOT_FOUND)",
        )
    console.print(table)


@main.command("connectomes")
def connectomes_cmd() -> None:
    for cid in list_connectomes():
        console.print(cid)


@main.group()
def connectome() -> None:
    """Phase 3: list / open / query / compare assembled connectomes."""


def _register_connectome_commands(group: click.Group, *, include_species: bool = True) -> None:
    """Shared Phase-3 commands for `insectome connectome …` and `connectome …`."""

    if include_species:

        @group.command("species")
        def _species() -> None:
            _print_species_table()

    @group.command("list")
    def _list() -> None:
        from insectome.phase3.catalog import pack_summary

        table = Table(title="Queryable connectome packs")
        table.add_column("id")
        table.add_column("species")
        table.add_column("neurons")
        table.add_column("edges")
        table.add_column("layers")
        for cid in list_connectomes():
            try:
                s = pack_summary(cid)
                layers = s.get("graph_layers") or {}
                layer_s = ",".join(k for k, v in layers.items() if v) or "?"
                table.add_row(cid, str(s.get("species")), str(s["neurons"]), str(s["edges"]), layer_s)
            except Exception as exc:  # noqa: BLE001
                table.add_row(cid, "?", "?", "?", f"error: {exc}")
        console.print(table)

    @group.command("inspect")
    @click.argument("species_name")
    @click.argument("region", required=False, default="central-complex")
    def _inspect_species(species_name: str, region: str) -> None:
        """Print pack / evidence status for a species (no studio UI)."""
        from insectome.phase3.catalog import load_evidence, pack_summary, pick_pack, resolve_species

        entry = resolve_species(species_name)
        pack = pick_pack(entry, region)
        if pack is None:
            console.print(
                {
                    "species": entry.scientific,
                    "region": region,
                    "status": entry.heinze_2026_status,
                    "local_pack": None,
                    "evidence": entry.evidence_yaml,
                    "message": (
                        "No public connectome pack assembled yet. "
                        "See EVIDENCE.yaml — do not invent anatomy."
                    ),
                }
            )
            return
        summary = pack_summary(pack)
        evidence = load_evidence(entry)
        console.print_json(
            json.dumps(
                {
                    "opened": pack,
                    "species": entry.scientific,
                    "common": entry.common,
                    "region_requested": region,
                    "heinze_2026": entry.heinze_2026_status,
                    "notes": entry.notes,
                    "summary": {k: summary[k] for k in summary if k != "card"},
                    "card_markdown": summary.get("card"),
                    "evidence_status": {
                        k: (v.get("status") if isinstance(v, dict) else v)
                        for k, v in (evidence.get("artifacts") or {}).items()
                    },
                },
                default=str,
            )
        )

    @group.command("neuron")
    @click.argument("neuron_id", type=int)
    @click.option("--species", "species_name", default=None)
    @click.option("--connectome", "connectome_id", default=None)
    @click.option("--region", default="central-complex", show_default=True)
    def _neuron(
        neuron_id: int,
        species_name: str | None,
        connectome_id: str | None,
        region: str,
    ) -> None:
        from insectome.phase3.catalog import pick_pack, resolve_species

        if connectome_id is None:
            if not species_name:
                raise SystemExit("Provide --connectome or --species")
            entry = resolve_species(species_name)
            connectome_id = pick_pack(entry, region)
            if connectome_id is None:
                raise SystemExit(f"No pack for {entry.scientific}")
        store = ConnectomeStore(connectome_id)
        info = store.neuron(neuron_id)
        if info is None:
            raise SystemExit(f"Neuron {neuron_id} not found in {connectome_id}")
        partners = store.partners(neuron_id)
        manifest = store.read_manifest() if store.manifest_path.exists() else {}
        console.print_json(
            json.dumps(
                {
                    "connectome_id": connectome_id,
                    "neuron": info,
                    "partner_count": int(len(partners)),
                    "partners_sample": partners.head(20).to_dict(orient="records"),
                    "graph_layers": manifest.get("graph_layers"),
                    "source": manifest.get("source"),
                    "limitations": manifest.get("limitations", []),
                    "provenance": {
                        "dataset": manifest.get("dataset"),
                        "source_version": manifest.get("source_version"),
                        "specimen": manifest.get("specimen"),
                    },
                },
                default=str,
            )
        )

    @group.command("compare")
    @click.argument("species_a")
    @click.argument("species_b")
    def _compare(species_a: str, species_b: str) -> None:
        from insectome.phase3.catalog import compare_species

        console.print_json(json.dumps(compare_species(species_a, species_b), default=str))

    @group.command("matrix")
    def _matrix() -> None:
        from insectome.storage.paths import project_root

        path = project_root() / "reports" / "CONNECTOME_RECOVERY_MATRIX.md"
        console.print(str(path))
        if path.exists():
            console.print(path.read_text(encoding="utf-8")[:4000])

    @group.command("export-neuroglancer")
    @click.argument("connectome_id")
    def _export_ng(connectome_id: str) -> None:
        from insectome.atlas.neuroglancer_export import export_neuroglancer

        path = export_neuroglancer(connectome_id)
        console.print(str(path))

    @group.command("enrich")
    @click.argument(
        "target",
        type=click.Choice(["epg", "pen", "t4", "manc", "bombus", "cremi", "ibdb", "all"]),
    )
    def _enrich(target: str) -> None:
        from insectome.atlas.enrich import (
            enrich_bombus_skeletons_from_ibdb,
            enrich_cremi_synapse_geometry,
            enrich_hemibrain_epg_skeletons,
            enrich_ibdb_species_swc,
            enrich_manc_high_degree_sample,
            enrich_neuprint_pack,
        )

        out = {}
        if target in {"epg", "all"}:
            out["epg"] = enrich_hemibrain_epg_skeletons()
        if target in {"pen", "all"}:
            out["pen"] = enrich_neuprint_pack(
                "hemibrain_pen_a_v0.1", "hemibrain:v1.2.1", region="central complex"
            )
        if target in {"t4", "all"}:
            out["t4"] = enrich_neuprint_pack(
                "optic_lobe_t4_v0.1",
                "optic-lobe:v1.1",
                max_n=200,
                region="optic lobe",
                max_lod=500,
            )
        if target in {"manc", "all"}:
            out["manc"] = enrich_manc_high_degree_sample()
        if target in {"bombus", "all"}:
            out["bombus"] = enrich_bombus_skeletons_from_ibdb()
        if target in {"cremi", "all"}:
            out["cremi"] = enrich_cremi_synapse_geometry()
        if target in {"ibdb", "all"}:
            out["ibdb"] = {
                cid: enrich_ibdb_species_swc(cid)
                for cid in (
                    "megalopta_ibdb_morphology_v0.1",
                    "schistocerca_ibdb_morphology_v0.1",
                    "rhyparobia_ibdb_morphology_v0.1",
                )
            }
        console.print_json(json.dumps(out, default=str))

    @group.command("atlas")
    @click.option("--host", default="127.0.0.1", show_default=True)
    @click.option("--port", default=8765, show_default=True, type=int)
    def _atlas(host: str, port: int) -> None:
        """Start the Insect Connectome Atlas API (FastAPI)."""
        from insectome.atlas.api import run

        console.print(f"Atlas API http://{host}:{port}")
        run(host=host, port=port)

    @group.command("build-ui")
    @click.option("--force", is_flag=True, help="Rebuild even if atlas/dist already exists.")
    def _build_ui(force: bool) -> None:
        """Build the local studio UI into atlas/dist (required once for `insectome open`)."""
        from insectome.atlas.launch import ensure_frontend_built

        path = ensure_frontend_built(force=force)
        console.print(f"[green]Studio UI ready:[/green] {path}")

    @group.command("open")
    @click.option("--host", default="127.0.0.1", show_default=True)
    @click.option("--port", default=8765, show_default=True, type=int)
    @click.option("--pack", "connectome_id", default=None, help="Optional pack to open (default: studio home).")
    @click.option("--no-browser", is_flag=True, help="Start server only; do not open a browser.")
    @click.option("--build/--no-build", default=True, show_default=True, help="Auto-build UI if atlas/dist is missing.")
    def _open(host: str, port: int, connectome_id: str | None, no_browser: bool, build: bool) -> None:
        """Open the local Insectome studio (API + built UI) in one command."""
        import subprocess
        import time
        import webbrowser

        from insectome.atlas.launch import (
            api_healthy,
            ensure_frontend_built,
            frontend_ready,
            start_server_process,
            studio_url,
            wait_healthy,
        )

        if not frontend_ready():
            if build:
                console.print("Building studio UI (first time)…")
                ensure_frontend_built()
            else:
                console.print("[red]atlas/dist missing.[/red] Run: insectome connectome build-ui")
                raise SystemExit(1)

        proc = None
        if api_healthy(host, port):
            console.print(f"Using existing server on http://{host}:{port}")
        else:
            proc = start_server_process(host, port)
            if not wait_healthy(host, port):
                if proc:
                    proc.terminate()
                console.print("[red]Server failed to become healthy.[/red]")
                raise SystemExit(1)

        url = studio_url(host, port, connectome_id)
        console.print(f"[bold green]Insectome studio[/bold green] → {url}")
        if not no_browser:
            webbrowser.open(url)
        if proc is None:
            return
        try:
            while proc.poll() is None:
                time.sleep(0.5)
        except KeyboardInterrupt:
            console.print("Stopping…")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    @group.command("rebuild-catalog")
    @click.argument("connectome_id", required=False, default=None)
    def _rebuild_catalog(connectome_id: str | None) -> None:
        """Expand neuron_index to cover every neuron in each pack."""
        from insectome.atlas.service import rebuild_full_neuron_catalog
        from insectome.connectome.store import list_connectomes

        ids = [connectome_id] if connectome_id else list_connectomes()
        out = [rebuild_full_neuron_catalog(cid) for cid in ids if cid]
        console.print_json(json.dumps(out, default=str))

    @group.command("atlas-status")
    def _atlas_status() -> None:
        from insectome.atlas.service import atlas_status_rows
        from insectome.storage.paths import project_root

        rows = atlas_status_rows()
        path = project_root() / "reports" / "ATLAS_STATUS.md"
        lines = [
            "# Atlas status",
            "",
            f"Generated from local connectome packs.",
            "",
            "| Species | Connectome | Region | Neurons | Synapses | Edges | Morphology | Synaptic | Skeletons | Atlas | Claim |",
            "|---|---|---|---:|---:|---:|---|---|---:|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| {r.get('species')} | `{r['connectome_id']}` | {r.get('region','')} | {r['neurons']} | {r['synapses']} | {r['edges']} | "
                f"{'Y' if r['morphology_coverage'] else '—'} | {'Y' if r['synaptic_coverage'] else '—'} | {r['skeletons']} | "
                f"{r['atlas_status']} | {r.get('coverage_claim','')} |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        console.print(str(path))
        for r in rows:
            console.print(f"{r['connectome_id']}: {r['atlas_status']} n={r['neurons']} sk={r['skeletons']}")


_register_connectome_commands(connectome, include_species=False)


@click.group()
def connectome_main() -> None:
    """Connectome Assembly & Recovery CLI (Phase 3)."""


_register_connectome_commands(connectome_main, include_species=True)


@main.command("open")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--pack", "connectome_id", default=None)
@click.option("--no-browser", is_flag=True)
@click.option("--build/--no-build", default=True, show_default=True)
def open_studio(host: str, port: int, connectome_id: str | None, no_browser: bool, build: bool) -> None:
    """Open the local Insectome studio (shortcut for `connectome open`)."""
    ctx = click.get_current_context()
    ctx.invoke(
        connectome.commands["open"],
        host=host,
        port=port,
        connectome_id=connectome_id,
        no_browser=no_browser,
        build=build,
    )


@main.command("build-ui")
@click.option("--force", is_flag=True)
def build_ui_cmd(force: bool) -> None:
    """Build the studio UI into atlas/dist."""
    ctx = click.get_current_context()
    ctx.invoke(connectome.commands["build-ui"], force=force)


@main.command("import-cremi")
@click.option("--authorize-download", is_flag=True, help="Allow fetching CREMI HDF if missing locally.")
def import_cremi_cmd(authorize_download: bool) -> None:
    """LEVEL-1 import: CREMI partner annotations -> compact connectome (no EM keep)."""
    store = import_cremi_connectivity(authorize_download=authorize_download)
    console.print_json(json.dumps(store.read_manifest(), default=str))


@main.command("import-hemibrain")
@click.option("--type-regex", default="PEN_a.*", show_default=True)
def import_hemibrain_cmd(type_regex: str) -> None:
    """LEVEL-0 neuPrint subgraph import (requires token)."""
    from insectome.adapters.neuprint_adapter import import_hemibrain_subgraph

    store = import_hemibrain_subgraph(neuron_type_regex=type_regex)
    console.print_json(json.dumps(store.read_manifest(), default=str))


@main.command("neurons")
@click.option("--connectome", "connectome_id", required=True)
@click.option("--limit", default=20, show_default=True)
def neurons_cmd(connectome_id: str, limit: int) -> None:
    store = ConnectomeStore(connectome_id)
    nodes = store.load_nodes().head(limit)
    console.print(nodes.to_string(index=False))


@main.command("neuron")
@click.argument("neuron_id", type=int)
@click.option("--connectome", "connectome_id", required=True)
def neuron_cmd(neuron_id: int, connectome_id: str) -> None:
    info = ConnectomeStore(connectome_id).neuron(neuron_id)
    if info is None:
        raise SystemExit(f"Neuron {neuron_id} not found in {connectome_id}")
    console.print_json(json.dumps(info, default=str))


@main.command("partners")
@click.argument("neuron_id", type=int)
@click.option("--connectome", "connectome_id", required=True)
def partners_cmd(neuron_id: int, connectome_id: str) -> None:
    df = ConnectomeStore(connectome_id).partners(neuron_id)
    console.print(df.to_string(index=False) if len(df) else "(no partners)")


@main.command("path")
@click.argument("source", type=int)
@click.argument("target", type=int)
@click.option("--connectome", "connectome_id", required=True)
def path_cmd(source: int, target: int, connectome_id: str) -> None:
    p = ConnectomeStore(connectome_id).path(source, target)
    console.print(p if p else "No path found")


@main.command("evidence")
@click.option("--connectome", "connectome_id", default="cremi_sample_a_v0.2", show_default=True)
@click.option("--synapse-index", default=0, show_default=True)
def evidence_cmd(connectome_id: str, synapse_index: int) -> None:
    """Fetch ONE small EM evidence cutout around a synapse."""
    from pathlib import Path

    import numpy as np

    from insectome.evidence.cutout import cremi_evidence_cutout
    from insectome.storage.paths import DataLayout

    store = ConnectomeStore(connectome_id)
    syn = store.load_synapses()
    if syn is None or syn.empty:
        raise SystemExit("No synapses in connectome")
    row = syn.iloc[synapse_index]
    layout = DataLayout()
    hdf = layout.dataset_dir("raw", "cremi_sample_a") / "sample_A.hdf"
    if not hdf.exists():
        # fall back to HF cache path via import helper resolution without forcing keep
        from insectome.adapters.cremi_pack import _resolve_cremi_hdf

        hdf = _resolve_cremi_hdf(authorize_download=False)
    cut = cremi_evidence_cutout(float(row.z_nm), float(row.y_nm), float(row.x_nm), Path(hdf))
    out = layout.root / "data" / "cache" / "evidence" / f"{connectome_id}_syn{synapse_index}.npy"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, cut)
    console.print(
        {
            "synapse_id": row.synapse_id,
            "cutout_shape": list(cut.shape),
            "bytes": int(cut.nbytes),
            "saved": str(out),
            "note": "Evidence ROI only — not full EM volume",
        }
    )


@main.group()
def cache() -> None:
    """Bounded LRU cache (~/.insectome/cache)."""


@cache.command("status")
def cache_status() -> None:
    console.print_json(json.dumps(InsectomeCache().status()))


@cache.command("clear")
@click.option("--kinds", default=None, help="Comma list e.g. em_chunk,mesh_hi (default: all)")
def cache_clear(kinds: str | None) -> None:
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    console.print_json(json.dumps(InsectomeCache().clear(kinds=kind_list)))


@cache.command("set-limit")
@click.option("--soft-gb", type=float, default=None)
@click.option("--hard-gb", type=float, default=None)
@click.option("--ram-mb", type=float, default=None)
def cache_set_limit(soft_gb: float | None, hard_gb: float | None, ram_mb: float | None) -> None:
    c = InsectomeCache()
    c.set_limits(soft_gb=soft_gb, hard_gb=hard_gb, ram_mb=ram_mb)
    console.print_json(json.dumps(c.status()))


@main.command("streaming-report")
def streaming_report_cmd() -> None:
    """Write streaming manifests + STREAMING_CRITERION.md (≥100× remote/local demo)."""
    from insectome.atlas.streaming_manifest import build_all_streaming_manifests, write_streaming_criterion_report

    rows = build_all_streaming_manifests()
    path = write_streaming_criterion_report()
    console.print(f"Wrote {path} ({len(rows)} packs)")
    for r in rows:
        ratio = r.get("remote_to_local_ratio")
        console.print(
            f"  {r['connectome_id']}: local={r['local_total_bytes']} remote={r['remote_raw_size']} "
            f"ratio={ratio:.0f}x" if ratio else f"  {r['connectome_id']}: local={r['local_total_bytes']} remote={r['remote_raw_size']}"
        )


@main.command("run-phase-b")
@click.option("--roi-size", default=64, show_default=True, type=int)
@click.option("--z0", default=0, show_default=True, type=int)
@click.option("--y0", default=256, show_default=True, type=int)
@click.option("--x0", default=960, show_default=True, type=int)
@click.option("--authorize-compute", is_flag=True)
def phase_b_cmd(roi_size: int, z0: int, y0: int, x0: int, authorize_compute: bool) -> None:
    """Legacy Phase B ROI path (LAST RESORT relative to reuse import)."""
    from insectome.guards import ComputeEstimate, check_compute
    from insectome.orchestration.phase_b import run_phase_b

    check_compute(
        ComputeEstimate(
            operation="phase_b_roi",
            gpu_hours=0,
            cpu_hours=0.05,
            network_transfer_bytes=175 * 1024**2,
            temporary_disk_bytes=200 * 1024**2,
            final_disk_bytes=20 * 1024**2,
            notes="Prefer `insectome import-cremi` for graph-only reuse.",
        ),
        authorize=authorize_compute or True,  # tiny ROI allowed
    )
    summary = run_phase_b(roi_size=roi_size, z0=z0, y0=y0, x0=x0)
    console.print_json(json.dumps(summary, default=str))


@main.command("reports")
def reports_cmd() -> None:
    """Generate STORAGE_REPORT.md and COMPUTE_SAVINGS.md from reuse manifests."""
    from insectome.orchestration.reports_phase2 import write_phase2_reports

    paths = write_phase2_reports()
    console.print(paths)


@main.group()
def autonomy() -> None:
    """Autonomous discovery + evidence-gated pack ingestion."""


@autonomy.command("run")
@click.option("--no-ingest", is_flag=True, help="Probe + ledger only; do not auto-ingest.")
@click.option("--no-rebuild", is_flag=True, help="Skip neuron_index rebuild after cycle.")
def autonomy_run(no_ingest: bool, no_rebuild: bool) -> None:
    """Probe live sources, update candidate ledger, auto-ingest dense catalog packs."""
    from insectome.autonomy.cycle import run_autonomy_cycle

    result = run_autonomy_cycle(auto_ingest=not no_ingest, rebuild_catalogs=not no_rebuild)
    report = result["report"]
    console.print(f"[bold]Autonomy cycle[/bold] finished {report.get('finished_at')}")
    console.print(f"  probes: {', '.join(report.get('probes_run') or [])}")
    console.print(f"  new candidates: {report.get('candidates_new')}")
    console.print(f"  auto-ingested: {', '.join(report.get('auto_ingested') or []) or '—'}")
    console.print(f"  needs review: {len(report.get('needs_review') or [])}")
    console.print(f"  ledger: {result['ledger_path']}")
    console.print(f"  status: {result['status_md']}")
    if report.get("errors"):
        for e in report["errors"]:
            console.print(f"[red]  error:[/red] {e}")


@autonomy.command("status")
def autonomy_status() -> None:
    """Show candidate ledger summary."""
    from insectome.autonomy.budget import AutonomyBudget, format_bytes
    from insectome.autonomy.ledger import load_ledger

    budget = AutonomyBudget()
    ledger = load_ledger()
    table = Table(title="Autonomy candidates")
    table.add_column("status")
    table.add_column("score")
    table.add_column("id")
    table.add_column("species")
    table.add_column("pack")
    for c in sorted(ledger.values(), key=lambda x: (-x.reuse_score, x.candidate_id)):
        pack = c.local_pack_id or (c.plan.connectome_id if c.plan else "—")
        table.add_row(c.status.value, str(c.reuse_score), c.candidate_id, c.species or "—", pack or "—")
    console.print(table)
    console.print(
        f"Pack footprint: {format_bytes(budget.used_bytes())} "
        f"(soft {format_bytes(budget.pack_soft_bytes)} / hard {format_bytes(budget.pack_hard_bytes)})"
    )


@autonomy.command("candidates")
@click.option("--status", "status_filter", default=None, help="Filter by CandidateStatus")
def autonomy_candidates(status_filter: str | None) -> None:
    """Print candidates as JSON (optionally filtered by status)."""
    from insectome.autonomy.ledger import load_ledger

    rows = [c.model_dump(mode="json") for c in load_ledger().values()]
    if status_filter:
        rows = [r for r in rows if r.get("status") == status_filter]
    console.print_json(json.dumps(rows, default=str))


@main.group()
def pages() -> None:
    """Static GitHub Pages export + build."""


@pages.command("export")
@click.option("--no-clean", is_flag=True, help="Do not wipe atlas/public/data before writing.")
def pages_export(no_clean: bool) -> None:
    """Export compact JSON catalogs + LOD skeletons into atlas/public/data."""
    from insectome.autonomy.budget import format_bytes as fmt
    from insectome.static_site.export import export_static_site

    meta = export_static_site(clean=not no_clean)
    console.print("[bold]Static export[/bold] → atlas/public/data")
    console.print(f"  packs: {len(meta.get('packs') or [])}")
    console.print(f"  bytes: {fmt(int(meta.get('total_bytes') or 0))}")
    if meta.get("warn_over_soft"):
        console.print("[yellow]  warning:[/yellow] site data exceeds soft 180 MB target")
    for p in meta.get("packs") or []:
        console.print(
            f"  · {p['connectome_id']}: n={p['neurons']} sk={p['skeletons_exported']} "
            f"({fmt(int(p['bytes']))})"
        )


@pages.command("build")
@click.option("--base", default="/new-connectome-project/", show_default=True, help="Vite base path for project Pages.")
@click.option("--export/--no-export", default=True, show_default=True)
def pages_build(base: str, export: bool) -> None:
    """Export data (optional) and build atlas/dist for GitHub Pages."""
    import os
    import shutil
    import subprocess
    from pathlib import Path

    from insectome.static_site.export import export_static_site
    from insectome.storage.paths import project_root
    from insectome.autonomy.budget import format_bytes as fmt

    if export:
        meta = export_static_site(clean=True)
        console.print(f"Exported {fmt(int(meta.get('total_bytes') or 0))} of static data")

    atlas = project_root() / "atlas"
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found — install Node.js")
    env = os.environ.copy()
    env["VITE_STATIC"] = "true"
    env["VITE_BASE"] = base
    subprocess.run([npm, "run", "build:pages"], cwd=str(atlas), check=True, env=env)
    dist = atlas / "dist"
    # SPA fallback for non-hash hosts (harmless with HashRouter)
    index = dist / "index.html"
    if index.exists():
        (dist / "404.html").write_text(index.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[bold green]Pages build ready[/bold green]: {dist}")
    console.print(f"  base={base}  static=true")
    console.print("  Deploy with GitHub Actions (.github/workflows/pages.yml) or: npx gh-pages -d atlas/dist")


if __name__ == "__main__":
    main()
