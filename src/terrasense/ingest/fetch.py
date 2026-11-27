"""Download registry files into data/raw/<source_id>/ with checksum verification.

Raw files are immutable: an existing file whose checksum matches is never
re-downloaded or modified. A mismatch aborts that file and is reported.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from terrasense.config import MANIFEST_DIR, RAW_DIR, load_registry

USER_AGENT = "terrasense-research-fetch/0.1"


@dataclass
class FetchRecord:
    source_id: str
    key: str
    url: str
    path: str
    size: int | None
    md5: str | None
    sha256: str | None
    expected_checksum: str | None
    checksum_ok: bool | None
    status: str
    fetched_at: str


def hash_file(path: Path) -> tuple[str, str]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def checksum_matches(expected: str | None, md5: str, sha: str) -> bool | None:
    if not expected:
        return None
    algo, _, value = expected.partition(":")
    return {"md5": md5, "sha256": sha}.get(algo.lower()) == value.lower()


def _download(url: str, dest: Path, retries: int = 3) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=60, headers={"User-Agent": USER_AGENT}) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(dest)
            return
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt * 2)


def iter_registry_files(include_large: bool = False, only: set[str] | None = None):
    reg = load_registry()
    for src in [reg["boundary"], *reg["sources"]]:
        if only and src["id"] not in only:
            continue
        for f in src.get("files", []):
            if f.get("fetch", True) or include_large:
                yield src["id"], f


def fetch_all(include_large: bool = False, only: set[str] | None = None) -> list[FetchRecord]:
    records: list[FetchRecord] = []
    for source_id, f in iter_registry_files(include_large, only):
        dest_dir = RAW_DIR / source_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f["key"]
        status = "cached"
        if dest.exists():
            md5, sha = hash_file(dest)
            if checksum_matches(f.get("checksum"), md5, sha) is False:
                status = "cached_checksum_mismatch"
        else:
            try:
                _download(f["url"], dest)
                status = "downloaded"
            except requests.RequestException as exc:
                records.append(FetchRecord(source_id, f["key"], f["url"], str(dest), None, None, None,
                                           f.get("checksum"), None, f"error: {exc}", _now()))
                continue
            md5, sha = hash_file(dest)
        ok = checksum_matches(f.get("checksum"), md5, sha)
        if ok is False and status == "downloaded":
            bad = dest.with_suffix(dest.suffix + ".checksum_mismatch")
            dest.replace(bad)
            status, dest = "rejected_checksum_mismatch", bad
        records.append(FetchRecord(source_id, f["key"], f["url"], str(dest.relative_to(RAW_DIR.parent.parent))
                                   if dest.is_relative_to(RAW_DIR.parent.parent) else str(dest),
                                   dest.stat().st_size, md5, sha, f.get("checksum"), ok, status, _now()))
    return records


def write_manifest(records: list[FetchRecord], name: str = "raw_manifest.json") -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = MANIFEST_DIR / name
    previous = {}
    if out.exists():
        previous = {(r["source_id"], r["key"]): r for r in json.loads(out.read_text())["files"]}
    for r in records:
        previous[(r.source_id, r.key)] = asdict(r)
    payload = {"generated_at": _now(), "files": sorted(previous.values(), key=lambda r: (r["source_id"], r["key"]))}
    out.write_text(json.dumps(payload, indent=2))
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
