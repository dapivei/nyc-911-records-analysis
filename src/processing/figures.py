"""Figures for the processing report (docs/01.processing_report.md), static PNG.

    python -m src.processing.figures      # after python -m src.processing.clean

Same visual style as src/analysis/network/figures.py: one accent color for what the cleaning
produces, neutral gray for what the site gave us, text always in ink colors.
"""
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.processing import settings  # noqa: E402

FIGURES = Path("outputs") / "figures" / "processing"
SURFACE, INK, INK2, GRID, OTHER = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#a9a8a2"
ACCENT = "#2a78d6"          # cleaned values
WARN = "#eb6834"            # values the cleaning flags or removes


def _style(ax, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _footer(fig, text):
    fig.text(0.01, 0.005, textwrap.fill(text, 175), fontsize=7, color=INK2, va="bottom", ha="left")


def _save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / name
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


def date_outcomes(documents: pd.DataFrame) -> pd.Series:
    """What the correction did to each document's date, compared with the site's date."""
    site, doc = documents["site_date"], documents["doc_date"]
    same = site.notna() & doc.notna() & (site.dt.normalize() == doc.dt.normalize())
    conflict = documents["date_fix"].eq("raw date (conflicts with title)")
    out = pd.Series("", index=documents.index)
    no_title = documents["date_fix"].eq("raw date (no title date)")
    out[same & ~conflict & ~no_title] = "site date confirmed by title"
    out[same & no_title] = "site date kept, title has no date"
    out[same & conflict] = "site date kept, title disagrees"
    out[site.notna() & doc.notna() & ~same] = "site date replaced"
    out[site.isna() & doc.notna()] = "missing date filled in"
    out[site.notna() & doc.isna()] = "wrong date removed, none left"
    out[site.isna() & doc.isna()] = "no date before or after"
    return out


def dates_figure(documents: pd.DataFrame):
    """Fig P1: documents per year before / after the date correction, and what happened to each date."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14, 5.6), facecolor=SURFACE, gridspec_kw={"width_ratios": [1.5, 1]})
    years = np.arange(1990, 2015)
    before = documents["site_date"].dt.year.value_counts().reindex(years, fill_value=0)
    after = documents["doc_date"].dt.year.value_counts().reindex(years, fill_value=0)
    w = 0.4
    ax.bar(years - w / 2, before.clip(lower=0.8), width=w, color=OTHER, label="site's date (earliest date in the text)")
    ax.bar(years + w / 2, after.clip(lower=0.8), width=w, color=ACCENT, label="corrected date (checked against the title)")
    ax.set_yscale("log")
    ax.set_ylim(0.8, after.max() * 3)
    ax.set_yticks([1, 10, 100, 1000, 10000], ["1", "10", "100", "1,000", "10,000"])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xticks(years[::2], [str(y) for y in years[::2]])
    _style(ax)
    ax.set_ylabel("documents (log scale)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    for y, note in [(1994, "NIOSH method date\n(8/15/94) on lab sheets")]:
        ax.annotate(f"{note}: {before[y]:,} → {after[y]:,}", (y - w / 2, before[y]), xytext=(0, 40),
                    textcoords="offset points", ha="center", fontsize=7.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.set_title("Documents per year, before and after the correction", fontsize=10,
                 color=INK, loc="left")

    outcome = date_outcomes(documents).value_counts()
    order = ["site date kept, title has no date", "site date confirmed by title", "missing date filled in", "site date replaced", "site date kept, title disagrees",
             "wrong date removed, none left", "no date before or after"]
    vals = outcome.reindex(order, fill_value=0)
    colors = [OTHER, OTHER, ACCENT, ACCENT, WARN, WARN, GRID]
    y = np.arange(len(order))[::-1]
    bx.barh(y, vals.to_numpy(), color=colors, height=0.62)
    for yi, v in zip(y, vals):
        bx.text(v + vals.max() * 0.01, yi, f"{v:,}", va="center", fontsize=8.5, color=INK)
    bx.set_yticks(y, order, fontsize=8.5, color=INK)
    bx.set_xlim(0, vals.max() * 1.18)
    bx.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _style(bx, grid_axis="x")
    bx.set_xlabel("documents")
    bx.set_title(f"What happened to each of the {len(documents):,} document dates", fontsize=10, color=INK, loc="left")
    fig.suptitle("Correcting document dates with the title as a cross-check", x=0.01, ha="left", y=0.985,
                 fontsize=12, color=INK)
    _footer(fig, "The site dates each document by the earliest date anywhere in its text. The correction drops dates "
                 "repeated across many documents that never match their titles (such as a lab-method date "
                 "printed on every sheet), then uses the title's month and year to fill in or replace implausible dates "
                 "(src/processing/dates.py). Years before 1990 and after 2014 are not shown.")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    return _save(fig, "figP1_dates.png")


def usable_text_figure(pages: pd.DataFrame):
    """Fig P2: the site's text label (ocr_status) against has_usable_text."""
    usable = pages["has_usable_text"].map({True: "usable", False: "not usable"})
    tab = pd.crosstab(pages["ocr_status"].fillna("(none)"), usable)
    tab = tab.reindex(columns=["usable", "not usable"], fill_value=0)
    tab = tab.loc[tab.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(11, 3.9), facecolor=SURFACE)
    y = np.arange(len(tab))
    ax.barh(y, tab["usable"], color=ACCENT, height=0.6, label="usable text (has_usable_text)")
    ax.barh(y, tab["not usable"], left=tab["usable"], color=OTHER, height=0.6, label="not usable: too short, number-heavy or scrambled")
    for yi, (u, n) in zip(y, tab[["usable", "not usable"]].to_numpy()):
        tot = u + n
        ax.text(tot + tab.sum(axis=1).max() * 0.01, yi, f"{tot:,} pages · {u / tot:.0%} usable", va="center",
                fontsize=8.5, color=INK)
    ax.set_yticks(y, [f"site label: {s}" for s in tab.index], fontsize=9, color=INK)
    ax.set_xlim(0, tab.sum(axis=1).max() * 1.3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _style(ax, grid_axis="x")
    ax.set_xlabel("pages")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ok = tab.loc["ok"] if "ok" in tab.index else None
    title = ("The site's 'ok' label does not mean readable prose"
             + (f": {ok["not usable"]:,} 'ok' pages fail the usable-text test" if ok is not None else ""))
    fig.suptitle(title, x=0.01, ha="left", y=0.98, fontsize=12, color=INK)
    _footer(fig, f"Usable = at least {settings.MIN_USABLE_CHARS} characters, at least "
                 f"{settings.MIN_ALPHA_RATIO:.0%} letters, and at least {settings.MIN_WORD_RATIO:.0%} of tokens real "
                 "words of 3+ letters (settings.py). Pages the site marks 'junk' are instrument printouts such as "
                 "chromatograms; most 'ok' pages that fail do so because fewer than 40% of their tokens are words.")
    fig.tight_layout(rect=(0, 0.09, 1, 0.93))
    return _save(fig, "figP2_usable_text.png")


def main():
    P = settings.PROCESSED
    documents = pd.read_parquet(P / "documents.parquet", columns=["doc_id", "site_date", "doc_date", "date_fix"])
    pages = pd.read_parquet(P / "pages.parquet", columns=["ocr_status", "has_usable_text"])
    print(dates_figure(documents))
    print(usable_text_figure(pages))


if __name__ == "__main__":
    main()
