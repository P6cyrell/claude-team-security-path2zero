# team-security-path2zero (skill)

Invoke with `/team-security-path2zero` in Claude Code.


Generates a per-team Path-to-Zero deliverable pair — Arrive-branded Microsoft PowerPoint and Word files — from a structured `plan.json`.

## Outputs

For a given `plan.json`, the renderer emits two files in `<cwd>/path-to-zero-plan/`:

- `<team>-Path-to-Zero-<YYYY-MM-DD>.pptx` — 10-slide deck
- `<team>-Security-Leadership-Update-<YYYY-MM-DD>.docx` — long-form leadership update

Both open in PowerPoint, Word, Keynote, Pages, Google Slides, and Google Docs without conversion.

## Directory layout

```
~/.claude/skills/team-security-path2zero/
├── brand/                  Arrive logos, palette, font config
├── templates/              Source-of-truth template files (do not edit by hand)
├── builders/
│   ├── build_template_pptx.py    re-builds the PPTX template from scratch
│   ├── build_template_docx.py    re-builds the DOCX template from scratch
│   └── render.py                 fills templates from plan.json
├── schemas/plan.schema.json      JSON Schema for plan.json (schema_version: 1)
├── placeholders.md               reference list of every {{TOKEN}}
└── prompts/                      sub-agent prompts (populated later)
```

## Render a deliverable

```bash
python3 ~/.claude/skills/team-security-path2zero/builders/render.py path/to/plan.json
```

Output lands in `<cwd>/path-to-zero-plan/`. Use `--out-dir` to override.

The renderer:

1. Validates `plan.json` against `schema_version: 1`.
2. Builds a flat token map from the structured plan.
3. Opens each template, walks every text run, replaces `{{TOKENS}}` inline (formatting preserved).
4. Adjusts pre-allocated table rows to match data (blank rows for fewer entries; rows beyond the pre-allocated count are dropped — see "Capacity limits").
5. Replaces the named `BURNDOWN_PLACEHOLDER` shape in the PPTX (and the `{{BURNDOWN_PLACEHOLDER}}` paragraph in the DOCX) with the PNG at `plan.burndown_png_path`.

## Capacity limits (pre-allocated rows)

| Section | PPTX rows | DOCX rows |
|---|---:|---:|
| Remaining surface  | 5 | 5 |
| Dependency regions | 3 | 3 |
| Epics              | 3 | 3 |
| Reallocation       | 5 | 5 |
| Timeline           | 7 | 7 |
| Asks               | 4 | 4 |

If a team's plan exceeds these counts, edit the builder scripts to increase row pre-allocation, re-run, then re-render.

## Brand font

`brand/font.json` specifies **Plus Jakarta Sans** as the primary brand font. macOS does not ship this font by default. Behavior depends on where the file is opened:

- **PowerPoint / Word for Mac, with the font installed locally** — renders correctly.
- **Without the font installed** — both apps substitute the nearest available system font (typically Helvetica Neue). Brand colors and layout are preserved; only the typeface differs.
- **Google Slides / Google Docs** — Plus Jakarta Sans is available natively as a Google Font; rendering matches the spec.

Install locally from <https://fonts.google.com/specimen/Plus+Jakarta+Sans> if you need brand-fidelity output on this Mac.

Override `brand/font.json:primary_name` if your team has the actual Arrive corporate font licensed (e.g. Aeonik, Söhne, Graphik). The fallback chain is corporate → Plus Jakarta Sans → Calibri → system default.

## Re-building the templates

If brand colors, font, or slide layout change, edit `brand/palette.json`, `brand/font.json`, or the builder scripts, then re-build:

```bash
python3 ~/.claude/skills/team-security-path2zero/builders/build_template_pptx.py
python3 ~/.claude/skills/team-security-path2zero/builders/build_template_docx.py
```

This overwrites the files in `templates/`. Existing rendered deliverables are unaffected.

## Schema versioning

`plan.json` requires `schema_version: 1`. The renderer rejects mismatched versions with an actionable error. When the schema evolves, bump the version and ship a migration script alongside.

## Required dependencies

```bash
pip install python-pptx python-docx
```

The renderer does not require Google Drive APIs, OAuth, or any external service. Everything runs locally against the templates on disk.
