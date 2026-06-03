"""
Validate a plan.json against schemas/plan.schema.json.

Exits 0 with no output on success.
Exits 1 with a human-readable error message on failure.

The synthesizer sub-agent MUST call this before writing plan.json to disk.
The renderer also calls this defensively.

Run:
  python3 validate_plan.py path/to/plan.json
"""

from __future__ import annotations

import json
import pathlib
import sys


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = SKILL_DIR / "schemas" / "plan.schema.json"


def validate(plan_path: pathlib.Path) -> list[str]:
    try:
        plan = json.loads(plan_path.read_text())
    except Exception as e:
        return [f"plan.json failed to parse as JSON: {e}"]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema not installed. Run: pip install jsonschema"]

    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(plan), key=lambda e: list(e.absolute_path))
    if not errors:
        return _semantic_checks(plan)

    msgs = []
    for err in errors:
        loc = ".".join(str(p) for p in err.absolute_path) or "(root)"
        msgs.append(f"[{loc}] {err.message}")
    return msgs


def _semantic_checks(plan: dict) -> list[str]:
    """Checks that JSON Schema can't express: numeric reconciliation, date ordering."""
    msgs = []

    # exec_summary.today must match the last actual burndown point
    last_actual = plan["burndown_series"]["actual"][-1]
    if last_actual["value"] != plan["exec_summary"]["today"]:
        msgs.append(
            f"exec_summary.today={plan['exec_summary']['today']} disagrees with last "
            f"burndown_series.actual point ({last_actual['date']}={last_actual['value']})"
        )

    # exec_summary.peak must match the max actual or baseline value
    max_observed = max(
        max(p["value"] for p in plan["burndown_series"]["actual"]),
        max(p["value"] for p in plan["burndown_series"]["baseline"]),
    )
    if plan["exec_summary"]["peak"] != max_observed:
        msgs.append(
            f"exec_summary.peak={plan['exec_summary']['peak']} does not equal the max of "
            f"burndown_series.actual / baseline ({max_observed})"
        )

    # forecast must end at 0 (target-zero)
    if plan["burndown_series"]["forecast"][-1]["value"] != 0:
        msgs.append("burndown_series.forecast must end at value=0 (target-zero point)")

    # timeline must be monotonically non-increasing in open_criticals (allowing minor noise is risky; warn instead)
    prev = None
    for row in plan["timeline"]:
        if prev is not None and row["open_criticals"] > prev:
            msgs.append(
                f"timeline shows open_criticals increasing at {row['date']} "
                f"({prev} → {row['open_criticals']}) — confirm this is intentional"
            )
        prev = row["open_criticals"]

    # remaining_surface critical sum must equal exec_summary.today
    surface_sum = sum(r["critical"] for r in plan["remaining_surface"])
    if surface_sum != plan["exec_summary"]["today"]:
        msgs.append(
            f"remaining_surface critical sum ({surface_sum}) disagrees with "
            f"exec_summary.today ({plan['exec_summary']['today']})"
        )

    # capacity limits enforced by the templates
    caps = {
        "remaining_surface": 5,
        "epic_status": 3,
        "resource_reallocation": 5,
        "timeline": 7,
        "asks": 4,
    }
    for key, cap in caps.items():
        n = len(plan[key])
        if n > cap:
            msgs.append(
                f"{key} has {n} entries; templates pre-allocate {cap}. "
                f"Trim or edit builders/build_template_*.py to raise the cap."
            )
    deps = plan["dependency_grid"]["regions"]
    if len(deps) > 3:
        msgs.append(
            f"dependency_grid.regions has {len(deps)} entries; template supports 3."
        )

    return msgs


def main(argv):
    if len(argv) != 1:
        print("usage: validate_plan.py path/to/plan.json", file=sys.stderr)
        return 2
    plan_path = pathlib.Path(argv[0]).resolve()
    msgs = validate(plan_path)
    if msgs:
        print("plan.json validation FAILED:", file=sys.stderr)
        for m in msgs:
            print(f"  - {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
