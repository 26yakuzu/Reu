"""Spatial-block splitting and leakage checks (used before ANY training).

Points are assigned to square blocks in a projected CRS; whole blocks go to one
split, so neighbouring (autocorrelated) samples never straddle train/test.
`leakage_report` measures the nearest train->test distance so a split can be
rejected if test points sit within `min_gap_m` of training points.
"""
from __future__ import annotations

import numpy as np
from sklearn.neighbors import KDTree


def block_ids(x: np.ndarray, y: np.ndarray, block_m: float) -> np.ndarray:
    bx = np.floor(np.asarray(x) / block_m).astype(np.int64)
    by = np.floor(np.asarray(y) / block_m).astype(np.int64)
    return bx * 1_000_003 + by


def spatial_block_split(x, y, block_m: float, fractions=(0.7, 0.15, 0.15), seed: int = 42) -> np.ndarray:
    """Return array of 'train'/'val'/'test' labels, assigned per block."""
    if not np.isclose(sum(fractions), 1.0):
        raise ValueError("fractions must sum to 1")
    ids = block_ids(x, y, block_m)
    uniq = np.unique(ids)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    n_tr = int(round(fractions[0] * len(uniq)))
    n_va = int(round(fractions[1] * len(uniq)))
    lab = {b: "train" for b in uniq[:n_tr]} | {b: "val" for b in uniq[n_tr:n_tr + n_va]} | {b: "test" for b in uniq[n_tr + n_va:]}
    return np.array([lab[b] for b in ids])


def leakage_report(xy_train: np.ndarray, xy_test: np.ndarray, min_gap_m: float) -> dict:
    if len(xy_train) == 0 or len(xy_test) == 0:
        return {"n_train": len(xy_train), "n_test": len(xy_test), "ok": False, "reason": "empty split"}
    d, _ = KDTree(xy_train).query(xy_test, k=1)
    d = d.ravel()
    dup = int((d == 0).sum())
    return {"n_train": int(len(xy_train)), "n_test": int(len(xy_test)), "min_m": float(d.min()),
            "median_m": float(np.median(d)), "share_below_gap": float((d < min_gap_m).mean()),
            "exact_duplicates": dup, "ok": bool(d.min() >= min_gap_m)}
