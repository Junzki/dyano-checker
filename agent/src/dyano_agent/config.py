"""Runtime configuration, driven by environment variables.

The agent is a one-shot container: everything it needs arrives via mounted
directories and environment variables set by the orchestrating worker.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class Config:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    input_dir: Path
    work_dir: Path

    @property
    def manifest_path(self) -> Path:
        return self.input_dir / "manifest.json"

    @property
    def rules_path(self) -> Path:
        return self.input_dir / "rules.yaml"

    @property
    def skills_dir(self) -> Path:
        return self.input_dir / "skills"

    @property
    def files_dir(self) -> Path:
        return self.input_dir / "files"

    @property
    def extracted_dir(self) -> Path:
        return self.work_dir / "extracted"

    @property
    def sanitized_dir(self) -> Path:
        return self.work_dir / "sanitized"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_base_url=os.environ.get("AGENT_LLM_BASE_URL", DEFAULT_BASE_URL),
            llm_api_key=os.environ.get("AGENT_LLM_API_KEY", ""),
            llm_model=os.environ.get("AGENT_LLM_MODEL", DEFAULT_MODEL),
            input_dir=Path(os.environ.get("AGENT_INPUT_DIR", "/input")),
            work_dir=Path(os.environ.get("AGENT_WORK_DIR", "/work")),
        )
