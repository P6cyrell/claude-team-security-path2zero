---
name: team-security-path2zero
description: Build a per-team Path-to-Zero criticals plan and emit Arrive-branded PowerPoint + Word deliverables. Use when the user asks for "path to zero criticals" / "path-to-zero" / "path2zero" for a named team (BRM, hub-portal, api-first, publishing-af, etc.), or when reviewing critical security vulnerability remediation progress and asks for leadership comms. Pulls live counts from the security-insights MCP, fans out per-cluster investigations to parallel sub-agents, synthesizes a structured plan.json, and renders the deck (PPTX) + leadership update (DOCX) into <cwd>/path-to-zero-plan/. Supports portfolio mode for cross-team rollup.
---

# team-security-path2zero

Generate a per-team Path-to-Zero plan for critical security vulnerabilities and emit Arrive-branded PowerPoint and Word deliverables.

## Trigger phrases

- "path to zero criticals for `<team>`"
- "do the path-to-zero for `<team>`"
- "build the path2zero plan for `<team>`"
- "same process for `<team>`" (when the prior turn was a path-to-zero run)
- with `--portfolio`: cross-team rollup of all four City Experience teams

## Outputs

Files land in `<cwd>/path-to-zero-plan/`:

- `<team>-Path-to-Zero-<YYYY-MM-DD>.pptx` — 10-slide leadership deck
- `<team>-Security-Leadership-Update-<YYYY-MM-DD>.docx` — long-form leadership update
- `<team>-Path-to-Zero-Burndown-<YYYY-MM-DD>.png` — embedded chart (also referenced from both files above)
- `<team>-advisory/plan.json` — structured source of truth
- `<team>-advisory/agents/NN-<topic>.md` — per-cluster technical advisories (research artifacts)

Portfolio mode additionally produces consolidated City-Experience-* deliverables and refreshes `CITYS-EXPERIENCE-SECURITY-GANTT.html`.

## Workflow

### Phase 0 — Preflight
- Resolve team scope from `~/.claude/shared/team-repos.json` (suggest `/team-repo-sync` if stale).
- Cross-check ownership via each repo's `catalog-info.yaml` `spec.owner`.
- `mcp__security-insights__health_check`; if 401, prompt for Bearer + cookie from portfolio.arrive.com DevTools and call `setup`.
- If `<team>-advisory/plan.json` from earlier today exists, ask: reuse / refresh / start fresh.

### Phase 1 — Data pull (sub-agent: `data-fetcher`)
- Paginate `get_security_issues` for severity=Critical to `<team>-advisory/_raw/issues-<date>.json`.
- Call `get_top_assets`, `get_resolving_trends`, `get_mttr_metrics`, `get_sla_metrics`; mark which `/reports/*` endpoints fail.
- Compute `_facts/concentration.json` (repo → critical count, %).
- **Returns to main (≤80 words):** total count, top-3 repos, working endpoints. Never raw issues.

### Phase 2 — Cluster derivation (orchestrator)
Read `concentration.json`, derive 3–6 data-driven clusters by repo affinity + vuln family. Write `_facts/clusters.json`.

### Phase 3 — Repo cache prime (sub-agent: `repo-primer`)
Shallow-clone the union of repos any cluster needs into `_shared/repo-cache/`. Eliminates duplicate clones across cluster sub-agents.

### Phase 4 — Cluster investigation (parallel sub-agents)
Spawn one sub-agent per cluster (single message, multiple Agent calls). Each:
- Reads its cluster spec + repo cache.
- Loads its full prompt from `prompts/cluster-investigation.md` (orchestrator never sees the prompt).
- Investigates reachability, writes advisory to `agents/NN-<topic>.md`.
- **Returns to main (≤60 words):** structured JSON — cluster ID, fix family (A/B/C), target close date, blocked-by tickets, confidence.

Token-refresh checkpoint after Phase 4: run `health_check` again; prompt for refresh if 401.

### Phase 5 — Synthesis (sub-agent: `synthesizer`)
- Reads all advisories from disk + optional team-lead update (PDF / Slack paste / Jira comment).
- Writes `<team>-advisory/plan.json` against `schemas/plan.schema.json` (schema_version: 1).
- Generates the burndown PNG via `builders/build_burndown.py` (matplotlib, 3-line spec per memory `feedback_burndown-include-original-plan`).

### Phase 6 — Render deliverables
```
python3 builders/render.py <team>-advisory/plan.json
```
Emits the PPTX + DOCX into `<cwd>/path-to-zero-plan/`. Pure file emission, no LLM tokens.

### Phase 7 — Portfolio rollup (only with `--portfolio`)
After per-team pipelines complete in parallel, spawn `portfolio-roller` sub-agent for consolidated burndown, City-Experience leadership doc/deck, and Gantt regeneration per memory `reference_gantt-chart-process`.

## Hard rules (lessons baked in)

1. **Criticals only**, not highs (unless `--include-highs` is passed).
2. **Portfolio counts are source of truth** — if security-insights says N criticals and cluster analysis suggests N+M, the portfolio number wins.
3. **Arrive branding via the bundled templates** in `templates/` — never re-style.
4. **Burndown has 3 lines**: actual (solid purple) / original plan baseline (dotted gray, locked at original-plan date) / current forecast (dashed pink).
5. **Output dir is `<cwd>/path-to-zero-plan/`** per memory `feedback_path-to-zero-deliverables-folder`, never `~/Downloads`.
6. **Repo ownership** via `catalog-info.yaml` `spec.owner`, per memory `reference_repo-ownership-catalog-info`.
7. **Confluence tables** (if any get published) use `data-layout="full-width"` per memory `feedback_confluence-table-width`.

## Resume semantics

If a cluster sub-agent fails or the auth token expires mid-run, the orchestrator records partial state in `_facts/existing-advisories.json`. A re-run picks up incomplete clusters only — completed advisories are not re-investigated.

## Capacity limits

The current templates pre-allocate: 5 surface rows / 3 dep regions / 3 epics / 5 reallocations / 7 timeline rows / 4 asks. To extend, edit `builders/build_template_*.py`, re-run, and re-render. See `README.md` for details.

## Dependencies

```
pip install python-pptx python-docx matplotlib jsonschema
```

The `mcp__security-insights__*` tools must be available; otherwise Phase 1 falls back to a manual paste of the critical-count + top-assets data.
