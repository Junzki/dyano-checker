"""Tool 3 — Checker.

Run each rule from the rule-set YAML, one by one, against the sanitized
extracted documents. Each rule's `skill` file becomes the agent system prompt
and its `gate` file the pass/fail criteria. Backed by Pydantic AI with an
OpenAI-compatible model.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .schemas import CheckResult, Rule

logger = logging.getLogger(__name__)


def _load_skill_gate(config: Config, rule: Rule) -> tuple[str, str]:
    skill = ""
    gate = ""
    if rule.skill:
        skill_path = config.skills_dir / rule.skill
        if skill_path.exists():
            skill = skill_path.read_text(encoding="utf-8")
        else:
            logger.warning("Skill file %s not found", skill_path)
    if rule.gate:
        gate_path = config.skills_dir / rule.gate
        if gate_path.exists():
            gate = gate_path.read_text(encoding="utf-8")
        else:
            logger.warning("Gate file %s not found", gate_path)
    return skill, gate


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
