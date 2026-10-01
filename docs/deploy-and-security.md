# Deployment & Security

This document describes how the Dyano Checker stack is deployed (the
Docker Compose topology, configuration, and volumes) and the security model and
known risks you must account for before running it outside a local/trusted
environment.

## Deployment

### Topology

The production-shaped deployment is driven by `docker-compose.yaml`. It runs
four services plus one build-only image:

| Service | Image | Role |
| --- | --- | --- |
| `redis` | `redis:7-alpine` | FastStream broker (append-only persistence enabled) |
| `backend` | built from `backend/Dockerfile` | uvicorn serving the Django API, admin, and Swagger UI |
| `worker` | built from `backend/Dockerfile` | FastStream Redis worker + checking-agent orchestrator |
| `web` | built from `web/Dockerfile` | nginx serving the built frontend and reverse-proxying `/api`, `/admin`, `/media`, `/static` |
| `agent` | built from `agent/Dockerfile` (profile `agent`) | one-shot checking-agent image; **not** run by Compose — the worker spawns it via `docker run` |

`backend` and `worker` share the same image. The `worker` additionally mounts
`/var/run/docker.sock` so it can launch agent containers (see
[Security](#security)).

### Configuration

All runtime configuration flows from environment variables, provided through a
`.env` file. Copy [`.env.example`](../.env.example) and adjust:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django secret key (**required**) | — |
| `DJANGO_DEBUG` | Django debug mode | `false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `*` |
| `REDIS_URL` | Broker URL | `redis://redis:6379/0` |
| `DB_PATH` | SQLite path (inside the `db_data` volume) | `/app/data/db.sqlite3` |
| `WEB_PORT` | Host port for nginx | `8080` |
| `AGENT_IMAGE` | Checking-agent image name | `dyano-checker-agent` |
| `AGENT_MEDIA_VOLUME` | Media volume name shared with the agent | `dyano-checker_media_data` |
| `AGENT_LLM_BASE_URL` / `AGENT_LLM_API_KEY` / `AGENT_LLM_MODEL` | OpenAI-compatible endpoint, key, model for the agent | see `.env.example` |
| `SETTINGS_LOCAL` | Host path to a custom settings override file | `./deploy/settings_local.py` |

Generate the secret key with:

```bash
./scripts/generate-secret.sh
```

### Settings override

The containers run with `DJANGO_SETTINGS_MODULE=config.settings_local`.
[`deploy/settings_local.py`](settings_local.py) is **not** baked into the image;
it is mounted read-only into `backend/backend/config/settings_local.py` and
imports everything from `config.settings`, then overrides `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS`, `REDIS_URL`, the agent settings, `DATABASES`, `STATIC_ROOT`, and
`MEDIA_ROOT` from the environment. This lets you patch settings without
rebuilding — point `SETTINGS_LOCAL` at your own copy to override.

### Entrypoint

[`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh) runs
`manage.py migrate` and `manage.py collectstatic` before the real command. The
`worker` sets `SKIP_MIGRATE=1` (migrations run in `backend`); the worker only
consumes.

### Volumes

Three named volumes persist state:

- `db_data` — the SQLite database (`/app/data`)
- `media_data` — uploaded rule sets, submissions, and agent input/work dirs (`/app/media`)
- `static_data` — collected static files (`/app/staticfiles`)

`media_data` and `static_data` are mounted read-only into `web` (nginx serves
`/media` and `/static` directly). `media_data` is also the shared mount between
the worker and the agent container (`AGENT_MEDIA_VOLUME`).

### Reverse proxy

[`web/nginx.conf`](../web/nginx.conf) serves the SPA, proxies `/api/` and
`/admin/` to `backend:8000` (forwarding `X-Forwarded-*` headers), and serves
`/media/` and `/static/` from the shared volumes via `alias`. Upload size is
capped at `client_max_body_size 100m`.

### Build & start

```bash
./scripts/generate-secret.sh          # writes DJANGO_SECRET_KEY to .env
docker compose build agent            # build the checking-agent image
docker compose up -d --build
docker compose run --rm backend python manage.py createsuperuser
```

Frontend: http://localhost:8080 · Swagger: http://localhost:8000/api/docs ·
Admin: http://localhost:8000/admin (or via the nginx host).

## Security

### Trust boundaries

```
browser ──▶ nginx ──▶ backend (uvicorn) ──▶ Redis ──▶ worker ──▶ docker daemon ──▶ agent container
                              │                                              └─▶ LLM API (outbound)
                              └─▶ db.sqlite3 (db_data) / media (media_data)
```

### Privileged worker / Docker socket

The worker mounts `/var/run/docker.sock` and runs `docker run --rm` once per
submission. This gives the worker the ability to create **arbitrary containers
on the Docker host** — effectively root-level access to the host.

- Treat the worker as a privilege boundary: isolate the host Docker daemon, and
  do not run the worker on a host that runs other trusted containers.
- There is no per-user isolation between submissions; a compromised worker (or
  any code path that reaches `docker run`) can escape to the host.
- The agent container is currently run with full access to the shared media
  volume (`-v <volume>:/media:rw`) and inherits `AGENT_LLM_API_KEY` via
  environment variables.

### Secrets handling

- `DJANGO_SECRET_KEY` lives in `.env` (gitignored) and is passed to the
  containers via Compose. It is required by Compose
  (`${DJANGO_SECRET_KEY:?...}`) — deployment fails without it.
- `AGENT_LLM_API_KEY` is forwarded from the worker's environment into each agent
  container via `-e`. It is visible in the container's environment and, in the
  agent's runtime, to anything running inside it.
- Never commit `.env`; it is covered by `.gitignore`.

### Authentication & authorization

The REST API (`/api`) has **no authentication or authorization** (see
[`intake.md`](intake.md) — "Not implemented (by design)"). Anyone who can reach
`/api` can list rule sets, view schemas, create submissions, and read any
submission's status, files, and `output_url`. Only the Django admin (`/admin/`)
is protected by Django's built-in auth. **Do not expose the API to untrusted
users** without adding an auth layer.

### Input / upload handling

- **File type** — the form requests only PDF (`accept=".pdf,application/pdf"`),
  but the backend does **not** validate the uploaded content type or extension.
  The agent's `pdf_reader` treats every uploaded file as a PDF; a malicious
  file is only limited by PyMuPDF/PaddleOCR behavior. Add server-side
  validation before public exposure.
- **Prompt injection** — uploaded documents and filenames are treated as
  untrusted. The agent's `sanitizer` (see
  [`agent-design.md`](agent-design.md)) is a *heuristic* defense that redacts
  known injection patterns; it is not a guarantee. Extracted text can still
  influence the model.
- **Media serving** — nginx serves `/media/` directly with no access control;
  uploaded files and generated outputs are publicly reachable by URL.

### Transport & Redis

- **TLS** — the stack assumes a trusted internal network; there is no TLS
  termination configured. Put the deployment behind a TLS-terminating proxy if
  exposed beyond localhost.
- **Redis** — the Compose `redis` service has **no password** and no exposed
  host port by default; `REDIS_URL` defaults to `redis://redis:6379/0`. The
  dev default in `config/settings.py` uses a password (`redis://:password@...`),
  but the Compose override does not. Secure Redis before public exposure.
- **Broker durability** — the default `RedisBroker` is pub/sub (non-durable):
  messages can be lost if the worker is down. Switch to `RedisStreamBroker` for
  durable queues.

### Django hardening

- `DEBUG` must remain `false` in deployment (`settings_local.py` defaults it
  that way). The baked-in `config.settings.py` uses an insecure dev-only
  `SECRET_KEY` and `DEBUG = True` — always run under `settings_local`.
- `ALLOWED_HOSTS` defaults to `*`; restrict it to your real hostname(s).
- `SecurityMiddleware`, `CsrfViewMiddleware`, and `XFrameOptionsMiddleware` are
  enabled. django-ninja's `NinjaAPI` runs with CSRF exempt, so the API is not
  protected by the CSRF middleware — another reason to add real auth.

### Backups

State lives in the `db_data` (SQLite) and `media_data` (uploads + generated
reports) volumes. `docker compose down` preserves them; `docker compose down -v`
deletes them. Back up both volumes regularly.
