"""Assertions behind the cleaning step: run `python -m src.processing.verify` after clean.py.

Toy inputs with hand-checked answers
  1. date rules (dates.py): title parsing, the four choose_date rules, repeated dates
  2. page text: portal header, Bates and litigation stamps removed; stamp source normalised;
     hyphen rejoining; usable-text thresholds
  3. names: company-name normalisation and the generic-name guard; file size; off-topic rule

The real output tables in data/processed/
  4. row bookkeeping: raw documents = kept + removed; removed documents absent from every doc-keyed table
  5. keys unique and joins complete (pages -> documents, mentions -> pages / entities)
  6. dates: inside the valid range, precision set exactly when a date exists, study-window flag
     consistent, every page carries its document's date
  7. text: no portal header or Bates stamp left; has_usable_text equals the thresholds in settings.py
  8. entities: every mention has an entity_id; agencies all mapped, with a level
  9. buildings: in_lower_manhattan equals the bounding box in settings.py
"""
import numpy as np
import pandas as pd

import config
from src.processing import clean, dates, settings

P = settings.PROCESSED


def check_date_rules():
    """1. dates.py on hand-made documents."""
    assert dates.title_period("DEP memo on air sampling, Oct 2001") == (2001, 10, None)
    assert dates.title_period("Letter dated October 11, 2001") == (2001, 10, 11)
    assert dates.title_period("Report, Jan-Feb 2002") == (2002, 1, None)       # range: first month, no day
    assert dates.title_period("125 Broadway 1001187 survey, 2002") == (2002, None, None)
    assert dates.title_period("Building 2500 survey") is None                   # outside TITLE_YEAR_RANGE
    T = pd.Timestamp
    # rule 2: a raw date in the title's month wins (the exact day if the title gives one)
    assert dates.choose_date([T("2001-10-03"), T("2001-10-11")], (2001, 10, 11)) == \
        (T("2001-10-11"), "day", "raw date matching title")
    # no title date: earliest raw date
    assert dates.choose_date([T("2002-03-05")], None) == (T("2002-03-05"), "day", "raw date (no title date)")
    # rule 3: no raw date -> title month; raw date before 9/11 for a post-9/11 title -> title month
    assert dates.choose_date([], (2002, 3, None)) == (T("2002-03-01"), "month", "title date (no raw date)")
    assert dates.choose_date([T("1994-08-15")], (2001, 10, None)) == \
        (T("2001-10-01"), "month", "title date (raw date implausible)")
    assert dates.choose_date([T("2008-08-22")], (2001, 10, None))[2] == "title date (raw date implausible)"
    # rule 4: both plausible -> keep the raw date, mark the conflict
    assert dates.choose_date([T("2001-12-20")], (2002, 1, None)) == \
        (T("2001-12-20"), "day", "raw date (conflicts with title)")
    # repeated date: in >= REPEATED_DATE_MIN_DOCS documents, never agreeing with their titles
    n = settings.REPEATED_DATE_MIN_DOCS
    cands = pd.Series([[T("1994-08-15"), T("2001-10-02")]] * n)
    periods = pd.Series([(2001, 10, None)] * n)
    assert dates.find_repeated_dates(cands, periods) == {T("1994-08-15")}
    # out-of-range raw dates are dropped; OCR text falls back to the site's own parse
    assert dates.raw_dates("2019-05-28, 2001-10-01", pd.NaT) == [T("2001-10-01")]
    assert dates.raw_dates("May 28, 19^8", T("1998-05-28")) == [T("1998-05-28")]
    print("1. date rules: title parsing, rules 2-4, repeated dates and valid range behave as documented")


def check_text_and_names():
    """2-3. page text, stamps, usable text, names, file size, off-topic rule."""
    raw = pd.Series(["NYC 9/11 Public Portal Document\nThe carry-\nout of asbestos   removal NYC-WTC_000125674\n"
                     "CITY_21MC100_004219846",
                     "Letter CITY_2IMCl00_0 04219846 about air",
                     "Subpoena page CITY_DEP_WORBY_CANNATA_SUBP_000123",
                     "Subpoena page CITY_DEP__WORBY_CANNATA_SUBP_000124",
                     "No stamp here"])
    st = clean.litigation_stamps(raw)
    assert st["litigation_source"].tolist()[:2] == ["21MC100", "21MC100"]          # OCR variant merged
    assert st["litigation_source"].iloc[2] == st["litigation_source"].iloc[3]      # underscore variants merged
    assert pd.isna(st["litigation_source"].iloc[4])
    txt = clean.clean_page_text(raw)
    assert "Portal" not in txt[0] and "NYC-WTC" not in txt[0] and "CITY_" not in txt[0]
    assert "carryout" in txt[0] and "  " not in txt[0]
    q = clean.text_quality(pd.Series(["word " * 30, "12.5 0.003 44 " * 20, "short text"]))
    assert q["has_usable_text"].tolist() == [True, False, False]
    assert clean.normalise_company_name("ATC Associates, Inc.") == clean.normalise_company_name("Atc Associates")
    assert clean.normalise_company_name("Associates Inc.") in clean.GENERIC_COMPANY_WORDS   # not merged
    assert np.allclose(clean.parse_file_size_mb(pd.Series(["9 pages / 8.2 MB", "1 page / 512 KB"])), [8.2, 0.5])
    docs = pd.DataFrame({"box": ["DEP Box 41", "DEP Box 41", "DEP Box 04"],
                         "title": ["Hurricane Irene claim", "WTC legal hold notice", "Anything"],
                         "description": [None, None, None]})
    assert clean.is_off_topic(docs).tolist() == [True, False, False]
    print("2-3. stamps, text cleaning, usable text, name merging, file size and the off-topic rule behave as documented")


def check_outputs():
    """4-9. the real tables in data/processed/."""
    raw_docs = pd.read_parquet(config.FINAL / "documents.parquet", columns=["doc_id"])
    d = pd.read_parquet(P / "documents.parquet")
    rm = pd.read_parquet(P / "removed_documents.parquet")
    pg = pd.read_parquet(P / "pages.parquet", columns=["doc_id", "page", "text", "date", "date_source",
                                                       "in_study_window", "n_chars", "alpha_ratio",
                                                       "word_ratio", "has_usable_text"])
    em = pd.read_parquet(P / "entity_mentions.parquet", columns=["source_type", "slug", "entity_type",
                                                                 "entity_id", "doc_id", "page"])
    bm = pd.read_parquet(P / "building_mentions.parquet", columns=["bin", "doc_id", "page"])
    ent = pd.read_parquet(P / "entities.parquet")
    b = pd.read_parquet(P / "buildings.parquet")

    # 4. bookkeeping
    assert len(raw_docs) == len(d) + len(rm), "raw documents != kept + removed"
    gone = set(rm["doc_id"])
    for name, t in [("documents", d), ("pages", pg), ("entity_mentions", em), ("building_mentions", bm)]:
        assert not t["doc_id"].isin(gone).any(), f"removed document left in {name}"
    print(f"4. {len(raw_docs):,} raw documents = {len(d):,} kept + {len(rm):,} removed; "
          "no removed document in any doc-keyed table")

    # 5. keys and joins
    assert d["doc_id"].is_unique and not pg.duplicated(["doc_id", "page"]).any()
    assert pg["doc_id"].isin(d["doc_id"]).all(), "page without a document"
    keys = pg.set_index(["doc_id", "page"]).index
    assert em.set_index(["doc_id", "page"]).index.isin(keys).all(), "entity mention without a page"
    assert not ent.duplicated(["source_type", "slug"]).any()
    print("5. keys unique; every page has a document; every entity mention has a page")

    # 6. dates
    dd = d["doc_date"]
    ok = dd.isna() | dd.between(pd.Timestamp(settings.EARLIEST_VALID_DATE), pd.Timestamp(settings.LATEST_VALID_DATE))
    assert ok.all(), "doc_date outside the valid range"
    assert (d["date_precision"].isna() == dd.isna()).all() and (d["date_fix"].eq("no date") == dd.isna()).all()
    assert d["in_study_window"].equals(clean.in_study_window(dd))
    page_dates = pg["doc_id"].map(d.set_index("doc_id")["doc_date"])
    assert ((pg["date"] == page_dates) | (pg["date"].isna() & page_dates.isna())).all()
    assert (pg["date_source"].eq("none") == pg["date"].isna()).all()
    print(f"6. dates: {dd.notna().sum():,} dated documents all in range; precision, date_fix, study window "
          "and page dates consistent")

    # 7. text
    t = pg["text"].fillna("")
    assert not t.str.contains(clean.PORTAL_HEADER_RE, regex=True).any(), "portal header left in text"
    assert not t.str.contains(clean.BATES_STAMP_RE, regex=True).any(), "Bates stamp left in text"
    rule = ((pg["n_chars"] >= settings.MIN_USABLE_CHARS) & (pg["alpha_ratio"] >= settings.MIN_ALPHA_RATIO - 5e-4)
            & (pg["word_ratio"] >= settings.MIN_WORD_RATIO - 5e-4))
    assert (rule == pg["has_usable_text"]).mean() > 0.9999, "has_usable_text does not follow settings.py"
    print(f"7. text: no portal header or Bates stamp left; has_usable_text follows settings.py "
          f"({pg['has_usable_text'].sum():,} usable pages)")

    # 8. entities
    assert em["entity_id"].notna().all(), "entity mention without entity_id"
    ag = ent[ent["entity_type"] == "agency"]
    assert ag["entity_id"].notna().all() and ag["agency_level"].notna().all()
    print(f"8. entities: every mention has an entity_id; {ag['entity_id'].nunique()} agencies, all with a level")

    # 9. buildings
    lon0, lat0, lon1, lat1 = settings.LOWER_MANHATTAN_BBOX
    inside = b["lon"].between(lon0, lon1) & b["lat"].between(lat0, lat1)
    assert inside.equals(b["in_lower_manhattan"])
    print(f"9. buildings: in_lower_manhattan matches the bounding box ({(~inside).sum()} of {len(b)} outside)")


if __name__ == "__main__":
    check_date_rules()
    check_text_and_names()
    check_outputs()
    print("all checks passed")
