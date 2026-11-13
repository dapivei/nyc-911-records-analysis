# Bureaucratic Networks, Spatial Testing, and Liability Sentiment in Post-9/11 Records

**Course:** DS-GA 1007 Programming for Data Science (Fall 2026)  
**Team Members:** Daniela Pinto Veizaga, Beibei Xia, You Fan, Betty Cui  

## Context
Following the city's release of over 170,000 pages of previously restricted post-9/11 environmental sampling reports, agency correspondence, and inspection logs, this project quantifies the macro-level structural, spatial, and linguistic patterns across the archive. 

## Research Questions & Hypotheses
1. **Network Topology:** How did inter-agency communication networks operate? 
   * *Hypothesis 1 (Network Centrality):* Municipal regulatory agencies and private real estate entities will exhibit significantly higher betweenness and degree centrality than public health advocacy groups.
2. **Spatial Equity:** What patterns characterized how Lower Manhattan blocks were prioritized for testing?
   * *Hypothesis 2 (Spatial Prioritization):* Commercial hubs will show a statistically significant concentration of early testing logs compared to residential zones.
3. **Sentiment Divergence:** How did administrative "liability anxiety" evolve compared to public messaging?
   * *Hypothesis 3 (Sentiment Divergence):* Internal memos will display an early, high-density spike in "liability and risk" terminology weeks before public-facing guidance adopts restrictive language.

## Datasets
* NYC 9/11 Document Portal
* 9/11 Records Independent Mirror

## Reproducibility


# NYC 9/11 Public Portal Dataset (`data/final/`)

This directory contains six structured Parquet datasets extracted and processed from the NYC 9/11 Public Portal (`911records.org`) environmental and administrative archives.

## Dataset Overview

| File | Rows | Columns | Description |
| :--- | :---: | :---: | :--- |
| `documents.parquet` | 64,619 | 23 | Document-level metadata, archival provenance, and PDF file paths. |
| `pages.parquet` | 230,888 | 14 | Page-level extracted text, OCR quality status, dates, and tagged contaminants. |
| `buildings.parquet` | 984 | 23 | NYC buildings/properties with geospatial coordinates and PLUTO-style attributes. |
| `building_mentions.parquet` | 16,151 | 4 | Cross-reference linking specific documents and pages to building identifiers. |
| `entities.parquet` | 15,915 | 8 | Directory of extracted entities (government agencies, official signatories, etc.). |
| `entity_mentions.parquet` | 650,196 | 7 | Cross-reference linking extracted entities to specific document pages. |

---

## Data Dictionary

### 1. `documents.parquet`
Contains metadata for each unique archival document (`64,619` unique `doc_id`s).

* **`doc_id`**: Unique document identifier (e.g., `NYC-WTC_000000001`).
* **`bates_start`**: Starting Bates stamp number for the document.
* **`bates_range`**: Full Bates stamp range across all pages in the document.
* **`n_pages`**: Total number of pages in the document.
* **`file_size`**: Human-readable page count and file size string (e.g., `9 pages / 8.2 MB`).
* **`collection`**: Archival collection name (e.g., `DEP Hard Copies (68 Boxes)`).
* **`agency`**: Originating or responsible government agency (e.g., `Environmental Protection, Dept. of`).
* **`production_volume`**: Production batch or volume code (e.g., `NYC-WTC0001`).
* **`box`**: Physical archive box identifier.
* **`folder`**: Physical archive folder number or code.
* **`folder_label`**: Original label text from the physical folder.
* **`title`**: Document title.
* **`title_confidence`**: Confidence score for machine-extracted or inferred titles.
* **`description`**: Summary description of the document's contents.
* **`doc_type`**: Classified document category.
* **`doc_type_confidence`**: Confidence score for the document type classification.
* **`site_date`**: Primary parsed date associated with the document (`YYYY-MM-DD`).
* **`doc_date_raw`**: Raw date string(s) extracted from the record.
* **`removed`**: Boolean flag indicating if the document was removed from the portal.
* **`removed_date`**: Date of removal, if applicable.
* **`pdf_path`**: Local relative path to the raw PDF file.
* **`pdf_links`**: List of source PDF download paths on the portal.
* **`url`**: Direct URL to the document on `911records.org`.

---

### 2. `pages.parquet`
Contains page-by-page text extractions and environmental taggings (`230,888` rows).

* **`doc_id`**: Foreign key linking to `documents.parquet`.
* **`page`**: 1-indexed page number within the document.
* **`text`**: Full extracted text content of the page.
* **`source`**: Method used to extract initial text (e.g., `pdftotext`).
* **`ocr_confidence`**: Confidence score when OCR was applied.
* **`bates_page`**: Bates stamp identifier for the individual page.
* **`date`**: Parsed date associated with the specific page.
* **`date_source`**: Origin of the page date (e.g., `document`, `none`).
* **`url`**: Direct URL to the specific page on `911records.org`.
* **`contaminants`**: List of environmental contaminants detected on the page (e.g., `['lead']`, `['asbestos', 'amosite']`, `['voc', 'dust']`).
* **`ocr_status`**: Quality/processing status of the text (e.g., `ok`, `ocr`, `junk`).
* **`ocr_source`**: Pipeline source that produced the final text (e.g., `pdftotext`, `ours`).
* **`entity_links`**: List of linked entity identifiers appearing on the page.
* **`building_bins`**: List of NYC Building Identification Numbers (BINs) referenced on the page.

---

### 3. `buildings.parquet`
Master table of NYC properties referenced across the archive (`984` rows).

* **`bin`**: NYC Building Identification Number (or `bbl:`-prefixed Borough-Block-Lot ID when BIN is unavailable).
* **`place_id`**: Standardized place identifier (`bin:<id>` or `bbl:<id>`).
* **`kind`**: Identifier type (`bin` or `bbl`).
* **`address`**: Street address of the property.
* **`lat`**: Latitude coordinate.
* **`lon`**: Longitude coordinate.
* **`n_docs`**: Number of unique documents mentioning this building.
* **`n_pages`**: Number of unique pages mentioning this building.
* **`n_test_pages`**: Count of pages classified as environmental testing records.
* **`n_inspection_pages`**: Count of pages classified as inspection records.
* **`name`**: Display name or primary address of the building.
* **`building_class`**: Human-readable NYC building classification (e.g., `hotel (H5)`, `office (O2)`).
* **`year_built`**: Year the structure was built.
* **`floors`**: Number of stories/floors.
* **`units`**: Summary of residential and total units.
* **`building_area`**: Gross floor area formatted in square feet.
* **`n_records`**: Total count of associated records.
* **`n_source_pages`**: Total source pages linked to the property.
* **`n_test_candidate_pages`**: Count of candidate environmental testing pages.
* **`building_class_code`**: Two-character NYC building class code (e.g., `H5`, `D5`, `C7`).


---

### 4. `building_mentions.parquet`
Join table connecting buildings to specific document pages (`16,151` rows).

* **`bin`**: Foreign key linking to `buildings.parquet` (`bin` / `bbl:` ID).
* **`doc_id`**: Foreign key linking to `documents.parquet`.
* **`page`**: Page number where the building is referenced.
* **`row_text`**: Contextual summary snippet describing the mention, confidence score, and record metadata.

---

### 5. `entities.parquet`
Catalog of normalized organizations, agencies, and individuals (`15,915` rows).

* **`entity_type`**: Category of entity (e.g., `agency`, `signatory`).
* **`slug`**: URL-friendly unique identifier within the entity type (e.g., `army-corps-of-engineers`).
* **`name`**: Human-readable name or role label.
* **`href`**: Relative portal URL path for the entity.
* **`n_pages`**: Total number of pages where the entity appears.
* **`n_docs`**: Total number of documents where the entity appears.
* **`first_date`**: Earliest document date associated with the entity (`YYYY-MM-DD`).
* **`last_date`**: Latest document date associated with the entity (`YYYY-MM-DD`).

---

### 6. `entity_mentions.parquet`
Join table linking entities to every page where they appear (`650,196` rows).

* **`entity_type`**: Foreign key matching `entities.parquet` (`agency`, `signatory`, etc.).
* **`slug`**: Foreign key matching `entities.parquet`.
* **`doc_id`**: Foreign key linking to `documents.parquet`.
* **`page`**: Page number where the entity is mentioned.
* **`link_text`**: Display title and page reference for the mention.
* **`confidence`**: Extraction/linking confidence score (`0.0` to `1.0`).
* **`row_text`**: Full formatted search/index snippet for the mention.
