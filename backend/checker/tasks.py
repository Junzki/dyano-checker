import json
import shutil
import subprocess
from pathlib import Path

import yaml
from asgiref.sync import sync_to_async
from django.conf import settings

from .models import Submission

DEFAULT_OUTPUT_TEMPLATE = "output.template.xlsx"


def _agent_root(submission: Submission) -> Path:
    return Path(settings.MEDIA_ROOT) / "agent" / str(submission.pk)


def _output_template_name(submission: Submission) -> str:
    """Return the template filename referenced by the YAML `output-template`."""
    rules_path = Path(submission.rule_set.yaml_file.path)
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}
    for entry in data.get("output-template", []):
        name = entry.get("file") if isinstance(entry, dict) else entry
        if name:
            return name
    return DEFAULT_OUTPUT_TEMPLATE


def _prepare_input(submission: Submission) -> None:
    """Assemble the agent input dir (manifest, rules, skills, files)."""
    root = _agent_root(submission)
    input_dir = root / "input"
    work_dir = root / "work"
    for directory in (input_dir / "files", input_dir / "skills", work_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # Rule-set YAML (full, including `rules` and `output-template`).
    rules_src = Path(submission.rule_set.yaml_file.path)
    shutil.copyfile(rules_src, input_dir / "rules.yaml")

    # Skills/gates: uploaded RuleSkillFile entries first, repo defaults next.
    skill_names: set[str] = set()
    for skill_file in submission.rule_set.skill_files.all():
        shutil.copyfile(
            Path(skill_file.file.path), input_dir / "skills" / skill_file.name
        )
        skill_names.add(skill_file.name)

    repo_skills = Path(settings.PROJECT_ROOT) / "skills"
    if repo_skills.is_dir():
        for path in repo_skills.iterdir():
            if path.is_file() and path.name not in skill_names:
                shutil.copyfile(path, input_dir / "skills" / path.name)

    # Output template: the dedicated RuleSet upload overrides the repo default.
    if submission.rule_set.output_template:
        template_name = _output_template_name(submission)
        shutil.copyfile(
            Path(submission.rule_set.output_template.path),
            input_dir / "skills" / template_name,
        )

    # Files + manifest (file_path is relative to the agent's files dir).
    manifest_files: list[dict] = []
    for submission_file in submission.files.all():
        source = Path(submission_file.file.path)
        destination = input_dir / "files" / submission_file.key / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest_files.append(
            {
                "key": submission_file.key,
                "category_name": submission_file.category_name,
                "requirement_name": submission_file.requirement_name,
                "file_path": f"{submission_file.key}/{source.name}",
                "original_name": submission_file.original_name,
            }
        )

    (input_dir / "manifest.json").write_text(
        json.dumps(
            {"submission_id": submission.pk, "files": manifest_files}, indent=2
        ),
        encoding="utf-8",
    )


def _run_agent(submission: Submission) -> None:
    """Run the agent container against the prepared input dir."""
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("docker CLI not found; is it installed on the worker?")

    command = [
        docker,
        "run",
        "--rm",
        "-v",
        f"{settings.AGENT_MEDIA_VOLUME}:/media:rw",
        "-e",
        f"AGENT_INPUT_DIR=/media/agent/{submission.pk}/input",
        "-e",
        f"AGENT_WORK_DIR=/media/agent/{submission.pk}/work",
        "-e",
        f"AGENT_LLM_BASE_URL={settings.AGENT_LLM_BASE_URL}",
        "-e",
        f"AGENT_LLM_API_KEY={settings.AGENT_LLM_API_KEY}",
        "-e",
        f"AGENT_LLM_MODEL={settings.AGENT_LLM_MODEL}",
        settings.AGENT_IMAGE,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(
            f"agent container exited {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()}"
        )


def _read_results(submission: Submission) -> dict:
    results_path = _agent_root(submission) / "work" / "results.json"
    if not results_path.exists():
        raise RuntimeError(f"agent did not produce {results_path}")
    return json.loads(results_path.read_text(encoding="utf-8"))


def process_submission_sync(submission_id: int) -> None:
    submission = (
        Submission.objects.select_related("rule_set")
        .prefetch_related("files", "rule_set__skill_files")
        .get(pk=submission_id)
    )
    submission.status = Submission.Status.PROCESSING
    submission.save(update_fields=["status", "updated_at"])

    try:
        for submission_file in submission.files.all():
            if not submission_file.file.storage.exists(submission_file.file.name):
                raise FileNotFoundError(
                    f"missing upload for '{submission_file.key}'"
                )

        _prepare_input(submission)
        _run_agent(submission)
        results = _read_results(submission)

        output_files = [
            f"agent/{submission.pk}/work/{name}"
            for name in results.get("output_files", [])
        ]
        if output_files:
            results["output_files"] = output_files
            results["output_file"] = output_files[0]
            results["output_url"] = settings.MEDIA_URL + output_files[0]

        submission.results = results
        submission.status = (
            Submission.Status.COMPLETED
            if results.get("status") == "completed"
            else Submission.Status.FAILED
        )
        submission.save(update_fields=["status", "results", "updated_at"])
    except Exception as exc:  # noqa: BLE001 - record failure, keep task alive
        submission.status = Submission.Status.FAILED
        submission.results = {"error": str(exc)}
        submission.save(update_fields=["status", "results", "updated_at"])


async def process_submission(submission_id: int) -> None:
    await sync_to_async(process_submission_sync)(submission_id)
