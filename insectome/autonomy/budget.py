"""Disk and policy budgets for autonomous ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from insectome.storage.paths import project_root

# Hard ceiling for all local connectome packs (not the streaming cache).
DEFAULT_PACK_BUDGET_BYTES = 10 * 1024**3
# Soft reserve so auto-ingest stops before the hard wall.
DEFAULT_PACK_SOFT_BYTES = 8 * 1024**3
# Single auto-ingest job may not grow packs by more than this.
DEFAULT_JOB_MAX_BYTES = 250 * 1024**2
# Never auto-download EM or anything claiming > this.
EM_REFUSE_BYTES = 1 * 1024**3


@dataclass(frozen=True)
class AutonomyBudget:
    pack_hard_bytes: int = DEFAULT_PACK_BUDGET_BYTES
    pack_soft_bytes: int = DEFAULT_PACK_SOFT_BYTES
    job_max_bytes: int = DEFAULT_JOB_MAX_BYTES

    def connectomes_dir(self) -> Path:
        return project_root() / "data" / "connectomes"

    def used_bytes(self) -> int:
        root = self.connectomes_dir()
        if not root.exists():
            return 0
        total = 0
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    def remaining_bytes(self) -> int:
        return max(0, self.pack_hard_bytes - self.used_bytes())

    def soft_room(self) -> int:
        return max(0, self.pack_soft_bytes - self.used_bytes())

    def may_auto_ingest(self, estimated_final_bytes: int) -> tuple[bool, str]:
        if estimated_final_bytes <= 0:
            return False, "estimate_missing"
        if estimated_final_bytes > self.job_max_bytes:
            return False, f"job_too_large:{estimated_final_bytes}"
        if estimated_final_bytes > self.soft_room():
            return False, f"soft_budget:{self.soft_room()}"
        if estimated_final_bytes > self.remaining_bytes():
            return False, f"hard_budget:{self.remaining_bytes()}"
        return True, "ok"


def format_bytes(n: int) -> str:
    for unit, div in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.2f} {unit}"
    return f"{n} B"
