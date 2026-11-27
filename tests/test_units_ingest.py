import numpy as np

from terrasense.ingest.fetch import checksum_matches
from terrasense.ingest.prepare import _map_block


def test_checksum_algorithms():
    assert checksum_matches("md5:ABC", "abc", "x") is True
    assert checksum_matches("sha256:def", "x", "def") is True
    assert checksum_matches("md5:abc", "zzz", "x") is False
    assert checksum_matches(None, "a", "b") is None


def test_frequency_fraction_to_scene_count():
    # 12-scene fractions (as float32 in source) must become exact integer counts
    a = np.array([[1 / 12, 0.5, 1.0, -9999.0]], dtype=np.float32)
    out = _map_block(a, -9999.0, "frac_n12")
    assert out.tolist() == [[1, 6, 12, 255]]


def test_presence_and_classes_nodata():
    a = np.array([[0.0, -9999.0]], dtype=np.float32)
    assert _map_block(a, -9999.0, "presence").tolist() == [[1, 0]]
    c = np.array([[0.0, 3.0, np.nan]])
    assert _map_block(c, None, "classes").tolist() == [[0, 3, 0]]


def test_binary_keeps_values():
    a = np.array([[0.0, 1.0]], dtype=np.float32)
    assert _map_block(a, 0.0, "binary0").tolist() == [[0, 1]]


def test_safe_extract_idempotent_and_refuses_traversal(tmp_path):
    import zipfile

    import pytest

    from terrasense.ingest.extract import safe_extract
    z = tmp_path / "SYNTHETIC.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("dir/", "")
        zf.writestr("dir/a.txt", "hello")
    out = tmp_path / "out"
    assert safe_extract(z, out) == ["dir/a.txt"]        # directory entries are not counted
    assert safe_extract(z, out) == []                   # second run extracts nothing
    bad = tmp_path / "SYNTHETIC_bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../evil.txt", "x")
    with pytest.raises(ValueError):
        safe_extract(bad, out)
