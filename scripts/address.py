"""
address.py — Reads review issues from a PR, writes refined prompt to FEEDBACK.md,
             then closes the PR.

Usage (called by Workflow 3 when score < 8):
  PR_NUMBER=42 TARGET_REPO=vishwak1002/my-ai-apps TARGET_REPO_PATH=./cloned python scripts/address.py
"""

import os
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import call_ai, gh, write_feedback, set_output


def get_pr_details(pr_number: str, repo: str) -> dict:
    """Fetch PR body and comments."""
    import json

    output = gh("pr", "view", pr_number, "--repo", repo, "--json", "body,comments,title")
    return json.loads(output)


def extract_original_prompt(pr_body: str) -> str:
    """Extract the original prompt from the PR description."""
    match = re.search(r"\*\*Prompt Used:\*\*\s*(.+)", pr_body)
    if match:
        return match.group(1).strip()
    return "Unknown prompt"


def extract_score_and_issues(comments: list) -> tuple[int, str]:
    """
    Parse the AI review comment to get score and issues summary.
    Returns (score, issues_summary).
    """
    for comment in reversed(comments):
        body = comment.get("body", "")
        if "<!-- autopilot_score:" in body:
            # Extract score
            score_match = re.search(r"<!-- autopilot_score:(\d+) -->", body)
            score = int(score_match.group(1)) if score_match else 0

            # Extract issues
            issues = re.findall(
                r"(?:🔴|🟡|🟢)\s+\*\*(?:HIGH|MEDIUM|LOW)\*\*:\s+(.+)",
                body
            )
            issues_summary = "; ".join(issues[:3]) if issues else "code quality below threshold"

            return score, issues_summary

    return 0, "review score not found"


def close_pr_with_comment(pr_number: str, repo: str, score: int) -> None:
    """Close PR with explanation and feedback link."""
    comment = (
        f"## 🔄 Autopilot: Queued for Improvement\n\n"
        f"Score **{score}/10** is below the merge threshold of **8/10**.\n\n"
        f"The issues have been extracted and a refined prompt has been written to "
        f"`FEEDBACK.md` in this repo. The next Autopilot cycle will pick it up and "
        f"generate an improved version.\n\n"
        f"_No action needed — this will be retried automatically._"
    )
    gh("pr", "comment", pr_number, "--repo", repo, "--body", comment)
    gh("pr", "close", pr_number, "--repo", repo)
    print(f"Closed PR #{pr_number} with feedback comment.")


if __name__ == "__main__":
    pr_number = os.environ["PR_NUMBER"]
    repo = os.environ["TARGET_REPO"]
    repo_path = os.environ.get("TARGET_REPO_PATH", ".")

    pr = get_pr_details(pr_number, repo)
    original_prompt = extract_original_prompt(pr.get("body", ""))
    score, issues_summary = extract_score_and_issues(pr.get("comments", []))

    print(f"PR #{pr_number} | Score: {score}/10 | Issues: {issues_summary}")

    write_feedback(repo_path, original_prompt, score, issues_summary)
    close_pr_with_comment(pr_number, repo, score)

    set_output("feedback_written", "true")
    set_output("refined_prompt", f"[Retry] {original_prompt[:100]}")
    set_output("score", str(score))
