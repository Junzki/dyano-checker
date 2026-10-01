# Dyano Checker — Implementation Summary

YAML-driven dynamic file-upload forms. Admins upload a rule-set YAML (with a
name) via Django admin; end users select the name and get a form that renders
one PDF file input per `file-requirement`. Files are stored locally and
processed by an async worker.

## What was built

### Backend (`backend/`)

- **Django 5.2 + SQLite**, project under `backend/` (`config/` settings/urls,
  `checker/` app). `MEDIA_ROOT` points to `media/` at the repo root.
- **Models** (`checker/models.py`):
  - `RuleSet` — `name`, `yaml_file`, `output_template` (optional output
    spreadsheet template), `schema` (JSONField), `created_at`
  - `Submission` — FK to `RuleSet`, `status` (`queued → processing → completed/failed`)
  - `SubmissionFile` — FK to `Submission`, `category_name`, `requirement_name`,
    `key`, `file`, `original_name`; upload path `submissions/<id>/<key>/`
- **Schema parsing** (`checker/schema.py`): `parse_ruleset()` flattens
  `check-requirements` into categories of `file_requirements` with a stable
  `key` (`<category-index>-<req-index>`), `name`, `description`, `kind`, and a
  uniform `accept=".pdf,application/pdf"` (only PDF supported). `rules` and
  `output-template` are ignored for the form.
- **Admin** (`checker/admin.py`): upload YAML + name; parses YAML into `schema`
  on save.
- **REST API** (`checker/api.py`, django-ninja, `/api`, Swagger `/api/docs`):
  - `GET /api/rulesets` — list rule sets
  - `GET /api/rulesets/{id}` — schema that drives the form
  - `POST /api/submissions` — multipart: `rule_set_id`, `keys_json` (JSON array
    of requirement keys), `files` (list); zips keys↔files, creates the
    submission, publishes to Redis
  - `GET /api/submissions/{id}` — status + files
- **Async pipeline** (`checker/broker.py`, `checker/tasks.py`,
  `checker/worker.py`, `runworker` command): FastStream `RedisBroker`
  (`REDIS_URL`, default `redis://:supersecure@localhost:6380/0`) with a
  `SubmissionMessage(submission_id)` published to the `submissions` channel.
  The worker sets `processing`, verifies files exist on storage, then sets
  `completed` (or `failed`).

### Frontend (`web/`)

- **React 18 + TypeScript + Vite**, plain function components + hooks.
- `src/api.ts` — typed fetch helpers for the four endpoints (no axios).
- `src/App.tsx` — loads rule sets, selection state, wires the form + status.
- `src/components/RuleSetSelector.tsx` — rule-set dropdown.
- `src/components/DynamicForm.tsx` — renders category sections and one PDF file
  input per `file_requirement`; builds `FormData` with `keys_json` + `files`.
- `src/components/StatusView.tsx` — polls status every 2s until terminal.
- `vite.config.ts` — dev proxy for `/api` and `/media` → `http://localhost:8000`
  (no CORS).

### Config & docs

- `pyproject.toml` — uv manifest (`package = false`), deps: django, django-ninja,
  pyyaml, faststream[redis], uvicorn[standard].
- `.gitignore` — `.venv/`, `backend/db.sqlite3`, `media/`, `web/node_modules/`,
  `web/dist/`.
- `README.md`, `AGENTS.md`, `CHANGELOG.md`, `docs/intake.md`.

## Key design decisions

- **Async worker = status pipeline** (`queued → processing → completed/failed`)
  that spawns the one-shot checking agent (see `docs/agent-design.md`), which
  extracts, sanitizes, checks each rule via the LLM, and fills the output
  spreadsheet template.
- **Only PDF** supported; every input uses `accept=".pdf,application/pdf"`.
- **Django project in a separate top-level `backend/` dir** (not under `src/`).
- **`keys_json` instead of `keys`**: a multipart field named `keys` collides with
  django-ninja's `dict.update` `keys()` lookup (pydantic model field shadows the
  method → `TypeError: 'str' object is not callable`).
- **Default `RedisBroker` is pub/sub** (non-durable); `RedisStreamBroker` is the
  upgrade path for durable queues.
- **Async view needs uvicorn**; `runserver` is not recommended for the publish path.

## Not implemented (by design)

- Permissions / authentication / user-side login.
- Form validation.

## Verified

- `manage.py check` clean; migrations apply.
- `npm run build` (tsc + vite build) passes.
- End-to-end: seed `docs/Rules.yaml` → form renders 4 PDF inputs (2 categories)
  → submit → status reaches `completed`; files land under
  `media/submissions/<id>/<key>/`.
- Swagger (`/api/docs`), admin (`/admin/`), and Vite proxy all reachable.
