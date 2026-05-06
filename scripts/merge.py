"""
merge.py — Merges a PR if score >= 8, otherwise delegates to address.py.

Usage (called by Workflow 3):
  PR_NUMBER=42 TARGET_REPO=vishwak1002/my-ai-apps REVIEW_SCORE=9 python scripts/merge.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import gh, set_output

MERGE_THRESHOLD = int(os.environ.get("MERGE_THRESHOLD", "8"))


def merge_pr(pr_number: str, repo: str, score: int) -> None:
    """Squash merge the PR and delete the branch."""
    print(f"Score {score}/10 >= {MERGE_THRESHOLD} — merging PR #{pr_number}")

    gh(
        "pr", "merge", pr_number,
        "--repo", repo,
        "--squash",
        "--delete-branch",
        "--subject", f"🤖 Autopilot merge: AI Generated Feature (Score: {score}/10)"
    )
    print(f"✅ Merged PR #{pr_number} into main.")
    set_output("merged", "true")
    set_output("score", str(score))


def skip_merge(pr_number: str, score: int) -> None:
    """Score too low — address.py will handle it."""
    print(f"Score {score}/10 < {MERGE_THRESHOLD} — delegating to address.py")
    set_output("merged", "false")
    set_output("score", str(score))


if __name__ == "__main__":
    pr_number = os.environ["PR_NUMBER"]
    repo = os.environ["TARGET_REPO"]
    score = int(os.environ.get("REVIEW_SCORE", "0"))

    if score >= MERGE_THRESHOLD:
        merge_pr(pr_number, repo, score)
    else:
        skip_merge(pr_number, score)
