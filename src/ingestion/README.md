# Ingestion: from 911records.org to `data/final/`

This step builds the raw archive as a set of joinable tables. It collects the indexes that 911records.org has already built (entities, buildings, the browse tree, catalog changes), the metadata for every document page, one PDF per document, and the text of every page. Then it combines them into Parquet tables in `data/final/`.

The output is a faithful copy of the sources. Nothing is corrected or interpreted here; that happens in [`src/processing`](../processing/README.md).

## How to run

```bash
# system tools for text extraction
brew install poppler tesseract        # or: apt-get install poppler-utils tesseract-ocr
pip install -r requirements.txt
# put your contact e-mail in config.USER_AGENT first

# from the repo root, in this order:
python -m src.ingestion.scrape_site
python -m src.ingestion.scrape_docs          # or: ... scrape_docs 500   (random sample, seed 1007)
python -m src.ingestion.get_pdfs             # or: ... get_pdfs zips-only
python -m src.ingestion.extract_text
python -m src.ingestion.build_tables
```

Each step prints its progress and reads the output of the steps before it. Every step is resumable: stop it at any time and re-run it to continue where it left off. All settings live in the root [`config.py`](../../config.py). Edit that file, not the step scripts.

Before a full scrape, check the parsers on a few cached pages (for example, `parsers.parse_doc_page(html, url)`). If a field comes back empty, adjust `parsers.py` and re-run. Pages are cached, so a re-run costs no new requests.

## Files

| File | Role |
| --- | --- |
| `scrape_site.py` | Step 1: scrapes the site's indexes (entities, buildings, browse tree, changes, contradictions) |
| `scrape_docs.py` | Step 2: scrapes the metadata of every document page; `all_doc_ids()` is the master ID list |
| `get_pdfs.py` | Step 3: unzips bulk ZIPs and downloads missing PDFs from the City portal |
| `extract_text.py` | Step 4: page text through pdftotext, then Tesseract OCR, then the site as a fallback |
| `build_tables.py` | Step 5: merges the interim outputs into `data/final/` |
| `web.py` | Polite fetching: rate limit, `robots.txt`, retries, HTML cache |
| `parsers.py` | HTML → dict parsers for every page type (no downloading) |
| `files.py` | Append-as-you-go `.jsonl` and `*_done.txt` helpers that make steps resumable |

## Data sources

There are two sources, and each is read differently.

**1. [911records.org](https://911records.org) (independent mirror): scraped HTML.** The site has no public API, so `web.py` downloads the pages and `parsers.py` parses them with BeautifulSoup. Each parser tries several strategies per field (`<dl>`, `<table>`, `Label: value`, meta tags), so a small markup change does not silently empty a column.

| Page | What we get | Step |
| --- | --- | --- |
| `/entities/{type}` and `/entity/{type}/{slug}` | Agencies, labs, contractors, substances, addresses and signatories, plus every document page each one appears on | 1 |
| `/map` and `/building/{bin}` | Mapped buildings (BIN, class, floors, coordinates) and the pages that mention them | 1 |
| `/browse` | The archive tree (collections → boxes → documents), which gives every document ID | 1 |
| `/changes` and `/changes/{date}` | Which documents the City added or removed, by capture date | 1 |
| `/contradictions` | The site's curated contradiction examples | 1 |
| `/doc/{id}` and `/doc/{id}/p/{n}` | Each page's metadata: agency, box and folder, Bates range, title, dates, contaminants, OCR status | 2 |
| `/doc/{id}/p/{n}` (fallback only) | Text for a page that is still empty after pdftotext and OCR | 4 |

**2. [NYC 9/11 Document Portal](https://sept11documents.cityofnewyork.us) (official City copy): PDF downloads.** The City portal is the authoritative copy and is used only to download one PDF per document (`config.CITY_PDF_URL`).

**How we fetch (`web.py`).** The fetcher follows these rules:
- **Rate limit:** one request per second per host.
- **Rules:** `robots.txt` is checked before each fetch.
- **Identification:** requests carry an identifiable `USER_AGENT`.
- **Errors:** retries with exponential backoff, and `Retry-After` is honored on 429 and 5xx responses.
- **Cache:** every HTML page is saved gzipped in `data/raw/html/`, keyed by the SHA-1 of its URL, so nothing is fetched twice.
- **Human checks:** if the site shows one (Turnstile), the code raises an error and stops instead of trying to get around it.

## What the pipeline does, in order

### 1. Scrape the site's indexes: `scrape_site.py`
Five functions each walk one part of the site and write to `data/interim/`:
- `scrape_entities()` follows the `/entities/{type}` listings, including pagination, and then each entity's page at 50 records per page. It writes `entities.parquet` and `entity_mentions.jsonl` (entity × doc × page), and is resumable through `entity_done.txt`.
- `scrape_buildings()` reads every BIN from `/map`, then each `/building/{bin}` page. It writes `buildings.parquet` and `building_mentions.parquet` (bin × doc × page).
- `scrape_browse()` does a breadth-first walk over `/browse` → collections → boxes and writes `browse_docs.parquet`.
- `scrape_changes()` writes `catalog_changes.parquet`.
- `scrape_contradictions()` writes `contradictions.parquet`.

*Why:* this is the cheapest way to find out which documents exist. Together these tables produce the master list of `doc_id`s that every later step iterates over. The entity and building mentions are also the raw edges for the network analysis (RQ1) and the spatial analysis (RQ2), so no entity extraction of our own is needed.

### 2. Scrape document metadata: `scrape_docs.py`
For every known `doc_id`, this step fetches `/doc/{id}`, reads `n_pages`, then fetches `/doc/{id}/p/2 … n`. `parse_doc_page()` extracts collection, agency, box and folder, Bates range, title and description (with confidence), dates, contaminants, OCR status, and links to entities, buildings and PDFs. It writes one row per page to `docs.jsonl`.

A document is marked done in `docs_done.txt` only if **every** page succeeded. On restart, the step works out which pages are still missing from the rows already saved.

*Why:* the archival provenance (agency, box, folder), the site's dates and the contaminant tags exist only on these pages. Contaminants and OCR status are page-level, so we need every page, not just page 1.

### 3. Get the PDFs: `get_pdfs.py`
- `unzip_all()` unzips the bulk ZIPs you downloaded by hand from <https://911records.org/downloads> and put in `data/raw/zips/`. That page has a human check, so the download is done in a browser.
- `download_missing()` fetches every PDF that is still missing from the City portal. If step 2 ran on a sample, only that sample's PDFs are fetched.

PDFs are saved as `data/raw/pdfs/{6 digits}/{doc_id}.pdf`, in subfolders of about 1,000 files. Each destination path is rebuilt from the `doc_id`; paths inside a ZIP are never trusted.

*Why:* the PDFs are the primary source. ZIPs come first because they are much faster and put no load on the servers.

### 4. Extract page text: `extract_text.py`
This step runs in parallel (`TEXT_WORKERS` processes) and works through each PDF page by page:
1. **`pdftotext`** reads the embedded text layer. This is the same text the site shows, and it needs no web requests.
2. If the page has fewer than `MIN_CHARS` characters, it is a scanned image. The step renders it at 300 dpi and runs **Tesseract**, recording the mean word confidence.
3. If the page is still empty and `USE_SITE_FALLBACK` is on, the step fetches that one page's text from the site.

It writes `pages.jsonl` with the columns `doc_id, page, text, source (pdftotext | tesseract | site | none), ocr_confidence`, and is resumable through `text_done.txt`.

*Why:* the order goes from the cheapest and most faithful source to the network as a last resort. The `source` and `ocr_confidence` columns let the analysis filter or weight pages by text quality.

### 5. Build the final tables: `build_tables.py`
- **`documents`:** the union of every known ID, every scraped ID and every PDF on disk. Document-level fields come from `docs.jsonl`, taking the first value that is not a placeholder. The step also adds `site_date`, `bates_start`, `pdf_path`, `url`, and `removed`/`removed_date` (set when the last catalog change was a removal).
- **`pages`:** `pages.jsonl` plus `bates_page`, a date (from the page or its document) with `date_source`, and page-level site metadata (contaminants, OCR status, building BINs). Text that is still empty is filled from the site's OCR.
- **`entities`, `entity_mentions`, `buildings`, `building_mentions`, `catalog_changes`, `contradictions`:** from step 1, with mention rows deduplicated.

It finishes with sanity checks: mention rows that point to unknown documents, and duplicate `(doc_id, page)` rows.

*Why:* a single join key everywhere, `doc_id` (`NYC-WTC_#########`, which is also the first Bates number) plus `page`. Pages are cited by `bates_page`.

## Outputs (`data/final/`)
`documents`, `pages`, `entities`, `entity_mentions`, `buildings`, `building_mentions`, `catalog_changes`, `contradictions`. The join keys are `doc_id` + `page`, `entity_type` + `slug`, and `bin`.

Intermediate files are kept in `data/raw/html/` (cached HTML), `data/raw/zips/`, `data/raw/pdfs/`, and `data/interim/` (per-step outputs and `*_done.txt`). All of them are gitignored; only `data/final/` is committed.

## Full pipeline at a glance

```
scrape_site → scrape_docs → get_pdfs → extract_text → build_tables   (src/ingestion → data/final/)
          → clean                                                    (src/processing → data/processed/)
          → analysis (src/analysis/network, notebooks)
```