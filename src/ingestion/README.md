# Ingestion: from 911records.org to `data/final/`

This step builds the raw archive as a set of joinable tables. It collects the indexes that 911records.org has already built (entities, buildings, the browse tree, catalog changes), the metadata of every document page, one PDF per document, and the text of every page, and combines them into Parquet tables in `data/final/`.

The output is a faithful copy of the sources. Nothing is corrected or interpreted here; that happens in [`src/processing`](../processing/README.md).

What the archive contains, how complete our copy is, the known issues and the data dictionary are in [`docs/00.ingestion_report.md`](../../docs/00.ingestion_report.md). The walkthrough is [`notebooks/00.data_ingestion.ipynb`](../../notebooks/00.data_ingestion.ipynb).

## How to run

**Most people only need the committed tables:**

```bash
git lfs pull                          # data/final/*.parquet (about 180 MB)
python -m src.ingestion.verify        # checks; ends with "all checks passed (known issues listed above)"
python -m src.ingestion.figures       # figures for the report, in outputs/figures/ingestion/
```

**Re-running the scrape** (hours: one request per second):

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
python -m src.ingestion.verify
```

Each step prints its progress and reads the output of the steps before it. Every step is resumable: stop it and re-run it to continue where it left off. All settings live in the root [`config.py`](../../config.py); edit that file, not the step scripts.

Before a full scrape, check the parsers on a few cached pages (for example, `parsers.parse_doc_page(html, url)`). If a field comes back empty, adjust `parsers.py` and re-run. Pages are cached, so a re-run costs no new requests.

## Files

| File | Role |
| --- | --- |
| `scrape_site.py` | Step 1: the site's indexes (entities, buildings, browse tree, changes, contradictions) |
| `scrape_docs.py` | Step 2: the metadata of every document page; `all_doc_ids()` is the master ID list |
| `get_pdfs.py` | Step 3: unzips bulk ZIPs and downloads missing PDFs from the City portal |
| `extract_text.py` | Step 4: page text through pdftotext, then Tesseract OCR, then the site as a fallback |
| `build_tables.py` | Step 5: merges the interim outputs into `data/final/` |
| `web.py` | Polite fetching: rate limit, `robots.txt`, retries, HTML cache |
| `parsers.py` | HTML → dict parsers for every page type (no downloading) |
| `files.py` | Append-as-you-go `.jsonl` and `*_done.txt` helpers that make steps resumable |
| `verify.py` | Checks on `data/final/`: keys, completeness, joins, counts against the site's own totals, known issues |
| `figures.py` | Figures I1–I2 for the report (static PNG) |

## Data sources

**1. [911records.org](https://911records.org) (independent mirror): scraped HTML.** The site has no public API, so `web.py` downloads the pages and `parsers.py` parses them with BeautifulSoup. Each parser tries several strategies per field (`<dl>`, `<table>`, `Label: value`, meta tags), so a small markup change does not silently empty a column.

| Page | What we get | Step |
| --- | --- | --- |
| `/entities/{type}` and `/entity/{type}/{slug}` | Agencies, labs, contractors, substances, addresses and signatories, and every page each one appears on | 1 |
| `/map` and `/building/{bin}` | Mapped buildings (BIN, class, floors, coordinates) and the pages that mention them | 1 |
| `/browse` | The archive tree (collections → boxes → documents), which gives document IDs | 1 |
| `/changes` and `/changes/{date}` | Which documents the City added, changed or removed, by capture date | 1 |
| `/contradictions` | The site's curated contradiction examples | 1 |
| `/doc/{id}` and `/doc/{id}/p/{n}` | Each page's metadata: agency, box and folder, Bates range, title, dates, contaminants, OCR status, building links | 2 |
| `/doc/{id}/p/{n}` (fallback only) | Text for a page still empty after pdftotext and OCR | 4 |

**2. [NYC 9/11 Document Portal](https://sept11documents.cityofnewyork.us) (official City copy): PDF downloads**, one per document (`config.CITY_PDF_URL`).

**How we fetch (`web.py`):** one request per second per host; `robots.txt` checked before each fetch; an identifiable `USER_AGENT`; retries with exponential backoff, honoring `Retry-After` on 429 and 5xx; every HTML page cached gzipped in `data/raw/html/` (keyed by the SHA-1 of its URL), so nothing is fetched twice. If the site shows a human check (Turnstile), the code stops instead of trying to get around it.

## What the pipeline does, in order

### 1. Scrape the site's indexes: `scrape_site.py`
Five functions each walk one part of the site and write to `data/interim/`:
* `scrape_entities()`: the `/entities/{type}` listings (with pagination), then each entity's page, 50 records per page → `entities.parquet`, `entity_mentions.jsonl` (entity × doc × page). Resumable through `entity_done.txt`.
* `scrape_buildings()`: every BIN from `/map`, then each `/building/{bin}` → `buildings.parquet`, `building_mentions.parquet` (bin × doc × page).
* `scrape_browse()`: breadth-first walk over `/browse` → collections → boxes → `browse_docs.parquet`.
* `scrape_changes()` → `catalog_changes.parquet`; `scrape_contradictions()` → `contradictions.parquet`.

Together these give the master list of `doc_id`s that every later step iterates over. The entity and building mentions are also the raw links for the network and spatial analyses, so no entity extraction of our own is needed.

### 2. Scrape document metadata: `scrape_docs.py`
For every known `doc_id`: fetch `/doc/{id}`, read `n_pages`, then fetch `/doc/{id}/p/2 … n`. `parse_doc_page()` extracts collection, agency, box and folder, Bates range, title and description, dates, contaminants, OCR status, and links to entities, buildings and PDFs → one row per page in `docs.jsonl`. A document is marked done in `docs_done.txt` only if **every** page succeeded; on restart, the missing pages are worked out from the rows already saved.

Contaminants, OCR status and building links are page-level, so every page is needed, not just page 1.

### 3. Get the PDFs: `get_pdfs.py`
* `unzip_all()` unzips the bulk ZIPs downloaded by hand from <https://911records.org/downloads> into `data/raw/zips/` (that page has a human check, so the download is done in a browser).
* `download_missing()` fetches every PDF still missing from the City portal (only the sample's, if step 2 ran on a sample).

PDFs are saved as `data/raw/pdfs/{6 digits}/{doc_id}.pdf`. Each path is rebuilt from the `doc_id`; paths inside a ZIP are never trusted.

### 4. Extract page text: `extract_text.py`
In parallel (`TEXT_WORKERS` processes), page by page:
1. **`pdftotext`** reads the embedded text layer (the same text the site shows; no web requests).
2. A page with fewer than `MIN_CHARS` characters is an image: it is rendered at 300 dpi and read with **Tesseract**, recording the mean word confidence.
3. If still empty and `USE_SITE_FALLBACK` is on, that one page's text is fetched from the site.

→ `pages.jsonl` (`doc_id, page, text, source, ocr_confidence`), resumable through `text_done.txt`.

### 5. Build the final tables: `build_tables.py`
* **`documents`:** the union of every known ID, every scraped ID and every PDF on disk. Document-level fields come from `docs.jsonl` (first value that is not a placeholder), plus `site_date`, `bates_start`, `pdf_path`, `url`, and `removed` / `removed_date` from the last catalog change.
* **`pages`:** `pages.jsonl` plus `bates_page`, a date with `date_source`, and the page-level site metadata (contaminants, OCR status, building BINs).
* **`entities`, `entity_mentions`, `buildings`, `building_mentions`, `catalog_changes`:** from step 1, mention rows deduplicated. `contradictions` is written too when step 1 produced it (it is not in the committed `data/final/`).

It ends with two quick checks (mentions pointing to unknown documents, duplicate pages); `verify.py` does the full set.

## Outputs

**`data/final/`** (committed with Git LFS; join keys `doc_id` + `page`, `entity_type` + `slug`, `bin`)

| Table | Rows | One row per |
| --- | --- | --- |
| `documents` | 64,619 | document ID (64,385 scraped documents + 234 ID-only rows, see the report) |
| `pages` | 230,888 | page, with its text |
| `entities` | 15,915 | entity (7 types) |
| `entity_mentions` | 650,196 | entity × page |
| `buildings` | 984 | building (BIN) or lot (BBL) |
| `building_mentions` | 16,151 | building × page, from the building's page |
| `catalog_changes` | 794 | change row in a capture |

Every column: the report's Appendix A (data dictionary). Intermediate files (`data/raw/html/`, `data/raw/zips/`, `data/raw/pdfs/`, `data/interim/`) are gitignored.

**`outputs/figures/ingestion/`**

| Figure | Shows |
| --- | --- |
| `figI1_whose_files` | Share of documents and of pages by the agency whose files they are |
| `figI2_building_links` | For the most-documented buildings: the site's page count, `building_mentions` and the page-level tags |

## Verification (`verify.py`)

Needs only `data/final/`. Assertions:
1. The files are real tables, not Git LFS pointers.
2. Keys: `doc_id` well formed and unique, `bates_start` equal to its number; `(doc_id, page)`, `(entity_type, slug)` and `bin` unique.
3. Completeness: every scraped document has all its pages, numbered 1 … `n_pages`, and `bates_page` = `doc_id` + page − 1.
4. Joins: every entity and building mention points to an existing entity or building and an existing page.
5. Our entity mentions equal the site's page count for every entity except 3 "Page Avenue" addresses (the site's count is the house number).
6. Text `source` values, and OCR confidence only where Tesseract ran.

Known issues, counted and printed (report section 6):

7. Document IDs with no metadata, and how many are the last page of another document.
8. `catalog_changes.change` is always "changed"; the type is in `context`.
9. `building_mentions` against the site's page counts and the page-level tags.

## Changing things

| To change | Edit | Then |
| --- | --- | --- |
| Request rate, user agent, sources | `config.py` (`SECONDS_BETWEEN_REQUESTS`, `USER_AGENT`, `SITE`, `CITY_PDF_URL`) | keep ≥ 1 second for the site |
| OCR and fallback | `config.TEXT_WORKERS`, `MIN_CHARS`, `USE_TESSERACT`, `USE_SITE_FALLBACK` | delete `data/interim/text_done.txt` and `pages.jsonl`, re-run `extract_text`, `build_tables` |
| How a page is parsed | `parsers.py` | re-run the step that reads that page (cached, no new requests), then `build_tables`, `verify` |
| Which columns reach `data/final/` | `build_tables.DOC_LEVEL_COLS`, `PAGE_LEVEL_COLS`, `keep` | re-run `build_tables`, then update the data dictionary |

After a rebuild, commit `data/final/` (Git LFS), then re-run processing and the analyses, and update the report's numbers.

## Full pipeline at a glance

```
scrape_site → scrape_docs → get_pdfs → extract_text → build_tables → verify → figures   (src/ingestion → data/final/)
          → clean → verify → figures                                                    (src/processing → data/processed/)
          → run → verify                                                                (src/analysis/network → outputs/network/)
```
Walkthroughs: `notebooks/00.data_ingestion.ipynb`, `01.process_pipeline.ipynb`, `02.network_centrality.ipynb`. Results: `docs/00.ingestion_report.md`, `01.processing_report.md`, `02.network_analysis_report.md`.
