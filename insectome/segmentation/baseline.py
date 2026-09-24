"""Baseline segmentation backends + GT metrics.

The watershed backend is deliberately simple and labeled MODEL_PREDICTED.
Ground-truth labels from CREMI are SOURCE_DOCUMENTED and used for validation,
not claimed as our reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import sobel
from skimage.measure import label
from skimage.morphology import h_minima
from skimage.segmentation import watershed


@dataclass
class SegmentationResult:
    labels: np.ndarray
    method: str
    parameters: dict
    evidence_state: str


def baseline_watershed(volume: np.ndarray, h: float = 0.08) -> SegmentationResult:
    """3D-ish watershed on per-slice edges (baseline only)."""
    vol = volume.astype(np.float32)
    if vol.max() > 1.0:
        vol = vol / 255.0
    # Mean edge magnitude across z as elevation
    elev = np.zeros_like(vol, dtype=np.float32)
    for z in range(vol.shape[0]):
        elev[z] = sobel(vol[z])
    markers = label(h_minima(elev, h))
    labels = watershed(elev, markers)
    return SegmentationResult(
        labels=labels.astype(np.int64),
        method="baseline_watershed_sobel",
        parameters={"h": h},
        evidence_state="MODEL_PREDICTED",
    )


def variation_of_information(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Return (VI, split_VI, merge_VI) between label volumes."""
    x = x.ravel()
    y = y.ravel()
    # Ignore background 0 if present in either
    mask = (x != 0) | (y != 0)
    x, y = x[mask], y[mask]
    if x.size == 0:
        return float("nan"), float("nan"), float("nan")

    _, x_idx = np.unique(x, return_inverse=True)
    _, y_idx = np.unique(y, return_inverse=True)
    n = x.size
    contingency = np.zeros((x_idx.max() + 1, y_idx.max() + 1), dtype=np.float64)
    np.add.at(contingency, (x_idx, y_idx), 1)
    pxy = contingency / n
    px = pxy.sum(axis=1)
    py = pxy.sum(axis=0)
    # H(X|Y) and H(Y|X)
    with np.errstate(divide="ignore", invalid="ignore"):
        hy_given_x = -np.nansum(px * np.nansum((pxy / px[:, None]) * np.log2(pxy / px[:, None] + 1e-12), axis=1))
        hx_given_y = -np.nansum(py * np.nansum((pxy / py[None, :]) * np.log2(pxy / py[None, :] + 1e-12), axis=0))
    vi = float(hx_given_y + hy_given_x)
    return vi, float(hy_given_x), float(hx_given_y)


def adapted_rand(seg: np.ndarray, gt: np.ndarray) -> float:
    """Simplified Adapted Rand error (lower is better)."""
    seg = seg.ravel()
    gt = gt.ravel()
    mask = gt != 0
    seg, gt = seg[mask], gt[mask]
    if seg.size == 0:
        return float("nan")
    # Pairwise agreement via contingency
    _, s_idx = np.unique(seg, return_inverse=True)
    _, g_idx = np.unique(gt, return_inverse=True)
    n = seg.size
    c = np.zeros((s_idx.max() + 1, g_idx.max() + 1), dtype=np.float64)
    np.add.at(c, (s_idx, g_idx), 1)
    sum_c2 = np.sum(c * c)
    sum_s2 = np.sum(np.sum(c, axis=1) ** 2)
    sum_g2 = np.sum(np.sum(c, axis=0) ** 2)
    # Precision / recall style ARAND components
    if sum_s2 == n or sum_g2 == n:
        return float("nan")
    prec = (sum_c2 - n) / (sum_s2 - n)
    rec = (sum_c2 - n) / (sum_g2 - n)
    if prec + rec == 0:
        return 1.0
    f_score = 2 * prec * rec / (prec + rec)
    return float(1.0 - f_score)
