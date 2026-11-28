# Methodology and Archival Forensics

## Scope

This analysis reconstructs NYC Department of Environmental Protection (DEP) oversight activity from post-9/11 records released by the NYC Law Department and indexed by the 9/11 Records mirror. It classifies evidence at the page level because one scanned PDF can contain several record types, including unrelated trailing pages.

## Record Provenance

The production uses sequential Bates identifiers (`NYC-WTC_...`), with each identifier corresponding to a scanned page. Records retain their agency and box/folder context, and some catalog entries were added or removed across capture dates. A `doc_id` can represent a multi-page packet rather than one discrete record.

A four-page packet for 24 Beaver Street (`NYC-WTC_000119140` through `NYC-WTC_000119143`) illustrates the issue:

1. A WTC visual survey form.
2. A DEP Asbestos Control Program demand letter.
3. A Department of Buildings `BISPIQ` property query.
4. An unrelated DEP Air/Noise hotline complaint filed behind the building records.

The packet is useful as an example of why document-level labels and building-level joins need page-level review. It is not, by itself, evidence that every packet has this structure.

## Page Classification

The oversight analysis in `src/analysis/dep_oversight.py` classifies page text into inspection, request, test-report, cleanup, clearance, or other stages. It excludes administrative property-query content and non-WTC hotline material from the oversight analysis. Cleanup records are further assessed for exterior-related language when sequencing remediation.

Classification is rule-based and depends on extracted text. OCR errors, sparse text, ambiguous terminology, and mixed-content pages can affect assignments. Stage labels are analytical indicators, not verified legal or agency determinations.

## Date Verification

The analysis favors explicit event dates in page text or titles. It excludes administrative `ENTERED` stamps and property-query dates, and ignores month-only inferred titles. This reduces false timeline patterns caused by data-entry dates or guessed dates. Only explicit day-precision dates are used for event-sequence claims.

## Human Review

The analysis exports `verify_sample.csv`, a random sample of inspected buildings with source-page URLs for manual review. This supports ongoing validation but does not mean every classified page has been independently reviewed. Treat derived coverage and timelines as estimates from the released DEP paper trail.

## Interpretation Limit

A missing DEP test report means no matching report was found in the records analyzed. It does not establish that no test occurred: other programs, including U.S. EPA and NYC Department of Health efforts, are outside this DEP-focused analysis.
