"""
Validate jira-facts.json against schemas/jira-facts.schema.json.

Run:
  python3 validate_jira_facts.py path/to/_facts/jira-facts.json
"""

from __future__ import annotations

import json
import pathlib
import sys


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = SKILL_DIR / "schemas" / "jira-facts.schema.json"


def validate(path: pathlib.Path) -> list[str]:
    try:
        d = json.loads(path.read_text())
    except Exception as e:
        return [f"jira-facts.json failed to parse: {e}"]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["jsonschema not installed. Run: pip install jsonschema"]

    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(d), key=lambda e: list(e.absolute_path))
    if errors:
        return [f"[{'.'.join(str(p) for p in e.absolute_path) or '(root)'}] {e.message}" for e in errors]

    # Semantic
    msgs = []
    for epic in d["epics"]:
        prog = epic["progress"]
        sum_status = prog["done"] + prog["in_progress"] + prog["todo"]
        if sum_status != prog["total"]:
            msgs.append(
                f"epic {epic['key']}: done+in_progress+todo ({sum_status}) != total ({prog['total']})"
            )
        if prog["total"] > 0:
            expected_pct = 100.0 * prog["done"] / prog["total"]
            if abs(prog["pct_complete"] - expected_pct) > 0.5:
                msgs.append(
                    f"epic {epic['key']}: pct_complete={prog['pct_complete']} but "
                    f"done/total={prog['done']}/{prog['total']}={expected_pct:.1f}"
                )
        # Children count must match progress.total
        if len(epic["children"]) != prog["total"]:
            msgs.append(
                f"epic {epic['key']}: children[] length ({len(epic['children'])}) != progress.total ({prog['total']})"
            )
    return msgs


def main(argv):
    if len(argv) != 1:
        print("usage: validate_jira_facts.py path/to/jira-facts.json", file=sys.stderr)
        return 2
    msgs = validate(pathlib.Path(argv[0]).resolve())
    if msgs:
        print("jira-facts.json validation FAILED:", file=sys.stderr)
        for m in msgs:
            print(f"  - {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
