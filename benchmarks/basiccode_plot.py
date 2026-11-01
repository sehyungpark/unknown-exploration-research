"""Render saved benchmark data to PNG/PDF with no GUI and no exploration rerun."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .basiccode_analysis import PAIRS, analyze
from .basiccode_runner import METHODS, write_json

COLORS = {"A": "#606c76", "B": "#d97706", "C*": "#007f86"}


def plot(directory):
    summary = analyze(directory)
    if not summary["valid"]:
        raise ValueError("Refusing comparison plots for incomplete/failed data; inspect summary.json issues")
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    directory = Path(directory)
    output = directory / "figures"
    output.mkdir(exist_ok=True)
    rates = sorted({g["obstacle_rate"] for g in summary["groups"]})
    title = summary["run_id"]
    if summary["purpose"] == "smoke_validation":
        title += " | SMOKE VALIDATION - NOT PERFORMANCE EVIDENCE"
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    files = []

    def save(fig, name, caption):
        fig.suptitle(title, fontsize=11, fontweight="bold")
        fig.text(0.5, 0.015, caption, ha="center", fontsize=8)
        fig.tight_layout(rect=(0, 0.06, 1, 0.94))
        for extension in ("png", "pdf"):
            path = output / f"{name}.{extension}"
            fig.savefig(path, dpi=180, bbox_inches="tight")
            files.append(path.name)
        plt.close(fig)

    def series(ax, points, label, color, scale=1.0, style="-"):
        defined = [(g["size"], v) for g, v in points if v["value"] is not None]
        if not defined:
            return
        x = [size for size, _ in defined]
        y = [v["value"] / scale for _, v in defined]
        # Percentile bootstrap intervals need not contain the point estimate.
        low = [v["ci95"][0] / scale for _, v in defined]
        high = [v["ci95"][1] / scale for _, v in defined]
        ax.plot(x, y, marker="o", label=label, color=color, linestyle=style)
        ax.vlines(x, low, high, colors=color, alpha=0.6, linewidth=1.5)

    def decorate(ax, ylabel):
        ax.set_xlabel("Square grid side length (cells)")
        ax.set_ylabel(ylabel)
        ax.set_xticks(sorted({g["size"] for g in summary["groups"]}))
        ax.grid(axis="y", alpha=0.22)
        handles, _ = ax.get_legend_handles_labels()
        if handles:
            ax.legend(fontsize=8)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    for ax, field, name in zip(axes, ("planner_ns", "episode_ns"), ("Planning", "Entire exploration")):
        for index, rate in enumerate(rates):
            groups = sorted((g for g in summary["groups"] if g["obstacle_rate"] == rate), key=lambda g: g["size"])
            for method in METHODS:
                series(ax, [(g, g["methods"][method][field]) for g in groups],
                       f"{method}, p={rate:g}", COLORS[method], 1e6, ("-", "--", ":")[index % 3])
        ax.set_title(name)
        decorate(ax, "Time per exploration (ms)")
        ax.set_ylim(bottom=0)
    save(fig, "timing", "Geometric mean of per-map repetition medians; bars: map-bootstrap 95% CI. Same machine only.")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    undefined = False
    for ax, field, name in zip(axes, ("planner_ns", "episode_ns"), ("Planning speedup", "Entire exploration speedup")):
        for index, rate in enumerate(rates):
            groups = sorted((g for g in summary["groups"] if g["obstacle_rate"] == rate), key=lambda g: g["size"])
            for pair_index, (label, _, _) in enumerate(PAIRS):
                points = [(g, g["speedups"][label][field]) for g in groups]
                undefined |= any(v["value"] is None for _, v in points)
                series(ax, points, f"{label}, p={rate:g}", ("#d97706", "#007f86", "#654aa0")[pair_index],
                       style=("-", "--", ":")[index % 3])
        ax.axhline(1, color="#999999", linewidth=1, linestyle="--")
        ax.set_title(name)
        decorate(ax, "Numerator time / denominator time (x)")
        ax.set_ylim(bottom=0)
    caption = "Paired map-level ratios; >1 means denominator is faster. Bars: map-bootstrap 95% CI."
    if undefined:
        caption += " Zero-time ratios undefined; see summary.json."
    save(fig, "speedup", caption)

    for field, name, ylabel, scale, caption in (
        ("exact_evaluations", "exact_evaluations", "Exact gain evaluations per exploration", 1,
         "Separate untimed structural pass; geometric mean across maps, map-bootstrap 95% CI."),
        ("python_peak_bytes", "python_memory", "Peak traced Python allocations (KiB)", 1024,
         "Separate tracemalloc pass; includes exploration results/wrapper; excludes input copies; not process RSS."),
    ):
        if all(g["methods"]["A"][field]["value"] is None for g in summary["groups"]):
            continue
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        for index, rate in enumerate(rates):
            groups = sorted((g for g in summary["groups"] if g["obstacle_rate"] == rate), key=lambda g: g["size"])
            for method in METHODS:
                series(ax, [(g, g["methods"][method][field]) for g in groups],
                       f"{method}, p={rate:g}", COLORS[method], scale, ("-", "--", ":")[index % 3])
        decorate(ax, ylabel)
        ax.set_ylim(bottom=0)
        save(fig, name, caption)
    write_json(output / "figure_manifest.json", {"matplotlib": matplotlib.__version__,
               "generated_utc": datetime.now(timezone.utc).isoformat(), "files": files,
               "run_id": summary["run_id"], "purpose": summary["purpose"]})
    return [output / filename for filename in files]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = plot(args.directory)
    except Exception as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"Saved {len(paths)} figures in {args.directory / 'figures'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
