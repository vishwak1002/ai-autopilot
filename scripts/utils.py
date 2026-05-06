"""
utils.py — Shared utilities for ai-autopilot scripts.
AI provider is intentionally a placeholder — swap AI_PROVIDER env var to change.
"""

import os
import json
import subprocess
from pathlib import Path
import yaml


# ---------------------------------------------------------------------------
# AI Client (placeholder — swap AI_PROVIDER to change provider)
# ---------------------------------------------------------------------------

def get_ai_client():
    provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
    api_key = os.environ.get("AI_API_KEY", "")

    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=api_key), provider

    if provider == "openai":
        import openai
        return openai.OpenAI(api_key=api_key), provider

    raise ValueError(f"Unsupported AI_PROVIDER: {provider}. Set to 'anthropic' or 'openai'.")


def call_ai(prompt: str, system_prompt: str = "") -> str:
    """Call the configured AI provider and return the response text."""
    client, provider = get_ai_client()
    model = os.environ.get("AI_MODEL", "claude-opus-4-5")

    if provider == "anthropic":
        messages = [{"role": "user", "content": prompt}]
        kwargs = {"model": model, "max_tokens": 8096, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(**kwargs)
        return response.content[0].text

    if provider == "openai":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content

    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# FEEDBACK.md helpers
# ---------------------------------------------------------------------------

FEEDBACK_HEADER = "## 🔄 Refined Prompts\n"


def read_feedback(repo_path: str) -> list[str]:
    """Return list of refined prompts from FEEDBACK.md (oldest first)."""
    feedback_file = Path(repo_path) / "FEEDBACK.md"
    if not feedback_file.exists():
        return []

    content = feedback_file.read_text()
    lines = content.splitlines()
    prompts = [
        line.lstrip("- ").strip()
        for line in lines
        if line.strip().startswith("- [Retry]")
    ]
    return prompts


def consume_feedback(repo_path: str, prompt: str) -> None:
    """Remove a consumed prompt from FEEDBACK.md."""
    feedback_file = Path(repo_path) / "FEEDBACK.md"
    if not feedback_file.exists():
        return

    lines = feedback_file.read_text().splitlines(keepends=True)
    new_lines = [
        line for line in lines
        if prompt[:40] not in line
    ]
    feedback_file.write_text("".join(new_lines))


def write_feedback(repo_path: str, original_prompt: str, score: int, issues: str) -> None:
    """Append a refined prompt to FEEDBACK.md."""
    feedback_file = Path(repo_path) / "FEEDBACK.md"

    if not feedback_file.exists():
        feedback_file.write_text(f"# Autopilot Feedback Log\n\n{FEEDBACK_HEADER}\n")

    content = feedback_file.read_text()
    if FEEDBACK_HEADER not in content:
        content += f"\n{FEEDBACK_HEADER}\n"

    entry = f"- [Retry] {original_prompt} | Fix: {issues} (score: {score}/10)\n"
    content += entry
    feedback_file.write_text(content)
    print(f"Written to FEEDBACK.md: {entry.strip()}")


# ---------------------------------------------------------------------------
# .autopilot.yml config loader
# ---------------------------------------------------------------------------

def load_autopilot_config(repo_path: str) -> dict:
    """Load .autopilot.yml from a target repo. Returns defaults if missing."""
    config_file = Path(repo_path) / ".autopilot.yml"
    defaults = {
        "language": "python",
        "style": "functional",
        "domain": "general",
        "target_branch": "main",
        "test_framework": "pytest",
    }
    if not config_file.exists():
        print(f"No .autopilot.yml found in {repo_path}, using defaults.")
        return defaults

    with open(config_file) as f:
        config = yaml.safe_load(f) or {}

    return {**defaults, **config}


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def gh(*args, check=True, capture=True) -> str:
    """Run a gh CLI command and return stdout."""
    cmd = ["gh"] + list(args)
    result = subprocess.run(cmd, capture_output=capture, text=True, check=check)
    return result.stdout.strip()


def set_output(name: str, value: str) -> None:
    """Write a key=value pair to GITHUB_OUTPUT."""
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    line = f"{name}={value}\n"
    if output_file:
        with open(output_file, "a") as f:
            f.write(line)
    print(f"OUTPUT: {line.strip()}")


def get_registered_targets() -> list[str]:
    """
    Read list of target repos from ai-autopilot README.md.
    Looks for a ## 🎯 Target Repos section with lines like:
      - vishwak1002/my-ai-apps
    """
    readme = Path("README.md")
    if not readme.exists():
        return []

    import re
    content = readme.read_text()
    section = re.search(r"## 🎯 Target Repos(.*?)(?=##|\Z)", content, re.DOTALL)
    if not section:
        return []

    targets = re.findall(r"^[-*]\s+(\S+/\S+)$", section.group(1), re.MULTILINE)
    return targets
