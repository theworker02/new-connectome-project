"""Phase 3 species ↔ connectome pack catalog (no specimen merging)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from insectome.connectome.store import ConnectomeStore, list_connectomes
from insectome.storage.paths import project_root


@dataclass(frozen=True)
class SpeciesEntry:
    key: str
    scientific: str
    common: str
    aliases: tuple[str, ...]
    packs: tuple[str, ...]
    evidence_yaml: str
    heinze_2026_status: str
    notes: str = ""


# Canonical catalog — packs must exist under data/connectomes/ when listed as available.
SPECIES_CATALOG: dict[str, SpeciesEntry] = {
    "drosophila": SpeciesEntry(
        key="drosophila",
        scientific="Drosophila melanogaster",
        common="fruit fly",
        aliases=("fly", "drosophila_melanogaster", "d_melanogaster"),
        packs=(
            "hemibrain_epg_v0.1",
            "hemibrain_pen_a_v0.1",
            "manc_sample_v0.1",
            "optic_lobe_t4_v0.1",
            "cremi_sample_a_v0.2",
        ),
        evidence_yaml="species/drosophila_melanogaster/EVIDENCE.yaml",
        heinze_2026_status="N/A",
        notes="Reference/validation only — do not merge overlapping specimens",
    ),
    "sweat_bee": SpeciesEntry(
        key="sweat_bee",
        scientific="Megalopta genalis",
        common="tropical sweat bee",
        aliases=("megalopta", "megalopta_genalis", "bee"),
        packs=("megalopta_ibdb_morphology_v0.1",),
        evidence_yaml="species/megalopta_genalis/EVIDENCE.yaml",
        heinze_2026_status="PUBLIC_ARTIFACT_NOT_FOUND",
        notes="Local pack is prior IBdb morphology, not 2026 SBEM CX",
    ),
    "army_ant": SpeciesEntry(
        key="army_ant",
        scientific="Eciton hamatum",
        common="army ant",
        aliases=("eciton", "eciton_hamatum", "ant"),
        packs=(),
        evidence_yaml="species/eciton_hamatum/EVIDENCE.yaml",
        heinze_2026_status="PUBLIC_ARTIFACT_NOT_FOUND",
    ),
    "locust": SpeciesEntry(
        key="locust",
        scientific="Schistocerca gregaria",
        common="desert locust",
        aliases=("schistocerca", "schistocerca_gregaria"),
        packs=("schistocerca_ibdb_morphology_v0.1",),
        evidence_yaml="species/schistocerca_gregaria/EVIDENCE.yaml",
        heinze_2026_status="PUBLIC_ARTIFACT_NOT_FOUND",
        notes="Local pack is prior IBdb morphology, not 2026 SBEM CX",
    ),
    "mantis": SpeciesEntry(
        key="mantis",
        scientific="Sphodromantis lineola",
        common="African praying mantis",
        aliases=("praying_mantis", "sphodromantis", "sphodromantis_lineola"),
        packs=(),
        evidence_yaml="species/sphodromantis_lineola/EVIDENCE.yaml",
        heinze_2026_status="PUBLIC_ARTIFACT_NOT_FOUND",
    ),
    "cockroach": SpeciesEntry(
        key="cockroach",
        scientific="Rhyparobia maderae",
        common="Madeira cockroach",
        aliases=("rhyparobia", "rhyparobia_maderae", "roach"),
        packs=("rhyparobia_ibdb_morphology_v0.1",),
        evidence_yaml="species/rhyparobia_maderae/EVIDENCE.yaml",
        heinze_2026_status="PUBLIC_ARTIFACT_NOT_FOUND",
        notes="Local pack is prior IBdb morphology, not 2026 SBEM CX",
    ),
    "earwig": SpeciesEntry(
        key="earwig",
        scientific="Forficula auricularia",
        common="European earwig",
        aliases=("forficula", "forficula_auricularia"),
        packs=(),
        evidence_yaml="species/forficula_auricularia/EVIDENCE.yaml",
        heinze_2026_status="PUBLIC_ARTIFACT_NOT_FOUND",
    ),
    "bumblebee": SpeciesEntry(
        key="bumblebee",
        scientific="Bombus terrestris",
        common="buff-tailed bumblebee",
        aliases=("bombus", "bombus_terrestris"),
        packs=("bombus_terrestris_cx_projectome_v0.1",),
        evidence_yaml="species/bombus_terrestris/EVIDENCE.yaml",
        heinze_2026_status="N/A (Sayre 2021 predecessor)",
        notes="CX projectome — OBSERVED_MORPHOLOGY only",
    ),
}

REGION_ALIASES = {
    "central-complex": "central_complex",
    "central_complex": "central_complex",
    "cx": "central_complex",
    "vnc": "vnc",
    "optic-lobe": "optic_lobe",
    "optic_lobe": "optic_lobe",
    "hemibrain": "hemibrain",
    "whole-brain": "whole_brain",
    "cremi": "cremi",
}


def _norm(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def resolve_species(name: str) -> SpeciesEntry:
    key = _norm(name)
    if key in SPECIES_CATALOG:
        return SPECIES_CATALOG[key]
    for entry in SPECIES_CATALOG.values():
        if key == _norm(entry.scientific) or key in {_norm(a) for a in entry.aliases}:
            return entry
        if key == _norm(entry.common):
            return entry
    raise KeyError(f"Unknown species: {name}")


def available_packs_for(entry: SpeciesEntry) -> list[str]:
    present = set(list_connectomes())
    return [p for p in entry.packs if p in present]


def pick_pack(entry: SpeciesEntry, region: str | None = None) -> str | None:
    packs = available_packs_for(entry)
    if not packs:
        return None
    if region is None:
        return packs[0]
    reg = REGION_ALIASES.get(_norm(region).replace("__", "_"), _norm(region))
    scored: list[tuple[int, str]] = []
    for p in packs:
        score = 0
        pl = p.lower()
        if reg == "central_complex" and any(x in pl for x in ("cx", "projectome", "ibdb", "epg", "pen")):
            score += 10
        if reg == "optic_lobe" and "optic" in pl:
            score += 10
        if reg == "vnc" and "manc" in pl:
            score += 10
        if reg == "hemibrain" and "hemibrain" in pl:
            score += 10
        if reg == "cremi" and "cremi" in pl:
            score += 10
        scored.append((score, p))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return scored[0][1]


def load_evidence(entry: SpeciesEntry) -> dict:
    path = project_root() / entry.evidence_yaml
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def pack_summary(connectome_id: str) -> dict:
    store = ConnectomeStore(connectome_id)
    manifest = store.read_manifest() if store.manifest_path.exists() else {}
    nodes = store.load_nodes()
    edges = store.load_edges()
    card = store.dir / "CONNECTOME_CARD.md"
    return {
        "connectome_id": connectome_id,
        "species": manifest.get("species"),
        "specimen": manifest.get("specimen"),
        "graph_layers": manifest.get("graph_layers"),
        "coverage_claim": manifest.get("coverage_claim"),
        "neurons": int(len(nodes)),
        "edges": int(len(edges)),
        "limitations": manifest.get("limitations", []),
        "card": card.read_text(encoding="utf-8") if card.exists() else None,
        "path": str(store.dir),
    }


def compare_species(a: str, b: str) -> dict:
    ea, eb = resolve_species(a), resolve_species(b)
    pa, pb = pick_pack(ea, "central_complex"), pick_pack(eb, "central_complex")
    out: dict = {
        "species_a": ea.scientific,
        "species_b": eb.scientific,
        "heinze_2026_a": ea.heinze_2026_status,
        "heinze_2026_b": eb.heinze_2026_status,
        "pack_a": pa,
        "pack_b": pb,
        "observed_synaptic_comparable": False,
        "observed_morphology_comparable": False,
        "warning": (
            "Do not treat missing or inferred edges as observed. "
            "Heinze 2026 CX synaptic graphs are not publicly deposited."
        ),
    }
    if pa:
        sa = pack_summary(pa)
        out["summary_a"] = {k: sa[k] for k in ("neurons", "edges", "graph_layers", "limitations")}
    if pb:
        sb = pack_summary(pb)
        out["summary_b"] = {k: sb[k] for k in ("neurons", "edges", "graph_layers", "limitations")}
    if pa and pb:
        la = (out.get("summary_a") or {}).get("graph_layers") or {}
        lb = (out.get("summary_b") or {}).get("graph_layers") or {}
        out["observed_morphology_comparable"] = bool(
            la.get("OBSERVED_MORPHOLOGY") and lb.get("OBSERVED_MORPHOLOGY")
        )
        out["observed_synaptic_comparable"] = bool(
            la.get("OBSERVED_SYNAPTIC") and lb.get("OBSERVED_SYNAPTIC")
        )
        out["neuron_count_delta"] = int(out["summary_a"]["neurons"]) - int(out["summary_b"]["neurons"])
    elif not pa and not pb:
        out["message"] = "Neither species has a public assembled pack yet."
    else:
        out["message"] = "Only one side has a public pack — comparison incomplete."
    return out


def evidence_paths() -> list[Path]:
    root = project_root() / "species"
    if not root.exists():
        return []
    return sorted(root.glob("*/EVIDENCE.yaml"))
