"""Slide versions of the key figures: large type, one message each.

    python -m src.presentation.figures     # after ingestion, processing and the network run

The report figures (outputs/figures/{ingestion,processing,network}/) are drawn to be read on a page:
many labels, small type, long footnotes. Shown on a slide, their text is too small to read from the
room. These versions keep only what each slide says and use type about twice as large. They reuse
the data and helpers of each step, so they always match the reports.

Writes outputs/figures/slides/*.png, used by slides.md as @figures/slides/<name>.png.
The data behind the interactive plots (components/*.vue) is written by src/presentation/data.py.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from src.analysis.network import settings as net_settings  # noqa: E402
from src.ingestion import verify as ingestion_verify  # noqa: E402
from src.processing import settings as proc_settings  # noqa: E402

FIGURES = Path("outputs") / "figures" / "slides"
NET = net_settings.OUT
SURFACE, INK, INK2, GRID, OTHER = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#a9a8a2"
ACCENT, WARN = "#2a78d6", "#eb6834"
BASE = 15            # base font size (pt); slide body text is about this size at full width
MIN_PAGES, Q = 20, 0.95   # same reporting thresholds as the network figures


def _style(ax, grid_axis="y"):
    """grid_axis: 'x', 'y', 'both' or None (no grid)."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=BASE - 2)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / name
    fig.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def whose_files(documents: pd.DataFrame, pages: pd.DataFrame):
    """Share of documents and of pages: DEP, Education, everyone else."""
    docs = ingestion_verify.scraped(documents)
    name = {"Environmental Protection, Dept. of": "DEP", "Education, Dept. of": "Education"}
    agency = docs.set_index("doc_id")["agency"].map(name).fillna("Other agencies (21)")
    order = ["DEP", "Education", "Other agencies (21)"]
    share_docs = agency.value_counts(normalize=True).reindex(order)
    share_pages = pages["doc_id"].map(agency).value_counts(normalize=True).reindex(order)
    fig, ax = plt.subplots(figsize=(6.6, 3.9), facecolor=SURFACE)
    y = np.arange(len(order))[::-1]
    h = 0.38
    ax.barh(y + h / 2, share_docs, height=h, color=OTHER, label="share of documents")
    ax.barh(y - h / 2, share_pages, height=h, color=ACCENT, label="share of pages")
    for yi, a, b in zip(y, share_docs, share_pages):
        ax.text(a + 0.01, yi + h / 2, f"{a:.0%}", va="center", fontsize=BASE - 1, color=INK)
        ax.text(b + 0.01, yi - h / 2, f"{b:.0%}", va="center", fontsize=BASE - 1, color=INK, fontweight="bold")
    ax.set_yticks(y, order, fontsize=BASE, color=INK)
    ax.set_xlim(0, 0.88)
    ax.set_xticks([])
    _style(ax, grid_axis=None)
    ax.spines["bottom"].set_visible(False)
    ax.legend(frameon=False, fontsize=BASE - 2, loc="lower right")
    return _save(fig, "s_whose_files.png")


def dates_per_year(documents: pd.DataFrame, first=1990, last=2004):
    """Documents per year with the site's date and with the corrected date."""
    years = np.arange(first, last + 1)
    before = documents["site_date"].dt.year.value_counts().reindex(years, fill_value=0)
    after = documents["doc_date"].dt.year.value_counts().reindex(years, fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 3.7), facecolor=SURFACE)
    w = 0.4
    ax.bar(years - w / 2, before.clip(lower=0.8), width=w, color=OTHER, label="site’s date")
    ax.bar(years + w / 2, after.clip(lower=0.8), width=w, color=ACCENT, label="corrected date")
    ax.set_yscale("log")
    ax.set_ylim(0.8, after.max() * 4)
    ax.set_yticks([10, 100, 1000, 10000], ["10", "100", "1,000", "10,000"])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xticks(years[::2], [str(y) for y in years[::2]])
    _style(ax)
    ax.set_ylabel("documents (log scale)", fontsize=BASE - 2, color=INK2)
    ax.legend(frameon=False, fontsize=BASE - 1, loc="upper left")
    ax.annotate(f"1994: {before[1994]} → {after[1994]}\n(lab-method date on every sheet)",
                (1994 - w / 2, before[1994]), xytext=(1989.6, 900), fontsize=BASE - 1, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=1))
    return _save(fig, "s_dates_per_year.png")


def pages_vs_ties(nodes: pd.DataFrame):
    """Organizations named on more pages have more ties (log axes: organizations with no tie are not drawn)."""
    d = nodes[nodes["degree"] > 0]
    fig, ax = plt.subplots(figsize=(6.6, 4.6), facecolor=SURFACE)
    ax.scatter(d["n_pages"], d["degree"], s=14, color=OTHER, alpha=0.55, edgecolors="none")
    big = d.nlargest(3, "n_pages")
    ax.scatter(big["n_pages"], big["degree"], s=70, color=ACCENT, edgecolors=SURFACE, linewidths=1.5, zorder=3)
    labels = {"NYC Dept. of Environmental Protection": "DEP", "U.S. EPA": "EPA",
              "NYC Dept. of Health and Mental Hygiene": "Health Dept."}
    offsets = {"DEP": (0, 12, "center"), "EPA": (2, -20, "center"), "Health Dept.": (-12, -4, "right")}
    for r in big.itertuples():
        label = labels.get(r.name, r.name)
        dx, dy, ha = offsets.get(label, (-10, 6, "right"))
        ax.annotate(label, (r.n_pages, r.degree), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, va="center", fontsize=BASE - 1, color=INK, fontweight="bold")
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, grid_axis="both")
    ax.set_xlabel("pages naming the organization", fontsize=BASE - 1, color=INK2)
    ax.set_ylabel("organizations it is tied to", fontsize=BASE - 1, color=INK2)
    rho = nodes["n_pages"].corr(nodes["degree"], method="spearman")     # all nodes, as in the report (fig 3)
    ax.set_ylim(top=d["degree"].max() * 3)
    ax.text(0.02, 0.97, f"{len(nodes):,} organizations · Spearman ρ = {rho:.2f}", transform=ax.transAxes,
            fontsize=BASE - 2, color=INK2, ha="left", va="top")
    return _save(fig, "s_pages_vs_ties.png")


def raw_vs_beyond_volume(cmp: pd.DataFrame):
    """Betweenness percentile before and after holding paperwork volume fixed."""
    pop = cmp[(cmp["n_pages"] >= MIN_PAGES) & cmp["ratio_betweenness"].notna() & (cmp["betweenness"] > 0)].copy()
    pop["raw"] = pop["betweenness"].rank(pct=True) * 100
    pop["adj"] = pop["ratio_betweenness"].rank(pct=True) * 100
    rows = [("NYC Dept. of Environmental Protection", "DEP", ACCENT), ("NYC Dept. of Health and Mental Hygiene", "Health Dept.", ACCENT),
            ("NYC Dept. of Buildings", "Buildings Dept.", ACCENT), ("U.S. EPA", "EPA", OTHER),
            ("Port Authority of NY & NJ", "Port Authority", INK), ("FDNY", "FDNY", INK), ("NYC Office of the Mayor", "Mayor’s Office", INK)]
    sel = pop.set_index("name")
    fig, ax = plt.subplots(figsize=(7.4, 5.6), facecolor=SURFACE)
    right = []
    for name, label, color in rows:
        r = sel.loc[name]
        ax.plot([0, 1], [r["raw"], r["adj"]], color=color, lw=3, zorder=2)
        ax.scatter([0, 1], [r["raw"], r["adj"]], s=70, color=color, edgecolors=SURFACE, linewidths=1.5, zorder=3)
        right.append((r["adj"], label, color))
    right.sort()
    ys = [y for y, _, _ in right]
    for k in range(1, len(ys)):                       # keep labels at least 5 points apart
        ys[k] = max(ys[k], ys[k - 1] + 5)
    for (y, label, color), yl in zip(right, ys):
        ax.text(1.06, yl, label, va="center", fontsize=BASE, color=INK if color != OTHER else INK2,
                fontweight="bold" if color == INK else "normal")
    med = pop.groupby("group")[["raw", "adj"]].median()
    reg = med.loc["municipal_regulatory"]
    ax.text(0.5, 8, f"city regulators’ median: {reg['raw']:.0f} → {reg['adj']:.0f}", ha="center",
            fontsize=BASE, color=ACCENT, fontweight="bold")
    ax.set_xlim(-0.25, 1.55)
    ax.set_ylim(0, 104)
    ax.set_xticks([0, 1], ["raw", "beyond volume"], fontsize=BASE, color=INK)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("betweenness percentile", fontsize=BASE - 1, color=INK2)
    _style(ax)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0)
    return _save(fig, "s_raw_vs_beyond_volume.png")


def connectors_per_month(tm: pd.DataFrame, phases: list[tuple[str, str, str]]):
    """How many organizations connected the response beyond their volume, each month."""
    months = pd.period_range(net_settings.TEMPORAL_START, net_settings.TEMPORAL_END, freq="M")
    sig = tm[(tm["pages"] >= MIN_PAGES) & (tm["null_q_betweenness"] >= Q) & (tm["ratio_betweenness"] > 1)]
    counts = sig.groupby(pd.PeriodIndex(sig["month"], freq="M")).size().reindex(months, fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 3.9), facecolor=SURFACE)
    x = np.arange(len(months))
    colors = [ACCENT if m < pd.Period("2001-12", "M") else "#8db7ea" for m in months]
    ax.bar(x, counts.to_numpy(), color=colors, width=0.72)
    for xi, c in zip(x, counts):
        ax.text(xi, c + 0.3, str(c), ha="center", fontsize=BASE, color=INK, fontweight="bold")
    brk = months.get_loc(pd.Period(phases[-1][0], "M")) - 0.5      # start of the last data-driven phase
    ax.axvline(brk, color=INK, lw=1.5, ls=(0, (4, 3)))
    ax.text(brk - 0.25, counts.max() + 2.6, "emergency", ha="right", fontsize=BASE, color=ACCENT, fontweight="bold")
    ax.text(brk + 0.25, counts.max() + 2.6, "clean-up and testing", ha="left",
            fontsize=BASE, color=INK2)
    ax.set_xticks(x, [m.strftime("%b\n%Y") if m.month in (1, 9) else m.strftime("%b") for m in months],
                  fontsize=BASE - 3)
    ax.set_yticks([])
    ax.set_ylim(0, counts.max() + 4)
    _style(ax, grid_axis=None)
    ax.spines["left"].set_visible(False)
    return _save(fig, "s_connectors_per_month.png")


def main():
    F, P = config.FINAL, proc_settings.PROCESSED
    raw_docs = pd.read_parquet(F / "documents.parquet", columns=["doc_id", "agency", "n_pages", "bates_start"])
    raw_pages = pd.read_parquet(F / "pages.parquet", columns=["doc_id"])
    print(whose_files(raw_docs, raw_pages))
    print(dates_per_year(pd.read_parquet(P / "documents.parquet", columns=["site_date", "doc_date"])))
    nodes, cmp = pd.read_csv(NET / "nodes_main.csv"), pd.read_csv(NET / "null_global_nodes.csv")
    tm = pd.read_csv(NET / f"temporal_{net_settings.TEMPORAL_NULL_SAMPLES}.csv")
    print(pages_vs_ties(nodes))
    print(raw_vs_beyond_volume(cmp))
    phases = [("2001-09", "2001-09", "first weeks"), ("2001-10", "2001-11", "fall 2001"),
              ("2001-12", "2002-12", "clean-up and testing")]    # the 3 data-driven phases (fig 6)
    print(connectors_per_month(tm, phases))


if __name__ == "__main__":
    main()
