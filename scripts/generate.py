"""
generate.py — Reads prompts from target repo, generates code via AI, writes files.

Usage (called by Workflow 1):
  TARGET_REPO_PATH=./cloned-repo python scripts/generate.py
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from utils import call_ai, load_prompt, read_feedback, consume_feedback, load_autopilot_config, set_output


def extract_prompts_from_file(repo_path: str) -> list[str]:
    """
    Read prompts from PROMPTS.md — one prompt per line starting with - or *.
    This is the dedicated prompts file, separate from README.md.
    """
    prompts_file = Path(repo_path) / "PROMPTS.md"
    if not prompts_file.exists():
        raise FileNotFoundError(
            f"PROMPTS.md not found in {repo_path}. "
            "Create a PROMPTS.md file with prompts as bullet points."
        )

    content = prompts_file.read_text()
    prompts = re.findall(r"^[-*]\s+(.+)$", content, re.MULTILINE)
    return [p.strip() for p in prompts if p.strip() and not p.startswith("#")]


def pick_prompt(repo_path: str) -> tuple[str, bool]:
    """
    Pick a prompt using priority queue logic:
    1. FEEDBACK.md first (refined/retry prompts)
    2. Fallback to PROMPTS.md

    Returns (prompt, is_retry)
    """
    feedback_prompts = read_feedback(repo_path)
    if feedback_prompts:
        prompt = feedback_prompts[0]
        consume_feedback(repo_path, prompt)
        print(f"Using FEEDBACK.md prompt (retry): {prompt[:80]}")
        return prompt, True

    prompts = extract_prompts_from_file(repo_path)
    if not prompts:
        raise ValueError("No prompts found in FEEDBACK.md or PROMPTS.md")

    import random
    prompt = random.choice(prompts)
    print(f"Using PROMPTS.md prompt (fresh): {prompt[:80]}")
    return prompt, False


def generate_code(prompt: str, config: dict, is_retry: bool) -> dict:
    """Call AI to generate code files based on prompt and repo config."""
    retry_context = ""
    if is_retry and "Fix:" in prompt:
        parts = prompt.split("| Fix:", 1)
        original = parts[0].replace("[Retry]", "").strip()
        fixes = parts[1].strip() if len(parts) > 1 else ""
        retry_context = f"\n\nIMPORTANT: This is a retry. Previous attempt failed. Required fixes:\n{fixes}"
        prompt = original

    user_prompt = load_prompt("generate_user").format(
        prompt=prompt,
        retry_context=retry_context,
        language=config["language"],
        style=config["style"],
        domain=config["domain"],
        test_framework=config["test_framework"],
    )

    response = call_ai(user_prompt, load_prompt("generate_system"))

    # Extract JSON robustly
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if not json_match:
        raise ValueError(f"AI response did not contain valid JSON.\nResponse: {response[:500]}")

    return json.loads(json_match.group())


def write_generated_files(repo_path: str, code_data: dict) -> list[str]:
    """Write generated code files to the target repo."""
    written = []
    for file_info in code_data.get("files", []):
        file_path = Path(repo_path) / file_info["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_info["content"])
        written.append(str(file_path))
        print(f"Written: {file_path}")
    return written


if __name__ == "__main__":
    repo_path = os.environ.get("TARGET_REPO_PATH", ".")

    config = load_autopilot_config(repo_path)
    prompt, is_retry = pick_prompt(repo_path)
    code_data = generate_code(prompt, config, is_retry)
    written_files = write_generated_files(repo_path, code_data)

    feature_name = code_data.get("feature_name", "feature")
    description = code_data.get("description", "")

    print(f"\nGenerated {len(written_files)} file(s) for feature: {feature_name}")

    set_output("feature_name", feature_name)
    set_output("description", description)
    set_output("prompt", prompt[:200].replace("\n", " "))
    set_output("is_retry", str(is_retry).lower())
