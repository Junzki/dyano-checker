"""Write `results.json` and a human-readable `report.md` into the work dir."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import CheckResult


def _verdict_rank(verdict: str) -> int:
    return {"error": 0, "fail": 1, "pass": 2}[verdict]


def write_results(
    work_dir: Path,
    submission_id: int,
    files: list[dict[str, Any]],
    checks: list[CheckResult],
    output_files: list[str] | None = None,
) -> dict[str, Any]:
    """Write results.json and report.md. Returns the payload dict."""
    checks_data = [c.model_dump() for c in checks]
    overall = "failed" if any(c.verdict in {"fail", "error"} for c in checks) else "completed"

    payload: dict[str, Any] = {
        "submission_id": submission_id,
        "status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "checks": checks_data,
        "output_files": output_files or [],
    }

    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Check report",
        "",
        f"- submission_id: {submission_id}",
        f"- overall status: {overall}",
        "",
        "## Files",
        "",
    ]
    for f in files:
        lines.append(
            f"- `{f['key']}` ({f.get('original_name', '')}): {f.get('pdf_type', 'unknown')}"
        )
    lines += ["", "## Checks", ""]
    for c in sorted(checks, key=lambda x: _verdict_rank(x.verdict)):
        lines.append(f"### {c.rule_name} — {c.verdict.upper()}")
        if c.reasoning:
            lines.append(f"{c.reasoning}")
        if c.evidence:
            lines.append("")
            lines.append("Evidence:")
            for e in c.evidence:
                lines.append(f"- {e}")
        lines.append("")

    (work_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return payload
