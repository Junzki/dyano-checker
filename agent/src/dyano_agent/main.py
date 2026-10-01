"""Agent entrypoint: read inputs, extract, sanitize, check, report, exit."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from .checker import run_checks
from .config import Config
from .pdf_reader import extract_pdf
from .report import write_results
from .sanitizer import sanitize_all
from .schemas import Manifest, Rule
from .xlsx_writer import load_output_template_names, write_output_xlsx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dyano_agent")


def _load_manifest(config: Config) -> Manifest:
    return Manifest.model_validate_json(config.manifest_path.read_text(encoding="utf-8"))


def _load_rules(config: Config) -> list[Rule]:
    data = yaml.safe_load(config.rules_path.read_text(encoding="utf-8")) or {}
    rules: list[Rule] = []
    for category in data.get("check-requirements", []):
        for raw in category.get("rules", []):
            rules.append(
                Rule(
                    name=raw.get("name", ""),
                    description=raw.get("description", ""),
                    skill=raw.get("skill", ""),
                    gate=raw.get("gate", ""),
                )
            )
    return rules


def _resolve_file(entry, config: Config) -> Path:
    # file_path is absolute (written by the worker) or relative to files_dir.
    candidate = Path(entry.file_path)
    if not candidate.is_absolute():
        candidate = config.files_dir / entry.file_path
    return candidate


def main() -> int:
    config = Config.from_env()
    logger.info("input_dir=%s work_dir=%s", config.input_dir, config.work_dir)
    logger.info("llm model=%s base_url=%s", config.llm_model, config.llm_base_url)

    manifest = _load_manifest(config)
    rules = _load_rules(config)

    config.extracted_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    for entry in manifest.files:
        pdf = _resolve_file(entry, config)
        logger.info("extracting %s -> %s", pdf, entry.key)
        if not pdf.exists():
            raise FileNotFoundError(f"missing input file: {pdf}")
        summary = extract_pdf(pdf, config.extracted_dir / f"{entry.key}.md")
        files.append(
            {
                "key": entry.key,
                "category_name": entry.category_name,
                "requirement_name": entry.requirement_name,
                "original_name": entry.original_name,
                **summary,
            }
        )

    report = sanitize_all(config.extracted_dir, config.sanitized_dir)
    (config.work_dir / "sanitizer-report.json").write_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if report.findings:
        logger.warning("sanitizer flagged %d finding(s)", len(report.findings))

    checks = run_checks(config, rules, config.sanitized_dir)

    output_files = write_output_xlsx(config, load_output_template_names(config), checks)

    payload = write_results(
        config.work_dir, manifest.submission_id, files, checks, output_files
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
