"""Glue: prepare inputs once, then build any network variant and its node metrics.

    prep = prepare()                                  # load, nodes, classification, advocacy hits
    net = build_network(prep)                         # main: page co-occurrence, extracted orgs
    net = build_network(prep, include_advocacy=True)  # exploratory supplement
"""
from dataclasses import dataclass

import pandas as pd

from src.analysis.network import build, classify, metrics


@dataclass
class Prepared:
    tables: dict
    om_all: pd.DataFrame          # organization mentions, every candidate node
    candidates: pd.DataFrame      # every candidate node + excluded_reason
    om: pd.DataFrame              # mentions of kept (analysis) nodes
    adv: pd.DataFrame             # advocacy text-dictionary mentions (supplement)
    node_info: pd.DataFrame       # kept + advocacy nodes: attributes and classification


def _date_span(om: pd.DataFrame, documents: pd.DataFrame) -> pd.DataFrame:
    """First and last doc_date on which each node is named."""
    d = om[["node_id", "doc_id"]].drop_duplicates().merge(documents[["doc_id", "doc_date"]], on="doc_id")
    return d.groupby("node_id")["doc_date"].agg(first_doc_date="min", last_doc_date="max",
                                                share_docs_dated=lambda s: s.notna().mean())


def prepare(with_advocacy: bool = True, keep_text: bool = False) -> Prepared:
    """Load processed tables once; return organization mentions, optional advocacy mentions and the classification."""
    tables = build.load_tables(with_text=with_advocacy or keep_text)
    om_all = build.org_mentions(tables["entity_mentions"], tables["entities"])
    candidates = build.candidate_nodes(om_all, tables["entities"])
    kept = candidates[candidates["excluded_reason"].isna()]
    om = om_all[om_all["node_id"].isin(kept["node_id"])].reset_index(drop=True)
    if with_advocacy:
        adv = build.advocacy_mentions(tables["pages"])
        adv_nodes = build.advocacy_nodes(adv)
        if not keep_text:
            tables["pages"] = tables["pages"].drop(columns="text")   # free memory
    else:
        adv, adv_nodes = om.iloc[:0].copy(), candidates.iloc[:0].copy()
    info = pd.concat([kept, adv_nodes], ignore_index=True)
    cls = classify.classify_nodes(info)
    info = info.drop(columns=["excluded_reason"]).merge(
        cls[["node_id", "group", "group_label", "basis", "review_status"]], on="node_id", validate="one_to_one")
    info = info.merge(_date_span(pd.concat([om, adv]), tables["documents"]), on="node_id", how="left")
    return Prepared(tables, om_all, candidates, om, adv, info)


def build_network(prep: Prepared, unit: str = "page", include_advocacy: bool = False,
                  max_unit_size: float | None = None, study_window_only: bool = False,
                  exclude_source_agency: str | None = None) -> dict:
    """Build one network variant and compute its node metrics.

    unit             "page" (main) or "doc"
    include_advocacy add the 4 exploratory advocacy nodes found by text search
    max_unit_size    drop co-occurrence units naming more organizations than this (sensitivity check)
    study_window_only keep only mentions on documents with in_study_window (2001-09-11..2009-12-31;
                     undated documents are dropped). The NODE SET stays fixed: a node with no
                     mention left becomes an isolate, so every variant ranks the same nodes.
    exclude_source_agency drop every mention on documents whose `agency` (whose files the document
                     came from) equals this value, e.g. DEP (archive-bias check). Node set fixed, as above.

    Returns a dict with edges, evidence, graph, stats, nodes, betweenness_info and params.
    """
    om = pd.concat([prep.om, prep.adv]) if include_advocacy else prep.om
    nodes = prep.node_info[prep.node_info["node_id"].isin(om["node_id"].unique())]
    if study_window_only:
        docs = prep.tables["documents"]
        om = om[om["doc_id"].isin(docs.loc[docs["in_study_window"].astype(bool), "doc_id"])]
    if exclude_source_agency is not None:
        docs = prep.tables["documents"]
        om = om[~om["doc_id"].isin(docs.loc[docs["agency"].eq(exclude_source_agency), "doc_id"])]
    om = build.drop_large_units(om, unit, max_unit_size)     # same mention rows for edges and n_pages_used
    edges, evidence = build.cooccurrence(om, unit=unit, max_unit_size=max_unit_size)
    G = metrics.to_graph(nodes["node_id"], edges)
    node_df, info = metrics.node_metrics(G)
    node_df = nodes.merge(node_df, on="node_id", validate="one_to_one")
    used = om.drop_duplicates(["node_id", "doc_id", "page"]).groupby("node_id").size()
    # n_pages_used: distinct pages naming the node among the mentions kept by THIS variant's filters
    # (study window, page-size cut). Counted from mentions, not edge evidence, so single-organization
    # pages and isolates are included.
    node_df["n_pages_used"] = node_df["node_id"].map(used).fillna(0).astype(int)
    node_df = metrics.add_percentiles(node_df)
    return {"unit": unit, "edges": edges, "evidence": evidence, "graph": G,
            "stats": metrics.global_stats(G), "nodes": node_df, "betweenness_info": info,
            "params": {"unit": unit, "include_advocacy": include_advocacy, "max_unit_size": max_unit_size,
                       "study_window_only": study_window_only, "exclude_source_agency": exclude_source_agency}}


def share_in_source(prep: Prepared, agency: str, include_advocacy: bool = True) -> tuple[pd.Series, float]:
    """Per node: share of its pages on documents from `agency`'s files; and the same share over all
    pages that name any organization (the archive-wide baseline)."""
    om = pd.concat([prep.om, prep.adv]) if include_advocacy else prep.om
    docs = prep.tables["documents"]
    src = set(docs.loc[docs["agency"].eq(agency), "doc_id"])
    om = om.assign(in_src=om["doc_id"].isin(src))
    return om.groupby("node_id")["in_src"].mean(), float(om.drop_duplicates(["doc_id", "page"])["in_src"].mean())
