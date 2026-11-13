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

# --- external data (optional, step 6) ----------------------------------------
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")   # free: api.census.gov/data/key_signup.html
FOOTPRINTS_FILE = ""                     # NYC Open Data "Building Footprints" export (GeoJSON or shapefile)
TIGER_BG_2000_URL = "https://www2.census.gov/geo/tiger/TIGER2010/BG/2000/tl_2010_36061_bg00.zip"
LOWER_MANHATTAN_BBOX = (-74.03, 40.695, -73.97, 40.73)  # lon_min, lat_min, lon_max, lat_max

for _p in (HTML_CACHE, ZIPS, PDFS, EXTERNAL, INTERIM, FINAL):
    _p.mkdir(parents=True, exist_ok=True)
