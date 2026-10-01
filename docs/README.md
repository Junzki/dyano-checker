# Docs

This folder is the authoritative source for the Dyano Checker design and
implementation narrative. Start here for a high-level overview, then follow the
links below for the details.

## What Dyano Checker is

Dyano Checker turns a YAML rule set into a dynamic file-upload form. An admin
uploads a rule-set YAML (plus optional skill/gate files and an output spreadsheet
template) via Django admin; end users pick a named rule set and get a form with
one file input per `file-requirement`. Uploaded files are stored locally and
processed asynchronously: each submission is checked by a one-shot LLM agent
container that extracts the documents, sanitizes them, evaluates every rule, and
fills in the output spreadsheet.

## Core features

- **YAML-driven forms** — the form is generated entirely from `check-requirements`
  in the rule-set YAML; no code changes are needed to add categories or file inputs.
- **Admin-managed rule sets** — a `RuleSet` (name + YAML + optional skill files and
  output template) is uploaded through Django admin and parsed into a schema on save.
- **Typed REST API** — django-ninja endpoints (`/api`) with generated Swagger docs,
  covering rule-set listing/schema and submission create/status.
- **Async processing pipeline** — a FastStream `RedisBroker` worker moves each
  submission through `queued → processing → completed/failed` and orchestrates the
  checking agent.
- **One-shot checking agent** — a disposable Docker container (Python 3.12, Pydantic
  AI) that extracts PDFs (native text or OCR), redacts prompt-injection attempts,
  runs each YAML rule against the sanitized text, and fills the output template.
- **Structured results** — per-rule verdicts (`pass`/`fail`/`error`) with reasoning
  and evidence, returned as `results.json` and rendered as `report.md` and `output.xlsx`.
- **React + TypeScript frontend** — renders the dynamic form, uploads files, and
  polls submission status.

## Architecture

```
admin (Django admin)  ──uploads YAML (+ skill files, output template)──▶  RuleSet
                                                                         (name + schema)
user (React form)     ──chooses RuleSet──▶  renders one file input per requirement
                                                                         │
                                     ──submits files──▶  Submission (queued)
                                                                         │ publish to Redis
                                                       FastStream worker  │ queued → processing
                                                                         │ assemble input + manifest
                                                                         │ docker run agent (per task)
                                                                         │ read results.json
                                                       checking agent     │ pdf_reader → sanitizer → check → xlsx_writer
                                                                         ▼
                                                          completed/failed + results
```

The system has four moving parts, split across the top-level directories:

- **`backend/`** — Django 5.2 project (`config/` settings/urls, `checker/` app).
  Holds the models (`RuleSet`, `Submission`, `SubmissionFile`, `RuleSkillFile`),
  the schema parser, the django-ninja API, and the FastStream broker/worker.
- **`agent/`** — the checking agent, packaged as its own Docker image (Python 3.12,
  not the backend's 3.14, because PaddleOCR has no 3.14 wheels).
- **`web/`** — React 18 + TypeScript + Vite frontend.
- **`media/`** — local file storage (`MEDIA_ROOT`), gitignored.

### Submission lifecycle

1. The frontend POSTs `rule_set_id`, a `keys_json` array of requirement keys, and
   the `files` list to `POST /api/submissions` (keys and files are zipped in order).
2. The API stores the files, creates a `Submission` with status `queued`, and
   publishes a `SubmissionMessage` to the Redis `submissions` channel.
3. The worker picks it up, marks it `processing`, assembles the per-submission
   input directory (`manifest.json`, `rules.yaml`, skills, output template, files)
   under `media/agent/<id>/input`, and runs `docker run --rm` on the agent image.
4. The agent writes `results.json` (plus `report.md` and the filled `output.xlsx`)
   to `media/agent/<id>/work`; the worker reads it back into `Submission.results`
   and sets the terminal status, exposing the output spreadsheet via `output_url`.

See the checking agent design document for the exact container contract, tool
pipeline, and configuration.

## Documents

| Document | Description |
| --- | --- |
| [`agent-design.md`](agent-design.md) | Design of the one-shot checking agent: container contract, input/work layout, `pdf_reader`/`sanitizer`/`check`/`xlsx_writer` tools, configuration, orchestration, and security. |
| [`deploy-and-security.md`](deploy-and-security.md) | Deployment topology (Docker Compose), configuration, volumes, reverse proxy, and the security model and risks (Docker socket, secrets, auth gaps, prompt injection). |
| [`intake.md`](intake.md) | Implementation summary: what was built (backend, frontend, config), key design decisions, and verification status. |
| [`Rules.yaml`](Rules.yaml) | Example rule-set YAML illustrating the `check-requirements` → `file-requirements` → `rules` → `output-template` shape. |

For operational setup and commands, see the top-level [`README.md`](../README.md);
for agent-facing conventions, see [`AGENTS.md`](../AGENTS.md).
