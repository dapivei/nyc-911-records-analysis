"""Clean the data/final/ tables and write analysis-ready copies to data/processed/.

data/final/ is left untouched; every step here is a pure function
(DataFrame in, DataFrame out) so it can be imported and tested on its own.

  documents          drop empty/constant columns, impossible dates -> NaT,
                     file size in MB, pdf_links as a list; doc_date = corrected
                     date (see dates.py; site_date kept as scraped); in_study_window flag
  pages              date = corrected doc_date where the page date came from the
                     document; strip the portal header and Bates stamps
                     from text; n_chars / alpha_ratio / has_usable_text flags
  buildings          numeric units, floor area and class code; in_lower_manhattan flag
  entities           entity_id / entity_name merging name variants
                     (agencies: hand map in agency_map.py; contractors and labs:
                     name normalisation); agency_level for agencies
  entity_mentions    entity_id added; constant confidence column dropped
  building_mentions  unchanged
  catalog_changes    capture_date parsed

Off-topic documents (settings.OFF_TOPIC_BOXES, unless they mention the WTC) are
removed from every doc-keyed table and listed in removed_documents.parquet.
entities.n_pages / n_docs still count them (a few pages at most).

Run alone:  python -m src.processing.clean
"""
import json
import re

import pandas as pd

import config
from src.processing import settings
from src.processing.agency_map import CONTRACTOR_SLUGS_THAT_ARE_AGENCIES, agency_lookup
from src.processing.dates import correct_document_dates

SOURCE, OUT = config.FINAL, settings.PROCESSED

PORTAL_HEADER_RE = r"NYC 9/11 Public Portal Document"
BATES_STAMP_RE = r"NYC-WTC[ _]\d{9}"
WTC_MENTION_RE = r"world trade|\bwtc\b|ground zero|9/11|september 11"
COMPANY_SUFFIXES = r"\b(inc|incorporated|llc|llp|lp|pc|pllc|corp|corporation|co|company|ltd|limited|the)\b"
SIZE_UNITS_MB = {"KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}
COMPANY_TYPES = ("contractor", "lab")      # entity types whose names get suffix normalisation
# a name that normalises to just one of these words ("Associates Inc.") is too vague to merge
GENERIC_COMPANY_WORDS = {
    "associates", "construction", "development", "environmental", "engineering", "engineers",
    "services", "group", "consultants", "consulting", "contracting", "contractors", "management",
    "industries", "enterprises", "systems", "partners", "laboratories", "laboratory", "labs",
    "analytical", "testing", "international", "realty", "properties", "",
}


# --- shared helpers -----------------------------------------------------------

def clean_dates(values: pd.Series) -> pd.Series:
    """Parse to datetime; dates before settings.EARLIEST_VALID_DATE become NaT."""
    dates = pd.to_datetime(values, errors="coerce")
    return dates.where(dates >= pd.Timestamp(settings.EARLIEST_VALID_DATE))


def in_study_window(dates: pd.Series) -> pd.Series:
    """True when a date falls inside settings.STUDY_START..STUDY_END."""
    return dates.between(pd.Timestamp(settings.STUDY_START), pd.Timestamp(settings.STUDY_END))


def normalise_company_name(name: str) -> str:
    """'ATC Associates, Inc.' and 'Atc Associates' -> 'atc associates'."""
    name = name.lower().replace("&", " and ")
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    name = re.sub(COMPANY_SUFFIXES, " ", name)
    return " ".join(name.split())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --- documents ----------------------------------------------------------------

def parse_file_size_mb(file_size: pd.Series) -> pd.Series:
    """'9 pages / 8.2 MB' -> 8.2"""
    parts = file_size.str.extract(r"([\d.]+)\s*(KB|MB|GB)", flags=re.IGNORECASE)
    return pd.to_numeric(parts[0], errors="coerce") * parts[1].str.upper().map(SIZE_UNITS_MB)


def parse_pdf_links(raw: str | None) -> list[str]:
    """JSON-encoded list string -> list of unique links (order kept)."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        links = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return list(dict.fromkeys(links))


def is_off_topic(documents: pd.DataFrame) -> pd.Series:
    """True for documents in settings.OFF_TOPIC_BOXES whose title/description never mention the WTC."""
    about = (documents["title"].fillna("") + " " + documents["description"].fillna("")).str.lower()
    mentions_wtc = about.str.contains(WTC_MENTION_RE, regex=True)
    return documents["box"].isin(settings.OFF_TOPIC_BOXES) & ~mentions_wtc


def clean_documents(documents: pd.DataFrame) -> pd.DataFrame:
    """Drop always-empty/constant columns, fix types and dates."""
    empty_or_constant = ["title_confidence", "doc_type", "doc_type_confidence", "removed", "removed_date"]
    docs = documents.drop(columns=empty_or_constant, errors="ignore").copy()
    docs["n_pages"] = docs["n_pages"].astype("Int64")
    docs["file_size_mb"] = parse_file_size_mb(docs["file_size"])
    docs["pdf_links"] = docs["pdf_links"].map(parse_pdf_links)
    docs["site_date"] = clean_dates(docs["site_date"])
    docs = docs.join(correct_document_dates(docs))
    docs["in_study_window"] = in_study_window(docs["doc_date"])
    return docs.drop(columns=["file_size"])


# --- pages --------------------------------------------------------------------

def clean_page_text(text: pd.Series) -> pd.Series:
    """Remove the portal header and Bates stamps; collapse whitespace, keep line breaks."""
    text = text.fillna("")
    text = text.str.replace(PORTAL_HEADER_RE, " ", regex=True)
    text = text.str.replace(BATES_STAMP_RE, " ", regex=True)
    text = text.str.replace(r"[ \t\f\r]+", " ", regex=True)
    text = text.str.replace(r"\s*\n\s*", "\n", regex=True)
    return text.str.strip()


def text_quality(text: pd.Series) -> pd.DataFrame:
    """n_chars, alpha_ratio, word_ratio and has_usable_text (prose-like enough for NLP).

    alpha_ratio = letters / non-space characters (low for numeric lab printouts);
    word_ratio  = 3+ letter words / tokens (low for scattered OCR characters).
    """
    n_chars = text.str.len()
    n_visible = text.str.count(r"\S")
    alpha_ratio = (text.str.count(r"[A-Za-z]") / n_visible.where(n_visible > 0)).fillna(0.0)
    n_tokens = text.str.count(r"\S+")
    word_ratio = (text.str.count(r"\b[A-Za-z]{3,}\b") / n_tokens.where(n_tokens > 0)).fillna(0.0)
    usable = ((n_chars >= settings.MIN_USABLE_CHARS)
              & (alpha_ratio >= settings.MIN_ALPHA_RATIO)
              & (word_ratio >= settings.MIN_WORD_RATIO))
    return pd.DataFrame({"n_chars": n_chars, "alpha_ratio": alpha_ratio.round(3),
                         "word_ratio": word_ratio.round(3), "has_usable_text": usable})


def clean_pages(pages: pd.DataFrame, doc_dates: pd.Series) -> pd.DataFrame:
    """Clean text and dates; flag pages usable for text analysis.

    doc_dates maps doc_id -> corrected doc_date (see dates.py).
    The site's own ocr_status is kept, but it is not reliable on its own
    ('junk' includes readable specifications), so use has_usable_text.
    """
    out = pages.drop(columns=["entity_links"], errors="ignore").copy()   # always '[]'
    out["text"] = clean_page_text(out["text"])
    out = pd.concat([out, text_quality(out["text"])], axis=1)
    # the site has no page-level dates (date_source is only "document" or "none"),
    # so every page takes its document's corrected date
    out["date"] = out["doc_id"].map(doc_dates)
    out["date_source"] = out["date"].notna().map({True: "document", False: "none"})
    out["in_study_window"] = in_study_window(out["date"])
    out["contaminants"] = out["contaminants"].map(lambda c: [] if c is None else list(c))
    out["building_bins"] = out["building_bins"].map(lambda b: [] if b is None else list(b))
    return out


# --- buildings ----------------------------------------------------------------

def clean_buildings(buildings: pd.DataFrame) -> pd.DataFrame:
    """Turn display strings into numbers and flag buildings inside Lower Manhattan."""
    out = buildings.copy()
    units = out["units"].str.extract(r"^\s*(\S+)\s+residential\s*/\s*(\S+)\s+total")
    out["residential_units"] = pd.to_numeric(units[0], errors="coerce").astype("Int64")
    out["total_units"] = pd.to_numeric(units[1], errors="coerce").astype("Int64")
    area = out["building_area"].str.replace(r"[^\d.]", "", regex=True)
    out["building_area_sqft"] = pd.to_numeric(area, errors="coerce")
    code_from_label = out["building_class"].str.extract(r"\(([A-Z0-9]{2})\)")[0]
    out["building_class_code"] = out["building_class_code"].fillna(code_from_label)
    out["year_built"] = out["year_built"].where(out["year_built"] > 0).astype("Int64")
    out["floors"] = out["floors"].astype("Int64")
    for col in ("first_date", "last_date"):
        out[col] = clean_dates(out[col])
    lon_min, lat_min, lon_max, lat_max = config.LOWER_MANHATTAN_BBOX
    out["in_lower_manhattan"] = out["lon"].between(lon_min, lon_max) & out["lat"].between(lat_min, lat_max)
    return out.drop(columns=["units", "building_area"])


# --- entities -----------------------------------------------------------------

def canonicalise_agencies(agencies: pd.DataFrame) -> pd.DataFrame:
    lookup = agency_lookup()
    unmapped = set(agencies["slug"]) - set(lookup)
    if unmapped:
        raise ValueError(f"add these agency slugs to agency_map.py: {sorted(unmapped)}")
    mapped = agencies["slug"].map(lookup)
    return agencies.assign(
        entity_id=mapped.str[0], entity_name=mapped.str[1], agency_level=mapped.str[2])


def canonicalise_companies(companies: pd.DataFrame) -> pd.DataFrame:
    """Merge name variants; the most-mentioned variant becomes entity_name."""
    key = companies["name"].fillna("").map(normalise_company_name)
    key = key.where(~key.isin(GENERIC_COMPANY_WORDS), companies["slug"])   # too vague: keep own slug
    most_mentioned = (companies.assign(_key=key)
                      .sort_values("n_pages", ascending=False)
                      .drop_duplicates("_key")
                      .set_index("_key")["name"])
    return companies.assign(entity_id=key.map(slugify), entity_name=key.map(most_mentioned))


def clean_entities(entities: pd.DataFrame) -> pd.DataFrame:
    """Add entity_id / entity_name for every entity (and agency_level for agencies).

    Public bodies the site filed as contractors are moved to entity_type "agency";
    source_type keeps the site's original type (the join key for entity_mentions).
    """
    entities = entities.assign(source_type=entities["entity_type"])
    misfiled = (entities["entity_type"] == "contractor") & entities["slug"].isin(CONTRACTOR_SLUGS_THAT_ARE_AGENCIES)
    entities.loc[misfiled, "entity_type"] = "agency"
    is_agency = entities["entity_type"] == "agency"
    is_company = entities["entity_type"].isin(COMPANY_TYPES)
    other = entities[~is_agency & ~is_company].assign(
        entity_id=lambda d: d["slug"], entity_name=lambda d: d["name"])
    parts = [canonicalise_agencies(entities[is_agency]), other]
    parts += [canonicalise_companies(group) for _, group in entities[is_company].groupby("entity_type")]
    out = pd.concat(parts).loc[entities.index]          # original row order
    for col in ("first_date", "last_date"):
        out[col] = clean_dates(out[col])
    return out


def clean_entity_mentions(mentions: pd.DataFrame, entities: pd.DataFrame) -> pd.DataFrame:
    """Attach entity_id and the corrected entity_type.

    Merged variants can repeat a page: dedupe at your analysis level.
    """
    canonical = entities[["source_type", "slug", "entity_type", "entity_id"]]
    out = (mentions.drop(columns=["confidence"], errors="ignore")   # always 1.0
           .rename(columns={"entity_type": "source_type"}))
    return out.merge(canonical, on=["source_type", "slug"], how="left", validate="many_to_one")


# --- catalog changes ----------------------------------------------------------

def clean_catalog_changes(changes: pd.DataFrame) -> pd.DataFrame:
    return changes.assign(capture_date=clean_dates(changes["capture_date"]))


# --- run ----------------------------------------------------------------------

def run():
    read = lambda name: pd.read_parquet(SOURCE / f"{name}.parquet")
    documents = read("documents")
    off_topic = is_off_topic(documents)
    removed = documents.loc[off_topic, ["doc_id", "box", "folder", "site_date", "title"]]
    keep = lambda table: table[~table["doc_id"].isin(removed["doc_id"])]

    entities = clean_entities(read("entities"))
    clean_docs = clean_documents(documents[~off_topic])
    tables = {
        "documents": clean_docs,
        "pages": clean_pages(keep(read("pages")), clean_docs.set_index("doc_id")["doc_date"]),
        "buildings": clean_buildings(read("buildings")),
        "building_mentions": keep(read("building_mentions")),
        "entities": entities,
        "entity_mentions": clean_entity_mentions(keep(read("entity_mentions")), entities),
        "catalog_changes": clean_catalog_changes(read("catalog_changes")),
        "removed_documents": removed,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_parquet(OUT / f"{name}.parquet", index=False)
        print(f"{name:18s} {len(table):>8,} rows -> {OUT / name}.parquet")


if __name__ == "__main__":
    run()
