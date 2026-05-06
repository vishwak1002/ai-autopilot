# AI Autopilot — Design Spec

**Date:** 2026-05-06
**Status:** Approved
**Author:** vishwak1002

---

## Overview

`ai-autopilot` is a meta-repository that acts as an **autonomous code generation engine**. It reads prompts from target repositories, generates code via AI, opens PRs, reviews them, and either merges (score ≥ 8/10) or re-queues failed attempts via a `FEEDBACK.md` priority queue for the next cycle.

---

## Repository Roles

| Repo | Role |
|------|------|
| `ai-autopilot` | Engine only — scripts + 3 GitHub Actions workflows |
| Each target repo | Owns its own `.autopilot.yml` + `README.md` prompts + `FEEDBACK.md` queue |

### `ai-autopilot` Structure

```
ai-autopilot/
├── docs/superpowers/specs/
│   └── 2026-05-06-ai-autopilot-design.md
├── scripts/
│   ├── generate.py       # Reads prompts → generates code files
│   ├── review.py         # Reads PR diff → posts score + issues
│   ├── address.py        # Reads review issues → writes refined prompt to FEEDBACK.md
│   ├── merge.py          # Checks score → merges or closes PR
│   └── utils.py          # Shared: AI client (placeholder), GitHub API helpers
├── .github/workflows/
│   ├── 1-generate-code.yml
│   ├── 2-review-pr.yml
│   └── 3-address-and-merge.yml
├── requirements.txt
├── .env.example
└── README.md             # Lists registered target repos
```

### Target Repo Structure (per repo)

```
target-repo/
├── README.md          # Contains ## 🤖 Prompts section (backlog of ideas)
├── FEEDBACK.md        # Auto-generated: refined prompts from failed PRs (priority queue)
└── .autopilot.yml     # Config: language, style, domain, target_branch
```

---

## Workflows

### Workflow 1: Generate Code (`1-generate-code.yml`)

**Trigger:** Cron `0 */4 * * *` + manual dispatch

**Steps:**
1. Read list of registered target repos from `ai-autopilot/README.md`
2. For each target repo:
   - Clone target repo
   - **Check `FEEDBACK.md` first** — if refined prompts exist, pick oldest, remove it (consumed)
   - **Fallback:** If `FEEDBACK.md` empty, read `README.md` `## 🤖 Prompts` section, pick a prompt
   - Read `.autopilot.yml` for language/style/domain context
   - Call `generate.py` → AI generates code files
   - Push to branch: `ai-gen/<feature-name>-<timestamp>`
   - Open PR in target repo with label: `autopilot`

**Priority Queue Logic:**
```
FEEDBACK.md exists + has prompts?
  YES → consume oldest prompt → generate with failure context
  NO  → read README.md ## 🤖 Prompts → pick prompt → generate fresh
```

---

### Workflow 2: Review PR (`2-review-pr.yml`)

**Trigger:** `pull_request` (opened, synchronize) where label = `autopilot`

**Steps:**
1. Get PR diff via `gh pr diff`
2. Call `review.py` → AI reads diff → returns structured review
3. Post comment on PR containing:
   - Score badge (`Score: X/10`)
   - Issues list by severity: 🔴 high / 🟡 medium / 🟢 low
   - Improvement suggestions
   - Hidden machine-readable tag: `<!-- autopilot_score:X -->`

---

### Workflow 3: Address and Merge (`3-address-and-merge.yml`)

**Trigger:** `pull_request_review` submitted on `autopilot`-labeled PRs

**Steps:**
1. Extract score from PR comment hidden tag `<!-- autopilot_score:X -->`
2. **If score ≥ 8/10:**
   - Call `merge.py` → squash merge → delete branch ✅
3. **If score < 8/10:**
   - Call `address.py`:
     - Read review issues + original prompt from PR description
     - Write refined prompt to target repo's `FEEDBACK.md`:
       ```
       - [Retry] <original prompt> | Fix: <issues summary> (score: X/10)
       ```
   - Close PR with comment: *"Score X/10 below threshold (8/10). Refined prompt added to FEEDBACK.md for next cycle."*
   - Delete branch

---

## Scripts

### `utils.py` — Shared utilities
- `get_ai_client()` → Returns configured AI client (reads `AI_PROVIDER` env var — placeholder)
- `call_ai(prompt, system_prompt)` → Makes AI API call, returns text
- `read_feedback(repo_path)` → Parses `FEEDBACK.md`, returns list of prompts
- `consume_feedback(repo_path, prompt)` → Removes prompt from `FEEDBACK.md` after use
- `write_feedback(repo_path, prompt, score, issues)` → Appends refined prompt to `FEEDBACK.md`
- `load_autopilot_config(repo_path)` → Reads `.autopilot.yml`, returns dict

### `generate.py`
- Accepts: prompt text, `.autopilot.yml` config dict
- Calls AI with prompt + language/style/domain context
- Returns: list of `{path, content}` file objects
- Writes files to `generated/<feature-name>/` in target repo
- Outputs: `feature_name`, `description` to `GITHUB_OUTPUT`

### `review.py`
- Accepts: PR number, repo (via env vars)
- Gets diff via `gh pr diff <PR_NUMBER>`
- Calls AI with diff for structured review
- Posts formatted comment with hidden score tag
- Outputs: `review_score`, `ready_to_merge` to `GITHUB_OUTPUT`

### `address.py`
- Accepts: PR number, repo, original prompt (via env vars)
- Reads review comments, extracts issues list
- Writes refined prompt to target repo's `FEEDBACK.md`
- Outputs: `feedback_written=true`, `refined_prompt` to `GITHUB_OUTPUT`

### `merge.py`
- Accepts: PR number, repo, score (via env vars)
- If score ≥ 8: squash merge + delete branch
- If score < 8: close PR with explanation comment

---

## Configuration

### `.autopilot.yml` (per target repo)

```yaml
language: python          # Code language
style: functional         # functional | OOP | etc.
domain: ai-apps           # Context hint for AI generation
target_branch: main       # Branch to merge into
test_framework: pytest    # Test framework to use
```

### Required Secrets (set in `ai-autopilot` repo settings)

| Secret | Description |
|--------|-------------|
| `AI_API_KEY` | AI provider API key (placeholder — set your own) |
| `GH_PAT` | Personal Access Token with `repo` + `workflow` scopes |

### `.env.example`

```env
AI_PROVIDER=anthropic        # or openai — swap as needed
AI_API_KEY=your_key_here
AI_MODEL=your_model_here     # placeholder — set your preferred model
GH_PAT=your_pat_here
```

---

## Full Data Flow

```
Target README.md (idea backlog)
         ↓ fallback only
Target FEEDBACK.md (priority queue — failures first)
         ↓ consumed oldest prompt
Workflow 1: generate.py → new branch + PR opened in target repo
         ↓
Workflow 2: review.py → score posted as PR comment
         ↓
    Score ≥ 8? ──YES──→ Workflow 3: merge.py → squash merge ✅
         ↓ NO
    Workflow 3: address.py → write refined prompt to FEEDBACK.md
               → Close PR + delete branch
                         ↓
              Next Workflow 1 picks FEEDBACK.md first
              → Generates improved code with failure context
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| AI call fails | Workflow fails with clear error, no PR opened |
| Target repo unreachable | Skip that target, log warning, continue others |
| `FEEDBACK.md` malformed | Fall back to `README.md` prompts |
| PR creation fails | Log error, do not retry same cycle |
| Score tag missing from review | Default to score 0, trigger address flow |

---

## Design Principles Applied

- **Single Responsibility** — Each script does exactly one thing
- **Open/Closed** — Add new target repos by adding `.autopilot.yml` — zero engine changes
- **Separation of Concerns** — Engine (`ai-autopilot`) vs config (target repos)
- **No Infinite Loops** — Failed PRs become refined prompts, not retry cycles
- **Traceability** — `FEEDBACK.md` is a human-readable log of what failed and why
- **Extensible Targets** — Any repo with `.autopilot.yml` can be a target
