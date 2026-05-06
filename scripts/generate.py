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
from utils import call_ai, read_feedback, consume_feedback, load_autopilot_config, set_output


SYSTEM_PROMPT = """You are an expert software developer. Generate clean, production-ready code.
Always include proper error handling, docstrings, and unit tests.
Respond ONLY with valid JSON — no markdown fences, no extra text."""


def extract_prompts_from_readme(repo_path: str) -> list[str]:
    """Extract prompts from ## 🤖 Prompts section in README.md."""
    readme = Path(repo_path) / "README.md"
    if not readme.exists():
        return []

    content = readme.read_text()
    section = re.search(r"## 🤖 Prompts(.*?)(?=##|\Z)", content, re.DOTALL)
    if not section:
        return []

    prompts = re.findall(r"^[-*]\s+(.+)$", section.group(1), re.MULTILINE)
    return [p.strip() for p in prompts if p.strip()]


def pick_prompt(repo_path: str) -> tuple[str, bool]:
    """
    Pick a prompt using priority queue logic:
    1. FEEDBACK.md first (refined/retry prompts)
    2. Fallback to README.md prompts

    Returns (prompt, is_retry)
    """
    feedback_prompts = read_feedback(repo_path)
    if feedback_prompts:
        prompt = feedback_prompts[0]
        consume_feedback(repo_path, prompt)
        print(f"Using FEEDBACK.md prompt (retry): {prompt[:80]}")
        return prompt, True

    readme_prompts = extract_prompts_from_readme(repo_path)
    if not readme_prompts:
        raise ValueError("No prompts found in FEEDBACK.md or README.md ## 🤖 Prompts section")

    import random
    prompt = random.choice(readme_prompts)
    print(f"Using README.md prompt (fresh): {prompt[:80]}")
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

    user_prompt = f"""Generate code for this feature request:

PROMPT: {prompt}
{retry_context}

CONFIG:
- Language: {config['language']}
- Style: {config['style']}
- Domain: {config['domain']}
- Test framework: {config['test_framework']}

Respond with this exact JSON structure:
{{
  "feature_name": "snake_case_name_max_5_words",
  "description": "One sentence description",
  "files": [
    {{
      "path": "generated/<feature_name>/main.py",
      "content": "# full file content here"
    }},
    {{
      "path": "generated/<feature_name>/test_main.py",
      "content": "# full test file content here"
    }}
  ]
}}"""

    response = call_ai(user_prompt, SYSTEM_PROMPT)

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
