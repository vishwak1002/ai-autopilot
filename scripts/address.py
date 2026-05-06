"""
address.py — Reads CodeRabbit's review, writes refined prompt to FEEDBACK.md, closes PR.

Usage (called by Workflow 3 when CodeRabbit requests changes):
  PR_NUMBER=42 TARGET_REPO=vishwak1002/my-ai-apps TARGET_REPO_PATH=./cloned python scripts/address.py
"""

import os
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import gh, write_feedback, set_output


def get_coderabbit_review(pr_number: str, repo: str) -> dict:
    """Fetch the latest CodeRabbit review from the PR."""
    output = gh("pr", "view", pr_number, "--repo", repo,
                "--json", "body,reviews,title,headRefName")
    data = json.loads(output)

    # Find CodeRabbit's review (submitted as a PR review, not a comment)
    reviews = data.get("reviews", [])
    coderabbit_reviews = [
        r for r in reviews
        if r.get("author", {}).get("login", "").lower() in ("coderabbitai[bot]", "coderabbitai")
    ]

    latest_review = coderabbit_reviews[-1] if coderabbit_reviews else {}
    return {
        "state": latest_review.get("state", "COMMENTED"),
        "body": latest_review.get("body", ""),
        "pr_title": data.get("title", ""),
        "branch": data.get("headRefName", ""),
    }


def extract_original_prompt(pr_body: str) -> str:
    """Extract the original prompt from the PR description."""
    match = re.search(r"\*\*Prompt Used:\*\*\s*(.+)", pr_body)
    if match:
        return match.group(1).strip()
    return "Unknown prompt"


def extract_issues_from_review(review_body: str) -> str:
    """Extract key issues from CodeRabbit's review body."""
    if not review_body:
        return "code quality issues flagged by CodeRabbit"

    # CodeRabbit structures reviews with sections — grab the actionable parts
    issues = []

    # Look for "Issues", "Problems", "Suggestions", "Changes requested" sections
    patterns = [
        r"(?:##?\s*(?:Issues?|Problems?|Changes? [Rr]equested|Actionable [Cc]omments?))(.*?)(?=##|\Z)",
        r"(?:❌|⚠️|🔴|🟡)\s*(.+)",
        r"\*\*(?:Issue|Problem|Error|Bug|Fix)\*\*[:\s]+(.+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, review_body, re.DOTALL)
        for match in matches:
            clean = re.sub(r'\s+', ' ', match.strip())[:200]
            if clean:
                issues.append(clean)

    if issues:
        return "; ".join(issues[:3])

    # Fallback — first 300 chars of review body as context
    clean_body = re.sub(r'\s+', ' ', review_body.strip())
    return clean_body[:300]


def get_pr_body(pr_number: str, repo: str) -> str:
    """Get the PR description body."""
    output = gh("pr", "view", pr_number, "--repo", repo, "--json", "body")
    return json.loads(output).get("body", "")


def close_pr_with_comment(pr_number: str, repo: str) -> None:
    """Close PR with explanation pointing to FEEDBACK.md."""
    comment = (
        "## 🔄 Autopilot: Queued for Improvement\n\n"
        "CodeRabbit has requested changes on this PR.\n\n"
        "The feedback has been extracted and a refined prompt written to `FEEDBACK.md`. "
        "The next Autopilot cycle will pick it up and generate an improved version.\n\n"
        "_No action needed — this will be retried automatically._"
    )
    gh("pr", "comment", pr_number, "--repo", repo, "--body", comment)
    gh("pr", "close", pr_number, "--repo", repo)
    print(f"Closed PR #{pr_number} — refined prompt written to FEEDBACK.md.")


if __name__ == "__main__":
    pr_number = os.environ["PR_NUMBER"]
    repo = os.environ["TARGET_REPO"]
    repo_path = os.environ.get("TARGET_REPO_PATH", ".")

    review = get_coderabbit_review(pr_number, repo)
    pr_body = get_pr_body(pr_number, repo)

    original_prompt = extract_original_prompt(pr_body)
    issues_summary = extract_issues_from_review(review["body"])

    print(f"PR #{pr_number} | CodeRabbit state: {review['state']}")
    print(f"Issues: {issues_summary[:100]}")

    write_feedback(repo_path, original_prompt, 0, issues_summary)
    close_pr_with_comment(pr_number, repo)

    set_output("feedback_written", "true")
    set_output("refined_prompt", f"[Retry] {original_prompt[:100]}")
