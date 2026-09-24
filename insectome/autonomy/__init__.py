"""Autonomous discovery + evidence-gated ingestion for Insectome.

Design principles
-----------------
* Never invent biology — only promote packs with verifiable public evidence.
* Never bulk-download EM — graph / morphology index packs only.
* Respect hard disk budget (default ≤10 GB connectome footprint).
* Prefer LEVEL-0 reuse (neuPrint / IBdb / CREMI) over reconstruction.
* Candidates without auto-ingest eligibility stay in the ledger for review.
"""

from __future__ import annotations

from insectome.autonomy.cycle import run_autonomy_cycle
from insectome.autonomy.ledger import load_ledger

__all__ = ["run_autonomy_cycle", "load_ledger"]
