"""Checks on the ingestion output: run `python -m src.ingestion.verify` after build_tables.py.

Needs only data/final/ (no web requests, no PDFs), so anyone can run it after `git lfs pull`.

Assertions (the run stops on the first failure)
  1. the files are real tables, not Git LFS pointers
  2. keys: doc_id well formed and unique, bates_start = doc_id number; (doc_id, page), (entity_type, slug), bin unique
  3. completeness: every scraped document has all its pages, numbered 1..n_pages, and bates_page = doc_id + page - 1
  4. joins: every entity / building mention points to a known entity or building and to an existing page
  5. entity mentions: our count per entity equals the site's n_pages (the only exceptions are 3 "Page Avenue"
     addresses, where the site's count is the house number read as a page count)
  6. text: source is pdftotext / tesseract / site / none, and ocr_confidence is set only where Tesseract ran

Known issues (counted and printed, not fixed here; see docs/00.ingestion_report.md, section 6)
  7. document IDs with no metadata, pages or PDF, and how many are the last page of another document
  8. catalog_changes.change is always "changed"; the real type is at the start of `context`
  9. building_mentions has fewer pages than the site reports for many buildings; pages.building_bins has more
"""
import json

import numpy as np
import pandas as pd

import config
from src.ingestion.parsers import DOC_ID_RE

F = config.FINAL
TABLES = ["documents", "pages", "entities", "entity_mentions", "buildings", "building_mentions", "catalog_changes"]
TEXT_SOURCES = {"pdftotext", "tesseract", "site", "none"}


def load():
    for name in TABLES:
        path = F / f"{name}.parquet"
        assert path.exists(), f"missing {path}: run the ingestion steps or `git lfs pull`"
        assert path.stat().st_size > 1_000, f"{path} is a Git LFS pointer: run `git lfs pull`"
    cols = {"pages": ["doc_id", "page", "source", "ocr_confidence", "bates_page", "building_bins"],
            "entity_mentions": ["entity_type", "slug", "doc_id", "page"]}
    t = {name: pd.read_parquet(F / f"{name}.parquet", columns=cols.get(name)) for name in TABLES}
    print(f"1. {len(TABLES)} tables loaded: " + ", ".join(f"{n} {len(d):,}" for n, d in t.items()))
    return t


def scraped(documents):
    """Documents whose page on the site was scraped (they have a title and a page count)."""
    return documents[documents["n_pages"].notna()]


def check_keys(t):
    d, pg = t["documents"], t["pages"]
    assert d["doc_id"].is_unique and d["doc_id"].map(lambda x: bool(DOC_ID_RE.fullmatch(x))).all()
    assert (d["bates_start"] == d["doc_id"].str[8:].astype(int)).all()
    assert not pg.duplicated(["doc_id", "page"]).any()
    assert not t["entities"].duplicated(["entity_type", "slug"]).any()
    assert t["buildings"]["bin"].is_unique
    print("2. keys unique and well formed (doc_id, (doc_id, page), (entity_type, slug), bin)")


def check_completeness(t):
    d, pg = scraped(t["documents"]), t["pages"]
    rows = pg.groupby("doc_id").size()
    assert set(rows.index) == set(d["doc_id"]), "scraped documents and documents with pages differ"
    assert (d.set_index("doc_id")["n_pages"] == rows.reindex(d["doc_id"]).to_numpy()).all(), "missing pages"
    numbered = pg.groupby("doc_id")["page"].agg(lambda s: s.min() == 1 and s.max() == len(s))
    assert numbered.all(), "page numbers are not 1..n"
    expected = "NYC-WTC_" + (pg["doc_id"].str[8:].astype(int) + pg["page"] - 1).astype(str).str.zfill(9)
    assert (pg["bates_page"] == expected).all()
    print(f"3. all {len(d):,} scraped documents have all their pages ({len(pg):,}), numbered 1..n, "
          "with consistent Bates page numbers")


def check_joins(t):
    pages = t["pages"].set_index(["doc_id", "page"]).index
    em, bm = t["entity_mentions"], t["building_mentions"]
    ent = t["entities"].set_index(["entity_type", "slug"]).index
    assert em.set_index(["entity_type", "slug"]).index.isin(ent).all(), "entity mention without entity"
    assert em.set_index(["doc_id", "page"]).index.isin(pages).all(), "entity mention without page"
    assert bm["bin"].isin(t["buildings"]["bin"]).all(), "building mention without building"
    assert bm.set_index(["doc_id", "page"]).index.isin(pages).all(), "building mention without page"
    assert t["catalog_changes"]["doc_id"].isin(t["documents"]["doc_id"]).all()
    print(f"4. every entity mention ({len(em):,}) and building mention ({len(bm):,}) joins to its entity or "
          "building and to an existing page")


def check_entity_counts(t):
    e = t["entities"][t["entities"]["entity_type"] != "building"]      # building entities have no mention pages
    ours = t["entity_mentions"].groupby(["entity_type", "slug"]).size()
    diff = e.set_index(["entity_type", "slug"])["n_pages"] - ours.reindex(e.set_index(["entity_type", "slug"]).index).fillna(0)
    off = diff[diff != 0]
    assert len(off) <= 3 and off.index.get_level_values("slug").str.endswith("page-avenue").all(), off
    print(f"5. entity mentions per entity equal the site's n_pages for {len(diff) - len(off):,} of {len(diff):,} "
          f"entities (exceptions: {len(off)} 'Page Avenue' addresses)")


def check_text(t):
    pg = t["pages"]
    assert set(pg["source"].unique()) <= TEXT_SOURCES
    has_conf = pg["ocr_confidence"].notna()
    assert has_conf[pg["source"] == "tesseract"].all()                       # every OCR'd page has a confidence
    assert pg.loc[has_conf, "source"].isin(["tesseract", "none"]).all()       # and only pages OCR was tried on
    counts = pg["source"].value_counts()
    print("6. text source: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))


def id_only_documents(documents):
    """IDs with no metadata, and which of them are the last page of another (scraped) document."""
    d = scraped(documents).sort_values("bates_start")
    start = d["bates_start"].to_numpy()
    end = start + d["n_pages"].to_numpy().astype(int) - 1
    ids = documents[documents["n_pages"].isna()]
    i = np.searchsorted(start, ids["bates_start"].to_numpy(), side="right") - 1
    last_page = (i >= 0) & (ids["bates_start"].to_numpy() == end[i.clip(0)])
    return ids.assign(last_page_of_other=last_page)


def change_type(changes):
    """The change type as written at the start of `context` ('bates range' for the extra ID-range rows)."""
    kind = changes["context"].str.extract(r"^(added|removed|changed)\b")[0]
    rng = changes["context"].str.contains(" – ", regex=False)
    return kind.fillna(pd.Series(np.where(rng, "bates range", "other"), index=changes.index))


def building_coverage(t):
    """Per building: the site's page count, pages in building_mentions, pages tagged in pages.building_bins."""
    b, bm, pg = t["buildings"], t["building_mentions"], t["pages"]
    tags = (pg.loc[pg["building_bins"] != "[]", ["doc_id", "page", "building_bins"]]
            .assign(bin=lambda x: x["building_bins"].map(json.loads)).explode("bin")
            .drop_duplicates(["bin", "doc_id", "page"]).groupby("bin").size())
    mentions = bm.drop_duplicates(["bin", "doc_id", "page"]).groupby("bin").size()
    out = b.set_index("bin")[["name", "kind", "record_type", "n_pages"]].rename(columns={"n_pages": "site_count"})
    out["building_mentions"] = mentions.reindex(out.index).fillna(0).astype(int)
    out["page_tags"] = tags.reindex(out.index).fillna(0).astype(int)
    return out


def known_issues(t):
    ids = id_only_documents(t["documents"])
    print(f"7. KNOWN ISSUE: {len(ids)} document IDs have no metadata, pages or PDF; "
          f"{int(ids['last_page_of_other'].sum())} of them are the last page of another document")
    kinds = change_type(t["catalog_changes"]).value_counts()
    print(f"8. KNOWN ISSUE: catalog_changes.change is {sorted(t['catalog_changes']['change'].unique())}; "
          "type from context: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
    cov = building_coverage(t)
    cov = cov[cov["kind"] == "bin"]                       # lot (BBL) entries have no page tags by construction
    short = (cov["building_mentions"] < cov["site_count"]).sum()
    print(f"9. KNOWN ISSUE: building_mentions has fewer pages than the site reports for {short} of {len(cov)} "
          f"BIN buildings ({cov['building_mentions'].sum():,} vs {cov['site_count'].sum():,} pages); "
          f"pages.building_bins tags {cov['page_tags'].sum():,}")


if __name__ == "__main__":
    tables = load()
    check_keys(tables)
    check_completeness(tables)
    check_joins(tables)
    check_entity_counts(tables)
    check_text(tables)
    known_issues(tables)
    print("all checks passed (known issues listed above)")
