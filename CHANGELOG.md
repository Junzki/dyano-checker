# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
