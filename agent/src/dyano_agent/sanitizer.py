"""Tool 2 — Sanitizer.

Scan extracted document text and original filenames for prompt-injection
attempts and redact suspicious lines before the content reaches the LLM.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .schemas import SanitizerFinding, SanitizerReport

logger = logging.getLogger(__name__)

# Lower-cased substrings that indicate an instruction aimed at the model rather
# than legitimate document content.
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "ignore the above",
    "disregard previous",
    "disregard the above",
    "do not follow",
    "you are now",
    "you are no longer",
    "as an ai",
    "as a language model",
    "system prompt",
    "system:",
    "override",
    "jailbreak",
    "forget everything",
    "reveal your prompt",
    "your instructions are",
]

_FILENAME_SUSPICIOUS = [
    "..",
    "/",
    "\\",
    "ignore",
    "instruct",
    "system",
    "prompt",
]


def _redact_line(line: str) -> str:
    return "[REDACTED]"


def sanitize_text(text: str, location: str, findings: list[SanitizerFinding]) -> str:
    """Redact lines containing injection patterns and record findings."""
    cleaned_lines: list[str] = []
    for raw in text.splitlines():
        lowered = raw.lower()
        matched = next((p for p in _INJECTION_PATTERNS if p in lowered), None)
        if matched:
            snippet = raw.strip()[:120]
            findings.append(
                SanitizerFinding(location=location, pattern=matched, snippet=snippet)
            )
            cleaned_lines.append(_redact_line(raw))
        else:
            cleaned_lines.append(raw)
    return "\n".join(cleaned_lines)


def sanitize_filename(name: str, findings: list[SanitizerFinding]) -> str:
    """Return a sanitized filename and record a finding when suspicious."""
    lowered = name.lower()
    suspicious = [p for p in _FILENAME_SUSPICIOUS if p in lowered]
    if suspicious:
        findings.append(
            SanitizerFinding(
                location=f"filename: {name}",
                pattern=", ".join(suspicious),
                snippet=name,
            )
        )
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return f"sanitized_{safe}"
    return name


def sanitize_all(extracted_dir: Path, sanitized_dir: Path) -> SanitizerReport:
    """Sanitize every extracted Markdown file; write sanitized copies + report."""
    sanitized_dir.mkdir(parents=True, exist_ok=True)
    report = SanitizerReport()

    for md_path in sorted(extracted_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        report.files.append(md_path.name)
        cleaned = sanitize_text(text, location=md_path.name, findings=report.findings)
        (sanitized_dir / md_path.name).write_text(cleaned, encoding="utf-8")

    return report
