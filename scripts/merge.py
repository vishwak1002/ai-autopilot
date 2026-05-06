"""
merge.py — Merges a PR if CodeRabbit approved it.

Usage (called by Workflow 3):
  PR_NUMBER=42 TARGET_REPO=vishwak1002/my-ai-apps REVIEW_STATE=APPROVED python scripts/merge.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import gh, set_output


def merge_pr(pr_number: str, repo: str) -> None:
    """Squash merge the PR and delete the branch."""
    print(f"CodeRabbit approved PR #{pr_number} — merging")
    gh(
        "pr", "merge", pr_number,
        "--repo", repo,
        "--squash",
        "--delete-branch",
        "--subject", f"🤖 Autopilot merge: AI Generated Feature (approved by CodeRabbit)"
    )
    print(f"✅ Merged PR #{pr_number} into main.")
    set_output("merged", "true")


def skip_merge(pr_number: str, state: str) -> None:
    """Changes requested — address.py will handle it."""
    print(f"CodeRabbit state '{state}' — delegating to address.py")
    set_output("merged", "false")


if __name__ == "__main__":
    pr_number = os.environ["PR_NUMBER"]
    repo = os.environ["TARGET_REPO"]
    review_state = os.environ.get("REVIEW_STATE", "COMMENTED").upper()

    if review_state == "APPROVED":
        merge_pr(pr_number, repo)
    else:
        skip_merge(pr_number, review_state)
