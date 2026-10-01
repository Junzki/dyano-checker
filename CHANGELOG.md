# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Checking agent "XLSX writer" tool that fills the rule set's output spreadsheet
  template with per-rule verdicts (`PASSED`/`FAILED`/`ERROR`).
- `RuleSet.output_template` FileField so an admin can upload the output template
  alongside the rule-set YAML; the worker mounts it into the agent container.
- `output_url` on `GET /api/submissions/{id}` and a download link in the web UI
  for the generated result spreadsheet.

### Changed

- Rule skills/gates are now user-defined and travel with the rule set: they can
  be defined inline in the YAML (multi-line content) or uploaded per rule set
  (`RuleSkillFile`) and referenced by filename. The repo-level `skills/`
  fallback directory and bundled example files were removed.

## [0.1.0] - 2026-10-01

### Added

- Django + SQLite backend (`backend/`) with `RuleSet`, `Submission`, and
  `SubmissionFile` models.
- Django admin support for uploading YAML rule sets with a name; YAML is parsed
  into a form schema on save.
- django-ninja REST API at `/api` with Swagger UI at `/api/docs`:
  - `GET /api/rulesets`
  - `GET /api/rulesets/{id}`
  - `POST /api/submissions` (multipart file upload)
  - `GET /api/submissions/{id}`
- FastStream + Redis async task pipeline (`queued → processing → completed/failed`)
  with a `runworker` management command.
- Local file storage under `media/` (ruleset YAML + uploaded submission files).
- React + TypeScript + Vite frontend (`web/`) that renders a dynamic file-input
  form from the selected rule set and polls submission status.
- Vite dev-server proxy for `/api` and `/media` (no CORS).
- `docs/Rules.yaml` example rule set.
- Project documentation (`README.md`, `AGENTS.md`).
