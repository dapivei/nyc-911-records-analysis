# Processing: from `data/final/` to `data/processed/`

Ingestion gives us a faithful copy of what the site and the PDFs say. This step makes that copy **analysis-ready**. It fixes types and dates, strips stamps from page text, flags pages good enough for NLP, merges duplicate entity names, and drops off-topic documents.

`data/final/` is never modified. The cleaned copies go to `data/processed/`, which is gitignored and regenerated with one command.

## How to run

```bash
# after ingestion (data/final/ exists), from the repo root:
python -m src.processing.clean
```

It prints the row count of each table written to `data/processed/`. Every cleaning function is a pure DataFrame → DataFrame function, so you can import any of them in a notebook or a test.

## Files

| File | Role |
| --- | --- |
| `clean.py` | The pipeline: one `clean_*` function per table and `run()` to orchestrate them |
| `dates.py` | Corrects document dates using the title as a cross-check |
| `agency_map.py` | Hand-curated map from the site's agency slugs to canonical agencies, each with a government level |
| `settings.py` | All thresholds: valid date range, study window, text-quality cut-offs, off-topic boxes |

## What `run()` does, in order

### 1. Remove off-topic documents
`is_off_topic()` flags documents in `settings.OFF_TOPIC_BOXES` (DEP legal and claims boxes about the 2007 steam-pipe explosion, the Howard Beach flood, Hurricane Irene, and similar matters) **unless** their title or description mentions the WTC, 9/11, or Ground Zero.
These documents are removed from every table keyed by `doc_id` and listed in `removed_documents.parquet` for transparency.
*Why:* they share the archive but not the subject, and would add noise to every research question.

### 2. Entities (done early, because mentions depend on it)
`clean_entities()` gives every entity a canonical `entity_id` and `entity_name`:
- **Agencies**: through `agency_map.py`. For example, `dep` and `department-of-environmental-protection` both become `nyc-dep`. Each agency also gets an `agency_level` (city / state / federal / regional / private / nonprofit), which is the grouping used to test Hypothesis 1. If an agency slug is missing from the map, the run **fails loudly**, so a new slug cannot slip through unmapped.
- **Contractors and labs**: names are normalised (lower-cased, punctuation and suffixes like Inc/LLC/Corp removed), and variants are merged. The name of the most-mentioned variant becomes `entity_name`. Names that reduce to a generic word ("Associates Inc.") keep their own slug, so unrelated companies are not merged.
- **Misfiled bodies**: the LMDC slugs that the site filed as contractors are moved to `agency`. `source_type` keeps the site's original type so the join to mentions still works.

*Why:* without merging, one organization shows up as several network nodes, which distorts centrality.

### 3. Documents: `clean_documents()`
- Drops columns that are always empty or always constant (`doc_type`, `title_confidence`, `removed`, …).
- Converts `file_size` to `file_size_mb`, parses `pdf_links` into a list, and makes `n_pages` an integer.
- Sets impossible dates (before 1900) to NaT.
- **`doc_date`** is the corrected date from `dates.py` (see below). `site_date` is kept as scraped.
- Adds `in_study_window`: `doc_date` falls between 2001-09-11 and 2009-12-31.

### 4. Pages: `clean_pages()`
- Pulls the **litigation stamp** out of the text *before* removing it, into `litigation_stamp` and `litigation_source` (`21MC100`, the WTC disaster-site litigation, or the name of a specific subpoena). OCR variants are normalised.
- **Cleans the text**: removes the portal header, the Bates stamps, and the litigation stamps; collapses whitespace while keeping line breaks; rejoins words hyphenated across a line break.
- **Measures text quality**: `n_chars`, `alpha_ratio` (letters ÷ visible characters, which is low for numeric lab printouts), `word_ratio` (share of tokens that are words of 3+ letters, which is low for OCR garbage), and **`has_usable_text`** when all three pass the thresholds in `settings.py`. Use this flag rather than the site's `ocr_status`, which marks some readable pages as "junk".
- **Dates**: the site has no page-level dates, so every page takes its document's corrected `doc_date`, plus `in_study_window`.
- Parses `contaminants` and `building_bins` into lists, and drops `entity_links`, which is always empty.

*Why:* stamps repeat on every page and would dominate word counts and sentiment scores (RQ3). The quality flag keeps lab tables and OCR noise out of the NLP.

### 5. Buildings: `clean_buildings()`
Parses display strings into numbers (`residential_units`, `total_units`, `building_area_sqft`, `year_built`, `floors`), fills `building_class_code`, parses the first and last mention dates, and adds `in_lower_manhattan` using `config.LOWER_MANHATTAN_BBOX` (the RQ2 study area).

### 6. Entity mentions, building mentions, catalog changes
- `entity_mentions`: attaches `entity_id` and the corrected `entity_type` (a many-to-one merge, validated), and drops `confidence`, which is always 1.0. Merged variants can repeat the same page, so **deduplicate at your level of analysis**.
- `building_mentions`: only the off-topic filter is applied.
- `catalog_changes`: `capture_date` is parsed.

## How the document date is corrected (`dates.py`)

The site's date is the **earliest** date found anywhere in the document. That is often wrong: lab-method revision dates printed on every sheet ("NIOSH 7400 … 8/15/94"), fax machines with unset clocks (01/01/1999), mentions of 9/11 itself, and later print or scan dates. Most titles end with the document's own month and year ("…, Oct 2001"), so the title is used as a cross-check:

0. Drop raw dates outside 1900–2015 (these are OCR misreads).
1. Drop **repeated** dates: a date that appears in ≥ 10 documents whose titles never agree with it.
2. If a raw date falls in the title's month (or year), use it. If the title gives an exact day that matches, use that one.
3. Otherwise, use the **title's date** when the raw date is clearly implausible: missing, on or before 9/11 for a post-9/11 title, or more than a year after the title's date.
4. Otherwise, keep the raw date and mark it as a conflict.

The output columns are `doc_date`, `date_precision` (day / month / year), and `date_fix`, which records the rule applied. Use `date_fix` to audit the correction, or to run a robustness check that keeps only the rule-2 dates.

## Outputs (`data/processed/`)
`documents`, `pages`, `buildings`, `building_mentions`, `entities`, `entity_mentions`, `catalog_changes`, `removed_documents`. They use the same join keys as ingestion: `doc_id` + `page`, `entity_id`, and `bin`.

## Full pipeline at a glance

```
scrape_site → scrape_docs → get_pdfs → extract_text → build_tables   (src/ingestion → data/final/)
          → clean                                                    (src/processing → data/processed/)
          → analysis (src/analysis/network, notebooks)
```

To change a threshold, edit `settings.py`. To change an agency mapping, edit `agency_map.py`. Then re-run `python -m src.processing.clean`. This takes seconds and makes no web requests.