import numpy as np

from terrasense.models.splits import leakage_report, spatial_block_split


def _synthetic_clustered(seed=0):
    """SYNTHETIC: clusters of points 5 m apart, mimicking polygon-sampled labels."""
    rng = np.random.default_rng(seed)
    centers = rng.uniform(0, 50_000, size=(60, 2))
    pts = np.concatenate([c + rng.normal(0, 5, size=(20, 2)) for c in centers])
    return pts[:, 0], pts[:, 1]


def test_random_split_leaks_block_split_does_not():
    x, y = _synthetic_clustered()
    rng = np.random.default_rng(1)
    mask = rng.random(len(x)) < 0.8
    naive = leakage_report(np.c_[x[mask], y[mask]], np.c_[x[~mask], y[~mask]], min_gap_m=500)
    assert not naive["ok"] and naive["median_m"] < 50

    lab = spatial_block_split(x, y, block_m=5_000, seed=3)
    tr, te = lab == "train", lab == "test"
    rep = leakage_report(np.c_[x[tr], y[tr]], np.c_[x[te], y[te]], min_gap_m=50)
    assert rep["exact_duplicates"] == 0
    assert rep["median_m"] > 1_000


def test_split_is_deterministic_and_blockwise():
    x, y = _synthetic_clustered()
    a = spatial_block_split(x, y, 5_000, seed=7)
    b = spatial_block_split(x, y, 5_000, seed=7)
    assert (a == b).all()
    ids = np.floor(x / 5_000) * 1e6 + np.floor(y / 5_000)
    for i in np.unique(ids):
        assert len(set(a[ids == i])) == 1
