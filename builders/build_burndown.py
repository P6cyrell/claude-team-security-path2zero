"""
Build the path-to-zero burndown PNG from plan.json.

Plots three series on shared axes per `feedback_burndown-include-original-plan`:
  - actual   — solid purple, observed history through today
  - baseline — dotted gray, the original plan-of-record locked at baseline_date
  - forecast — dashed pink, projection from today to target-zero

Writes the PNG to plan.burndown_png_path.

Run:
  python3 build_burndown.py path/to/plan.json
  python3 build_burndown.py path/to/plan.json --out /tmp/burndown.png
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt    # noqa: E402


SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
BRAND_DIR = SKILL_DIR / "brand"

PALETTE = json.loads((BRAND_DIR / "palette.json").read_text())
FONT    = json.loads((BRAND_DIR / "font.json").read_text())


def hex_(name: str) -> str:
    return PALETTE[name]


def parse_series(series):
    xs = [dt.date.fromisoformat(p["date"]) for p in series]
    ys = [p["value"] for p in series]
    return xs, ys


def build(plan_path: pathlib.Path, out_override: pathlib.Path | None = None) -> pathlib.Path:
    plan = json.loads(plan_path.read_text())
    bs = plan["burndown_series"]

    actual_x, actual_y     = parse_series(bs["actual"])
    baseline_x, baseline_y = parse_series(bs["baseline"])
    forecast_x, forecast_y = parse_series(bs["forecast"])

    # Try the brand font if installed locally — silently fall back to system default otherwise.
    import matplotlib.font_manager as fm
    import warnings
    installed = {f.name for f in fm.fontManager.ttflist}
    if FONT["primary_name"] in installed:
        plt.rcParams["font.family"] = FONT["primary_name"]
    # Suppress matplotlib's "font not found" chatter regardless
    warnings.filterwarnings("ignore", message=".*not found.*", module="matplotlib.*")

    fig, ax = plt.subplots(figsize=(13, 6.5), dpi=160)
    fig.patch.set_facecolor("white")

    ax.plot(baseline_x, baseline_y,
            linestyle=":", linewidth=2.4, color=hex_("muted_purple"),
            label=f"Original plan baseline (locked {bs['baseline_date']})",
            marker="o", markersize=4)

    ax.plot(actual_x, actual_y,
            linestyle="-", linewidth=3.0, color=hex_("primary_purple"),
            label="Actual",
            marker="o", markersize=5)

    ax.plot(forecast_x, forecast_y,
            linestyle="--", linewidth=2.6, color=hex_("primary_pink"),
            label="Current forecast",
            marker="o", markersize=4)

    # Title + subtitle
    title = f"{plan['team']} — Path to Zero criticals"
    subtitle = f"As of {plan['as_of_date']}  ·  Engineering lead: {plan['engineering_lead']}"
    ax.set_title(title, fontsize=18, color=hex_("primary_purple"),
                 fontweight="bold", loc="left", pad=22)
    fig.text(0.072, 0.905, subtitle, fontsize=11, color=hex_("muted_purple"))

    ax.set_ylabel("Open critical vulnerabilities", fontsize=11, color=hex_("dark_purple"))
    ax.set_xlabel("")

    # Y-axis: start at 0, leave headroom
    ymax = max(max(actual_y), max(baseline_y), max(forecast_y))
    ax.set_ylim(bottom=0, top=ymax * 1.08)

    # X-axis date formatting
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=9,
             color=hex_("dark_purple"))
    plt.setp(ax.get_yticklabels(), fontsize=9, color=hex_("dark_purple"))

    # Grid + spines
    ax.grid(True, axis="y", linestyle="-", linewidth=0.6, color=hex_("neutral_cool"))
    for side, spine in ax.spines.items():
        if side in ("top", "right"):
            spine.set_visible(False)
        else:
            spine.set_color(hex_("neutral_cool"))

    # Today line
    today = dt.date.fromisoformat(plan["as_of_date"])
    ax.axvline(today, color=hex_("muted_purple"), linewidth=0.8,
               linestyle="-", alpha=0.4)
    ax.annotate(
        "Today", xy=(today, ymax * 1.04),
        xytext=(6, 0), textcoords="offset points",
        fontsize=9, color=hex_("muted_purple"), va="top",
    )

    # Annotate end-of-forecast (target zero)
    last = bs["forecast"][-1]
    ax.annotate(
        f"Target: {last['value']} on {last['date']}",
        xy=(dt.date.fromisoformat(last["date"]), last["value"]),
        xytext=(-90, 28), textcoords="offset points",
        fontsize=10, color=hex_("primary_purple"), fontweight="bold",
        arrowprops=dict(arrowstyle="-", color=hex_("primary_purple"), lw=1.0),
    )

    # Legend
    leg = ax.legend(loc="upper right", frameon=True, framealpha=0.95,
                    fontsize=10, facecolor="white",
                    edgecolor=hex_("neutral_cool"))
    for txt in leg.get_texts():
        txt.set_color(hex_("dark_purple"))

    # Brand accent — thin pink rule along bottom
    fig.add_artist(plt.Rectangle((0, 0), 1, 0.006,
                                 transform=fig.transFigure,
                                 facecolor=hex_("primary_pink"),
                                 edgecolor="none"))

    fig.tight_layout(rect=[0.0, 0.03, 1.0, 0.93])

    out = out_override or pathlib.Path(plan["burndown_png_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="path to plan.json")
    ap.add_argument("--out", default=None,
                    help="override plan.burndown_png_path")
    args = ap.parse_args(argv)

    plan_path = pathlib.Path(args.plan).resolve()
    out_path  = pathlib.Path(args.out).resolve() if args.out else None

    written = build(plan_path, out_path)
    print(f"wrote {written}  ({written.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main(sys.argv[1:])
