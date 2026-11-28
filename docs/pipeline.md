# Data Pipeline and Reproducibility

## Pipeline Stages

The ingestion code is in `src/ingestion/`:

1. `scrape_site.py`, `web.py`, and `parsers.py` collect indexed building, entity, document, and catalog-change metadata from 911records.org. The HTTP client includes rate limiting, robots.txt handling, retries, and a local HTML cache.
2. `scrape_docs.py` collects document and page metadata; `get_pdfs.py` unpacks or retrieves source PDFs.
3. `extract_text.py` extracts embedded PDF text and uses Tesseract OCR for image-based pages. PDF utilities such as `pdftotext` and `pdftoppm`, plus Tesseract, may be required depending on the input files.
4. `build_tables.py` assembles the normalized Parquet outputs in `data/final/`.
5. `src/analysis/dep_oversight.py` performs page-level classification and generates the oversight tables, audit sample, summary, and coverage figure.

## Environment

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

The PDF command-line utilities and Tesseract are system dependencies for extraction/OCR; installing the Python requirements alone may not install them.

## Run

From the repository root, build the normalized tables:

```bash
python -m src.ingestion.build_tables
```

Run the DEP oversight analysis:

```bash
python src/analysis/dep_oversight.py --data ./data/final --out ./outputs/dep_oversight_verified
```

The analysis output includes page-stage records, a building timeline, a manual-review sample, coverage summaries, an exterior-cleanup sequence table, a figure, and a text summary. The exact files are listed in the script's module documentation.

## Repository Map

```text
src/ingestion/              Crawling, PDF retrieval, extraction, and table assembly
src/analysis/dep_oversight.py
                            Page-level DEP oversight analysis
data/final/                 Normalized Parquet tables
outputs/                    Generated analysis artifacts
```

The output files in `data/final/` and `outputs/` may be generated locally and are not necessarily committed with the source code. See [the dataset guide](../data/final/README.md) for the current table inventory.
