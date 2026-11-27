"""Whole-network statistics, node centrality and descriptive group summaries.

Definitions (n = number of nodes in the network, isolates included):
  degree               number of distinct co-occurring organizations
  degree_centrality    degree / (n - 1)
  strength             sum of edge weights (shared pages) -- weighted degree
  betweenness          unweighted shortest-path betweenness on the FULL network,
                       normalised by (n - 1)(n - 2) / 2 (networkx normalized=True, undirected).
                       Nodes outside the largest component only lie on paths inside their own
                       component; in_lcc is reported so this can be checked.
  pct_<metric>         percentile rank of the metric within the network (0-100)

Groups are compared descriptively only (n, median, quartiles, min, max): nodes of one network
are not independent observations, two hypothesis groups have 4 nodes each, and the advocacy
nodes were found by a different method (text search), so a significance test would add false
precision rather than evidence.
"""
import time

import networkx as nx
import numpy as np
import pandas as pd

from src.analysis.network import settings


def to_graph(node_ids, edges: pd.DataFrame) -> nx.Graph:
    """Undirected networkx graph: every node (isolates included) and every edge with its weight."""
    G = nx.Graph()
    G.add_nodes_from(node_ids)
    G.add_weighted_edges_from(zip(edges["source"], edges["target"], edges["weight"].astype(float)),
                              weight="weight")
    return G


def global_stats(G: nx.Graph) -> dict:
    """Size, density, components, isolates, degree and edge-weight summaries of a graph."""
    n, m = G.number_of_nodes(), G.number_of_edges()
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    deg = np.array([d for _, d in G.degree()])
    w = np.array([d["weight"] for *_, d in G.edges(data=True)]) if m else np.array([0.0])
    return {
        "nodes": n, "edges": m, "density": nx.density(G),
        "components": len(comps), "largest_component_nodes": len(comps[0]) if comps else 0,
        "largest_component_share": len(comps[0]) / n if n else 0.0,
        "isolates": int((deg == 0).sum()),
        "degree_mean": deg.mean(), "degree_median": float(np.median(deg)), "degree_max": int(deg.max()),
        "weight_median": float(np.median(w)), "weight_mean": float(w.mean()), "weight_max": float(w.max()),
        "share_edges_weight_1": float((w == 1).mean()),
    }


def betweenness(G: nx.Graph) -> tuple[dict, dict]:
    """Exact unweighted betweenness (Brandes, O(n*m)) and how long it took.

    With ~1,650 nodes and ~11,000 edges this takes a few seconds, so no sampling is needed.
    """
    t0 = time.perf_counter()
    values = nx.betweenness_centrality(G, normalized=True)
    info = {"method": "exact (Brandes)", "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
            "seconds": round(time.perf_counter() - t0, 2)}
    return values, info


def node_metrics(G: nx.Graph) -> tuple[pd.DataFrame, dict]:
    """One row per node: degree, degree centrality, strength, betweenness, component size, in_lcc."""
    n = G.number_of_nodes()
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    comp_size = {v: len(c) for c in comps for v in c}
    lcc = comps[0] if comps else set()
    df = pd.DataFrame({"node_id": list(G.nodes())})
    df["degree"] = df["node_id"].map(dict(G.degree()))
    df["degree_centrality"] = df["degree"] / (n - 1)
    df["strength"] = df["node_id"].map(dict(G.degree(weight="weight"))).astype(float)
    bt, info = betweenness(G)
    df["betweenness"] = df["node_id"].map(bt)
    df["component_size"] = df["node_id"].map(comp_size)
    df["in_lcc"] = df["node_id"].isin(lcc)
    return df, info


def add_percentiles(df: pd.DataFrame, metrics=("degree_centrality", "strength", "betweenness")) -> pd.DataFrame:
    """Percentile rank (0-100) of each metric within the network; ties share the average rank."""
    out = df.copy()
    for m in metrics:
        out[f"pct_{m}"] = out[m].rank(pct=True, method="average") * 100
    return out


def hypothesis_views(nodes: pd.DataFrame) -> pd.DataFrame:
    """Nodes of the hypothesis groups, one row per (view, node).

    Views: municipal regulators; private real estate (all, i.e. manual + keyword rule);
    private real estate confirmed by hand (review_status == settings.CONFIRMED_STATUS);
    private real estate manual incl. 'manual (uncertain)'; public-health advocacy (exploratory).
    A node can appear in several real-estate views.
    """
    g, status = nodes["group"], nodes["review_status"]
    is_re = g.eq("private_real_estate")
    views = [
        ("municipal regulatory", g.eq("municipal_regulatory")),
        ("private real estate: all", is_re),
        ("private real estate: manual, incl. uncertain", is_re & status.str.startswith("manual")),
        ("private real estate: manually confirmed", is_re & status.eq(settings.CONFIRMED_STATUS)),
        ("public-health advocacy (exploratory)", g.eq("public_health_advocacy")),
    ]
    return pd.concat([nodes[mask].assign(view=name) for name, mask in views], ignore_index=True)


def group_summary(nodes: pd.DataFrame, metrics=("pct_degree_centrality", "pct_betweenness"),
                  by: str = "view") -> pd.DataFrame:
    """n, median, quartiles, min and max of each metric per group (or per view)."""
    long = nodes.melt(id_vars=[by], value_vars=list(metrics), var_name="metric")
    out = long.groupby([by, "metric"], sort=False)["value"].agg(
        n="size", median="median", q1=lambda s: s.quantile(.25), q3=lambda s: s.quantile(.75),
        min="min", max="max")
    return out.reset_index()
