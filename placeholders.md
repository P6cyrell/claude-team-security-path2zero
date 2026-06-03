# Placeholder tokens

Canonical list of `{{tokens}}` baked into the Slides + Docs templates. The renderer fills these via `replaceAllText` batchUpdate. Names use `SCREAMING_SNAKE_CASE` so they're unmistakable in the template.

Token names match keys in `plan.json` (see `schemas/plan.schema.json`).

## Title slide (slide 1) / Doc cover

| Token                          | Source in plan.json                |
|--------------------------------|------------------------------------|
| `{{TEAM_NAME}}`                | `team`                             |
| `{{AS_OF_DATE}}`               | `as_of_date`                       |
| `{{ENGINEERING_LEAD}}`         | `engineering_lead`                 |
| `{{EPIC_LIST}}`                | derived from `epics[]` (joined)    |

## Executive Summary (slide 2 / Doc §1)

| Token                          | Source                              |
|--------------------------------|-------------------------------------|
| `{{STAT_PEAK}}`                | `exec_summary.peak`                 |
| `{{STAT_TODAY}}`               | `exec_summary.today`                |
| `{{STAT_SERVICES_WITH_CRITS}}` | `exec_summary.services_with_criticals` |
| `{{STAT_SERVICES_AFTER}}`      | `exec_summary.services_after_eod`   |
| `{{HEADLINE_BULLETS}}`         | `exec_summary.headline_bullets[]`   |

## Burndown (slide 3 / Doc §2)

Burndown image is inserted into a named shape on slide 3 and at a bookmark in the Doc. The shape name in the Slides template is `BURNDOWN_PLACEHOLDER`; in Docs it is the bookmark `burndown`.

## Remaining attack surface (slide 4 / Doc §3)

`{{REMAINING_SURFACE_TABLE}}` is replaced by inserting rows into a table object. Each row from `remaining_surface[]`: repo, critical, high, status.

## Dependency status (slide 5 / Doc §4)

| Token                       | Source                          |
|-----------------------------|---------------------------------|
| `{{DEP_GRID_TITLE}}`        | `dependency_grid.title`         |
| `{{DEP_GRID_NARRATIVE}}`    | `dependency_grid.narrative`     |
| `{{DEP_GRID_REGIONS}}`      | `dependency_grid.regions[]`     |

## Critical-path deep dive (slide 6 / Doc §5)

| Token                          | Source                                  |
|--------------------------------|-----------------------------------------|
| `{{CP_SERVICE}}`               | `critical_path_deep_dive.service`       |
| `{{CP_STAT_LINE}}`             | `critical_path_deep_dive.stat_line`     |
| `{{CP_RATIONALE_BULLETS}}`     | `critical_path_deep_dive.rationale_bullets[]` |

## Q2 epic structure (slide 7 / Doc §6)

`{{EPIC_STATUS_TABLE}}` — rows from `epic_status[]`: id, state, summary.

## Resource reallocation (slide 8 / Doc §7)

`{{REALLOCATION_TABLE}}` — rows from `resource_reallocation[]`: engineer, from, to.

## Updated Timeline to Zero (slide 9 / Doc §8)

`{{TIMELINE_TABLE}}` — rows from `timeline[]`: date, milestone, open_criticals.

## Asks of Security leadership (slide 10 / Doc §9)

`{{ASKS_LIST}}` — items from `asks[]`: num, title, body.

## Footer (every slide)

| Token                 | Source                          |
|-----------------------|---------------------------------|
| `{{FOOTER_TEAM}}`     | `team`                          |
| `{{FOOTER_DATE}}`     | `as_of_date`                    |
| `{{FOOTER_SLIDE_N}}`  | auto (1..10)                    |
