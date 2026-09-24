"""Content-addressable disk cache with weighted LRU and hard budgets.

Tiers (eviction preference, highest first):
  em_chunk > mesh_hi > mesh_lo > skeleton > metadata

Never silently fill the drive: reserve() before writes; stream-without-persist if full.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Kind = Literal["em_chunk", "mesh_hi", "mesh_lo", "skeleton", "metadata", "blob", "em_evidence", "file"]

# Higher = evict sooner
EVICT_WEIGHT: dict[str, float] = {
    "em_chunk": 100.0,
    "em_evidence": 95.0,
    "mesh_hi": 80.0,
    "mesh_lo": 60.0,
    "blob": 40.0,
    "file": 40.0,
    "skeleton": 20.0,
    "metadata": 1.0,
}

DEFAULT_SOFT_LIMIT = 5 * 1024**3
DEFAULT_HARD_LIMIT = 10 * 1024**3
DEFAULT_RAM_LIMIT = 512 * 1024**2


def cache_root() -> Path:
    override = os.environ.get("INSECTOME_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".insectome" / "cache"


@dataclass
class CacheConfig:
    soft_limit_bytes: int = DEFAULT_SOFT_LIMIT
    hard_limit_bytes: int = DEFAULT_HARD_LIMIT
    ram_limit_bytes: int = DEFAULT_RAM_LIMIT


@dataclass
class RamEntry:
    data: bytes
    kind: str
    last_access: float = field(default_factory=time.time)
    size: int = 0


class InsectomeCache:
    """Disk + tiny RAM L1. Content-addressable paths under ~/.insectome/cache."""

    def __init__(self, root: Path | None = None, config: CacheConfig | None = None):
        self.root = root or cache_root()
        self.config = config or CacheConfig()
        self.root.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.root / "cache_index.json"
        self._lock = threading.RLock()
        self._index = self._load_index()
        self._ram: dict[str, RamEntry] = {}

    def _load_index(self) -> dict:
        if self._meta_path.exists():
            data = json.loads(self._meta_path.read_text(encoding="utf-8"))
            data.setdefault("entries", {})
            return data
        return {
            "entries": {},
            "soft_limit_bytes": self.config.soft_limit_bytes,
            "hard_limit_bytes": self.config.hard_limit_bytes,
            "ram_limit_bytes": self.config.ram_limit_bytes,
        }

    def _save_index(self) -> None:
        self._index["soft_limit_bytes"] = self.config.soft_limit_bytes
        self._index["hard_limit_bytes"] = self.config.hard_limit_bytes
        self._index["ram_limit_bytes"] = self.config.ram_limit_bytes
        self._meta_path.write_text(json.dumps(self._index, indent=2), encoding="utf-8")

    def set_limits(
        self,
        soft_gb: float | None = None,
        hard_gb: float | None = None,
        ram_mb: float | None = None,
    ) -> None:
        with self._lock:
            if soft_gb is not None:
                self.config.soft_limit_bytes = int(soft_gb * 1024**3)
            if hard_gb is not None:
                self.config.hard_limit_bytes = int(hard_gb * 1024**3)
            if ram_mb is not None:
                self.config.ram_limit_bytes = int(ram_mb * 1024**2)
            self._save_index()
            self.evict_if_needed()

    def _key_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.root / digest[:2] / digest

    def content_hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> Path | None:
        with self._lock:
            entry = self._index["entries"].get(key)
            if not entry:
                return None
            path = Path(entry["path"])
            if not path.exists():
                self._index["entries"].pop(key, None)
                self._save_index()
                return None
            entry["last_access"] = time.time()
            self._save_index()
            return path

    def get_bytes(self, key: str) -> bytes | None:
        with self._lock:
            ram = self._ram.get(key)
            if ram is not None:
                ram.last_access = time.time()
                return ram.data
        path = self.get(key)
        if path is None:
            return None
        data = path.read_bytes()
        self._put_ram(key, data, kind=self._index["entries"].get(key, {}).get("kind", "blob"))
        return data

    def _put_ram(self, key: str, data: bytes, kind: str) -> None:
        with self._lock:
            self._ram[key] = RamEntry(data=data, kind=kind, size=len(data))
            self._evict_ram()

    def _ram_total(self) -> int:
        return sum(e.size for e in self._ram.values())

    def _evict_ram(self) -> None:
        while self._ram_total() > self.config.ram_limit_bytes and self._ram:
            oldest = min(self._ram.items(), key=lambda kv: kv[1].last_access)[0]
            self._ram.pop(oldest, None)

    def reserve(self, nbytes: int) -> bool:
        """Ensure nbytes can be written under the hard limit (evicting if needed)."""
        with self._lock:
            if nbytes > self.config.hard_limit_bytes:
                return False
            while self.total_bytes() + nbytes > self.config.hard_limit_bytes and self._index["entries"]:
                if not self._evict_one():
                    break
            return self.total_bytes() + nbytes <= self.config.hard_limit_bytes

    def put_bytes(
        self,
        key: str,
        data: bytes,
        kind: str = "blob",
        persist: bool = True,
        source: str | None = None,
    ) -> Path | None:
        """Store object. If persist=False or reserve fails, keep RAM-only (or drop)."""
        self._put_ram(key, data, kind=kind)
        if not persist:
            return None
        with self._lock:
            if not self.reserve(len(data)):
                # stream without persistence
                return None
            path = self._key_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self._index["entries"][key] = {
                "path": str(path),
                "size": len(data),
                "kind": kind,
                "sha256": self.content_hash(data),
                "source": source,
                "last_access": time.time(),
                "created": time.time(),
            }
            self._save_index()
            self.evict_if_needed()
            return path

    def put_file(self, key: str, src: Path, kind: str = "file") -> Path | None:
        return self.put_bytes(key, src.read_bytes(), kind=kind)

    def total_bytes(self) -> int:
        return int(sum(e.get("size", 0) for e in self._index["entries"].values()))

    def breakdown(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self._index["entries"].values():
            k = e.get("kind", "blob")
            out[k] = out.get(k, 0) + int(e.get("size", 0))
        return out

    def status(self) -> dict:
        with self._lock:
            return {
                "root": str(self.root),
                "entries": len(self._index["entries"]),
                "total_bytes": self.total_bytes(),
                "soft_limit_bytes": self.config.soft_limit_bytes,
                "hard_limit_bytes": self.config.hard_limit_bytes,
                "ram_limit_bytes": self.config.ram_limit_bytes,
                "ram_bytes": self._ram_total(),
                "ram_entries": len(self._ram),
                "breakdown_bytes": self.breakdown(),
                "architecture": "zero-storage-streaming",
            }

    def clear(self, kinds: list[str] | None = None) -> dict:
        with self._lock:
            if kinds is None:
                if self.root.exists():
                    shutil.rmtree(self.root)
                self.root.mkdir(parents=True, exist_ok=True)
                self._ram.clear()
                self._index = {
                    "entries": {},
                    "soft_limit_bytes": self.config.soft_limit_bytes,
                    "hard_limit_bytes": self.config.hard_limit_bytes,
                    "ram_limit_bytes": self.config.ram_limit_bytes,
                }
                self._save_index()
                return {"cleared": "all"}
            removed = 0
            for key, entry in list(self._index["entries"].items()):
                if entry.get("kind") in kinds:
                    path = Path(entry["path"])
                    if path.exists():
                        path.unlink()
                    self._index["entries"].pop(key, None)
                    removed += 1
            for key in list(self._ram):
                if self._ram[key].kind in kinds:
                    self._ram.pop(key, None)
            self._save_index()
            return {"cleared_kinds": kinds, "removed": removed}

    def _evict_score(self, entry: dict) -> float:
        age = time.time() - float(entry.get("last_access", 0))
        weight = EVICT_WEIGHT.get(entry.get("kind", "blob"), 40.0)
        size = float(entry.get("size", 1))
        # Prefer evicting large, heavy-kind, stale objects
        return weight * age * (1.0 + size / (1024**2))

    def _evict_one(self) -> bool:
        if not self._index["entries"]:
            return False
        oldest_key = max(self._index["entries"].items(), key=lambda kv: self._evict_score(kv[1]))[0]
        entry = self._index["entries"].pop(oldest_key)
        path = Path(entry["path"])
        if path.exists():
            path.unlink()
        parent = path.parent
        if parent.exists() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
        return True

    def evict_if_needed(self) -> None:
        hard = self.config.hard_limit_bytes
        soft = self.config.soft_limit_bytes
        # Soft: prefer evicting EM first until under soft
        target = soft if self.total_bytes() > soft else hard
        while self.total_bytes() > target and self._index["entries"]:
            if not self._evict_one():
                break
        # Always enforce hard
        while self.total_bytes() > hard and self._index["entries"]:
            if not self._evict_one():
                break
        self._save_index()
