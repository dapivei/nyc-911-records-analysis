"""All settings in one place. Edit this file, not the step scripts."""
import os
from pathlib import Path

# --- who you are (the site asks automated users to be identifiable) ---------
USER_AGENT = "wtc911-research (NYU course project; contact: PUT_YOUR_EMAIL_HERE)"

# --- sources -----------------------------------------------------------------
SITE = "https://911records.org"
CITY_PDF_URL = "https://sept11documents.cityofnewyork.us/apps/content/September11_MD/{doc_id}.pdf"
SECONDS_BETWEEN_REQUESTS = 1.0          # be polite: keep >= 1 for 911records.org
ENTITY_TYPES = ["agency", "lab", "contractor", "substance", "address", "signatory"]

# --- folders -----------------------------------------------------------------
DATA = Path("data")
HTML_CACHE = DATA / "raw" / "html"       # every downloaded page, so nothing is fetched twice
ZIPS = DATA / "raw" / "zips"             # put ZIPs from 911records.org/downloads here
PDFS = DATA / "raw" / "pdfs"             # one PDF per document
MANIFEST = DATA / "raw" / "manifest.json"  # optional, from 911records.org/downloads
EXTERNAL = DATA / "raw" / "external"     # census, building footprints
INTERIM = DATA / "interim"               # output of each step
FINAL = DATA / "final"                   # clean tables for analysis

# --- text extraction ---------------------------------------------------------
TEXT_WORKERS = 4                         # parallel processes for pdftotext / OCR
MIN_CHARS = 25                           # fewer characters = page has no text layer
USE_TESSERACT = True                     # OCR image-only pages locally
USE_SITE_FALLBACK = True                 # if still empty, fetch that page's text from the site

