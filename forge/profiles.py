"""Harness capabilities are distinct from model providers and cost tiers."""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil

@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    argv: tuple[str, ...]
    task_argv: tuple[str, ...] | None = None
    tier: str = "unknown"

    def command(self, prompt: str | None = None) -> list[str]:
        template = self.argv if prompt is None else self.task_argv
        if template is None:
            raise ValueError(f"{self.label}: automated task mode has not been verified; use interactive mode")
        if not self.available:
            raise ValueError(f"{self.argv[0]} is not on PATH. Install and authenticate using its official instructions.")
        return [part.replace("{prompt}", prompt or "") for part in template]

    @property
    def available(self) -> bool:
        return bool(shutil.which(self.argv[0]))


def profiles(project: Path) -> dict[str, Profile]:
    shell = os.environ.get("SHELL") or "/bin/bash"
    default = [Profile("shell", "Project shell", (shell,)),
               Profile("claude", "Claude Code", ("claude",), ("claude", "-p", "{prompt}")),
               Profile("codex", "OpenAI Codex", ("codex",), ("codex", "exec", "{prompt}")),
               Profile("gemini", "Gemini CLI", ("gemini",), ("gemini", "-p", "{prompt}")),
               Profile("kimi", "Kimi Code", ("kimi",)),
               Profile("opencode", "OpenCode", ("opencode",)),
               Profile("aider", "Aider", ("aider",))]
    result = {profile.id: profile for profile in default}
    config = project / ".agent-forge" / "profiles.json"
    if config.is_symlink():
        raise ValueError("Refusing symlinked profile configuration")
    if config.exists():
        items = json.loads(config.read_text())
        if not isinstance(items, list) or len(items) > 30:
            raise ValueError("profiles.json must contain at most 30 profiles")
        for item in items:
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", item.get("id", "")):
                raise ValueError("Profile ID must be a lowercase slug")
            for key in ("argv", "task_argv"):
                value = item.get(key)
                if value is not None and (not isinstance(value, list) or not value or not all(isinstance(v, str) and v and '\0' not in v for v in value)):
                    raise ValueError(f"Invalid {key}")
            if not item.get("argv"):
                raise ValueError("A profile needs argv")
            tier = item.get("tier", "unknown")
            if tier not in {"strong", "economy", "local", "unknown"}:
                raise ValueError("Tier: strong, economy, local or unknown")
            result[item["id"]] = Profile(item["id"], item.get("label", item["id"])[:100], tuple(item["argv"]), tuple(item["task_argv"]) if item.get("task_argv") else None, tier)
    from .ollama import read_settings
    selected = read_settings(project / ".agent-forge").get("selected_model")
    if selected:
        result["ollama"] = Profile("ollama", "Ollama / " + selected, ("ollama", "run", selected), tier="local")
    return result


def recommend(available: list[Profile], risk: str) -> str | None:
    # A transparent user-configured policy, not invented vendor prices or free allowances.
    tier_order = ["strong", "unknown", "economy", "local"] if risk == "high" else ["local", "economy", "unknown", "strong"]
    candidates = [p for p in available if p.available and p.task_argv]
    for tier in tier_order:
        if matches := [p for p in candidates if p.tier == tier]:
            return matches[0].id
    return None
