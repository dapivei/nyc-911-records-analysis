"""Sensitivity checks for the two choices that could change the conclusions.

Scenarios (each rebuilds the network, with the 4 exploratory advocacy nodes included, and
recomputes every metric and percentile):
  * baseline                       page co-occurrence
  * without multi-organization pages   page co-occurrence, dropping pages that name more
                                   organizations than the p99 of multi-organization pages.
                                   The rule uses page size only: it does not identify what kind
                                   of document a page belongs to.
  * document co-occurrence         the alternative unit rejected for the main analysis
  * study window only              page co-occurrence using only mentions on documents dated
                                   2001-09-11..2009-12-31 (advocacy mentions filtered the same way;
                                   undated documents dropped). Node set fixed: nodes with no
                                   mention left are isolates (refiltered_ranks recomputes the percentiles
                                   within the active-node subset as a check).

Percentiles are recomputed within each network, so a group's percentile can rise while its raw
degree or betweenness falls (other nodes fell more). Raw values and ranks are kept for checking.

The classification sensitivity (all real-estate nodes vs those confirmed by hand) is applied in
every scenario through metrics.hypothesis_views().
"""
import pandas as pd

from src.analysis.network import build, metrics, pipeline

BASELINE = "baseline: page co-occurrence"
WINDOW = "page, study window only (2001-09-11 to 2009-12-31)"


def add_ranks(nd: pd.DataFrame) -> pd.DataFrame:
    """Rank among all nodes of the network (1 = highest; ties share the best rank)."""
    return nd.assign(rank_degree=nd["degree"].rank(ascending=False, method="min").astype(int),
                     rank_betweenness=nd["betweenness"].rank(ascending=False, method="min").astype(int))


def refiltered_ranks(net: dict) -> pd.DataFrame:
    """Percentiles recomputed within the subset of active nodes (>= 1 mention kept in this variant).

    The network is NOT rebuilt: degree, betweenness and every other metric are those of the full
    fixed-node network. Degree and the unnormalised betweenness path counts would be the same in a
    rebuilt smaller network (the dropped nodes are isolates); normalised betweenness would not,
    because it divides by (n - 1)(n - 2) / 2 with the smaller n. Percentile ranks are unaffected by
    that common rescaling, but the absolute betweenness values here are the full-network ones.
    """
    nd = net["nodes"]
    kept = nd[nd["n_pages_used"] > 0]
    return metrics.add_percentiles(kept[[c for c in kept.columns if not c.startswith("pct_")]])


def scenarios(prep: pipeline.Prepared) -> dict:
    """Scenario name -> keyword arguments for pipeline.build_network."""
    page_cut = build.large_unit_cutoff(prep.om, "page")
    return {
        BASELINE: dict(unit="page"),
        f"page, without multi-organization pages (> {page_cut:.0f} orgs)": dict(unit="page", max_unit_size=page_cut),
        "document co-occurrence": dict(unit="doc"),
        WINDOW: dict(unit="page", study_window_only=True),
    }


def run(prep: pipeline.Prepared):
    """Returns (summary, group_summary, hypothesis_nodes, nets) over all scenarios."""
    nets, rows, summaries, views = {}, [], [], []
    for name, kw in scenarios(prep).items():
        net = pipeline.build_network(prep, include_advocacy=True, **kw)
        nets[name] = net
        nd, st = net["nodes"], net["stats"]
        extracted = nd[nd["node_kind"] != "advocacy"]
        rows.append({"scenario": name, "nodes": st["nodes"], "edges": st["edges"], "density": st["density"],
                     "lcc_share": st["largest_component_share"], "isolates": st["isolates"],
                     "top5_degree": "; ".join(extracted.nlargest(5, "degree_centrality")["name"]),
                     "top5_betweenness": "; ".join(extracted.nlargest(5, "betweenness")["name"])})
        v = metrics.hypothesis_views(add_ranks(nd))
        summaries.append(metrics.group_summary(v).assign(scenario=name))
        views.append(v.assign(scenario=name))
    cols = ["scenario", "view", "node_id", "name", "review_status", "n_pages", "n_pages_used", "degree",
            "betweenness", "rank_degree", "rank_betweenness", "pct_degree_centrality", "pct_betweenness"]
    return (pd.DataFrame(rows), pd.concat(summaries, ignore_index=True),
            pd.concat(views, ignore_index=True)[cols], nets)
