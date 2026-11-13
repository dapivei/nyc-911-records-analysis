# """Scrape each document's page on 911records.org for its metadata.

# Gets data/interim/docs.jsonl: collection, agency, box/folder, Bates range,
# page count, plus the site's machine-extracted title, document type and date.

# Document ids come from step 1 (browse, entity and building mentions,
# catalog changes) and from data/raw/manifest.json if you downloaded it.

# 64,385 documents at 1 request/second is about 18 hours, so try a sample first:
#     python -m pipeline.scrape_docs 500
# Resumable: finished ids are in docs_done.txt.
# """
# import json
# import random
# import sys

# import config
# from pipeline import parsers as P
# from pipeline.files import append_rows, done_keys, mark_done, read_table


# def all_doc_ids():
#     I = config.INTERIM
#     ids = set()
#     for f in ("browse_docs.parquet", "entity_mentions.jsonl", "building_mentions.parquet",
#               "catalog_changes.parquet", "contradictions.parquet"):
#         ids |= set(read_table(I / f).get("doc_id", []))
#     if config.MANIFEST.exists():  # optional: the full inventory from /downloads
#         ids |= set(P.DOC_ID_RE.findall(config.MANIFEST.read_text()))
#     return sorted(i for i in ids if isinstance(i, str) and P.DOC_ID_RE.fullmatch(i))


# def run(sample=None):
#     print("Scrape document metadata")
#     from pipeline.web import get_page

#     done = done_keys(config.INTERIM / "docs_done.txt")
#     todo = [d for d in all_doc_ids() if d not in done]
#     if sample and sample < len(todo):
#         todo = sorted(random.Random(1007).sample(todo, sample))
#     print(f"  {len(todo)} documents to fetch ({len(done)} done)")
#     for i, doc_id in enumerate(todo, 1):
#         url = f"{config.SITE}/doc/{doc_id}"
#         html = get_page(url)
#         if html:
#             row = P.parse_doc_page(html, url)
#             row["doc_id"] = row["doc_id"] or doc_id
#             row["ocr_text_page1"] = row.pop("ocr_text")
#             append_rows(config.INTERIM / "docs.jsonl", [row])
#         mark_done(config.INTERIM / "docs_done.txt", [doc_id])
#         if i % 200 == 0:
#             print(f"  {i}/{len(todo)}")
# if __name__ == "__main__":
#     run(int(sys.argv[1]) if len(sys.argv) > 1 else None)
    
"""Scrape missing document pages on 911records.org for their metadata.

Reads data/interim/docs.jsonl to determine which pages have already been
scraped for each document, calculates the missing pages based on n_pages, 
and fetches only the remaining pages with periodic progress updates.
"""
import json
import random
import sys
from collections import defaultdict

import config
from pipeline import parsers as P
from pipeline.files import append_rows, done_keys, mark_done, read_table


def all_doc_ids():
    I = config.INTERIM
    ids = set()
    for f in ("browse_docs.parquet", "entity_mentions.jsonl", "building_mentions.parquet",
              "catalog_changes.parquet", "contradictions.parquet"):
        ids |= set(read_table(I / f).get("doc_id", []))
    if config.MANIFEST.exists():
        ids |= set(P.DOC_ID_RE.findall(config.MANIFEST.read_text()))
    return sorted(i for i in ids if isinstance(i, str) and P.DOC_ID_RE.fullmatch(i))


def run(sample=None):
    print("Scraping missing document pages...")
    from pipeline.web import get_page

    # 1. Track exactly which pages we already have for each document
    doc_pages_done = defaultdict(list)
    doc_total_pages = {}

    with open(config.INTERIM / "docs.jsonl", "r") as f:
        for line in f:
            row = json.loads(line)
            doc_id = row.get("doc_id")
            page_num = row.get("page", 1) 
            
            if doc_id:
                doc_pages_done[doc_id].append(page_num)
                if row.get("n_pages"):
                    doc_total_pages[doc_id] = row["n_pages"]

    # 2. Figure out exactly which pages are missing
    todo = []
    for doc_id, n_pages in doc_total_pages.items():
        if isinstance(n_pages, int) and n_pages > 1:
            completed_pages = set(doc_pages_done[doc_id])
            expected_pages = set(range(2, n_pages + 1))
            
            missing_pages = sorted(list(expected_pages - completed_pages))
            
            if missing_pages:
                todo.append({"doc_id": doc_id, "missing_pages": missing_pages})
    
    if sample and sample < len(todo):
        todo = sorted(random.Random(1007).sample(todo, sample))

    total_missing_pages = sum(len(item["missing_pages"]) for item in todo)
    print(f"  {len(todo)} documents to process ({total_missing_pages} total missing pages)")

    # 3. Fetch missing pages with periodic progress updates
    pages_processed = 0

    for i, item in enumerate(todo, 1):
        doc_id = item["doc_id"]
        missing = item["missing_pages"]
        
        for p in missing:
            page_url = f"{config.SITE}/doc/{doc_id}/p/{p}"
            page_html = get_page(page_url)
            
            if page_html:
                page_row = P.parse_doc_page(page_html, page_url)
                page_row["doc_id"] = page_row["doc_id"] or doc_id
                
                if "ocr_text" in page_row:
                    page_row[f"ocr_text_page{p}"] = page_row.pop("ocr_text")
                    
                append_rows(config.INTERIM / "docs.jsonl", [page_row])
                pages_processed += 1

        if i % 200 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} docs ({pages_processed}/{total_missing_pages} pages finished)")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else None)