"""Atlas enrichment / service smoke tests."""

from __future__ import annotations

from pathlib import Path

from insectome.atlas.canonical import make_global_id
from insectome.atlas.service import atlas_status_rows, batch_skeletons, load_index
from insectome.atlas.skeletons import read_skeleton_bin
from insectome.connectome.store import ConnectomeStore


def test_global_id_format():
    gid = make_global_id("Drosophila melanogaster", "hemibrain:v1.2.1", "hemibrain", 123)
    assert "drosophila_melanogaster" in gid
    assert gid.endswith("/123")


def test_epg_has_skeletons():
    store = ConnectomeStore("hemibrain_epg_v0.1")
    assert (store.dir / "neuron_index.parquet").exists()
    idx = load_index("hemibrain_epg_v0.1")
    assert len(idx) >= 40
    sid = int(idx.iloc[0]["source_id"])
    assert (store.dir / "skeletons" / f"{sid}.lod.skbin").exists()
    verts, links, meta = read_skeleton_bin(store.dir / "skeletons" / f"{sid}.lod.skbin")
    assert len(verts) > 10
    assert len(links) == len(verts)


def test_batch_skeletons_epg():
    batch = batch_skeletons("hemibrain_epg_v0.1", limit=5)
    assert batch["count"] == 5
    assert len(batch["neurons"][0]["line_segments"]) > 0


def test_atlas_status_has_viewer_ready():
    rows = atlas_status_rows()
    ids = {r["connectome_id"]: r["atlas_status"] for r in rows}
    assert ids.get("hemibrain_epg_v0.1") == "VIEWER_3D_READY"
    assert ids.get("bombus_terrestris_cx_projectome_v0.1") == "VIEWER_3D_READY"
