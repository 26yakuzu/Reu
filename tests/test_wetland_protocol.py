"""Training-protocol guards for the wetland classifier, on SYNTHETIC tables (no imagery needed)."""
import numpy as np
import pandas as pd

from terrasense.models import wetland as W


def _synthetic(n=600, seed=0):
    """SYNTHETIC points in clusters across a 400 x 200 km area with random labels."""
    rng = np.random.default_rng(seed)
    centers = rng.uniform([0, 0], [400_000, 200_000], size=(40, 2))
    xy = np.concatenate([c + rng.normal(0, 800, size=(n // 40, 2)) for c in centers])
    return pd.DataFrame({"x6933": xy[:, 0], "y6933": xy[:, 1],
                         "target": rng.choice(W.CLASSES, size=len(xy))})


def test_every_source_class_is_mapped():
    src = {"Forest", "Built up/bare land", "Mangrove", "Deep water", "Swamp", "Cultivated land", "Shallow water", "Marsh"}
    assert set(W.LABEL_MAP) == src
    assert set(W.LABEL_MAP.values()) == set(W.CLASSES)


def test_split_blocks_and_buffer():
    df = _synthetic()
    split, rep = W.make_split(df)
    assert set(split) <= {"train", "test", "buffer_dropped"}
    assert 0.1 < (split == "test").mean() < 0.35
    assert rep["ok"] and rep["min_m"] >= W.BUFFER_M and rep["exact_duplicates"] == 0
    split2, _ = W.make_split(df)
    assert (split == split2).all()          # seeded, deterministic


def test_rule_baseline_never_predicts_wetland():
    df = pd.DataFrame({"wofs_freq": [0.9, 0.0, np.nan, 0.1], "MNDWI": [-0.5, 0.2, -0.3, np.nan]})
    assert W.rule_baseline(df).tolist() == ["open_water", "open_water", "other", "other"]


def test_feature_columns_exclude_count_and_labels():
    assert "COUNT" not in W.FEATURE_COLS
    assert not {"target", "class_name", "class_code", "lon", "lat", "x6933", "y6933"} & set(W.FEATURE_COLS)
