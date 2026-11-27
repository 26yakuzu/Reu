"""Alias of audit.py (validate = audit raw sources). Usage: python -I scripts/validate.py

Usage: python -I scripts/audit.py
"""
from terrasense.config import ARTIFACTS_DIR, REPO_ROOT
from terrasense.ingest.audit import run_audit, write_audit
from terrasense.ingest.report import render_markdown

rep = run_audit()
p = write_audit(rep, ARTIFACTS_DIR / "reports" / "audit.json")
md = REPO_ROOT / "docs" / "data_dictionary" / "AUDIT.md"
md.write_text(render_markdown(rep))
for sid, r in rep["results"].items():
    print(f"{sid:24s} {r.get('status', 'ok') if isinstance(r, dict) else r}")
print("wrote", p, "and", md)
