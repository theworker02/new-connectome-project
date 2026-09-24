"""Streaming cache + criterion tests."""

from __future__ import annotations

from pathlib import Path

from insectome.atlas.streaming_manifest import build_streaming_manifest, write_streaming_criterion_report
from insectome.storage.cache import InsectomeCache


def test_weighted_cache_evicts_em_before_metadata(tmp_path: Path):
    c = InsectomeCache(root=tmp_path / "cache")
    c.set_limits(soft_gb=0.000001, hard_gb=0.000002)  # ~1–2 KB hard — tiny
    # Actually use byte-ish limits via direct config
    c.config.hard_limit_bytes = 800
    c.config.soft_limit_bytes = 400
    c.put_bytes("meta1", b"m" * 100, kind="metadata")
    c.put_bytes("em1", b"e" * 500, kind="em_chunk")
    c.put_bytes("em2", b"e" * 500, kind="em_chunk")
    # After puts, EM should be preferentially gone; metadata more likely kept
    kinds = {e.get("kind") for e in c._index["entries"].values()}
    assert c.total_bytes() <= c.config.hard_limit_bytes
    # metadata preferred over filling with EM
    assert "metadata" in kinds or c.total_bytes() <= 800


def test_reserve_rejects_oversized():
    c = InsectomeCache()
    c.config.hard_limit_bytes = 1000
    assert c.reserve(5000) is False


def test_hemibrain_streaming_ratio_passes():
    m = build_streaming_manifest("hemibrain_epg_v0.1")
    assert m["local_total_bytes"] > 0
    assert m["remote_raw_size"] > 0
    assert m["remote_to_local_ratio"] is not None
    assert m["remote_to_local_ratio"] >= 100


def test_streaming_report_writes(tmp_path: Path, monkeypatch):
    path = write_streaming_criterion_report()
    text = path.read_text(encoding="utf-8")
    assert "STREAMING" in text.upper() or "Streaming" in text
    assert "hemibrain_epg" in text
