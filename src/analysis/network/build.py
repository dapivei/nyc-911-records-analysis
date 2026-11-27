"""Load data/processed/ tables and build organization nodes and co-occurrence edges.

Pipeline
  1. org_mentions()      entity_mentions -> one row per (node, doc_id, page), organizations only,
                         after company merges; deduplicated so a page counts once per node
  2. candidate_nodes()   one row per node with doc/page counts and an exclusion reason
                         (artifact name, or support below MIN_NODE_DOCS)
  3. cooccurrence()      pairs of distinct nodes sharing a unit (page or document), unit-level
                         dedupe first; returns edges plus the evidence rows behind every edge

An edge means "named on the same page / in the same document". It is not evidence of
communication, collaboration or influence.
"""
import numpy as np
import pandas as pd

from src.analysis.network import classify, settings

UNIT_KEYS = {"page": ["doc_id", "page"], "doc": ["doc_id"]}

# Exploratory supplement only: public-health / environmental advocacy organizations,
# detected by fixed name patterns in page text (the portal's extractor never tagged them).
ADVOCACY_PATTERNS = {
    "nycosh": ("NYCOSH (NY Committee for Occupational Safety & Health)",
               r"\bnycosh\b|new york committee for occupational safety"),
    "911-environmental-action": ("9/11 Environmental Action", r"9/11 environmental action|911 environmental action"),
    "nrdc": ("Natural Resources Defense Council", r"natural resources defense council|\bnrdc\b"),
    "american-lung-association": ("American Lung Association", r"american lung association"),
}
# Checked and dropped before any metric was computed (precision check, notebook section 2):
#   Sierra Club        6 pages, all unrelated (election endorsement, case name "Sierra Club v.", upstate list)
#   Beyond Ground Zero matches the plain phrase "beyond Ground Zero", not the organization
# Regulatory / method citations ("EPA Method", "NIOSH 7400", "40 CFR", "AHERA") on agency pages:
CITATION_PATTERN = (r"\b(?:epa|niosh|osha)\s*(?:method|meth\.|\d{3,4}\b)|40 ?cfr|29 ?cfr|ahera|"
                    r"federal register|nvlap|elap|osha standard|niosh method|epa method|permissible exposure|pel\b")


# --- loading ---------------------------------------------------------------------------

def read(name: str, columns=None) -> pd.DataFrame:
    path = settings.PROCESSED / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m src.processing.clean` first")
    return pd.read_parquet(path, columns=columns)


def load_tables(with_text: bool = False) -> dict[str, pd.DataFrame]:
    page_cols = ["doc_id", "page", "ocr_status", "has_usable_text", "n_chars"] + (["text"] if with_text else [])
    return {
        "documents": read("documents", ["doc_id", "n_pages", "collection", "agency", "box", "title",
                                        "doc_date", "doc_date_raw", "date_precision", "date_fix",
                                        "in_study_window"]),
        "pages": read("pages", page_cols),
        "entities": read("entities"),
        "entity_mentions": read("entity_mentions", ["source_type", "slug", "doc_id", "page",
                                                    "entity_type", "entity_id"]),
    }


# --- nodes -----------------------------------------------------------------------------

def org_mentions(mentions: pd.DataFrame, entities: pd.DataFrame) -> pd.DataFrame:
    """Organization mentions as (node_id, node_kind, entity_id, doc_id, page), one row per node-page.

    contractor and lab rows with the same entity_id are the same normalised company name,
    so both map to one 'company' node. Companies whose id equals an agency id (Con Edison,
    Verizon filed as contractors) join that agency node.
    """
    org = mentions[mentions["entity_type"].isin(settings.ORG_TYPES)].copy()
    agency_ids = set(entities.loc[entities["entity_type"] == "agency", "entity_id"])
    is_agency = org["entity_type"].eq("agency")
    company_id = org["entity_id"].map(lambda i: classify.COMPANY_MERGES.get(i, i))
    org["entity_id"] = org["entity_id"].where(is_agency, company_id)
    org["node_kind"] = np.where(is_agency | org["entity_id"].isin(agency_ids), "agency", "company")
    org["node_id"] = org["node_kind"] + ":" + org["entity_id"]
    return (org[["node_id", "node_kind", "entity_id", "doc_id", "page"]]
            .drop_duplicates(["node_id", "doc_id", "page"])
            .reset_index(drop=True))


def node_names(entities: pd.DataFrame) -> pd.DataFrame:
    """Display name and agency_level for each (node_kind, entity_id)."""
    ent = entities[entities["entity_type"].isin(settings.ORG_TYPES)].copy()
    agencies = (ent[ent["entity_type"] == "agency"].drop_duplicates("entity_id")
                .assign(node_kind="agency")[["node_kind", "entity_id", "entity_name", "agency_level"]])
    comp = ent[ent["entity_type"] != "agency"].copy()
    # name of the most-mentioned variant (merged variants never name the node)
    comp["is_canonical"] = ~comp["entity_id"].isin(classify.COMPANY_MERGES)
    comp["entity_id"] = comp["entity_id"].map(lambda i: classify.COMPANY_MERGES.get(i, i))
    comp = (comp.sort_values(["is_canonical", "n_pages"], ascending=False)
            .drop_duplicates("entity_id").assign(node_kind="company", agency_level=None))
    comp = comp[~comp["entity_id"].isin(agencies["entity_id"])]
    return (pd.concat([agencies, comp[["node_kind", "entity_id", "entity_name", "agency_level"]]])
            .rename(columns={"entity_name": "name"}))


def candidate_nodes(om: pd.DataFrame, entities: pd.DataFrame) -> pd.DataFrame:
    """Every organization node with counts and an exclusion reason (None = kept)."""
    counts = om.groupby(["node_id", "node_kind", "entity_id"]).agg(
        n_pages=("page", "size"), n_docs=("doc_id", "nunique")).reset_index()
    nodes = counts.merge(node_names(entities), on=["node_kind", "entity_id"], how="left", validate="one_to_one")
    nodes["name"] = nodes["name"].fillna(nodes["entity_id"])
    is_company = nodes["node_kind"].eq("company")
    reason = pd.Series(None, index=nodes.index, dtype=object)
    generic = nodes["name"].map(classify.is_generic_name) & ~nodes["entity_id"].isin(classify.MANUAL_GROUPS)
    reason[is_company & generic] = "generic name (no distinctive word)"
    listed = is_company & nodes["entity_id"].isin(classify.ARTIFACT_IDS)
    reason[listed] = "artifact: " + nodes.loc[listed, "entity_id"].map(classify.ARTIFACT_IDS)
    reason[reason.isna() & is_company & (nodes["n_docs"] < settings.MIN_NODE_DOCS)] = \
        f"support: < {settings.MIN_NODE_DOCS} documents"
    nodes["excluded_reason"] = reason
    return nodes.sort_values("n_docs", ascending=False).reset_index(drop=True)


def advocacy_mentions(pages_text: pd.DataFrame) -> pd.DataFrame:
    """Exploratory: pages whose text names an ADVOCACY_PATTERNS organization."""
    text = pages_text["text"].fillna("").str.lower()
    rows = []
    for entity_id, (_, pattern) in ADVOCACY_PATTERNS.items():
        hit = pages_text.loc[text.str.contains(pattern, regex=True), ["doc_id", "page"]]
        rows.append(hit.assign(node_id=f"advocacy:{entity_id}", node_kind="advocacy", entity_id=entity_id))
    out = pd.concat(rows, ignore_index=True)
    return out[["node_id", "node_kind", "entity_id", "doc_id", "page"]].drop_duplicates(["node_id", "doc_id", "page"])


def advocacy_nodes(adv: pd.DataFrame) -> pd.DataFrame:
    """One row per advocacy node with page and document counts (same columns as candidate_nodes)."""
    counts = adv.groupby(["node_id", "node_kind", "entity_id"]).agg(
        n_pages=("page", "size"), n_docs=("doc_id", "nunique")).reset_index()
    counts["name"] = counts["entity_id"].map(lambda i: ADVOCACY_PATTERNS[i][0])
    return counts.assign(agency_level=None, excluded_reason=None)


# --- edges -----------------------------------------------------------------------------

def unit_sizes(om: pd.DataFrame, unit: str) -> pd.Series:
    """Number of distinct nodes per co-occurrence unit."""
    return om.drop_duplicates(["node_id"] + UNIT_KEYS[unit]).groupby(UNIT_KEYS[unit]).size().rename("n_orgs")


def large_unit_cutoff(om: pd.DataFrame, unit: str, quantile: float = settings.LARGE_UNIT_QUANTILE) -> float:
    """Organizations-per-unit value at `quantile` among units with >= 2 organizations (default p99)."""
    sizes = unit_sizes(om, unit)
    return float(sizes[sizes >= 2].quantile(quantile))


def drop_large_units(om: pd.DataFrame, unit: str, max_unit_size: float | None) -> pd.DataFrame:
    """Mention rows minus those on units naming more than max_unit_size distinct organizations.

    Units naming one organization are kept, so a node whose only mentions are single-organization
    pages keeps them (it is an isolate, not a missing node). None returns om unchanged.
    """
    if max_unit_size is None:
        return om
    keys = UNIT_KEYS[unit]
    size = unit_sizes(om, unit).rename("unit_size").reset_index()
    return om.merge(size, on=keys, how="left").query("unit_size <= @max_unit_size").drop(columns="unit_size")


def cooccurrence(om: pd.DataFrame, unit: str = "page", max_unit_size: float | None = None):
    """Undirected co-occurrence edges.

    Within each unit the node list is deduplicated first, then every unordered pair
    (source < target) is counted once. Returns (edges, evidence):

      edges     source, target, weight (= distinct units shared), n_docs[, n_pages]
      evidence  source, target, doc_id[, page], unit_size  -- one row per unit behind each edge
    """
    keys = UNIT_KEYS[unit]
    u = om[["node_id"] + keys].drop_duplicates()
    size = u.groupby(keys)["node_id"].transform("size")
    u = u.assign(unit_size=size)[size >= 2]
    if max_unit_size is not None:
        u = u[u["unit_size"] <= max_unit_size]
    pairs = u.merge(u[["node_id"] + keys], on=keys, suffixes=("_a", "_b"))
    pairs = pairs[pairs["node_id_a"] < pairs["node_id_b"]]          # unordered, no self-loops
    evidence = pairs.rename(columns={"node_id_a": "source", "node_id_b": "target"})
    evidence = evidence[["source", "target"] + keys + ["unit_size"]].reset_index(drop=True)
    agg = {"weight": ("doc_id", "size"), "n_docs": ("doc_id", "nunique")}
    if unit == "page":
        agg["n_pages"] = ("page", "size")
    edges = evidence.groupby(["source", "target"]).agg(**agg).reset_index()
    return edges.sort_values("weight", ascending=False).reset_index(drop=True), evidence
