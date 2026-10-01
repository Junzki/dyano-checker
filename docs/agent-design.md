# Checking Agent — Design

The checking agent is the component that actually evaluates a submission. For
every checking task it runs once, as a disposable Docker container, and then
exits. It is stateless: everything it needs arrives via mounted directories and
environment variables, and everything it produces is written to a mounted work
directory.

## Overview

```
Submission created
   │  publish to Redis
   ▼
FastStream worker
   │  queued → processing
   │  assemble /input (manifest + rules + skills + files)
   │  docker run --rm agent image
   │  read results.json
   ▼
Agent container (one-shot)
   │  1. pdf_reader   — detect + extract each PDF to Markdown
   │  2. sanitizer    — redact prompt-injection attempts
   │  3. check        — run each YAML rule, one by one, via the LLM
   │  4. xlsx_writer  — fill the output template's verdict cells
   ▼
/work/results.json + report.md + output.xlsx + extracted/*.md + sanitized/*.md
```

The agent is a single-run CLI (`python -m dyano_agent`), not a server. The LLM
is invoked only during the check step; PDF extraction and sanitizing are
deterministic and run before anything reaches the model.

## Container contract

The worker and the agent share the media volume. The worker builds the input
under `MEDIA_ROOT/agent/<submission_id>/` and runs the container with the media
volume mounted at `/media`:

```
/media/agent/<submission_id>/input   (read-only in spirit)
├── manifest.json        # submission_id + file entries
├── rules.yaml           # full rule-set YAML (check-requirements, rules, output-template)
├── skills/              # uploaded skill/gate files + output template xlsx
└── files/<key>/<name>   # one uploaded file per requirement key

/media/agent/<submission_id>/work    (written by the agent)
├── extracted/<key>.md
├── sanitized/<key>.md
├── sanitizer-report.json
├── results.json
├── report.md
└── output.xlsx          # filled output template
```

`manifest.json` maps each requirement key to its metadata and file path:

```json
{
  "submission_id": 1,
  "files": [
    {
      "key": "0-0",
      "category_name": "Category 1",
      "requirement_name": "req1",
      "file_path": "0-0/report.pdf",
      "original_name": "report.pdf"
    }
  ]
}
```

`file_path` is relative to the agent's files directory, so the agent never
hardcodes absolute paths.

## Configuration

All configuration is passed through environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `AGENT_LLM_BASE_URL` | OpenAI-compatible API entrypoint | `https://api.openai.com/v1` |
| `AGENT_LLM_API_KEY` | API key | (required) |
| `AGENT_LLM_MODEL` | Model name | `gpt-4o-mini` |
| `AGENT_INPUT_DIR` | Mounted input directory | `/input` |
| `AGENT_WORK_DIR` | Writable work directory | `/work` |

The worker sets `AGENT_INPUT_DIR`/`AGENT_WORK_DIR` to the per-submission paths
under `/media` and forwards the LLM settings from Django settings.

## Tools

### 1. PDF reader (`pdf_reader.py`)

For each PDF in the manifest:

1. **Detection** — open with PyMuPDF and count non-whitespace text characters.
   Below a threshold (`NATIVE_TEXT_THRESHOLD = 50`) the PDF is treated as a
   scanned image.
2. **Native PDF** — extract Markdown with `pymupdf4llm`; inspect AcroForm fields
   via PyMuPDF (`doc.is_form`, `page.widgets()`) and run a best-effort Docling
   pass to locate tables/forms.
3. **Scanned PDF** — render each page to an image and OCR with PaddleOCR,
   emitting page-by-page Markdown.

Output is written to `/work/extracted/<key>.md`. A summary (pdf type, form
notes, character count) is recorded per file.

### 2. Sanitizer (`sanitizer.py`)

Before any extracted content reaches the model, it is scanned for
prompt-injection attempts. Two surfaces are checked:

- **Text** — lines containing injection patterns (e.g. "ignore previous
  instructions", "you are now", "system prompt", "override") are replaced with
  `[REDACTED]`.
- **Filenames** — suspicious names are flagged and rewritten to a safe form.

Sanitized copies are written to `/work/sanitized/<key>.md` and a
`sanitizer-report.json` records every finding (location, pattern, snippet). The
check step consumes only sanitized text.

### 3. Check (`checker.py`)

Runs each `rule` from the rule-set YAML, sequentially, in YAML order. Each rule
provides a `skill` (instructions) and a `gate` (pass/fail criteria), either
inline in the YAML or as an uploaded file referenced by name:

- The resolved `skill` content becomes the Pydantic AI agent's **system prompt**.
- The user prompt contains the rule name/description, the sanitized documents,
  and the `gate` criteria.
- A structured result is requested via `result_type`:

```python
class CheckResult(BaseModel):
    rule_name: str
    verdict: Literal["pass", "fail", "error"]
    reasoning: str
    evidence: list[str]
```

The model is a Pydantic AI `OpenAIModel(model, base_url=..., api_key=...)`,
which makes the agent provider-agnostic (any OpenAI-compatible endpoint).
Per-rule failures are captured as `verdict="error"` so the pipeline continues
rather than aborting.

### 4. XLSX writer (`xlsx_writer.py`)

Fills the rule set's output spreadsheet template from the check results and
writes it to `/work/output.xlsx` (`output-2.xlsx`, etc. when the YAML lists more
than one template). The template files are named by the `output-template` entry
in the rule-set YAML:

```yaml
output-template:
  - file: output.template.xlsx
```

The template already contains the rules and gates as rows; the writer only fills
in the verdict. The header row (row 1) defines two columns:

- **Rule** (`rule`, `rule name`, or `name`) — the row key, matched against
  `CheckResult.rule_name`.
- **Result** (`result`, `verdict`, `status`, or `outcome`) — the cell that
  receives the verdict (`PASSED`, `FAILED`, or `ERROR`).

Rows whose rule name has no matching check result are left blank and logged as a
warning. Existing cells and formatting are preserved (openpyxl loads the
template, only the Result cells are written).

The writer runs after `run_checks` and records the produced filenames in
`results.json` under `output_files`.

## Output

`results.json` is the machine-readable result and is what the worker reads back
into `Submission.results`:

```json
{
  "submission_id": 1,
  "status": "completed",
  "generated_at": "...",
  "files": [
    {"key": "0-0", "original_name": "report.pdf", "pdf_type": "native", "forms": ["..."], "char_count": 1234}
  ],
  "checks": [
    {"rule_name": "rule1", "verdict": "pass", "reasoning": "...", "evidence": ["..."]}
  ],
  "output_files": ["output.xlsx"]
}
```

`status` is `completed` when every rule passes, otherwise `failed`. `report.md`
is a human-readable rendering of the same data. `output_files` lists the filled
spreadsheet(s) written to the work dir; the worker copies those names into
`Submission.results` as media-relative paths and exposes the first one as
`output_url` on `GET /api/submissions/{id}`.

## Technology

- **Python 3.12** (not the backend's 3.14 — PaddleOCR/PaddlePaddle has no 3.14
  wheels yet). The agent has its own image and its own dependency set.
- **Pydantic AI** for the LLM agent (OpenAI-compatible model).
- **PyMuPDF** + **pymupdf4llm** for native PDF text/form extraction.
- **Docling** for form/layout discovery.
- **PaddleOCR** for scanned PDFs.
- **openpyxl** for filling the output spreadsheet template.

Dependencies are resolved at image build time (`uv sync`, no committed
`uv.lock`) because the PaddlePaddle wheel set is large and volatile.

## Orchestration

The Django/FastStream worker (`backend/checker/tasks.py`) is responsible for the
container lifecycle:

1. Mark the submission `processing`.
2. Build the input directory (copy rules.yaml, skills, output template, files;
   write `manifest.json`).
3. Run `docker run --rm` with the media volume mounted and LLM env vars set.
4. Read `/work/results.json` back into `Submission.results` and set the terminal
   status (`completed`/`failed`); copy the produced spreadsheet paths into
   `results` and expose the first as `output_url`.

Skills are user-defined and travel with the rule set: either inline in the YAML
(multi-line `skill`/`gate` content) or as per-rule-set `RuleSkillFile` uploads
referenced by filename. The output template comes from the
`RuleSet.output_template` upload (placed under `skills/` with the name the YAML
references). The worker image therefore ships the `docker` CLI and runs with
`/var/run/docker.sock` mounted.

## Security considerations

- **Docker socket** — the worker can create arbitrary containers on the host.
  Treat this as a privilege boundary; isolate the host Docker daemon.
- **Prompt injection** — the sanitizer is a heuristic defense, not a guarantee;
  extracted documents should be treated as untrusted input.
- **Secrets** — the API key is passed via environment variable and is visible in
  the running container's environment.

## Extensions

- Rules run sequentially by design; a parallel fan-out could be added later.
- The XLSX writer matches rows by exact rule name; a richer template schema
  (e.g. per-file or per-requirement rows) could be added later.
