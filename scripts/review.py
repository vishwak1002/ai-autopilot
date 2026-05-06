"""
review.py — Reviews a PR diff via AI and posts a structured score comment.

Usage (called by Workflow 2):
  PR_NUMBER=42 TARGET_REPO=vishwak1002/my-ai-apps python scripts/review.py
"""

import os
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import call_ai, load_prompt, gh, set_output


def get_pr_diff(pr_number: str, repo: str) -> str:
    """Fetch the diff for a given PR."""
    diff = gh("pr", "diff", pr_number, "--repo", repo)
    if not diff:
        raise ValueError(f"Empty diff for PR #{pr_number} in {repo}")
    return diff


def review_diff(diff: str) -> dict:
    """Send diff to AI for review. Returns structured review dict."""
    prompt = load_prompt("review_user").format(diff=diff[:12000])
    response = call_ai(prompt, load_prompt("review_system"))

    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if not json_match:
        raise ValueError(f"AI review response was not valid JSON.\nResponse: {response[:500]}")

    return json.loads(json_match.group())


def format_review_comment(review: dict) -> str:
    """Format the review dict into a readable GitHub PR comment."""
    score = review.get("score", 0)
    score_bar = "🟢" if score >= 8 else ("🟡" if score >= 5 else "🔴")

    severity_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    issues_text = ""
    for issue in review.get("issues", []):
        icon = severity_icons.get(issue.get("severity", "low"), "⚪")
        issues_text += (
            f"\n{icon} **{issue.get('severity', '').upper()}**: {issue.get('description', '')}\n"
            f"   > 💡 {issue.get('suggestion', '')}\n"
        )

    positives_text = "\n".join(
        f"- ✅ {p}" for p in review.get("positive_aspects", [])
    )

    verdict = "✅ **Ready to merge**" if review.get("ready_to_merge") else "⚠️ **Changes needed before merge**"

    comment = f"""## 🤖 Autopilot Code Review

{score_bar} **Score: {score}/10** (merge threshold: 8/10)

### Summary
{review.get('summary', '')}

### Issues Found
{issues_text if issues_text else "_No issues found._"}

### Positive Aspects
{positives_text if positives_text else "_N/A_"}

### Verdict
{verdict}

---
<!-- autopilot_score:{score} -->"""

    return comment


def post_review_comment(pr_number: str, repo: str, comment: str) -> None:
    """Post the review comment on the PR."""
    gh("pr", "comment", pr_number, "--repo", repo, "--body", comment)
    print(f"Posted review comment on PR #{pr_number}")


if __name__ == "__main__":
    pr_number = os.environ["PR_NUMBER"]
    repo = os.environ["TARGET_REPO"]

    diff = get_pr_diff(pr_number, repo)
    review = review_diff(diff)
    comment = format_review_comment(review)
    post_review_comment(pr_number, repo, comment)

    score = review.get("score", 0)
    ready = review.get("ready_to_merge", False)

    print(f"\nReview complete — Score: {score}/10 | Ready: {ready}")
    set_output("review_score", str(score))
    set_output("ready_to_merge", str(ready).lower())
