# 🤖 AI Autopilot

An autonomous code generation engine. Every 4 hours it reads prompts from your target repos, generates production-ready code via AI, opens a PR, reviews it, and either merges (score ≥ 8/10) or re-queues it for improvement — all without manual intervention.

## How It Works

```
FEEDBACK.md (priority queue — retries first)
       ↓ fallback
README.md ## 🤖 Prompts (idea backlog)
       ↓
Workflow 1: Generate code → open PR in target repo
       ↓
Workflow 2: AI reviews PR → posts score (1–10)
       ↓
Score ≥ 8 ──→ Workflow 3: Merge ✅
Score < 8 ──→ Workflow 3: Write refined prompt to FEEDBACK.md → close PR
                    ↓
         Next cycle picks FEEDBACK.md first → retry with context
```

## 🎯 Target Repos

Add your repos below — one per line. Each repo needs a `.autopilot.yml` file.

- vishwak1002/my-ai-apps
- vishwak1002/india-stock-analysis
- vishwak1002/voice-agents
- vishwak1002/my-gym-apps
- vishwak1002/myAIClone

## Setup

### 1. Add Secrets to this repo (`ai-autopilot`)

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `AI_API_KEY` | Your AI provider API key |
| `GH_PAT` | GitHub Personal Access Token (`repo` + `workflow` scopes) |

### 2. Add Variables (optional overrides)

| Variable | Default | Options |
|----------|---------|---------|
| `AI_PROVIDER` | `anthropic` | `anthropic`, `openai` |
| `AI_MODEL` | `claude-opus-4-5` | Any model name |

### 3. Add `.autopilot.yml` to each target repo

Copy the template from `.autopilot.yml.example` into each target repo and customise it.

### 4. Add `## 🤖 Prompts` section to each target repo's README

```markdown
## 🤖 Prompts

- Build a real-time stock price fetcher for NSE using websockets
- Create a portfolio tracker with P&L calculations
- Add a candlestick chart generator using matplotlib
```

### 5. Enable the `autopilot` label in each target repo

```bash
gh label create autopilot --color "7057ff" --description "AI Autopilot generated PR" --repo vishwak1002/my-ai-apps
```

### 6. Add Workflows 2 & 3 to each target repo

Workflows 2 and 3 need to live in each target repo (they trigger on PR events in that repo).
Copy `.github/workflows/2-review-pr.yml` and `.github/workflows/3-address-and-merge.yml`
into each target repo's `.github/workflows/` directory.

---

## Project Structure

```
ai-autopilot/
├── scripts/
│   ├── generate.py       # Reads prompts → generates code
│   ├── review.py         # Reviews PR diff → posts score
│   ├── address.py        # Extracts issues → writes FEEDBACK.md → closes PR
│   ├── merge.py          # Merges if score ≥ 8
│   └── utils.py          # Shared: AI client, GitHub helpers, FEEDBACK.md I/O
├── .github/workflows/
│   ├── 1-generate-code.yml     # Cron every 4h
│   ├── 2-review-pr.yml         # On PR open/update
│   └── 3-address-and-merge.yml # On PR review submitted
├── docs/superpowers/specs/
│   └── 2026-05-06-ai-autopilot-design.md
├── .autopilot.yml.example
├── requirements.txt
└── .env.example
```

## Design Principles

- **Single Responsibility** — Each script does exactly one thing
- **Open/Closed** — Add targets by adding `.autopilot.yml` — no engine changes
- **No Infinite Loops** — Failed PRs → `FEEDBACK.md` → fresh retry next cycle
- **Traceability** — `FEEDBACK.md` is a human-readable log of failures and why
- **AI Provider Agnostic** — Swap `AI_PROVIDER` env var to switch providers
