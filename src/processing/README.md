# Processing: from `data/final/` to `data/processed/`

Ingestion gives us a faithful copy of what the site and the PDFs say. This step makes that copy **analysis-ready**: it removes documents that are not about 9/11, corrects document dates, strips stamps from page text, flags pages good enough for text analysis, and merges duplicate organization names.

`data/final/` is never modified. The cleaned copies go to `data/processed/`, which is gitignored and recreated with one command.

What the cleaning found and changed, with numbers, is in [`docs/01.processing_report.md`](../../docs/01.processing_report.md). The step-by-step walkthrough is [`notebooks/01.process_pipeline.ipynb`](../../notebooks/01.process_pipeline.ipynb).

## How to run

```bash
# after ingestion (data/final/ exists, `git lfs pull` done), from the repo root:
python -m src.processing.clean      # writes data/processed/ (about a minute), prints row counts
python -m src.processing.verify     # assertions; ends with "all checks passed"
python -m src.processing.figures    # figures for the report, in outputs/figures/processing/
```

No web requests. Every cleaning step is a plain DataFrame → DataFrame function you can import in a notebook (`from src.processing import clean, dates`).

## Files

| File | Role |
| --- | --- |
| `clean.py` | The pipeline: one `clean_*` function per table and `run()` to run them in order |
| `dates.py` | Corrects document dates using the title as a cross-check |
| `agency_map.py` | Hand-curated map from the site's agency names to 30 agencies, each with a government level |
| `settings.py` | All thresholds: valid dates, study window, text-quality cut-offs, off-topic boxes, study area |
| `verify.py` | Checks: the rules on hand-made inputs, and the output tables (bookkeeping, keys, joins, ranges) |
| `figures.py` | Figures P1–P2 for the report (static PNG) |

## What `run()` does, in order

### 1. Remove off-topic documents
`is_off_topic()` flags documents in `settings.OFF_TOPIC_BOXES` (City legal and claims boxes: the 2007 steam-pipe explosion, a Howard Beach flood, Hurricane Irene, …) **unless** their title or description mentions the WTC, Ground Zero or 9/11. They are removed from every table keyed by `doc_id` and listed in `removed_documents.parquet`.

### 2. Entities (early, because mentions depend on it)
`clean_entities()` gives every entity an `entity_id` and `entity_name`:
* **Agencies** through `agency_map.py` (`dep` and `department-of-environmental-protection` → `nyc-dep`), with an `agency_level`. An agency name missing from the map **stops the run**.
* **Contractors and labs**: names are normalised (case, punctuation, Inc/LLC/Corp removed) and variants merged; the most-mentioned variant becomes `entity_name`. Names that reduce to a generic word keep their own slug.
* **Misfiled bodies**: the Lower Manhattan Development Corporation, filed by the site as a contractor, is moved to `agency`. `source_type` keeps the site's type for the join to mentions.

### 3. Documents: `clean_documents()`
* Drops always-empty or constant columns; `file_size` → `file_size_mb`; `pdf_links` → list; `n_pages` → integer.
* **`doc_date`**, `date_precision`, `date_fix` from `dates.py` (below). `site_date` is kept as scraped.
* `in_study_window`: `doc_date` between `STUDY_START` and `STUDY_END`.

### 4. Pages: `clean_pages()`
* Pulls the **litigation stamp** out of the text *before* cleaning it, into `litigation_stamp` and `litigation_source` (`21MC100` or a subpoena name, OCR variants merged).
* **Cleans the text**: removes the portal header, Bates and litigation stamps; collapses whitespace but keeps line breaks; rejoins words hyphenated across a line.
* **Text quality**: `n_chars`, `alpha_ratio`, `word_ratio`, and **`has_usable_text`** when all three pass the thresholds. Use it instead of the site's `ocr_status`.
* **Dates**: pages take their document's corrected `doc_date`, plus `in_study_window`.
* `contaminants` and `building_bins` → lists; drops `entity_links` (always empty).

### 5. Buildings: `clean_buildings()`
Display strings → numbers (`residential_units`, `total_units`, `building_area_sqft`, `year_built`, `floors`), fills `building_class_code`, parses first/last mention dates, and adds `in_lower_manhattan` from `settings.LOWER_MANHATTAN_BBOX`.

### 6. Mentions and catalog changes
* `entity_mentions`: adds `entity_id` and the corrected `entity_type` (validated many-to-one merge), drops `confidence` (always 1.0). Merged variants can repeat a page: **deduplicate at your level of analysis**.
* `building_mentions`: off-topic filter only. `catalog_changes`: `capture_date` parsed.

## How the document date is corrected (`dates.py`)

The site's date is the **earliest** date anywhere in the text, which is often a lab-method date, an unset fax clock, a mention of 9/11 or a later print date. Most titles end with the document's own month and year, so the title is the cross-check:

0. Drop raw dates outside `EARLIEST_VALID_DATE`–`LATEST_VALID_DATE`.
1. Drop **repeated** dates: found in ≥ `REPEATED_DATE_MIN_DOCS` documents whose titles never agree with them.
2. A raw date in the title's month (or year) wins; the exact day if the title gives one.
3. Otherwise the **title's date**, when the raw date is missing, on or before 9/11 for a post-9/11 title, or more than a year after the title.
4. Otherwise keep the raw date and mark a conflict.

`date_fix` records which rule applied; `date_precision` says whether the date is exact to the day, month or year. Examples, counts and how to use them: report section 4.2 and Appendix A2.

## Outputs

**`data/processed/`** (gitignored; same join keys as ingestion: `doc_id` + `page`, `entity_id`, `bin`)

| Table | Key additions |
| --- | --- |
| `documents` | `doc_date`, `date_precision`, `date_fix`, `in_study_window`, `file_size_mb` |
| `pages` | cleaned `text`, `litigation_stamp`, `litigation_source`, `n_chars`, `alpha_ratio`, `word_ratio`, `has_usable_text`, `date`, `in_study_window` |
| `entities` | `entity_id`, `entity_name`, `agency_level`, `source_type` |
| `entity_mentions` | `entity_id`, corrected `entity_type` |
| `buildings` | numeric unit and area columns, `in_lower_manhattan` |
| `building_mentions`, `catalog_changes` | off-topic filter; parsed dates |
| `removed_documents` | the 78 removed documents with box, folder and title |

**`outputs/figures/processing/`**

| Figure | Shows |
| --- | --- |
| `figP1_dates` | Documents per year before and after the date correction, and what happened to each date |
| `figP2_usable_text` | The site's text label against `has_usable_text` |

## Verification (`verify.py`)

Toy inputs with hand-checked answers:
1. **Dates:** title parsing (month, exact day, month range, bare year, non-years), rules 2–4, repeated-date detection, the valid range and the OCR fallback.
2. **Text:** header, Bates and litigation stamps removed; stamp variants merged; hyphen rejoining; usable-text thresholds.
3. **Names and documents:** company-name merging and the generic-name guard; file size; the off-topic rule.

The real output tables:

4. Raw documents = kept + removed, and no removed document is left in any table keyed by `doc_id`.
5. Keys are unique; every page has a document; every entity mention has a page.
6. Dates are in range; precision and `date_fix` are set exactly when a date exists; `in_study_window` and page dates agree with `doc_date`.
7. No portal header or Bates stamp is left in the text; `has_usable_text` follows the thresholds in `settings.py`.
8. Every mention has an `entity_id`; every agency is mapped and has a level.
9. `in_lower_manhattan` matches the bounding box.

## Changing things

| To change | Edit | Then |
| --- | --- | --- |
| A threshold (dates, usable text, study window) | `settings.py` | re-run `clean`, `verify`, `figures`; update the report's numbers |
| Which boxes are off-topic | `settings.OFF_TOPIC_BOXES` (and `WTC_MENTION_RE` in `clean.py` for the exception) | same |
| An agency mapping or a new agency name | `agency_map.py` | same |
| A company that should not be merged | `GENERIC_COMPANY_WORDS` / `normalise_company_name` in `clean.py` | same |
| The study area | `settings.LOWER_MANHATTAN_BBOX` | same |

Every downstream analysis reads `data/processed/`, so re-run them after a change (for the network, a changed node list also means deleting `outputs/network/temporal_100.csv`; see its README). If a change moves a reported number, say so in the report.

## Full pipeline at a glance

```
scrape_site → scrape_docs → get_pdfs → extract_text → build_tables → verify → figures   (src/ingestion → data/final/)
          → clean → verify → figures                                                    (src/processing → data/processed/)
          → run → verify                                                                (src/analysis/network → outputs/network/)
```
Walkthroughs: `notebooks/00.data_ingestion.ipynb`, `01.process_pipeline.ipynb`, `02.network_centrality.ipynb`. Results: `docs/00.ingestion_report.md`, `01.processing_report.md`, `02.network_analysis_report.md`.
