"""
Validate concentration.json against schemas/concentration.schema.json.

Run:
  python3 validate_concentration.py path/to/_facts/concentration.json
"""

from __future__ import annotations

import json
import pathlib
import sys


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = SKILL_DIR / "schemas" / "concentration.schema.json"


def validate(path: pathlib.Path) -> list[str]:
    try:
        d = json.loads(path.read_text())
    except Exception as e:
        return [f"concentration.json failed to parse: {e}"]

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
    s = sum(r["critical_count"] for r in d["repos"])
    if abs(s - d["total_criticals"]) > 5:
        msgs.append(
            f"repos[].critical_count sum ({s}) deviates from total_criticals ({d['total_criticals']}) "
            f"by more than 5. Likely cause: data-fetcher dropped issues with no repo field, OR "
            f"the API count includes issues the issues endpoint didn't return."
        )
    pct_sum = sum(r["pct_of_total"] for r in d["repos"])
    if d["total_criticals"] > 0 and abs(pct_sum - 100.0) > 1.0:
        msgs.append(f"pct_of_total values sum to {pct_sum:.1f} (expected ~100)")
    return msgs


def main(argv):
    if len(argv) != 1:
        print("usage: validate_concentration.py path/to/concentration.json", file=sys.stderr)
        return 2
    msgs = validate(pathlib.Path(argv[0]).resolve())
    if msgs:
        print("concentration.json validation FAILED:", file=sys.stderr)
        for m in msgs:
            print(f"  - {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
