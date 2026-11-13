"""Combine everything into clean, joinable tables in data/final/.

  documents          one row per document (metadata, dates, removed?, PDF path)
  pages              one row per page (text, Bates page ID, best date, OCR/scraped page metadata)
  entities           agencies, labs, contractors, substances, addresses
  entity_mentions    entity x page                  -> network analysis
  buildings          building facts
  building_mentions  building x page                -> spatial analysis
  catalog_changes, contradictions                   (from step 1)

Join keys: doc_id (e.g. NYC-WTC_000104027) and page. Cite pages by bates_page.

Run alone:  python -m src.ingestion.build_tables
"""
import pandas as pd

import config
from src.ingestion.files import read_table
from src.ingestion.text_tools import parse_site_date

I, F = config.INTERIM, config.FINAL

DOC_LEVEL_COLS = [
    "doc_id", "n_pages", "collection", "agency", "production_volume",
    "box", "folder", "folder_label", "bates_range", "file_size",
    "title", "title_confidence", "description", "doc_type",
    "doc_type_confidence", "doc_date_raw", "pdf_links",
]

PAGE_LEVEL_COLS = [
    "doc_id", "page", "url", "contaminants", "ocr_status",
    "ocr_source", "entity_links", "building_bins",
]


def _load_raw_docs():
    docs = read_table(I / "docs.jsonl")
    if docs.empty:
        return docs
    # Drop dynamic sparse columns: ocr_text_page1, ocr_text_page2, ..., ocr_text_pageN
    ocr_cols = [c for c in docs.columns if c.startswith("ocr_text_page")]
    docs = docs.drop(columns=ocr_cols, errors="ignore")
    if "page" in docs.columns:
        docs = docs.sort_values(["doc_id", "page"])
    return docs


def build_documents(raw_docs):
    from src.ingestion.scrape_docs import all_doc_ids

    pdfs = {p.stem: str(p) for p in config.PDFS.rglob("*.pdf")}
    ids = sorted(set(all_doc_ids()) | set(raw_docs.get("doc_id", [])) | set(pdfs))
    df = pd.DataFrame({"doc_id": ids})

    if len(raw_docs):
        doc_cols = [c for c in DOC_LEVEL_COLS if c in raw_docs.columns]
        # Replace em-dash placeholders ("—") with None so .first() prefers real values if present
        cleaned = raw_docs[doc_cols].replace("\u2014", pd.NA)
        docs_dedup = cleaned.groupby("doc_id", as_index=False).first()
        df = df.merge(docs_dedup, on="doc_id", how="left")

    df["site_date"] = df.get("doc_date_raw", pd.Series(index=df.index, dtype=object)).map(parse_site_date)
    df["bates_start"] = df.doc_id.str[8:].astype(int)
    df["pdf_path"] = df.doc_id.map(pdfs)
    df["url"] = config.SITE + "/doc/" + df.doc_id

    changes = read_table(I / "catalog_changes.parquet")
    df["removed"] = False
    if len(changes):                    # removed = last recorded change for the doc is a removal
        last = changes.sort_values("capture_date").groupby("doc_id").tail(1)
        removed = last[last.change == "removed"].set_index("doc_id").capture_date
        df["removed"] = df.doc_id.isin(removed.index)
        df["removed_date"] = pd.to_datetime(df.doc_id.map(removed))

    keep = [
        "doc_id", "bates_start", "bates_range", "n_pages", "file_size",
        "collection", "agency", "production_volume", "box", "folder", "folder_label",
        "title", "title_confidence", "description", "doc_type", "doc_type_confidence",
        "site_date", "doc_date_raw", "removed", "removed_date", "pdf_path", "pdf_links", "url",
    ]
    return df[[c for c in keep if c in df]]


def build_pages(documents, raw_docs):
    pages = read_table(I / "pages.jsonl")
    if pages.empty:
        return pages

    pages["bates_page"] = "NYC-WTC_" + (pages.doc_id.str[8:].astype(int) + pages.page - 1).astype(str).str.zfill(9)
    site_date = documents.set_index("doc_id").site_date

    if "page_date" in pages.columns:
        pages["date"] = pages.page_date.fillna(pages.doc_id.map(site_date))
        pages["date_source"] = pages.page_date.notna().map({True: "page", False: "document"})
    else:
        pages["date"] = pages.doc_id.map(site_date)
        pages["date_source"] = "document"
    pages.loc[pages.date.isna(), "date_source"] = "none"

    # Attach page-level scraped metadata from docs.jsonl if available
    if len(raw_docs) and {"doc_id", "page"}.issubset(raw_docs.columns):
        p_cols = [c for c in PAGE_LEVEL_COLS if c in raw_docs.columns and (c not in pages.columns or c in ("doc_id", "page"))]
        page_meta = raw_docs[p_cols].drop_duplicates(["doc_id", "page"], keep="last")
        pages = pages.merge(page_meta, on=["doc_id", "page"], how="left")

        # Fill missing text from scraped_ocr_text if present
        if "text" in pages.columns and "scraped_ocr_text" in pages.columns:
            pages["text"] = pages["text"].fillna(pages["scraped_ocr_text"])

    return pages


def build_buildings():
    b = read_table(I / "buildings.parquet")
    if b.empty:
        return b
    b["bin"] = b["bin"].astype(str)
    b["building_class_code"] = b.get("building_class", pd.Series(dtype=str)).astype(str).str.extract(r"\(([A-Z]\d?)\)")[0]
    return b


def run():
    print("Build final tables")
    raw_docs = _load_raw_docs()
    documents = build_documents(raw_docs)
    tables = {
        "documents": documents,
        "pages": build_pages(documents, raw_docs),
        "entities": read_table(I / "entities.parquet").drop(columns=["row_text"], errors="ignore"),
        "entity_mentions": (
            read_table(I / "entity_mentions.jsonl").drop_duplicates(["entity_type", "slug", "doc_id", "page"])
            if (I / "entity_mentions.jsonl").exists()
            else pd.DataFrame()
        ),
        "buildings": build_buildings(),
        "building_mentions": read_table(I / "building_mentions.parquet").drop_duplicates(["bin", "doc_id", "page"]),
        "catalog_changes": read_table(I / "catalog_changes.parquet"),
        "contradictions": read_table(I / "contradictions.parquet"),
    }

    for name, df in tables.items():
        if df is None or df.empty:
            print(f"  {name:<18} (empty - its step hasn't run yet)")
            continue
        df.to_parquet(F / f"{name}.parquet", index=False)
        print(f"  {name:<18} {len(df):>9,} rows")

    # quick sanity checks
    known = set(documents.doc_id)
    for name in ("pages", "entity_mentions", "building_mentions"):
        df = tables[name]
        if len(df):
            missing = (~df.doc_id.isin(known)).sum()
            if missing:
                print(f"  CHECK: {missing} rows in {name} point to unknown documents")
    if len(tables["pages"]) and tables["pages"].duplicated(["doc_id", "page"]).any():
        print("  CHECK: duplicate pages found")
    print(f"  saved to {F}/ (parquet)")


if __name__ == "__main__":
    run()