# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

Dyano Checker — YAML-driven dynamic file-upload forms. Admins upload a rule-set
YAML via Django admin; end users pick a rule set and get a form with one file
input per `file-requirement`. Uploaded files are stored locally and processed
by a FastStream/Redis worker.

## Tech stack & versions

- Python 3.14 (uv-managed; `uv sync` installs from `pyproject.toml`, `package = false`)
- Django 5.2, django-ninja 1.7, PyYAML, FastStream 0.7 (`faststream[redis]`), uvicorn
- React 18 + TypeScript + Vite (npm), no test framework configured
- SQLite (`backend/db.sqlite3`), local file storage in `media/` (repo root)
- Redis broker at `redis://:supersecure@localhost:6380/0` (see `~/Werkzeug/Runtime`)

## Directory layout

- `backend/` — Django project (`config/` = settings/urls, `checker/` = app).
  Not a package under `src/`; run via `uv run backend/manage.py`.
- `backend/checker/`:
  - `models.py` — `RuleSet`, `RuleSkillFile`, `Submission`, `SubmissionFile`
  - `schema.py` — YAML → form schema parsing + requirement-key mapping
  - `api.py` — django-ninja API (`/api`, Swagger `/api/docs`)
  - `broker.py` — `RedisBroker` + `SubmissionMessage`
  - `tasks.py` / `worker.py` — FastStream subscriber + agent orchestration
  - `management/commands/runworker.py` — run the worker
- `agent/` — one-shot LLM checking agent (Pydantic AI), Python 3.12, own image:
  - `src/dyano_agent/` — `main.py`, `config.py`, `pdf_reader.py`,
    `sanitizer.py`, `checker.py`, `schemas.py`, `report.py`
  - `Dockerfile` — `python:3.12-slim`; deps resolved at build (no committed lock)
- `skills/` — default `SKILL*.md` / `GATE*.md` / `output.template.xlsx`,
  fallback for rule sets without uploaded `RuleSkillFile`s.
- `web/` — React frontend (`src/api.ts`, `src/App.tsx`, `src/components/*`)

## Commands

```bash
# Backend
uv sync                                   # install deps into .venv
uv run backend/manage.py check            # Django system check
uv run backend/manage.py migrate          # apply migrations
uv run backend/manage.py makemigrations checker
uv run backend/manage.py createsuperuser
uv run backend/manage.py runworker        # FastStream Redis worker
uv run uvicorn config.asgi:application --app-dir backend --reload --port 8000

# Frontend
cd web && npm install
cd web && npm run build                   # tsc typecheck + vite build
cd web && npm run dev                     # dev server (proxies /api, /media)

# Checking agent (Python 3.12, own image)
cd agent && uv sync                       # resolve agent deps (Python 3.12)
docker build -t dyano-checker-agent agent # build the agent image
```

There is no Python linter/test suite or npm test configured. For verification
use `manage.py check`, `manage.py migrate`, `npm run build`, and the smoke-test
flow below.

## Conventions

- Python files: no type-checking command is wired up, but keep type hints
  consistent with existing code (e.g. `dict[str, Any]`).
- Django settings live in `backend/config/settings.py`; `PROJECT_ROOT` is the
  repo root, `MEDIA_ROOT = PROJECT_ROOT / "media"`.
- API endpoints are defined in `checker/api.py` using django-ninja `Schema`
  response types so Swagger stays accurate.
- Frontend: plain function components + hooks; API calls go through `web/src/api.ts`
  (no axios). The Vite dev server proxies `/api` and `/media` to
  `http://localhost:8000`, so do not add CORS.

## Gotchas

- A multipart form field named `keys` breaks django-ninja (pydantic model field
  `keys` shadows `dict.update`'s `keys()` lookup, causing
  `TypeError: 'str' object is not callable`). The field is therefore named
  `keys_json`. Avoid naming any `Form`/body field `keys` or `items`.
- File uploads use `keys_json` (JSON array of requirement keys) zipped with the
  `files` list, in order — see `create_submission` in `checker/api.py` and
  `web/src/api.ts`.
- Async views (the submission endpoint) need uvicorn; `runserver` is not
  recommended for the publish path.
- Default `RedisBroker` is pub/sub (non-durable). If durable queues are needed,
  switch to `RedisStreamBroker`.
- The worker spawns the checking agent via `docker run` and therefore needs the
  Docker socket mounted and the `docker` CLI in its image (see
  `docker-compose.yaml` and `backend/Dockerfile`). The agent image is built from
  `agent/` (Python 3.12, not 3.14 — PaddleOCR has no 3.14 wheels).
- `media/`, `backend/db.sqlite3`, `web/node_modules/`, `web/dist/` are gitignored.

## Smoke test

```bash
uv sync
uv run backend/manage.py migrate
# seed a rule set (admin upload is the real path; this is a shortcut):
uv run backend/manage.py shell -c "
import yaml
from django.core.files import File
from checker.models import RuleSet
from checker.schema import parse_ruleset
data = yaml.safe_load(open('docs/Rules.yaml'))
rs = RuleSet(name='Example Rules'); rs.schema = parse_ruleset(data)
with open('docs/Rules.yaml','rb') as f: rs.yaml_file.save('Rules.yaml', File(f), save=False)
rs.save()"
uv run backend/manage.py runworker &   # terminal 2
uv run uvicorn config.asgi:application --app-dir backend --reload --port 8000 &   # terminal 3
# POST files keyed to requirements:
curl -s -X POST http://localhost:8000/api/submissions \
  -F "rule_set_id=1" \
  -F "files=@test1.pdf;type=application/pdf" \
  -F "files=@test2.pdf;type=application/pdf" \
  -F 'keys_json=["0-0","1-0"]'
curl -s http://localhost:8000/api/submissions/1   # status should reach "completed"
```

The checking pipeline now runs the agent in Docker: the worker needs a working
`docker` CLI, `/var/run/docker.sock`, the `dyano-checker-agent` image built, and
`AGENT_LLM_API_KEY` (plus `AGENT_LLM_BASE_URL`/`AGENT_LLM_MODEL`) set, otherwise
the submission ends in `failed` with the reason recorded in `Submission.results`.
