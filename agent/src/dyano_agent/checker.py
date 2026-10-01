"""Tool 3 — Checker.

Run each rule from the rule-set YAML, one by one, against the sanitized
extracted documents. Each rule's `skill` (inline content or a referenced file)
becomes the agent system prompt and its `gate` the pass/fail criteria. Backed
by Pydantic AI with an OpenAI-compatible model.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .schemas import CheckResult, Rule

logger = logging.getLogger(__name__)


def _resolve_skill_value(config: Config, value: str, kind: str) -> str:
    """Resolve a rule's `skill`/`gate` value.

    The YAML may hold either the skill content inline or a filename reference to
    a file uploaded alongside the rule set (available under ``skills_dir``).
    Multi-line values are always inline content; single-line values are treated
    as a filename when a matching file exists, otherwise used inline.
    """
    if not value:
        return ""
    if "\n" in value:
        return value
    path = config.skills_dir / value
    if path.is_file():
        return path.read_text(encoding="utf-8")
    logger.warning("%s file '%s' not found; using value as inline content", kind, value)
    return value


def _load_skill_gate(config: Config, rule: Rule) -> tuple[str, str]:
    return (
        _resolve_skill_value(config, rule.skill, "Skill"),
        _resolve_skill_value(config, rule.gate, "Gate"),
    )


def _build_documents(sanitized_dir: Path) -> str:
    sections: list[str] = []
    for md_path in sorted(sanitized_dir.glob("*.md")):
        sections.append(f"## Document: {md_path.name}\n\n{md_path.read_text(encoding='utf-8')}")
    return "\n\n".join(sections) if sections else "(no documents provided)"


def run_checks(config: Config, rules: list[Rule], sanitized_dir: Path) -> list[CheckResult]:
    """Run all rules sequentially and return one result per rule."""
    if not config.llm_api_key:
        raise RuntimeError("AGENT_LLM_API_KEY is not set; cannot run checks")

    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIModel

    model = OpenAIModel(
        config.llm_model,
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
    )

    documents = _build_documents(sanitized_dir)
    results: list[CheckResult] = []

    for rule in rules:
        skill, gate = _load_skill_gate(config, rule)
        system_prompt = skill or "You are a careful document checker."
        prompt = (
            f"# Rule\n\n**{rule.name}**\n\n"
            f"{rule.description}\n\n"
            f"# Documents\n\n{documents}\n\n"
            f"# Gate (pass/fail criteria)\n\n{gate or '(no gate provided)'}"
        )

        agent = Agent(model, system_prompt=system_prompt, result_type=CheckResult)
        logger.info("Running check for rule '%s'", rule.name)
        try:
            result = agent.run_sync(prompt)
            data: CheckResult = result.data
            data.rule_name = rule.name
            results.append(data)
        except Exception as exc:  # noqa: BLE001 - keep pipeline going per rule
            logger.exception("Check for rule '%s' failed", rule.name)
            results.append(
                CheckResult(
                    rule_name=rule.name,
                    verdict="error",
                    reasoning=f"check raised an error: {exc}",
                )
            )

    return results
