"""
Compute the historical-trend series for a team from the saved
get_sla_metrics response.

Phase 1a's data-fetcher saves sla-metrics-<date>.json to _raw/. That file
contains an `openTrends[]` array with daily critical-count snapshots back
to selectedFirstDate. This script normalises it into a stable
`_facts/trend.json` shape that the synthesizer can drop straight into
`plan.burndown_series.actual[]`.

Run:
  python3 compute_trend.py \\
    --sla-metrics path/to/_raw/sla-metrics-<date>.json \\
    --severity CRITICAL \\
    --as-of <date> \\
    --out path/to/_facts/trend.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from collections import defaultdict


def _parse_date(s: str) -> str:
    """Strip the time component if any; return YYYY-MM-DD."""
    return s[:10]


def compute(sla_metrics_path: pathlib.Path, severity: str, as_of: str) -> dict:
    raw = json.loads(sla_metrics_path.read_text())
    if not isinstance(raw, dict) or "openTrends" not in raw:
        raise SystemExit(
            f"{sla_metrics_path}: expected an object with 'openTrends', got "
            f"{list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}"
        )

    sev_lower = severity.lower()
    # openTrends entries can be repeated per github_org for the same date;
    # sum across orgs to get one value per date.
    by_date: defaultdict[str, int] = defaultdict(int)
    for entry in raw["openTrends"]:
        if str(entry.get("severity", "")).lower() != sev_lower:
            continue
        date = _parse_date(entry["date"])
        by_date[date] += int(entry["vulnerabilitycount"])

    if not by_date:
        raise SystemExit(
            f"no entries matched severity={severity!r} in openTrends — "
            f"check the severity filter passed to get_sla_metrics"
        )

    # Sort chronologically, oldest first
    series = [{"date": d, "value": by_date[d]} for d in sorted(by_date)]

    # Diagnostic: do peak / trough / today line up?
    peak = max(series, key=lambda p: p["value"])
    today_entry = next((p for p in series if p["date"] == as_of), series[-1])

    return {
        "schema_version": 1,
        "severity": severity.upper(),
        "as_of_date": as_of,
        "first_date": series[0]["date"],
        "last_date": series[-1]["date"],
        "peak": {"date": peak["date"], "value": peak["value"]},
        "today": {"date": today_entry["date"], "value": today_entry["value"]},
        "series": series,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sla-metrics", required=True)
    ap.add_argument("--severity", default="CRITICAL",
                    choices=["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"])
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    trend = compute(
        pathlib.Path(args.sla_metrics),
        args.severity,
        args.as_of,
    )

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(trend, indent=2) + "\n")
    print(f"wrote {out_path}  ({out_path.stat().st_size:,} bytes)")
    print(f"  {trend['severity']}: peak={trend['peak']['value']} on {trend['peak']['date']}, "
          f"today={trend['today']['value']} on {trend['today']['date']}, "
          f"{len(trend['series'])} daily points")


if __name__ == "__main__":
    main(sys.argv[1:])
