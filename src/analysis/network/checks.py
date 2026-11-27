"""Data checks behind the network: coverage, keys, joins, unit sizes, dates, extraction caveats."""
import numpy as np
import pandas as pd

from src.analysis.network import build


def key_checks(t: dict) -> pd.DataFrame:
    """Uniqueness of primary keys and completeness of the mention -> page -> document joins."""
    em, pages, docs, ents = t["entity_mentions"], t["pages"], t["documents"], t["entities"]
    page_keys = pd.MultiIndex.from_frame(pages[["doc_id", "page"]])
    rows = [
        ("documents: duplicate doc_id", int(docs["doc_id"].duplicated().sum())),
        ("pages: duplicate (doc_id, page)", int(pages.duplicated(["doc_id", "page"]).sum())),
        ("entities: duplicate (source_type, slug)", int(ents.duplicated(["source_type", "slug"]).sum())),
        ("entity_mentions: duplicate (source_type, slug, doc_id, page)",
         int(em.duplicated(["source_type", "slug", "doc_id", "page"]).sum())),
        ("entity_mentions: duplicate (entity_type, entity_id, doc_id, page) after entity_id merge",
         int(em.duplicated(["entity_type", "entity_id", "doc_id", "page"]).sum())),
        ("entity_mentions: missing entity_id", int(em["entity_id"].isna().sum())),
        ("entity_mentions: doc_id not in documents", int((~em["doc_id"].isin(docs["doc_id"])).sum())),
        ("entity_mentions: (doc_id, page) not in pages",
         int((~pd.MultiIndex.from_frame(em[["doc_id", "page"]]).isin(page_keys)).sum())),
        ("entity_id values shared by >1 entity_type",
         int((ents.groupby("entity_id")["entity_type"].nunique() > 1).sum())),
    ]
    return pd.DataFrame(rows, columns=["check", "count"])


def entity_type_overview(t: dict) -> pd.DataFrame:
    """Per entity type: distinct entity_ids, deduplicated mention pages and documents."""
    em = t["entity_mentions"].drop_duplicates(["entity_type", "entity_id", "doc_id", "page"])
    out = em.groupby("entity_type").agg(entity_ids=("entity_id", "nunique"), mention_pages=("page", "size"),
                                        docs=("doc_id", "nunique")).reset_index()
    out["in_network"] = out["entity_type"].isin(["agency", "contractor", "lab"])
    return out


def unit_size_distribution(om: pd.DataFrame) -> pd.DataFrame:
    """Quantiles of organizations per page and per document, and share of pairs from the largest units."""
    rows = []
    for unit in ("page", "doc"):
        s = build.unit_sizes(om, unit)
        pairs = s * (s - 1) / 2
        top1 = pairs.sort_values(ascending=False).head(max(1, int(len(s) * 0.01))).sum() / pairs.sum()
        rows.append({"unit": unit, "units_with_org": len(s), "units_with_2plus": int((s >= 2).sum()),
                     "median_orgs": s.median(), "p90": s.quantile(.9), "p99": s.quantile(.99),
                     "p99_of_2plus": s[s >= 2].quantile(.99), "max": int(s.max()),
                     "pairs_total": int(pairs.sum()), "share_pairs_from_top1pct_units": top1})
    return pd.DataFrame(rows)


def largest_units(om: pd.DataFrame, docs: pd.DataFrame, unit: str = "page", n: int = 15) -> pd.DataFrame:
    """The n pages (or documents) naming the most organizations, with title, date and box for manual review."""
    s = build.unit_sizes(om, unit).sort_values(ascending=False).head(n).reset_index()
    return s.merge(docs[["doc_id", "title", "doc_date", "box"]], on="doc_id", how="left")


def date_coverage(om: pd.DataFrame, docs: pd.DataFrame) -> dict:
    """Date coverage of the documents that name a kept organization, with explicit denominators.

    share_*_of_all uses every such document (undated ones count as 'no'); share_*_of_dated uses
    only documents with a doc_date. The study window comes from src/processing/settings.py.
    """
    d = docs[docs["doc_id"].isin(om["doc_id"])]
    dated = d[d["doc_date"].notna()]
    year = dated["doc_date"].dt.year
    in_window = dated["in_study_window"].astype(bool)
    return {"docs_with_org": len(d), "docs_dated": len(dated),
            "share_dated_of_all": len(dated) / len(d),
            "docs_in_study_window": int(in_window.sum()),
            "share_in_window_of_all": in_window.sum() / len(d),
            "share_in_window_of_dated": in_window.mean(),
            "docs_before_2001_09_11": int((dated["doc_date"] < "2001-09-11").sum()),
            "docs_1997_2000": int(year.between(1997, 2000).sum()),
            "docs_before_1997": int((year < 1997).sum()),
            "docs_after_2009": int((year > 2009).sum()),
            "share_2001_2002_of_dated": year.isin([2001, 2002]).mean(),
            "doc_date_min": dated["doc_date"].min(), "doc_date_max": dated["doc_date"].max(),
            "date_precision_counts": d["date_precision"].value_counts(dropna=False).to_dict(),
            "date_fix_counts": d["date_fix"].value_counts().to_dict()}


def date_period(docs: pd.DataFrame) -> pd.Series:
    """Per doc_id: 'undated', 'before 2001-09-11', 'study window' or 'after study window'."""
    d = docs.set_index("doc_id")
    out = pd.Series("after study window", index=d.index)
    out[d["doc_date"] < "2001-09-11"] = "before 2001-09-11"
    out[d["in_study_window"].astype(bool)] = "study window"
    out[d["doc_date"].isna()] = "undated"
    return out


def date_extremes(om: pd.DataFrame, docs: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The n earliest and n latest dated documents that name a kept organization, for manual review.

    doc_date_raw (all raw dates the site found) and date_fix (which cleaning rule applied) show whether an
    extreme date is the document's own date or a parse / OCR error.
    """
    cols = ["doc_id", "doc_date", "date_precision", "date_fix", "title", "doc_date_raw", "agency", "box"]
    d = docs[docs["doc_id"].isin(om["doc_id"]) & docs["doc_date"].notna()].sort_values("doc_date")
    cols = [c for c in cols if c in d.columns]
    return pd.concat([d.head(n)[cols].assign(end="earliest"), d.tail(n)[cols].assign(end="latest")],
                     ignore_index=True)


def evidence_by_period(evidence: pd.DataFrame, docs: pd.DataFrame) -> pd.DataFrame:
    """Share of the network's pair evidence (one row per pair x page) by the period of its document."""
    period = evidence["doc_id"].map(date_period(docs))
    out = period.value_counts().rename("pair_evidence_rows").reset_index()
    out["share"] = out["pair_evidence_rows"] / len(evidence)
    return out.rename(columns={"doc_id": "period", "index": "period"})


def source_bias(om: pd.DataFrame, docs: pd.DataFrame) -> pd.DataFrame:
    """Which agency's files the organization documents come from (archive provenance)."""
    d = docs[docs["doc_id"].isin(om["doc_id"])]
    out = d["agency"].fillna("(missing)").value_counts().rename("docs").reset_index()
    out["share"] = out["docs"] / out["docs"].sum()
    return out


def citation_share(om: pd.DataFrame, pages_text: pd.DataFrame, node_ids) -> pd.DataFrame:
    """Share of an agency's pages whose text also contains a method / regulation citation pattern."""
    pt = pages_text.set_index(["doc_id", "page"])["text"].fillna("").str.lower()
    rows = []
    for nid in node_ids:
        keys = pd.MultiIndex.from_frame(om.loc[om["node_id"] == nid, ["doc_id", "page"]])
        t = pt.loc[keys]
        rows.append({"node_id": nid, "pages": len(t),
                     "share_pages_with_citation_pattern": t.str.contains(build.CITATION_PATTERN, regex=True).mean()})
    return pd.DataFrame(rows)


def text_vs_entity_recall(pages_text: pd.DataFrame, om: pd.DataFrame) -> pd.DataFrame:
    """Docs where a name appears in text vs docs where the extractor tagged it (illustrative)."""
    probes = {"company:silverstein-properties": r"silverstein", "company:rockrose-development": r"rockrose",
              "agency:red-cross": r"red cross"}
    low = pages_text["text"].fillna("").str.lower()
    rows = []
    for nid, pat in probes.items():
        text_docs = pages_text.loc[low.str.contains(pat, regex=True), "doc_id"].nunique()
        ent_docs = om.loc[om["node_id"] == nid, "doc_id"].nunique()
        rows.append({"node_id": nid, "pattern": pat, "docs_text_match": text_docs, "docs_entity_tagged": ent_docs,
                     "ratio_tagged_to_text": ent_docs / text_docs if text_docs else np.nan})
    return pd.DataFrame(rows)
