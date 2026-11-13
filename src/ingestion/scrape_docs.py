"""Scrape document metadata and all pages on 911records.org.

Works from scratch (fetching page 1 first to discover n_pages) or resumes
an existing scrape by reading data/interim/docs.jsonl to calculate missing pages.
Includes retry logic and prevents marking incomplete documents as done on failure.
"""
import json
import random
import sys
import time
from collections import defaultdict

import config
from src.ingestion import parsers as P
from src.ingestion.files import append_rows, done_keys, mark_done, read_table


def all_doc_ids():
    I = config.INTERIM
    ids = set()
    for f in ("browse_docs.parquet", "entity_mentions.jsonl", "building_mentions.parquet",
              "catalog_changes.parquet", "contradictions.parquet"):
        ids |= set(read_table(I / f).get("doc_id", []))
    if config.MANIFEST.exists():
        ids |= set(P.DOC_ID_RE.findall(config.MANIFEST.read_text()))
    return sorted(i for i in ids if isinstance(i, str) and P.DOC_ID_RE.fullmatch(i))


def fetch_with_retry(get_page_fn, url, retries=3, backoff=2.0):
    """Fetch a URL with exponential backoff retries on failure."""
    for attempt in range(1, retries + 1):
        try:
            html = get_page_fn(url)
            if html:
                return html
        except Exception as e:
            print(f"    [Warning] Error fetching {url} (attempt {attempt}/{retries}): {e}")
        
        if attempt < retries:
            time.sleep(backoff * attempt)
            
    print(f"    [Failed] Could not fetch {url} after {retries} attempts.")
    return None


def run(sample=None):
    print("Scraping document metadata and missing pages...")
    from src.ingestion.web import get_page

    docs_path = config.INTERIM / "docs.jsonl"
    done_path = config.INTERIM / "docs_done.txt"
    fully_done = done_keys(done_path)

    # 1. Track pages already scraped if docs.jsonl exists
    doc_pages_done = defaultdict(set)
    doc_total_pages = {}

    if docs_path.exists():
        with open(docs_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                doc_id = row.get("doc_id")
                page_num = row.get("page", 1)

                if doc_id:
                    doc_pages_done[doc_id].add(page_num)
                    if row.get("n_pages"):
                        doc_total_pages[doc_id] = row["n_pages"]

    # 2. Build the todo list across ALL known document IDs
    todo = []
    for doc_id in all_doc_ids():
        if doc_id in fully_done:
            continue

        # Case A: Page 1 hasn't been scraped yet (we don't know n_pages yet)
        if 1 not in doc_pages_done[doc_id]:
            todo.append({"doc_id": doc_id, "needs_p1": True, "missing_pages": []})

        # Case B: Page 1 is scraped; check if pages 2..n_pages are missing
        else:
            n_pages = doc_total_pages.get(doc_id, 1)
            if isinstance(n_pages, int) and n_pages > 1:
                expected_pages = set(range(2, n_pages + 1))
                missing_pages = sorted(list(expected_pages - doc_pages_done[doc_id]))
                if missing_pages:
                    todo.append({"doc_id": doc_id, "needs_p1": False, "missing_pages": missing_pages})
                else:
                    # All pages are already present; mark fully done
                    mark_done(done_path, [doc_id])
            else:
                mark_done(done_path, [doc_id])

    if sample and sample < len(todo):
        todo = sorted(random.Random(1007).sample(todo, sample))

    known_missing = sum(len(item["missing_pages"]) + (1 if item["needs_p1"] else 0) for item in todo)
    print(f"  {len(todo)} documents to process (at least {known_missing} pages queued)")

    # 3. Fetch Page 1 (if needed) and any missing subsequent pages
    pages_processed = 0
    failed_docs = 0

    for i, item in enumerate(todo, 1):
        doc_id = item["doc_id"]
        missing = list(item["missing_pages"])
        all_ok = True

        # Fetch Page 1 first if missing, then dynamically queue pages 2..n_pages
        if item["needs_p1"]:
            url = f"{config.SITE}/doc/{doc_id}"
            html = fetch_with_retry(get_page, url)
            if html:
                row = P.parse_doc_page(html, url)
                row["doc_id"] = row["doc_id"] or doc_id
                row["page"] = 1
                if "ocr_text" in row:
                    row["ocr_text_page1"] = row.pop("ocr_text")

                append_rows(docs_path, [row])
                pages_processed += 1

                # Calculate remaining pages from the freshly scraped metadata
                n_pages = row.get("n_pages", 1)
                if isinstance(n_pages, int) and n_pages > 1:
                    expected_pages = set(range(2, n_pages + 1))
                    missing = sorted(list(expected_pages - doc_pages_done[doc_id]))
            else:
                all_ok = False

        # Fetch remaining pages (2..n_pages)
        for p in missing:
            page_url = f"{config.SITE}/doc/{doc_id}/p/{p}"
            page_html = fetch_with_retry(get_page, page_url)

            if page_html:
                page_row = P.parse_doc_page(page_html, page_url)
                page_row["doc_id"] = page_row["doc_id"] or doc_id
                page_row["page"] = p

                if "ocr_text" in page_row:
                    page_row[f"ocr_text_page{p}"] = page_row.pop("ocr_text")

                append_rows(docs_path, [page_row])
                pages_processed += 1
            else:
                all_ok = False

        # Only mark document complete if EVERY page succeeded
        if all_ok:
            mark_done(done_path, [doc_id])
        else:
            failed_docs += 1

        if i % 200 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} docs ({pages_processed} pages fetched, {failed_docs} incomplete)")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else None)
