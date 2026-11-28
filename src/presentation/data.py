"""Data behind the interactive plots in the slides (components/*.vue), as small JSON files.

    python -m src.presentation.data     # after ingestion, processing and the network run

Every number is computed from the project's own tables, with the same rules and thresholds as the
reports, so the slides can't drift from the analysis. Writes outputs/figures/slides/*.json:

  pipeline.json             counts for each stage of the pipeline explorer
  code_map.json             lines of code per module, grouped by step and role
  cleaning.json             real before/after examples for each cleaning step, and the
                            usable-text distribution behind the threshold sliders
  connectors_by_month.json  organizations connecting beyond their volume, per month
  beyond_volume.json        raw vs beyond-volume betweenness percentile, per organization
  pages_vs_ties.json        pages naming each organization vs organizations tied to
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import config
from src.analysis.network import settings as net_settings
from src.analysis.network.figures import SHORT
from src.ingestion import verify as ingestion_verify
from src.processing import clean, settings as proc_settings

OUT = Path("outputs") / "figures" / "slides"
NET = net_settings.OUT
MIN_PAGES, Q = 20, 0.95      # same reporting thresholds as the network figures
BIN = 0.05                   # bin width of the usable-text distribution (alpha_ratio x word_ratio)

GROUP_KIND = {"municipal_regulatory": "City regulators", "city_other": "Other city agencies",
              "state_federal_regional": "State & federal", "private_real_estate": "Real estate",
              "public_health_advocacy": "Advocacy groups"}          # everything else: "Companies & others"


def write_json(data, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return path


def _kind(group: str) -> str:
    return GROUP_KIND.get(group, "Companies & others")


def _label(name: str) -> str:
    return SHORT.get(name, name)


# --- pipeline and code -------------------------------------------------------------------

def pipeline_numbers(raw_docs, raw_pages, entities, mentions, buildings, docs, pages) -> dict:
    """Counts shown in the pipeline explorer, one block per stage."""
    scraped = ingestion_verify.scraped(raw_docs)
    src = raw_pages["source"].value_counts()
    site, fixed = docs["site_date"].dt.normalize(), docs["doc_date"].dt.normalize()
    changed = ((site != fixed) & docs["doc_date"].notna()).sum() \
        + ((docs["date_fix"] == "raw date (conflicts with title)") & (site == fixed)).sum()   # filled, replaced or flagged
    return {
        "doc_ids": len(raw_docs), "documents": len(scraped), "pages": len(raw_pages),
        "entities": len(entities), "entity_links": len(mentions), "buildings": len(buildings),
        "pdftotext": int(src.get("pdftotext", 0)), "tesseract": int(src.get("tesseract", 0)),
        "site_text": int(src.get("site", 0)), "no_text": int(src.get("none", 0)),
        "ocr_conf_median": round(float(raw_pages["ocr_confidence"].median()), 0),
        "removed_docs": len(raw_docs) - len(docs), "dates_changed_or_flagged": int(changed),
        "usable_pages": int(pages["has_usable_text"].sum()), "clean_pages": len(pages),
    }


def code_map(root: Path = Path("src")) -> list[dict]:
    """Non-blank lines of every module, with its step and role."""
    role_of = {"settings.py": "settings", "figures.py": "figures", "verify.py": "checks", "checks.py": "checks"}
    out = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        step = "/".join(parts[:-1]) or "src"
        text = path.read_text(encoding="utf-8")
        out.append({"step": step, "module": path.stem, "role": role_of.get(path.name, "pipeline"),
                    "lines": sum(1 for line in text.splitlines() if line.strip()),
                    "functions": len(re.findall(r"^\s*def ", text, flags=re.M)),
                    "asserts": len(re.findall(r"^\s*assert ", text, flags=re.M))})
    return out


# --- cleaning examples -------------------------------------------------------------------

def _segments(text: str) -> list[dict]:
    """Split a raw page into kept text and the stamps the cleaning removes (for highlighting)."""
    patterns = [("header", clean.PORTAL_HEADER_RE), ("bates", clean.BATES_STAMP_RE),
                ("stamp", clean.LITIGATION_STAMP_RE)]
    spans = sorted((m.start(), m.end(), kind) for kind, rx in patterns for m in re.finditer(rx, text))
    out, pos = [], 0
    for start, end, kind in spans:
        if start < pos:
            continue
        if start > pos:
            out.append({"t": text[pos:start], "k": "keep"})
        out.append({"t": text[start:end], "k": kind})
        pos = end
    if pos < len(text):
        out.append({"t": text[pos:], "k": "keep"})
    return out


def cleaning_examples(raw_docs, raw_pages_text, docs, pages, removed, entities,
                      page_example, junk_example, date_examples) -> dict:
    """Real before/after examples for each cleaning step."""
    # 1. off-topic documents
    folders = removed["folder"].str.strip("“” ").value_counts().head(5)
    in_boxes = raw_docs["box"].isin(proc_settings.OFF_TOPIC_BOXES).sum()

    # 2. dates: one example per rule that changes a date
    examples = []
    for doc_id in date_examples:
        row = docs.set_index("doc_id").loc[doc_id]
        examples.append({"title": row["title"], "site": str(row["site_date"].date()),
                         "fixed": str(row["doc_date"].date()), "precision": row["date_precision"],
                         "rule": row["date_fix"]})

    # 3. page text: raw page with the removed stamps marked, and its cleaned version
    doc_id, page = page_example
    raw_text = raw_pages_text.loc[(doc_id, page)]
    cleaned = pages.set_index(["doc_id", "page"]).loc[(doc_id, page)]

    # 4. usable text: distribution of letters x words among pages long enough, and two examples
    long_enough = pages[pages["n_chars"] >= proc_settings.MIN_USABLE_CHARS]
    nb = int(round(1 / BIN))
    ai = np.minimum((long_enough["alpha_ratio"] / BIN).astype(int), nb - 1)
    wi = np.minimum((long_enough["word_ratio"] / BIN).astype(int), nb - 1)
    # ratios are stored rounded to 3 decimals, so a page just under a threshold can round onto it:
    # move those few pages one bin down, so the default thresholds reproduce has_usable_text exactly
    a0, w0 = round(proc_settings.MIN_ALPHA_RATIO / BIN), round(proc_settings.MIN_WORD_RATIO / BIN)
    off = ~long_enough["has_usable_text"] & (ai >= a0) & (wi >= w0)
    on_alpha_edge = (long_enough["alpha_ratio"] - proc_settings.MIN_ALPHA_RATIO).abs() < 1e-3
    ai = ai - (off & on_alpha_edge).astype(int)
    wi = wi - (off & ~on_alpha_edge).astype(int)
    grid = np.zeros((nb, nb), dtype=int)
    np.add.at(grid, (ai.to_numpy(), wi.to_numpy()), 1)

    def page_card(key, label):
        p = pages.set_index(["doc_id", "page"]).loc[key]
        return {"label": label, "doc_id": key[0], "page": int(key[1]), "text": p["text"][:420],
                "chars": int(p["n_chars"]), "alpha": float(p["alpha_ratio"]), "words": float(p["word_ratio"])}

    # 5. names: agencies and companies with several spellings
    def merges(kind, n):
        g = entities[entities["entity_type"] == kind].groupby("entity_id").agg(
            names=("name", list), entity_name=("entity_name", "first"), pages=("n_pages", "sum"))
        g = g[g["names"].map(len) >= 2].sort_values("pages", ascending=False).head(n)
        return [{"names": r.names, "into": r.entity_name} for r in g.itertuples()]

    agencies = entities[entities["entity_type"] == "agency"]
    companies = entities[entities["entity_type"] == "contractor"]
    return {
        "offtopic": {"in_boxes": int(in_boxes), "removed": len(removed), "kept": int(in_boxes - len(removed)),
                     "pages_removed": int(len(raw_pages_text) - len(pages)),
                     "boxes": list(proc_settings.OFF_TOPIC_BOXES),
                     "folders": [{"folder": f, "docs": int(n)} for f, n in folders.items()]},
        "dates": {"examples": examples, "filled": int((docs["site_date"].isna() & docs["doc_date"].notna()).sum()),
                  "replaced": int((docs["site_date"].notna() & docs["doc_date"].notna()
                                   & (docs["site_date"].dt.normalize() != docs["doc_date"].dt.normalize())).sum()),
                  "flagged": int(((docs["date_fix"] == "raw date (conflicts with title)")
                                  & (docs["site_date"].dt.normalize() == docs["doc_date"].dt.normalize())).sum()),
                  "undated_before": int(docs["site_date"].isna().sum()), "undated_after": int(docs["doc_date"].isna().sum())},
        "text": {"doc_id": doc_id, "page": int(page), "segments": _segments(raw_text), "cleaned": cleaned["text"],
                 "stamp": cleaned["litigation_stamp"], "source": cleaned["litigation_source"],
                 "stamped_docs_share": round(float(pages.groupby("doc_id")["litigation_source"]
                                                    .apply(lambda s: s.notna().any()).mean()), 3)},
        "usable": {"bin": BIN, "grid": grid.tolist(), "usable_pages": int(pages["has_usable_text"].sum()), "too_short": int(len(pages) - len(long_enough)),
                   "total": len(pages), "min_chars": proc_settings.MIN_USABLE_CHARS,
                   "alpha": proc_settings.MIN_ALPHA_RATIO, "words": proc_settings.MIN_WORD_RATIO,
                   "examples": [page_card(page_example, "letter from a contractor"),
                                page_card(junk_example, "instrument printout")]},
        "names": {"agency_names": len(agencies), "agencies": int(agencies["entity_id"].nunique()),
                  "company_names": len(companies), "companies": int(companies["entity_id"].nunique()),
                  "agency_examples": merges("agency", 4), "company_examples": merges("contractor", 3)},
    }


# --- network -----------------------------------------------------------------------------

def connectors_data(tm: pd.DataFrame, nodes: pd.DataFrame) -> list[dict]:
    """Per month: how many organizations connected beyond their volume, and which ones."""
    months = pd.period_range(net_settings.TEMPORAL_START, net_settings.TEMPORAL_END, freq="M")
    sig = tm[(tm["pages"] >= MIN_PAGES) & (tm["null_q_betweenness"] >= Q) & (tm["ratio_betweenness"] > 1)]
    sig = sig.merge(nodes[["node_id", "name", "group"]], on="node_id", how="left")
    out = []
    for m in months:
        rows = sig[sig["month"] == str(m)].sort_values("ratio_betweenness", ascending=False)
        out.append({"month": str(m), "label": m.strftime("%b %Y"), "count": len(rows),
                    "orgs": [{"name": _label(r.name), "kind": _kind(r.group), "ratio": round(r.ratio_betweenness, 1),
                              "pages": int(r.pages)} for r in rows.itertuples()]})
    return out


def beyond_volume_data(cmp: pd.DataFrame) -> list[dict]:
    """Every organization named on >= MIN_PAGES pages: raw vs beyond-volume betweenness percentile."""
    pop = cmp[(cmp["n_pages"] >= MIN_PAGES) & cmp["ratio_betweenness"].notna() & (cmp["betweenness"] > 0)].copy()
    pop["raw"] = pop["betweenness"].rank(pct=True) * 100
    pop["adj"] = pop["ratio_betweenness"].rank(pct=True) * 100
    return [{"name": _label(r.name), "kind": _kind(r.group), "raw": round(r.raw, 1), "adj": round(r.adj, 1),
             "ratio": round(r.ratio_betweenness, 2), "pages": int(r.n_pages)} for r in pop.itertuples()]


def pages_ties_data(nodes: pd.DataFrame) -> list[dict]:
    """Every organization of the main network with at least one tie: pages naming it vs organizations tied to."""
    d = nodes[nodes["degree"] > 0]
    return [{"name": _label(r.name), "kind": _kind(r.group), "pages": int(r.n_pages), "ties": int(r.degree)}
            for r in d.itertuples()]


# Examples shown in the cleaning explorer (chosen because each shows one fix clearly)
PAGE_EXAMPLE = ("NYC-WTC_000175521", 2)          # contractor letter: portal header, Bates and litigation stamps
JUNK_EXAMPLE = ("NYC-WTC_000176014", 1)          # instrument printout the site labels "junk"
DATE_EXAMPLES = ["NYC-WTC_000094809",            # lab-method date 1994 -> date in the title's month
                 "NYC-WTC_000093241",            # "since September 11, 2001" -> title month, Oct 2002
                 "NYC-WTC_000119105"]            # unset fax clock 1999-01-01 -> title month, Feb 2002


def main(page_example=PAGE_EXAMPLE, junk_example=JUNK_EXAMPLE, date_examples=DATE_EXAMPLES):
    F, P = config.FINAL, proc_settings.PROCESSED
    raw_docs = pd.read_parquet(F / "documents.parquet")
    raw_pages = pd.read_parquet(F / "pages.parquet", columns=["doc_id", "page", "text", "source", "ocr_confidence"])
    docs = pd.read_parquet(P / "documents.parquet")
    pages = pd.read_parquet(P / "pages.parquet", columns=["doc_id", "page", "text", "n_chars", "alpha_ratio", "word_ratio",
                                                          "has_usable_text", "litigation_stamp", "litigation_source"])
    entities = pd.read_parquet(P / "entities.parquet")
    print(write_json(pipeline_numbers(raw_docs, raw_pages, pd.read_parquet(F / "entities.parquet"),
                                      pd.read_parquet(F / "entity_mentions.parquet", columns=["doc_id"]),
                                      pd.read_parquet(F / "buildings.parquet", columns=["bin"]), docs, pages),
                     "pipeline.json"))
    print(write_json(code_map(), "code_map.json"))
    raw_text = raw_pages.set_index(["doc_id", "page"])["text"]
    print(write_json(cleaning_examples(raw_docs, raw_text, docs, pages,
                                       pd.read_parquet(P / "removed_documents.parquet"), entities,
                                       page_example, junk_example, date_examples), "cleaning.json"))
    nodes, cmp = pd.read_csv(NET / "nodes_main.csv"), pd.read_csv(NET / "null_global_nodes.csv")
    tm = pd.read_csv(NET / f"temporal_{net_settings.TEMPORAL_NULL_SAMPLES}.csv")
    print(write_json(connectors_data(tm, nodes), "connectors_by_month.json"))
    print(write_json(beyond_volume_data(cmp), "beyond_volume.json"))
    print(write_json(pages_ties_data(nodes), "pages_vs_ties.json"))


if __name__ == "__main__":
    main()
