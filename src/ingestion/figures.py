"""Figures for the ingestion report (docs/00.ingestion_report.md), static PNG.

    python -m src.ingestion.figures      # after build_tables (or `git lfs pull`)

Same visual style as src/processing/figures.py and src/analysis/network/figures.py.
"""
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from src.ingestion import verify  # noqa: E402

FIGURES = Path("outputs") / "figures" / "ingestion"
SURFACE, INK, INK2, GRID, OTHER = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#a9a8a2"
ACCENT, WARN = "#2a78d6", "#eb6834"
SHORT = {"Environmental Protection, Dept. of": "Environmental Protection (DEP)",
         "Education, Dept. of": "Education (Board of Ed.)",
         "Citywide Administrative Services, Dept. of": "Citywide Admin. Services",
         "Design and Construction, Dept. of": "Design and Construction",
         "Records and Information Services, Dept. of": "Records and Information Services",
         "Health and Mental Hygiene, Dept. of": "Health and Mental Hygiene"}


def _style(ax, grid_axis="x"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.xaxis.label.set_color(INK2)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _footer(fig, text):
    fig.text(0.01, 0.005, textwrap.fill(text, 180), fontsize=7, color=INK2, va="bottom", ha="left")


def _save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / name
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


def whose_files_figure(documents: pd.DataFrame, pages: pd.DataFrame):
    """Fig I1: share of documents and of pages by the agency whose files they are."""
    docs = verify.scraped(documents)
    n_docs = docs["agency"].value_counts()
    n_pages = pages[["doc_id"]].merge(docs[["doc_id", "agency"]], on="doc_id")["agency"].value_counts()
    top = n_pages.head(5).index
    order = list(top) + [f"Other agencies ({len(n_pages) - 5})"]
    share = lambda s: pd.concat([s.reindex(top), pd.Series({order[-1]: s.drop(top).sum()})]) / s.sum()
    sd, sp = share(n_docs), share(n_pages)
    fig, ax = plt.subplots(figsize=(11, 4.4), facecolor=SURFACE)
    y = np.arange(len(order))[::-1]
    h = 0.36
    ax.barh(y + h / 2, sd.to_numpy(), height=h, color=OTHER, label=f"share of documents ({len(docs):,})")
    ax.barh(y - h / 2, sp.to_numpy(), height=h, color=ACCENT, label=f"share of pages ({len(pages):,})")
    for yi, a, b in zip(y, sd, sp):
        pct = lambda v: "<1%" if v < 0.005 else f"{v:.0%}"
        ax.text(a + 0.006, yi + h / 2, pct(a), va="center", fontsize=8, color=INK)
        ax.text(b + 0.006, yi - h / 2, pct(b), va="center", fontsize=8, color=INK)
    ax.set_yticks(y, [SHORT.get(a, a) for a in order], fontsize=9, color=INK)
    ax.set_xlim(0, max(sd.max(), sp.max()) * 1.12)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    _style(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("Whose files? Half the documents are Education's, three quarters of the pages are DEP's",
                 x=0.01, ha="left", y=0.98, fontsize=12, color=INK)
    _footer(fig, "Agency = the City agency whose files the document comes from, as listed on 911records.org. 94% of "
                 "Department of Education documents are one page long (mostly asbestos air-sample sheets and lab "
                 "results for Board of Education sites); DEP documents average 7 pages.")
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    return _save(fig, "figI1_whose_files.png")


def building_links_figure(coverage: pd.DataFrame, n=15):
    """Fig I2: for the most-documented buildings, the site's page count against the two link tables."""
    coverage = coverage[coverage["kind"] == "bin"]      # BBL entries have no page tags by construction
    top = coverage.sort_values("site_count", ascending=False).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor=SURFACE)
    y = np.arange(len(top))
    for yi, (_, r) in zip(y, top.iterrows()):
        lo, hi = r[["site_count", "building_mentions", "page_tags"]].min(), r[["site_count", "building_mentions", "page_tags"]].max()
        ax.plot([lo, hi], [yi, yi], color=GRID, lw=2, zorder=1)
    ax.scatter(top["site_count"], y, s=70, color=OTHER, zorder=3, label="site's page count (buildings.n_pages)",
               edgecolor=SURFACE, linewidth=1.5)
    ax.scatter(top["page_tags"], y, s=60, color=ACCENT, zorder=4, marker="D", edgecolor=SURFACE, linewidth=1.5,
               label="pages tagged with the building (pages.building_bins)")
    ax.scatter(top["building_mentions"], y, s=60, color=WARN, zorder=4, marker="s", edgecolor=SURFACE, linewidth=1.5,
               label="pages in building_mentions")
    labels = [f"{r['name'][:34]} ({r['record_type']})" for _, r in top.iterrows()]
    ax.set_yticks(y, labels, fontsize=8.5, color=INK)
    _style(ax)
    ax.set_xlabel("pages")
    ax.set_xlim(0, top[["site_count", "building_mentions", "page_tags"]].to_numpy().max() * 1.05)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    short = (coverage["building_mentions"] < coverage["site_count"]).sum()
    fig.suptitle(f"building_mentions misses pages for the most-tested buildings ({short} of {len(coverage)} BIN buildings short)",
                 x=0.01, ha="left", y=0.98, fontsize=12, color=INK)
    _footer(fig, f"The {n} buildings (identified by BIN) with the most pages on the site. building_mentions comes from each building's "
                 "page on 911records.org; pages.building_bins comes from each document page's building links. Over "
                 "all BIN buildings: site count "
                 f"{coverage['site_count'].sum():,}, building_mentions {coverage['building_mentions'].sum():,}, "
                 f"page tags {coverage['page_tags'].sum():,} pages. The 138 lot-level (BBL) entries are left out: "
                 "page tags only use BINs. Record type in brackets.")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    return _save(fig, "figI2_building_links.png")


def main():
    F = config.FINAL
    documents = pd.read_parquet(F / "documents.parquet", columns=["doc_id", "agency", "n_pages", "bates_start"])
    t = {"pages": pd.read_parquet(F / "pages.parquet", columns=["doc_id", "page", "building_bins"]),
         "buildings": pd.read_parquet(F / "buildings.parquet"),
         "building_mentions": pd.read_parquet(F / "building_mentions.parquet")}
    print(whose_files_figure(documents, t["pages"]))
    print(building_links_figure(verify.building_coverage(t)))


if __name__ == "__main__":
    main()
