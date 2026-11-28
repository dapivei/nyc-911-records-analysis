"""Settings for the cleaning step (src/processing/clean.py).

Kept here rather than in the root config.py so the ingestion settings stay untouched.
"""
import config

PROCESSED = config.DATA / "processed"    # data/final tables after cleaning (gitignored)

# --- dates -------------------------------------------------------------------
EARLIEST_VALID_DATE = "1900-01-01"       # earlier dates are parse errors (e.g. year 0001) -> NaT
STUDY_START = "2001-09-11"               # in_study_window flag: the post-9/11 response period
STUDY_END = "2009-12-31"

# --- page text quality (has_usable_text) ---------------------------------------
MIN_USABLE_CHARS = 100                   # cleaned page text shorter than this is not usable for NLP
MIN_ALPHA_RATIO = 0.5                    # share of letters among non-space characters (excludes numeric lab printouts)
MIN_WORD_RATIO = 0.4                     # share of tokens that are 3+ letter words (excludes scattered OCR characters)

# --- buildings -------------------------------------------------------------------
# Study area for in_lower_manhattan (RQ2). Kept here since the cleaning step is its only user
# (it used to live in the root config.py).
LOWER_MANHATTAN_BBOX = (-74.03, 40.695, -73.97, 40.73)   # lon_min, lat_min, lon_max, lat_max

# --- off-topic documents -------------------------------------------------------
# Archive boxes of unrelated DEP legal/claims files (2007 steam pipe explosion, 2014 Howard Beach
# flood, Hurricane Irene, premises-liability requests). Their documents are dropped unless they mention the WTC.
OFF_TOPIC_BOXES = ("DEP Box 41", "GRM 010290082 - BOX 26")

# --- document date correction (dates.py) ----------------------------------------
LATEST_VALID_DATE = "2015-12-31"       # later raw dates are OCR misreads (the archive ends ~2014)
TITLE_YEAR_RANGE = (1985, 2015)          # years outside this in a title are not dates (addresses, IDs)
REPEATED_DATE_MIN_DOCS = 10              # raw date in this many docs, never matching their titles -> ignored
