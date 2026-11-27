"""Settings for the RQ1 organization co-occurrence network (src/analysis/network/).

Every threshold used by the analysis lives here so it is fixed before results
are seen and can be cited in the report.
"""
from pathlib import Path

from src.processing import settings as processing_settings

PROCESSED = processing_settings.PROCESSED            # data/processed/ (output of src.processing.clean)
OUT = Path("outputs") / "network"                    # tables (csv)
FIGURES = Path("outputs") / "figures" / "network"    # png figures

# --- nodes ---------------------------------------------------------------------
# entity types that name organizations. signatory (people / role labels), address,
# building and substance are not organizations and are excluded.
ORG_TYPES = ("agency", "contractor", "lab")
# a company node must appear in at least this many distinct documents. One-document
# names are mostly OCR fragments; this is a support filter, applied before any metric.
MIN_NODE_DOCS = 2

# --- edges ---------------------------------------------------------------------
MAIN_UNIT = "page"                                   # co-occurrence unit of the main analysis
# sensitivity check: drop multi-organization pages, i.e. co-occurrence units whose number of
# distinct organizations is above this quantile of units with >= 2 organizations. This is a
# rule about page SIZE only; it does not identify a document type.
LARGE_UNIT_QUANTILE = 0.99

# --- metrics and figures ---------------------------------------------------------
SEED = 1007                                          # figure jitter, verification sample, layout fallback
# hypothesis groups (fixed in classify.py before results were computed)
HYPOTHESIS_GROUPS = ("municipal_regulatory", "private_real_estate", "public_health_advocacy")
# classification sensitivity: real-estate nodes whose group was confirmed by hand
CONFIRMED_STATUS = "manual"

TOP_N_RANKING = 20
NETWORK_FIG_TOP_COMPANIES = 25                       # companies shown next to all agencies
