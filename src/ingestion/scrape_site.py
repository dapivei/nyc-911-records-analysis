"""Scrape the indexes 911records.org has already built.

Gets (into data/interim/):
  entities.parquet            agencies, labs, contractors, substances, addresses
  entity_mentions.jsonl       which document pages each entity appears on
  buildings.parquet           mapped buildings: BIN, building class, floors
  building_mentions.parquet   which document pages mention each building
  browse_docs.parquet         every document id listed under /browse
  catalog_changes.parquet     documents the City added / removed, by date
  contradictions.parquet      the site's 9 curated contradictions (labelled examples)

Run alone:  python -m src.ingestion.scrape_site
Resumable: entities already finished are listed in entity_done.txt.
"""
import math

import pandas as pd

import config
from src.ingestion import parsers as P
from src.ingestion.files import append_rows, done_keys, mark_done
from src.ingestion.web import get_page

OUT = config.INTERIM

def scrape_entities(types=config.ENTITY_TYPES):
    """Scrapes the platform entities and maps them to their respective document pages.

    Process Phases:
    - Listing Pages: Iteratively discovers and extracts all entities across different
      sub-categories using a pagination-following queue. Removes duplicates by entity
      type and slug, persisting the results to entities.parquet.
    - Mention Pages: For each discovered entity (excluding building), extracts all
      document pages where it appears at a rate of 50 records per page. Progressively
      appends results into a JSON Lines format file.

    Resumable Mechanism:
    This function references entity_done.txt at initialization to skip any entity/slug
    combinations that were fully processed in prior execution windows.

    Args:
        types (list, optional): List of target entity types to scrape.
            Defaults to config.ENTITY_TYPES.

    Outputs:
        - data/interim/entities.parquet
        - data/interim/entity_mentions.jsonl
        - data/interim/entity_done.txt (State logging file)
    """
    rows = []
    for etype in types:
        todo, seen = [f'/entities/{etype}'], set()
        while todo:  # follow letter / pagination links
            url = todo.pop(0)
            if url in seen:
                continue
            seen.add(url)
            html = get_page(url)
            if html:
                found, more = P.parse_entity_listing(html, etype)
                rows += found
                todo += [u for u in more if u not in seen]
        print(f'  {etype}: {sum(r["entity_type"] == etype for r in rows)} entities')

    entities = pd.DataFrame(rows).drop_duplicates(['entity_type', 'slug'])
    entities.to_parquet(OUT / 'entities.parquet', index=False)

    done = done_keys(OUT / 'entity_done.txt')
    todo = entities[
        (entities.entity_type != 'building')
        & ~(entities.entity_type + '/' + entities.slug).isin(done)
    ]
    print(f'  entity pages: {len(todo)} to go ({len(done)} done)')

    for i, (etype, slug) in enumerate(zip(todo.entity_type, todo.slug), 1):
        seen, page, last_page = set(), 1, None
        base_url = f'/signatory/{slug}' if etype == 'signatory' else f'/entity/{etype}/{slug}'
        while True:
            html = get_page(base_url + (f'?page={page}' if page > 1 else ''))
            if not html:
                break
            parsed = P.parse_entity_page(html, etype, slug)
            if page == 1 and parsed['total_records']:
                last_page = math.ceil(parsed['total_records'] / 50)  # 50 rows per page
            new = [r for r in parsed['links'] if (r['doc_id'], r['page']) not in seen]
            if not new:
                break
            seen |= {(r['doc_id'], r['page']) for r in new}
            append_rows(OUT / 'entity_mentions.jsonl', new)
            page += 1
            if last_page and page > last_page:
                break
        mark_done(OUT / 'entity_done.txt', [f'{etype}/{slug}'])
        if i % 100 == 0:
            print(f'  entity pages {i}/{len(todo)}')


def scrape_buildings():
    """Extracts geographic building metadata and building document linkages.

    First queries the map root endpoint to extract all available Building Identification
    Numbers (BIN), then iterates over each identifier to pull structural building profiles
    (building class, floor counts) paired with matching text snippets and coordinates from
    official City records.

    Outputs:
      - data/interim/buildings.parquet: Master spatial structural catalog indexed by BIN.
      - data/interim/building_mentions.parquet: Relational mapping of bin -> doc_id -> page.
    """
    html_map = get_page('/map') or ''
    parsed_map = P.parse_map_page(html_map)
    print(f"Extracted from map: {len(parsed_map)} | Unique BINs: {len({b['bin'] for b in parsed_map})}")

    bins = {b["bin"]: b for b in P.parse_map_page(get_page("/map") or "")}
    rows, links = [], []
    for i, b in enumerate(sorted(bins), 1):
        html = get_page(f"/building/{b}")
        if html:
            info = P.parse_building_page(html, b)
            links += info.pop("links")
            rows.append({**bins[b], **{k: v for k, v in info.items() if v is not None}})
        if i % 100 == 0:
            print(f"  buildings {i}/{len(bins)}")
    pd.DataFrame(rows).to_parquet(OUT / "buildings.parquet", index=False)
    pd.DataFrame(links, columns=["bin", "doc_id", "page", "row_text"]).to_parquet(
        OUT / "building_mentions.parquet", index=False)
    print(f"  buildings: {len(rows)}")


def scrape_browse():
    """Walk /browse -> collections -> boxes, collecting every document id.

    Implements a Breadth-First Search (BFS) graph traversal strategy across the web 
    platform's archive hierarchy to harvest a unique master index of all documents 
    and their label texts.

    Outputs:
        - data/interim/browse_docs.parquet: Consolidated schema containing ["doc_id", "row_text"].
    """
    todo, seen, docs = ["/browse"], set(), []
    while todo:
        url = todo.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html = get_page(url)
        if html:
            found, more = P.parse_browse(html)
            docs += found
            todo += [u for u in more if u not in seen]
    df = pd.DataFrame(docs, columns=["doc_id", "row_text"]).drop_duplicates("doc_id")
    df.to_parquet(OUT / "browse_docs.parquet", index=False)
    print(f"  browse: {len(df)} documents from {len(seen)} pages")


def scrape_changes():
    """Scrapes historical catalog additions and removals organized by capture date.

    Loops through the chronological web index of log modifications to compile a comprehensive 
    audit trail of documents inserted or deleted from the collection by municipal entities over time.

    Outputs:
        - data/interim/catalog_changes.parquet
    """

    _, dates = P.parse_changes_index(get_page("/changes") or "")
    rows = []
    for d in dates:
        rows += P.parse_change_capture(get_page(f"/changes/{d}") or "", d)
    pd.DataFrame(rows, columns=["capture_date", "change", "doc_id", "context"]).to_parquet(
        OUT / "catalog_changes.parquet", index=False)
    print(f"  catalog changes: {len(rows)} rows from {len(dates)} captures")


def scrape_contradictions():
    """Extracts curated factual contradictions indexed by the platform.

    Downloads and processes documented instances of conflicting public declarations or 
    discrepancies in data patterns manually flagged within environmental sampling reports.

    Outputs:
        - data/interim/contradictions.parquet: Curated dataframe containing labeled contradictions.
    """
    rows = P.parse_contradictions(get_page("/contradictions") or "")
    pd.DataFrame(rows).to_parquet(OUT / "contradictions.parquet", index=False)
    print(f"  contradictions: {len({r['entry_id'] for r in rows})} entries")


def run():
    """Orchestrator to run all scraping steps sequentially.

    Executes the entire web scraping pipeline and provides logging status checkpoints in the console.
    """
    print("Scrape 911records.org indexes")
    scrape_entities()
    scrape_buildings()
    scrape_browse()
    scrape_changes()
    scrape_contradictions()


if __name__ == "__main__":
    run()
