"""
DEP building oversight after 9/11 — conservative reconstruction of inspection, owner reporting,
and cleanup coverage from the released NYC records (911records.org mirror).

Verified Research Questions
  Q1  Coverage & Stage Counts: Which buildings appear in DEP inspection, test report, request,
      cleanup, and clearance records?
  Q2  Test Report Coverage: How many DEP-inspected buildings have a documented test report in
      the city's records, broken down by building type and distance to the WTC site?
  Q3  Exterior Cleanup Sequence: Among buildings with both an inspection and exterior cleanup
      record, how consistently does exterior cleanup follow inspection (using verified field dates)?

Inputs (one folder, default ./data):
  buildings.parquet, building_mentions.parquet, pages.parquet, documents.parquet

Run:
  pip install pandas pyarrow matplotlib scipy
  python dep_oversight.py --data ./data --out ./outputs/dep_oversight

Outputs (in --out):
  pages_staged.csv            page-level staged records with verified dates and URLs
  building_timeline.csv       one row per building: attributes + stage flags & verified dates
  verify_sample.csv           100 random inspected buildings for manual audit
  q2_report_coverage.csv      share of inspected buildings with a test report, by type and distance
  q3_exterior_cleanup.csv     inspection -> exterior cleanup sequence & lag (verified dates only)
  fig_q2_coverage.png         test-report coverage by distance band and building type
  summary.txt                 headline verified numbers + audit caveats
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

WTC = (40.7115, -74.0134)  # approx. centre of the WTC site
T0 = pd.Timestamp("2001-09-11")
WINDOW = (pd.Timestamp("2001-09-12"), pd.Timestamp("2003-12-31"))

# ----------------------------------------------------------------------------- stage rules
WTC_CONTEXT = re.compile(r"WTC|World Trade|9/11|September 11|asbestos|dust|debris|environmental|sampl", re.I)
STAGES = [
    ("inspection", re.compile(r"inspection form|visual (survey|inspection)|facade inspection|building inspection|"
                              r"visual survey|inspection record|survey form", re.I)),
    ("request", re.compile(r"\bDEP\b.{0,40}\b(request|letter|notice|order|notification)|"
                           r"request\w*.{0,40}(environmental|assessment|data|report|results|copies)", re.I)),
    ("clearance", re.compile(r"clearance|re-?occupan|close-?out|final (air|visual)|cleared for", re.I)),
    ("cleanup", re.compile(r"clean-?up|abatement|remediat|decontaminat|removal of (debris|dust)", re.I)),
    ("test_report", re.compile(r"result|sampl|analy|air monitor|wipe|\bPLM\b|\bTEM\b|\bPCM\b|laborator|"
                               r"lab report|survey report|environmental (assessment|report|survey)|"
                               r"asbestos (survey|report|inspection)|dust test|air quality", re.I)),
]
EXTERIOR = re.compile(r"facade|façade|exterior|roof|setback|ledge|sidewalk|street", re.I)

# Exclude administrative/data-entry stamps ("ENTERED Date: 4/12/2002", "BISPIQ" DOB printouts)
ADMIN_STAMP = re.compile(r"(?:ENTERED\s*[:;\-]?\s*|BISPIQ|MULTI-AGENCY COMPOSITE PROPERTY|Report Date\s*Service Request)", re.I)

# Labelled event dates in page text, by stage (strictly event dates, not data-entry dates)
LABELLED = {
    "inspection": r"(?:date\s*of\s*(?:inspection|survey|visit)|inspection\s*date|survey\s*date|date\s*inspected)",
    "test_report": r"(?:date\s*(?:sampled|collected|of\s*sampling)|sampl\w*\s*date|collect\w*\s*date)",
    "cleanup": r"(?:date\s*(?:of\s*)?(?:completion|completed|work)|start\s*date|abatement\s*date)",
    "clearance": r"(?:clearance\s*date|date\s*of\s*clearance|date\s*cleared)",
    "request": r"(?:dated?)",
}
DATE_NUM = r"\s*[:;.|]?\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})"
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
LETTER_DATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
                         r"\s+(\d{1,2}),?\s+(20\d\d)\b")
# Only accept title dates if an explicit day is present (reject AI-guessed month-only titles like "Oct 2001")
EXACT_TITLE_DATE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(\d{1,2}),?\s+(20\d\d)\b", re.I)


def in_window(ts):
    return ts is not None and not pd.isna(ts) and WINDOW[0] <= ts <= WINDOW[1]


def mk(y, m, d):
    y = int(y)
    y = y + 2000 if y < 100 else y
    try:
        return pd.Timestamp(year=y, month=int(m), day=int(d))
    except (ValueError, OverflowError):
        return None


def labelled_date(text: str, stage: str):
    pat = LABELLED.get(stage)
    if not pat:
        return None
    for m in re.finditer(pat + DATE_NUM, text, re.I):
        # Skip if immediately preceded by "ENTERED" (e.g., "ENTERED Date: 4/12/2002")
        prefix = text[max(0, m.start() - 25):m.start()]
        if re.search(r"ENTERED", prefix, re.I):
            continue
        ts = mk(m.group(3), m.group(1), m.group(2))
        if in_window(ts):
            return ts
    return None


def letter_date(text: str):
    """'February 12, 2002' near the top of a DEP notice/letter."""
    m = LETTER_DATE.search(text[:1500])
    if m:
        ts = mk(m.group(3), MONTHS[m.group(1)[:3].lower()], m.group(2))
        return ts if in_window(ts) else None
    return None


def exact_title_date(title: str):
    """Only accept titles with an explicit day (e.g., 'Mar 13, 2002'), ignoring month-only guesses."""
    m = EXACT_TITLE_DATE.search(title or "")
    if not m:
        return None
    day = int(m.group(2))
    if not (1 <= day <= 31):
        return None
    ts = mk(m.group(3), MONTHS[m.group(1)[:3].lower()], day)
    return ts if in_window(ts) else None


def classify(text_blob: str) -> str:
    for name, rx in STAGES:
        if rx.search(text_blob):
            return name
    return "other"


BTYPE = {"D": "residential", "C": "residential", "R": "residential", "S": "residential",
         "O": "office", "K": "commercial/retail", "H": "hotel", "W": "education",
         "G": "garage/transport", "U": "utility", "M": "religious/community", "P": "religious/community",
         "Y": "government", "Z": "other", "I": "health", "E": "warehouse", "A": "residential", "B": "residential"}


# ----------------------------------------------------------------------------- pipeline
def build(data: Path):
    links = pd.read_parquet(
        data / "final/building_mentions.parquet",
        columns=["bin", "doc_id"],
    ).drop_duplicates()
    relevant_docs = set(links["doc_id"])

    docs = pd.read_parquet(
        data / "final/documents.parquet",
        columns=["doc_id", "title", "description", "agency", "site_date", "url"],
    )
    docs = docs[docs["doc_id"].isin(relevant_docs)].copy()

    pages = pd.read_parquet(
        data / "final/pages.parquet",
        columns=["doc_id", "page", "date", "url", "text", "ocr_status"],
    )
    pages = pages[
        pages["doc_id"].isin(relevant_docs) & ~pages["ocr_status"].isin(["junk", "empty"])
    ].copy()
    pages = pages.rename(columns={"url": "page_url"}).drop(columns=["ocr_status"])
    pages["text"] = pages["text"].fillna("").str.slice(0, 6000)
    pages["date"] = pd.to_datetime(pages["date"], errors="coerce")

    # Merge document metadata onto pages so multi-page packets (e.g. survey + demand letter)
    # are classified per page rather than letting page 1 hide page 2
    p_df = pages.merge(docs, on="doc_id", how="inner")

    stages, exteriors, wtc_flags, dates, date_sources = [], [], [], [], []
    for r in p_df.itertuples():
        # Page 1 inherits document title/description; subsequent pages rely on their own OCR text
        meta_blob = f"{r.title or ''} || {r.description or ''}" if r.page == 1 else ""
        classify_blob = f"{meta_blob} || {r.text[:2500]}"
        full_blob = f"{meta_blob} || {r.text[:3500]}"

        has_wtc = bool(WTC_CONTEXT.search(full_blob))
        stg = classify(classify_blob) if has_wtc else "other"

        # Exclude unrelated hotline service requests or pure DOB BISPIQ lookup pages from staging
        if ADMIN_STAMP.search(r.text[:800]) and stg in ("inspection", "other"):
            if "WTC Visual Survey Form" not in r.text[:500]:
                stg = "other"

        ext = bool(EXTERIOR.search(classify_blob))

        # Extract ONLY verified event dates (no DOB printout proxies, no ENTERED stamps, no month-only titles)
        d, src = pd.NaT, None
        if stg != "other":
            ld = labelled_date(r.text, stg)
            if ld is not None:
                d, src = ld, "labelled event date in text"
            elif stg == "request":
                let_d = letter_date(r.text)
                if let_d is not None:
                    d, src = let_d, "letterhead date"
            if pd.isna(d) and r.page == 1:
                td = exact_title_date(r.title)
                if td is not None:
                    d, src = td, "exact day title"

        stages.append(stg)
        exteriors.append(ext)
        wtc_flags.append(has_wtc)
        dates.append(d)
        date_sources.append(src)

    p_df["stage"] = stages
    p_df["exterior"] = exteriors
    p_df["wtc_context"] = wtc_flags
    p_df["verified_date"] = dates
    p_df["date_source"] = date_sources

    p_staged = p_df[p_df["stage"] != "other"].copy()
    p_staged["stage2"] = np.where(
        p_staged["stage"] == "cleanup",
        np.where(p_staged["exterior"], "cleanup_exterior", "cleanup_interior"),
        p_staged["stage"],
    )

    # Link staged pages to buildings (note: stage presence does NOT require a verified_date)
    staged = links.merge(p_staged, on="doc_id", how="inner")

    # --- building attributes
    b = pd.read_parquet(data / "final/buildings.parquet")
    b["dist_m"] = np.hypot((b.lat - WTC[0]) * 111_000, (b.lon - WTC[1]) * 84_300)
    b["btype"] = b.building_class_code.str[0].map(BTYPE).fillna("unknown")
    b["area_sqft"] = pd.to_numeric(b.building_area.astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce")
    b["dist_band"] = pd.cut(b.dist_m, [0, 250, 500, 750, 1000, 99_999],
                            labels=["<250 m", "250–500 m", "500–750 m", "750 m–1 km", ">1 km"])

    # Stage presence flags per building (reliable even when handwritten dates are missing)
    stage_presence = (
        staged.assign(present=True)
        .drop_duplicates(["bin", "stage2"])
        .pivot(index="bin", columns="stage2", values="present")
        .fillna(False)
    )
    stage_presence.columns = [f"has_{c}" for c in stage_presence.columns]

    # Earliest VERIFIED date per stage (strictly day-precision event dates only)
    dated = staged.dropna(subset=["verified_date"]).sort_values("verified_date")
    first_verified = (
        dated.drop_duplicates(["bin", "stage2"])
        .pivot(index="bin", columns="stage2", values="verified_date")
    )
    first_verified.columns = [f"verified_{c}" for c in first_verified.columns]

    tl = b.merge(stage_presence, left_on="bin", right_index=True, how="left")
    for col in stage_presence.columns:
        tl[col] = tl[col].fillna(False)
    tl = tl.merge(first_verified, left_on="bin", right_index=True, how="left")

    return staged, tl


# ----------------------------------------------------------------------------- verified analyses
def q2_coverage(tl: pd.DataFrame, out: Path, lines: list):
    from scipy.stats import chi2_contingency

    ins = tl[tl["has_inspection"]].copy()
    rows = []
    for col in ["btype", "dist_band"]:
        g = ins.groupby(col, observed=True).agg(
            inspected=("bin", "size"),
            with_report=("has_test_report", "sum"),
        )
        g["without_report"] = g["inspected"] - g["with_report"]
        g["share_with_report"] = (g["with_report"] / g["inspected"]).round(3)
        g.insert(0, "group_by", col)
        rows.append(g.reset_index().rename(columns={col: "group"}))
        if g["inspected"].min() >= 5:
            chi = chi2_contingency(np.c_[g["with_report"], g["without_report"]])
            lines.append(f"  chi-square test-report coverage by {col}: chi2={chi.statistic:.2f}, p={chi.pvalue:.4f}")

    cov_df = pd.concat(rows, ignore_index=True)
    cov_df.to_csv(out / "q2_report_coverage.csv", index=False)

    lines += [
        "",
        "Q2  TEST REPORT COVERAGE AMONG DEP-INSPECTED BUILDINGS (VERIFIED PRESENCE)",
        f"  inspected buildings: {len(ins):,} | with test report: {ins['has_test_report'].sum():,} ({ins['has_test_report'].mean():.1%})"
        f" | NO report in archive: {(~ins['has_test_report']).sum():,} ({(~ins['has_test_report']).mean():.1%})",
    ]
    for r in cov_df[cov_df["group_by"] == "dist_band"].itertuples():
        lines.append(f"    distance {r.group:12s}: {r.with_report:3d}/{r.inspected:3d} ({r.share_with_report:.1%}) have a test report")
    for r in cov_df[cov_df["group_by"] == "btype"].sort_values("inspected", ascending=False).head(5).itertuples():
        lines.append(f"    type     {r.group:18s}: {r.with_report:3d}/{r.inspected:3d} ({r.share_with_report:.1%}) have a test report")

    # Plot verified report coverage by distance and top building types
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    dist_sub = cov_df[cov_df["group_by"] == "dist_band"]
    axes[0].bar(dist_sub["group"].astype(str), dist_sub["share_with_report"], color="#2a78d6", width=0.55)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Share of inspected buildings with test report")
    axes[0].set_title("Test-report coverage by distance to WTC", loc="left", fontsize=10.5)
    axes[0].tick_params(axis="x", rotation=20)

    type_sub = cov_df[(cov_df["group_by"] == "btype") & (cov_df["inspected"] >= 15)].sort_values("share_with_report", ascending=False)
    axes[1].bar(type_sub["group"].astype(str), type_sub["share_with_report"], color="#1baf7a", width=0.55)
    axes[1].set_ylim(0, 1)
    axes[1].set_title("Test-report coverage by building type (n ≥ 15)", loc="left", fontsize=10.5)
    axes[1].tick_params(axis="x", rotation=20)

    for ax in axes:
        ax.grid(axis="y", color="#e6e5e0", lw=0.6)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)

    fig.tight_layout()
    fig.savefig(out / "fig_q2_coverage.png", dpi=150)
    plt.close(fig)


def q3_exterior_sequence(tl: pd.DataFrame, out: Path, lines: list):
    """Only evaluate inspection -> exterior cleanup on verified field dates."""
    if "verified_inspection" not in tl or "verified_cleanup_exterior" not in tl:
        return

    x = tl.dropna(subset=["verified_inspection", "verified_cleanup_exterior"]).copy()
    x["gap_days"] = (x["verified_cleanup_exterior"] - x["verified_inspection"]).dt.days
    x["in_expected_order"] = x["gap_days"] >= 0

    rows = []
    for g, gg in [("ALL", x)] + list(x.groupby("btype")):
        if len(gg) < 3:
            continue
        rows.append(dict(
            btype=g,
            n=len(gg),
            median_days=gg["gap_days"].median(),
            q25=gg["gap_days"].quantile(0.25),
            q75=gg["gap_days"].quantile(0.75),
            share_in_expected_order=gg["in_expected_order"].mean().round(3),
        ))

    res = pd.DataFrame(rows)
    res.to_csv(out / "q3_exterior_cleanup.csv", index=False)

    lines += ["", "Q3  EXTERIOR CLEANUP SEQUENCE (VERIFIED FIELD DATES ONLY)"]
    if not res.empty:
        r = res[res["btype"] == "ALL"].iloc[0]
        lines.append(
            f"  inspection -> exterior cleanup (n={int(r.n)}): median {r.median_days:.0f} days "
            f"[IQR {r.q25:.0f}..{r.q75:.0f}], in expected order {r.share_in_expected_order:.1%}"
        )


def verify_sample(staged: pd.DataFrame, tl: pd.DataFrame, out: Path, n=100, seed=42):
    inspected_bins = tl[tl["has_inspection"]]["bin"]
    bins = inspected_bins.sample(n=min(n, len(inspected_bins)), random_state=seed)
    s = (
        staged[staged["bin"].isin(bins)]
        .sort_values(["bin", "doc_id", "page"])
        .drop_duplicates(["bin", "stage2"])
        [["bin", "stage2", "verified_date", "date_source", "doc_id", "page", "title", "page_url", "url"]]
    )
    s = s.merge(tl[["bin", "address", "btype", "dist_m"]], on="bin", how="left")
    for col in ["ok_stage (y/n)", "ok_building (y/n)", "true_event_date", "notes"]:
        s[col] = ""
    s.sort_values(["bin", "doc_id", "page"]).to_csv(out / "verify_sample.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="outputs/dep_oversight_verified")
    a = ap.parse_args()
    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    staged, tl = build(data)
    staged.drop(columns=["description", "text"]).to_csv(out / "pages_staged.csv", index=False)
    tl.to_csv(out / "building_timeline.csv", index=False)

    stage_cols = [c for c in tl.columns if c.startswith("has_")]
    lines = [
        "DEP BUILDING OVERSIGHT AFTER 9/11 — VERIFIED SUMMARY",
        "=" * 60,
        f"staged building-page links: {len(staged):,} | distinct buildings: {staged['bin'].nunique():,}",
        "buildings with documented records by stage: "
        + ", ".join(f"{c.replace('has_', '')} {int(tl[c].sum())}" for c in stage_cols),
    ]

    q2_coverage(tl, out, lines)
    q3_exterior_sequence(tl, out, lines)
    verify_sample(staged, tl, out)

    lines += [
        "",
        "METHODOLOGICAL SAFEGUARDS APPLIED:",
        "  1. Excluded 'ENTERED' data-entry stamps, 'BISPIQ' DOB printouts, and AI-guessed month-only titles from date timelines.",
        "  2. Classified stages at the page level so bundled demand letters (e.g., Page 2 after a survey form) are captured.",
        "  3. Omitted Q1 survival/Cox models and pre-inspection gap estimates, as missing field dates on visual survey forms prevent reliable time-to-first-inspection estimation.",
        "  4. 'No report in the records' reflects the released City archive, not proof that private testing never occurred.",
    ]
    (out / "summary.txt").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()