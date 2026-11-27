"""Render the audit JSON as Markdown (machine-generated; do not hand-edit AUDIT.md)."""
from __future__ import annotations

import json


def _fmt(v) -> str:
    if isinstance(v, (dict, list)):
        s = json.dumps(v, default=str)
        return s if len(s) < 400 else s[:400] + " …"
    return str(v)


def render_markdown(rep: dict) -> str:
    lines = ["# Dataset audit (generated)", "",
             f"Generated `{rep['generated_at']}` by `python -I scripts/audit.py`. Boundary: `{rep['boundary']}`.",
             "Every value below was computed from files in `data/raw/`; none is copied from the project brief.", ""]
    for sid, r in rep["results"].items():
        lines += [f"## `{sid}`", ""]
        elig = r.pop("eligibility", None) if isinstance(r, dict) else None
        lines += ["| field | value |", "|---|---|"]
        for k, v in r.items():
            if isinstance(v, dict) and all(isinstance(x, dict) for x in v.values()) and k != "categorical_counts":
                for kk, vv in v.items():
                    lines.append(f"| {k} / {kk} | `{_fmt(vv)}` |")
            else:
                lines.append(f"| {k} | `{_fmt(v)}` |")
        if elig:
            lines += ["", "**Eligibility by role**", ""] + [f"- **{k}**: {v}" for k, v in elig.items()]
            r["eligibility"] = elig
        lines.append("")
    if rep.get("not_audited"):
        lines += ["## Registered but not audited", ""] + [f"- `{k}`: {v}" for k, v in rep["not_audited"].items()]
    return "\n".join(lines) + "\n"
