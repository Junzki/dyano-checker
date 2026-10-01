"""Shared data models for the agent pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileManifestEntry(BaseModel):
    key: str
    category_name: str = ""
    requirement_name: str = ""
    file_path: str
    original_name: str = ""


class Manifest(BaseModel):
    submission_id: int
    files: list[FileManifestEntry] = Field(default_factory=list)


class Rule(BaseModel):
    name: str
    description: str = ""
    skill: str = ""
    gate: str = ""


class CheckResult(BaseModel):
    rule_name: str
    verdict: Literal["pass", "fail", "error"]
    reasoning: str = ""
    evidence: list[str] = Field(default_factory=list)


class SanitizerFinding(BaseModel):
    location: str
    pattern: str
    snippet: str = ""


class SanitizerReport(BaseModel):
    files: list[str] = Field(default_factory=list)
    findings: list[SanitizerFinding] = Field(default_factory=list)
