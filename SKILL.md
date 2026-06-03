---
name: team-security-path2zero
description: Build a per-team Path-to-Zero criticals plan and emit Arrive-branded PowerPoint + Word deliverables. Use when the user asks for "path to zero criticals" / "path-to-zero" / "path2zero" for a named team (BRM, hub-portal, api-first, publishing-af, etc.), or when reviewing critical security vulnerability remediation progress and asks for leadership comms. Pulls live counts from the security-insights MCP, fans out per-cluster investigations to parallel sub-agents, synthesizes a structured plan.json, and renders the deck (PPTX) + leadership update (DOCX) into <cwd>/path-to-zero-plan/. Supports portfolio mode for cross-team rollup.
---

# team-security-path2zero — orchestrator runbook

You are the orchestrator. When the user invokes `/team-security-path2zero`, you follow this runbook to produce the per-team (or cross-team portfolio) deliverables. Sub-agents do the heavy work; you maintain state, fan them out, and chain the deterministic helpers.

## Invocation

```
/team-security-path2zero <team>                       # single-team run
/team-security-path2zero <team> --as-of 2026-05-22    # historical snapshot
/team-security-path2zero <team> --resume              # resume from last completed phase
/team-security-path2zero --portfolio                  # cross-team rollup (all 4 City Experience teams)
/team-security-path2zero <team> --include-highs       # rarely needed; criticals only by default
```

If the user types only `/team-security-path2zero` with no team, ask which team in scope (default list: BRM, hub-portal, api-first, publishing-af). Do not guess.

## Working dir layout (the orchestrator creates this on first run)

```
<cwd>/path-to-zero-plan/<team>-advisory/
├── state.json                  # progress + resume tracking
├── _raw/                       # security-insights API dumps (data-fetcher writes)
├── _facts/                     # concentration.json, clusters.json, prime-report.json
├── _shared/repo-cache/<team>/  # shallow clones, populated by Phase 3
├── agents/                     # NN-<slug>.md advisories from Phase 4
├── plan.json                   # synthesized in Phase 5
└── burndown.png                # rendered in Phase 5
```

Final deliverables land **one level up**, in `<cwd>/path-to-zero-plan/`:

- `<team>-Path-to-Zero-<YYYY-MM-DD>.pptx`
- `<team>-Security-Leadership-Update-<YYYY-MM-DD>.docx`

---

# Phase 0 — Preflight

Run these checks in order. Stop and ask the user if any decision is required.

**0.1 — Resolve the team.** Accept the team-name argument or ask. Map it to the entry in `~/.claude/shared/team-repos.json` (case-insensitive). If the team isn't in `team-repos.json`, tell the user to run `/team-repo-sync` first.

**0.2 — Resolve `AS_OF_DATE`.** Default = today (`date +%Y-%m-%d`). Override with `--as-of`.

**0.3 — Compute paths.** Set `WORK_DIR=<cwd>/path-to-zero-plan/<team>-advisory/` and `OUT_DIR=<cwd>/path-to-zero-plan/`. Create `WORK_DIR/_raw`, `WORK_DIR/_facts`, `WORK_DIR/agents`, `WORK_DIR/_shared/repo-cache/<team>` if missing.

**0.4 — Detect prior run.** If `WORK_DIR/state.json` exists:

```bash
python3 <SKILL>/builders/state.py show --work-dir <WORK_DIR>
```

If it shows partial progress and the user passed `--resume`, jump to the resume point (`state.py resume-point`). Otherwise ask: **reuse / refresh / start fresh**.

- *reuse* → skip the pipeline, just re-render from the existing `plan.json` (jump to Phase 6).
- *refresh* → keep `state.json` but bump `as_of_date`; re-run from Phase 1.
- *start fresh* → delete `WORK_DIR` and re-init.

If no `state.json` exists, init:

```bash
python3 <SKILL>/builders/state.py init \
  --work-dir <WORK_DIR> --team <team> --as-of <AS_OF_DATE>
```

**0.5 — Auth check.** Call `mcp__security-insights__health_check`. If 401, prompt the user for Bearer + cookie from `portfolio.arrive.com` DevTools (Network tab → any request → Headers). When you receive them, call `mcp__security-insights__setup` with the values.

**0.6 — Memory check.** Recall any active memory for this team:
- `project_brm-context.md` / `project_hub-portal-context.md` / `project_api-first-context.md` / `project_publishing-af-remediation.md`

Memory may have specific counts, named owners, or in-flight ticket IDs that should flow into Phase 5 synthesis. Don't act on them now — just be ready to surface to the synthesizer sub-agent.

**Mark phase 0 done:**

```bash
python3 <SKILL>/builders/state.py set-phase \
  --work-dir <WORK_DIR> --phase 0_preflight --status done
```

---

# Phase 1 — Data-fetcher (sub-agent)

Launch the data-fetcher sub-agent with the prompt loaded from `<SKILL>/prompts/data-fetcher.md`. Pass team-specific inputs as a single message:

```
Agent(
  description: "data-fetcher for <team> as of <AS_OF_DATE>",
  subagent_type: "general-purpose",
  prompt: <contents of prompts/data-fetcher.md, then append:>

  TEAM=<team>
  AS_OF_DATE=<AS_OF_DATE>
  RAW_DIR=<WORK_DIR>/_raw
  FACTS_DIR=<WORK_DIR>/_facts
  COMPUTE_CONCENTRATION_PY=<SKILL>/builders/compute_concentration.py
  VALIDATE_CONCENTRATION_PY=<SKILL>/builders/validate_concentration.py
)
```

Mark `1_data_fetcher` in_progress before launching, done on success, failed on error. On failure, surface the sub-agent's error and ask the user to retry or skip (e.g. manual paste-in of the count).

**What you keep in main context after Phase 1:**
- Total critical count
- Top 3 repos with % of total
- Working / failed endpoints

Discard everything else — the raw issues stay on disk.

---

# Phase 2 — Cluster derivation (no sub-agent)

```bash
python3 <SKILL>/builders/derive_clusters.py \
  --concentration   <WORK_DIR>/_facts/concentration.json \
  --issues          <WORK_DIR>/_raw/issues-<AS_OF_DATE>.json \
  --repo-cache-root <WORK_DIR>/_shared/repo-cache/<team> \
  --out             <WORK_DIR>/_facts/clusters.json

python3 <SKILL>/builders/validate_clusters.py <WORK_DIR>/_facts/clusters.json
```

If validation fails, report errors verbatim and stop. The likely cause is concentration data drift.

**Review the cluster output before fan-out.** Print the derived cluster names + cve_counts to the user and ask: *"Fan out N parallel sub-agents to investigate these clusters? Or edit clusters.json first?"* This is the one human-in-the-loop checkpoint — clusters with bad names produce hard-to-read advisories.

Mark phase done.

---

# Phase 3 — Repo cache prime (no sub-agent)

```bash
python3 <SKILL>/builders/prime_repo_cache.py \
  --clusters <WORK_DIR>/_facts/clusters.json \
  --report   <WORK_DIR>/_facts/prime-report.json
```

The script clones the union of repos referenced by all clusters. Idempotent — existing clones get `git fetch && git pull --ff-only`.

**If `prime-report.json` shows any `unresolved` repos**, surface them to the user. Most likely a stale `team-repos.json` — suggest `/team-repo-sync`. Continue with the resolved repos (Phase 4 sub-agents handle missing repos gracefully).

Mark phase done.

---

# Phase 4 — Cluster investigation (parallel sub-agents)

**Token-refresh checkpoint.** Run `mcp__security-insights__health_check` again. If 401, prompt for fresh credentials before launching.

Read `<WORK_DIR>/_facts/clusters.json` to get the N clusters (1–6). For each cluster, prepare:

```
Agent(
  description: "Cluster <NN> — <cluster.name>",
  subagent_type: "general-purpose",
  prompt: <contents of prompts/cluster-investigation.md, then append:>

  CLUSTERS_JSON=<WORK_DIR>/_facts/clusters.json
  CLUSTER_ID=<NN>
  REPO_CACHE_ROOT=<WORK_DIR>/_shared/repo-cache/<team>
  OPEN_VULNS_JSON=<WORK_DIR>/_raw/open-vulnerabilities-<AS_OF_DATE>.json
  OUT_ADVISORY=<WORK_DIR>/agents/<NN>-<slug>.md
)
```

**Fan them out in a single message — multiple `Agent` tool calls in one assistant turn.** This is the parallelism point. With N=6 clusters, you launch 6 sub-agents at once. Wait for all to return.

For each sub-agent return:

```bash
python3 <SKILL>/builders/state.py set-advisory \
  --work-dir <WORK_DIR> --cluster-id <NN> --status done \
  --fix-family <A|B|C> --target-close-date <YYYY-MM-DD>
```

On any sub-agent failure, mark that advisory `failed` with the error. **Do not abort the run.** Phase 5 reads what's on disk — partial completion is fine for a v1 draft. Surface the gap in the final deliverable's "Risks / unknowns" section.

**Validate advisories before synthesis:**

```bash
python3 <SKILL>/builders/validate_advisories.py \
  <WORK_DIR>/agents/ \
  --clusters <WORK_DIR>/_facts/clusters.json
```

If a sub-agent wrote a malformed advisory, re-launch just that one sub-agent with explicit feedback on what was wrong.

Mark `4_investigation` done.

---

# Phase 5 — Synthesis (sub-agent)

If the user provided a team-lead update (Slack paste, Gemini transcript PDF, Jira comment), save it to `<WORK_DIR>/team-lead-update.{txt,pdf,md}` first. The synthesizer will mine it for structured facts.

Determine `BASELINE_DATE` — the original plan-of-record date for the team. Typically `2026-05-19` for the City Experience teams (per memory). If a prior `plan.json` exists with `burndown_series.baseline_date`, copy that value.

Launch:

```
Agent(
  description: "synthesizer for <team> as of <AS_OF_DATE>",
  subagent_type: "general-purpose",
  prompt: <contents of prompts/synthesizer.md, then append:>

  ADVISORY_DIR=<WORK_DIR>/agents
  CONCENTRATION_JSON=<WORK_DIR>/_facts/concentration.json
  OPEN_VULNS_JSON=<WORK_DIR>/_raw/open-vulnerabilities-<AS_OF_DATE>.json
  OUT_PLAN_JSON=<WORK_DIR>/plan.json
  BURNDOWN_PNG_OUT=<WORK_DIR>/burndown.png
  BASELINE_DATE=<BASELINE_DATE>
  TEAM_LEAD_UPDATE=<path if provided, else omit>
  PRIOR_PLAN_JSON=<path if exists, else omit>
)
```

The synthesizer runs `validate_plan.py` and `build_burndown.py` itself. On return, sanity-check the values:

```bash
python3 <SKILL>/builders/validate_plan.py <WORK_DIR>/plan.json
```

Mark phase done.

---

# Phase 6 — Render (no sub-agent)

```bash
python3 <SKILL>/builders/render.py \
  <WORK_DIR>/plan.json \
  --out-dir <OUT_DIR>
```

Emits:
- `<OUT_DIR>/<team>-Path-to-Zero-<AS_OF_DATE>.pptx`
- `<OUT_DIR>/<team>-Security-Leadership-Update-<AS_OF_DATE>.docx`

Mark phase done. Print the file paths to the user.

---

# Phase 7 — Portfolio rollup (only if `--portfolio` was passed)

This runs after per-team pipelines complete. For portfolio mode, the runbook differs:

**Option A — fresh portfolio run:** fan out 4 per-team sub-agents in parallel, each running the full Phases 0–6 pipeline above (in its own sub-context). Wait for all 4. Then proceed.

**Option B — rollup of existing per-team runs:** look for `<cwd>/path-to-zero-plan/<team>-advisory/plan.json` for each team. If all 4 exist with matching `as_of_date`, skip directly to the roller.

Then launch the portfolio-roller:

```
Agent(
  description: "portfolio rollup for City Experience as of <AS_OF_DATE>",
  subagent_type: "general-purpose",
  prompt: <contents of prompts/portfolio-roller.md, then append:>

  TEAM_PLANS=<comma-separated paths>
  TEAM_BURNDOWNS=<comma-separated paths>
  OUT_DIR=<OUT_DIR>
  PORTFOLIO_NAME=City Experience
  AS_OF_DATE=<AS_OF_DATE>
  BUILDER_DIR=<SKILL>/builders
)
```

Mark phase done.

---

# Resume semantics

If a phase fails or the user interrupts, the next `/team-security-path2zero <team> --resume` jumps to the first phase whose status isn't `done` or `skipped`:

```bash
RESUME_AT=$(python3 <SKILL>/builders/state.py resume-point --work-dir <WORK_DIR>)
```

Phase 4 resume is finer-grained: only re-launch sub-agents whose advisory state isn't `done`. The other completed advisories on disk are reused.

---

# Hard rules (lessons baked in)

1. **Criticals only.** Highs only enter the plan via `remaining_surface.high_count` as context. The headline numbers are critical-only.
2. **Portfolio counts are source of truth.** If `get_open_vulnerabilities` says N and cluster sums say N+M, the API wins. The sub-agents may double-count.
3. **Arrive branding via the bundled templates** in `templates/`. Don't re-style at render time.
4. **Burndown has 3 lines.** Actual (solid purple), original-plan baseline (dotted gray, locked at `baseline_date`), current forecast (dashed pink). Per memory `feedback_burndown-include-original-plan`.
5. **Output dir is `<cwd>/path-to-zero-plan/`** per memory `feedback_path-to-zero-deliverables-folder`. Never `~/Downloads`.
6. **Repo ownership via `catalog-info.yaml`** `spec.owner`, per memory `reference_repo-ownership-catalog-info`. Cross-check `team-repos.json` against this if a repo seems mis-assigned.
7. **Confluence tables** (if any get published downstream) use `data-layout="full-width"` per memory `feedback_confluence-table-width`.
8. **No prose from sub-agents to the orchestrator.** Each sub-agent returns ≤80 words of structured JSON. Raw artifacts stay on disk.

---

# Sub-agent inventory

| Phase | Sub-agent | Prompt file | Inputs | Output | Return budget |
|---|---|---|---|---|---|
| 1 | data-fetcher | `prompts/data-fetcher.md` | TEAM, AS_OF_DATE, dirs | `_raw/*.json`, `concentration.json` | ≤80 words |
| 4 | cluster-investigator (×N) | `prompts/cluster-investigation.md` | one cluster + repo cache | `agents/NN-*.md` | ≤60 words |
| 5 | synthesizer | `prompts/synthesizer.md` | advisories + concentration | `plan.json` + burndown.png | ≤80 words |
| 7 | portfolio-roller | `prompts/portfolio-roller.md` | per-team plans + burndowns | consolidated DOCX/PPTX/Gantt | ≤80 words |

---

# Helpers inventory

| Script | Use |
|---|---|
| `state.py` | init / show / set-phase / set-advisory / resume-point |
| `compute_concentration.py` | issues.json → concentration.json (Phase 1) |
| `validate_concentration.py` | schema + sum-reconciliation check |
| `derive_clusters.py` | concentration → clusters.json (Phase 2) |
| `validate_clusters.py` | schema + repo-uniqueness check |
| `prime_repo_cache.py` | clusters.json → populated repo cache (Phase 3) |
| `validate_advisories.py` | per-file YAML frontmatter validation + cluster cross-check |
| `validate_plan.py` | schema + semantic reconciliation (today, peak, surface sum, forecast→0) |
| `build_burndown.py` | plan.json → 3-line burndown PNG |
| `render.py` | plan.json → PPTX + DOCX |
| `build_template_pptx.py` / `build_template_docx.py` | rebuild brand templates (run after brand changes) |

---

# Dependencies

```
pip install python-pptx python-docx matplotlib jsonschema pyyaml
```

`~/.claude/shared/team-repos.json` must exist (`/team-repo-sync` generates it). Phase 3 fails actionable if missing.

The `mcp__security-insights__*` tools must be available. If they aren't (e.g. running offline), Phase 1 can be skipped by manually placing `concentration.json` + `issues.json` in `_raw`/`_facts` and starting at Phase 2 via `--resume`.

---

# Failure modes the orchestrator handles

- **Sub-agent crash** → mark its phase failed, surface the error, ask retry/skip.
- **Auth token expiry mid-run** → caught by the Phase 4 token-refresh checkpoint; user re-pastes credentials, run continues.
- **Cluster sub-agent produces malformed advisory** → caught by `validate_advisories.py`; re-launch just that one sub-agent with feedback.
- **plan.json fails validation** → synthesizer self-iterates; orchestrator double-checks before render.
- **Unresolved repo (not in team-repos.json)** → Phase 3 surfaces it; orchestrator continues with what was primed; Phase 4 sub-agents skip missing repos.
- **`/reports/*` endpoints 500** → expected; recorded in `endpoint-status.json`; pipeline proceeds.
