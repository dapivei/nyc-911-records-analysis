# Table Inventory

| File | Granularity | Purpose |
| --- | --- | --- |
| `documents.parquet` | One row per `doc_id` | Bates range, archival provenance, title/type metadata, dates, removal status, and PDF paths. |
| `pages.parquet` | One row per `(doc_id, page)` | Extracted page text, Bates page ID, dates, OCR metadata, source URLs, contaminants, and linked entities/buildings. |
| `buildings.parquet` | One row per property identifier | Building identity, address, coordinates, classification, structural attributes, and derived record counts. Identifiers may be BINs or `bbl:`-prefixed BBLs. |
| `building_mentions.parquet` | One row per building/document/page mention | Page-level link between a property and a source record. |
| `entities.parquet` | One row per normalized entity | Entity type, slug, display name, portal link, and document/page totals and date bounds. |
| `entity_mentions.parquet` | One row per entity/document/page mention | Page-level entity links, extraction confidence, and source-index text. |
| `catalog_changes.parquet` | One row per catalog change | Captured additions/removals from the source catalog. |

## Key Fields

### `documents.parquet`

- `doc_id`: Unique document identifier, such as `NYC-WTC_000000001`.
- `bates_start`, `bates_range`, `n_pages`: Bates identifiers and packet size.
- `collection`, `agency`, `production_volume`, `box`, `folder`, `folder_label`: Archival provenance.
- `title`, `title_confidence`, `description`, `doc_type`, `doc_type_confidence`: Source-index metadata and confidence values.
- `site_date`, `doc_date_raw`: Parsed and source date values.
- `removed`, `removed_date`: Catalog removal status and date, when available.
- `pdf_path`, `pdf_links`, `url`: Local and source locations.

### `pages.parquet`

- `doc_id`, `page`: Document key and 1-indexed page number.
- `bates_page`: Bates identifier for this page.
- `text`: Extracted or OCR-recognized page text.
- `source`, `ocr_source`, `ocr_status`, `ocr_confidence`: Text extraction and quality metadata.
- `date`, `date_source`: Parsed page/document date and its origin.
- `url`, `contaminants`, `entity_links`, `building_bins`: Source URL and page-level tags/links.

### `buildings.parquet`

- `bin`, `place_id`, `kind`: Property identifiers and identifier type (`bin` or `bbl`).
- `address`, `lat`, `lon`: Address and coordinates.
- `name`, `building_class`, `building_class_code`, `year_built`, `floors`, `units`, `building_area`: Property attributes.
- `n_docs`, `n_pages`, `n_test_pages`, `n_inspection_pages`, `n_records`, `n_source_pages`, `n_test_candidate_pages`: Derived record/page counts where present.

### `building_mentions.parquet`

- `bin`, `doc_id`, `page`: Property-to-source-page join keys.
- `row_text`: Context from the indexed mention.

### `entities.parquet`

- `entity_type`, `slug`: Entity key.
- `name`, `href`: Display name and source link.
- `n_pages`, `n_docs`, `first_date`, `last_date`: Mention totals and observed date bounds.

### `entity_mentions.parquet`

- `entity_type`, `slug`, `doc_id`, `page`: Entity-to-source-page join keys.
- `link_text`, `confidence`, `row_text`: Source label, extraction/link confidence, and contextual index text.



## Join Guidance

Use `doc_id` to join document and page records. Use `(doc_id, page)` to connect page-level mentions and extracted text. Use `bin`/`place_id` to connect building records; preserve the identifier type because some properties use BBL rather than BIN identifiers. Cite page-level evidence using `bates_page` and, where available, the source `url`.

## Interpretation

A missing record in these tables means it was not present in the captured/processed source data. It does not establish that an event did not occur. OCR, source indexing, and entity/building matching can also introduce omissions or false matches.
