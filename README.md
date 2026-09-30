# Dyano Checker

YAML-driven dynamic file-upload forms. An admin uploads a YAML file that
describes a set of *file requirements* (grouped into categories); end users
then pick the named rule set and get a form that renders one file input per
requirement. Uploaded files are stored locally and processed by an async
worker.

## Tech stack

- **Backend**: Django + SQLite, [django-ninja](https://django-ninja.dev/) (REST + Swagger)
- **Async tasks**: [FastStream](https://faststream.airt.ai/) with Redis as broker
- **Python**: uv-managed, Python 3.14
- **Frontend**: React + TypeScript + Vite (npm)
- **Storage**: local filesystem under `media/`

## Architecture

```
admin (Django admin)  ──uploads YAML──▶  RuleSet (name + parsed schema)
                                              │
user (React form)  ──chooses RuleSet──▶  renders file inputs from schema
                                              │
                          ──submit files──▶  Submission (queued)
                                              │  publish to Redis
                                          FastStream worker
                                              │  queued → processing → completed/failed
                                          SubmissionFile(s) saved under media/
```

## Directory layout

```
dyano-checker/
├── pyproject.toml          # uv project manifest (deps only, no package build)
├── .python-version         # 3.14
├── docs/Rules.yaml         # example rule-set YAML
├── media/                  # MEDIA_ROOT (gitignored)
├── backend/                # Django project
│   ├── manage.py
│   ├── config/             # settings.py, urls.py, asgi.py, wsgi.py
│   └── checker/            # models, admin, api, schema, broker, worker
│       └── management/commands/runworker.py
└── web/                    # React + TS + Vite frontend
    └── src/
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) with Python 3.14
- Node.js + npm
- Redis

## Setup

```bash
uv sync
uv run backend/manage.py migrate
uv run backend/manage.py createsuperuser
```

## Running

```bash
# 1. Async worker (FastStream / Redis)
uv run python backend/manage.py runworker

# 2. API server (uvicorn recommended for async views)
uv run uvicorn config.asgi:application --app-dir backend --reload --port 8000

# 3. Frontend
cd web && npm install && npm run dev
```

- Frontend: http://localhost:5173 (dev server proxies `/api` and `/media` to :8000)
- Swagger: http://localhost:8000/api/docs
- Django admin: http://localhost:8000/admin

## Usage

1. **Admin**: in Django admin, add a `RuleSet` — give it a name and upload a YAML file.
2. **User**: on the frontend, choose the rule set name; the form renders one file input per `file-requirement`.
3. Upload the files; the submission cycles `queued → processing → completed`.

## Rule-set YAML format

See [`docs/Rules.yaml`](docs/Rules.yaml). A rule set has `check-requirements`
(a list of categories, each with `file-requirements` and optional `rules`) and
an optional `output-template`. The form is driven by `file-requirements`
(`name`, `description`, `kind`). Only `PDF` is currently supported, so every
input uses `accept=".pdf,application/pdf"`.

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/rulesets` | List rule sets |
| GET | `/api/rulesets/{id}` | Rule-set schema (drives the form) |
| POST | `/api/submissions` | Create submission (`multipart/form-data`) |
| GET | `/api/submissions/{id}` | Submission status + files |

## Configuration

- `REDIS_URL` — broker URL, defaults to
  `redis://:password@localhost:6380/0`
- Media files are stored under `media/` (`MEDIA_ROOT`)

## Deploying with Docker

The repo ships Docker images for the backend and frontend plus a
`docker-compose.yaml` that runs the full stack: Redis (broker), the API server
(uvicorn), the FastStream worker, and nginx (serving the built frontend and
proxying `/api`, `/admin`, `/media`, `/static` to the backend).

### 1. Generate a secret key

```bash
./scripts/generate-secret.sh
```

This writes `DJANGO_SECRET_KEY` into `.env` (the file is gitignored). Fill in
the remaining variables from `.env.example` as needed (e.g. `DJANGO_DEBUG`,
`DJANGO_ALLOWED_HOSTS`, `REDIS_URL`).

### 2. Custom settings (optional)

The containers are started with `DJANGO_SETTINGS_MODULE=config.settings_local`.
`settings_local.py` is not baked into the image — it is mounted in via a
volume, so you can patch it without rebuilding:

```bash
# use your own patched settings file
export SETTINGS_LOCAL=/path/to/my_settings_local.py
```

The provided template is [`deploy/settings_local.py`](deploy/settings_local.py)
and reads all values from environment variables (see `.env.example`).

### 3. Build and start

```bash
docker compose up -d --build
```

Then create the initial admin user:

```bash
docker compose run --rm backend python manage.py createsuperuser
```

### 4. What runs where

| Service   | Role                                | Port |
| --------- | ----------------------------------- | ---- |
| `web`     | nginx: frontend + reverse proxy     | 8080 |
| `backend` | uvicorn (Django API / admin)        | 8000 |
| `worker`  | FastStream Redis worker             | —    |
| `redis`   | broker                              | —    |

- Frontend: http://localhost:8080
- Swagger: http://localhost:8000/api/docs
- Django admin: http://localhost:8000/admin (or via http://localhost:8080/admin)

Data is persisted in Docker named volumes (`db_data`, `media_data`,
`static_data`). To stop: `docker compose down` (add `-v` to also delete the
volumes).

## License

[Apache License 2.0](LICENSE)
