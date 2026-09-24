"""Phase 3 catalog / recovery smoke tests (no network)."""

from __future__ import annotations

from click.testing import CliRunner

from insectome.cli import connectome_main, main
from insectome.phase3.catalog import compare_species, resolve_species


def test_resolve_cockroach():
    e = resolve_species("cockroach")
    assert e.scientific == "Rhyparobia maderae"


def test_compare_cockroach_locust_morphology_only():
    c = compare_species("cockroach", "locust")
    assert c["observed_morphology_comparable"] is True
    assert c["observed_synaptic_comparable"] is False
    assert c["pack_a"] and c["pack_b"]


def test_compare_cockroach_mantis_incomplete():
    c = compare_species("cockroach", "mantis")
    assert c["pack_b"] is None
    assert c["observed_morphology_comparable"] is False


def test_connectome_cli_species():
    r = CliRunner().invoke(connectome_main, ["species"])
    assert r.exit_code == 0
    assert "cockroach" in r.output
    assert "Rhyparobia" in r.output


def test_connectome_cli_open_cockroach():
    r = CliRunner().invoke(connectome_main, ["open", "cockroach", "central-complex"])
    assert r.exit_code == 0
    assert "rhyparobia_ibdb_morphology_v0.1" in r.output
    assert "PUBLIC_ARTIFACT_NOT_FOUND" in r.output


def test_insectome_species_top_level():
    r = CliRunner().invoke(main, ["species"])
    assert r.exit_code == 0
    assert "drosophila" in r.output
