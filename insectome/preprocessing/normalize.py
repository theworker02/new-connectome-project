"""Reproducible preprocessing — never invent missing biology."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PreprocessResult:
    image: np.ndarray
    parameters: dict
    missing_mask: np.ndarray | None = None


def contrast_normalize(volume: np.ndarray, p_low: float = 1.0, p_high: float = 99.0) -> PreprocessResult:
    """Percentile-based intensity normalization. Marks empty slices explicitly."""
    vol = volume.astype(np.float32)
    missing = np.zeros(vol.shape[0], dtype=bool)
    for z in range(vol.shape[0]):
        sl = vol[z]
        if not np.any(sl):
            missing[z] = True
            continue
        lo, hi = np.percentile(sl, [p_low, p_high])
        if hi <= lo:
            missing[z] = True
            continue
        vol[z] = np.clip((sl - lo) / (hi - lo), 0.0, 1.0)
    out = (vol * 255.0).astype(np.uint8)
    return PreprocessResult(
        image=out,
        parameters={"method": "percentile_normalize", "p_low": p_low, "p_high": p_high},
        missing_mask=missing,
    )
