"""Assertions behind the network: run `python -m src.analysis.network.verify` after run.py.

1. toy graph: every metric against hand-computed values
2. nodes / edges: no duplicates, source < target, no self-loops, no edges to unknown nodes
3. no join blow-up: evidence rows == sum over units of C(k, 2)
4. edge weights recomputed independently from raw entity_mentions (set intersection of pages)
5. agency-subgraph betweenness equals networkx on a separately built graph
6. group summaries recomputed directly from the saved node table; view membership is consistent
7. study-window network: pages used per node recounted from raw entity_mentions + documents
8. n_pages_used under the page-size cut: toy network through pipeline.build_network (single-organization
   pages and isolates included), and every node of the real scenario recounted from raw mentions
"""
import itertools

import networkx as nx
import numpy as np
import pandas as pd

import json

from src.analysis.network import build, classify, metrics, pipeline, settings


def check_toy():
    """Path a-b-c plus pendant d on b; pages: p1{a,b}, p2{a,b}, p3{b,c}, p4{b,d}, p5{a,b,c}."""
    om = pd.DataFrame([("a", "D1", 1), ("b", "D1", 1), ("a", "D1", 2), ("b", "D1", 2), ("b", "D2", 1),
                       ("c", "D2", 1), ("b", "D3", 1), ("d", "D3", 1), ("a", "D4", 1), ("b", "D4", 1),
                       ("c", "D4", 1), ("a", "D4", 1)],                # duplicate mention must not count twice
                      columns=["node_id", "doc_id", "page"])
    edges, evidence = build.cooccurrence(om, "page")
    w = {(r.source, r.target): r.weight for r in edges.itertuples()}
    assert w == {("a", "b"): 3, ("b", "c"): 2, ("b", "d"): 1, ("a", "c"): 1}, w
    assert len(evidence) == 1 + 1 + 1 + 1 + 3                       # C(2,2)*4 + C(3,2)
    small, _ = build.cooccurrence(om, "page", max_unit_size=2)      # drops the 3-organization page p5
    assert dict(zip(zip(small.source, small.target), small.weight)) == {("a", "b"): 2, ("b", "c"): 1, ("b", "d"): 1}
    doc_edges, _ = build.cooccurrence(om, "doc")
    assert dict(zip(zip(doc_edges.source, doc_edges.target), doc_edges.weight))[("a", "b")] == 2   # D1, D4
    G = metrics.to_graph(["a", "b", "c", "d", "e"], edges)            # e = isolate
    df, _ = metrics.node_metrics(G)
    df = metrics.add_percentiles(df).set_index("node_id")
    assert df.loc["b", "degree"] == 3 and df.loc["e", "degree"] == 0
    assert np.isclose(df.loc["b", "degree_centrality"], 3 / 4)
    assert df.loc["b", "strength"] == 3 + 2 + 1 and df.loc["a", "strength"] == 3 + 1
    # unweighted shortest paths among a,b,c,d (triangle a-b-c + pendant d):
    # b lies on every path from d -> {a, c}: 2 pairs; normalisation (n-1)(n-2)/2 = 6 for n = 5
    assert np.isclose(df.loc["b", "betweenness"], 2 / 6), df.loc["b", "betweenness"]
    assert np.isclose(df.loc["a", "betweenness"], 0.0)
    assert df.loc["b", "pct_degree_centrality"] == 100 and df["pct_degree_centrality"].min() == 20   # 5 nodes
    assert not df.loc["e", "in_lcc"]
    print("1. toy graph: all metrics match hand-computed values")


def check_outputs():
    nodes = pd.read_csv(settings.OUT / "nodes_main.csv")
    edges = pd.read_csv(settings.OUT / "edges_main.csv")
    ev = pd.read_parquet(settings.OUT / "edge_evidence_main.parquet")
    assert nodes["node_id"].is_unique, "duplicate nodes"
    assert not edges.duplicated(["source", "target"]).any(), "duplicate edges"
    assert (edges["source"] < edges["target"]).all(), "edge order / self-loop"
    assert set(edges["source"]).union(edges["target"]) <= set(nodes["node_id"]), "edge to unknown node"
    assert not ev.duplicated(["source", "target", "doc_id", "page"]).any(), "duplicate evidence"
    assert ev.groupby(["source", "target"]).size().sort_index().equals(
        edges.set_index(["source", "target"])["weight"].sort_index().rename(None)), "weight != evidence rows"
    sizes = ev.groupby(["doc_id", "page"])["unit_size"].first()
    assert len(ev) == int((sizes * (sizes - 1) / 2).sum()), "join blow-up"
    n = len(nodes)
    assert np.allclose(nodes["degree_centrality"], nodes["degree"] / (n - 1))
    deg = pd.concat([edges["source"], edges["target"]]).value_counts()
    assert (nodes.set_index("node_id")["degree"].reindex(deg.index) == deg).all(), "degree != edge count"
    print(f"2-3. {n} nodes / {len(edges)} edges: unique, ordered, no self-loops; evidence rows = sum C(k,2) "
          f"= {len(ev)}; degree = edge count")
    return nodes, edges


def raw_org_mentions() -> pd.DataFrame:
    """Organization mentions with node_id, rebuilt from raw entity_mentions without build.org_mentions."""
    em = build.read("entity_mentions", ["entity_type", "entity_id", "doc_id", "page"])
    em = em[em["entity_type"].isin(settings.ORG_TYPES)]
    agency_ids = set(em.loc[em["entity_type"] == "agency", "entity_id"])

    def node_of(row_type, eid):
        if row_type == "agency":
            return f"agency:{eid}"
        eid = classify.COMPANY_MERGES.get(eid, eid)
        return f"agency:{eid}" if eid in agency_ids else f"company:{eid}"

    em["node_id"] = [node_of(t, e) for t, e in zip(em["entity_type"], em["entity_id"])]
    return em


def check_weights_from_raw(edges: pd.DataFrame, n_edges: int = 25):
    """Recount page co-occurrence for sampled edges straight from entity_mentions (independent path)."""
    em = raw_org_mentions()
    pages = em.groupby("node_id")[["doc_id", "page"]].apply(lambda d: set(zip(d["doc_id"], d["page"])))
    sample = pd.concat([edges.head(10), edges.sample(n_edges - 10, random_state=settings.SEED)])
    for r in sample.itertuples():
        shared = pages[r.source] & pages[r.target]
        assert len(shared) == r.weight, (r.source, r.target, len(shared), r.weight)
    print(f"4. {len(sample)} edge weights (10 heaviest + {n_edges - 10} random) match an independent recount "
          f"from raw entity_mentions")


def check_against_networkx_on_component(nodes: pd.DataFrame, edges: pd.DataFrame):
    """Unweighted betweenness of the 30-agency subgraph equals networkx on a separately built graph."""
    ag = nodes[nodes["node_kind"] == "agency"]["node_id"]
    sub = edges[edges["source"].isin(ag) & edges["target"].isin(ag)]
    G = nx.Graph()
    G.add_nodes_from(ag)
    G.add_edges_from(itertools.zip_longest(sub["source"], sub["target"]))
    mine, _ = metrics.node_metrics(metrics.to_graph(ag, sub.assign(weight=1)))
    ref = nx.betweenness_centrality(G, normalized=True)
    assert np.allclose(mine.set_index("node_id")["betweenness"].reindex(list(ref)), list(ref.values()))
    print("5. agency-subgraph betweenness equals a direct networkx computation")


def check_group_summaries():
    """Baseline group medians recomputed from nodes_with_advocacy.csv with plain pandas."""
    nodes = pd.read_csv(settings.OUT / "nodes_with_advocacy.csv")
    summary = pd.read_csv(settings.OUT / "group_summary_by_scenario.csv")
    hyp = pd.read_csv(settings.OUT / "hypothesis_nodes_by_scenario.csv")
    base = summary[summary["scenario"] == summary["scenario"].iloc[0]].set_index(["view", "metric"])
    re_all = nodes[nodes["group"] == "private_real_estate"]
    expected = {
        "municipal regulatory": nodes[nodes["group"] == "municipal_regulatory"],
        "private real estate: all": re_all,
        "private real estate: manually confirmed": re_all[re_all["review_status"] == settings.CONFIRMED_STATUS],
        "public-health advocacy (exploratory)": nodes[nodes["group"] == "public_health_advocacy"],
    }
    for view, sub in expected.items():
        for m in ("pct_degree_centrality", "pct_betweenness"):
            row = base.loc[(view, m)]
            assert row["n"] == len(sub) and np.isclose(row["median"], sub[m].median()), (view, m)
    confirmed = set(hyp.loc[hyp["view"] == "private real estate: manually confirmed", "node_id"])
    assert confirmed <= set(hyp.loc[hyp["view"] == "private real estate: all", "node_id"])
    assert hyp.groupby(["scenario", "view"]).size().unstack().nunique().eq(1).all(), "view sizes differ by scenario"
    print(f"6. baseline group medians match a direct recomputation; confirmed real estate = {len(confirmed)} nodes "
          f"(subset of all {len(re_all)}); every scenario has the same nodes per group")


def check_window_filter():
    """Study-window pages per node (municipal + real-estate hypothesis nodes) recounted from raw tables."""
    hyp = pd.read_csv(settings.OUT / "hypothesis_nodes_by_scenario.csv")
    win = hyp[hyp["scenario"].str.contains("study window")]
    win = win[~win["view"].str.startswith("public-health")].drop_duplicates("node_id")
    assert len(win) > 0, "study-window scenario missing"
    docs = build.read("documents", ["doc_id", "in_study_window"])
    em = raw_org_mentions()
    em = em[em["doc_id"].isin(docs.loc[docs["in_study_window"], "doc_id"])]
    recount = em.drop_duplicates(["node_id", "doc_id", "page"]).groupby("node_id").size()
    got = win.set_index("node_id")["n_pages_used"]
    assert (recount.reindex(got.index).fillna(0).astype(int) == got).all(), "window page counts differ"
    print(f"7. study-window pages for {len(got)} municipal / real-estate nodes match a recount from raw tables")


def check_pages_used_filter():
    """n_pages_used counts the mentions kept by the page-size cut, including single-organization pages."""
    # toy: P1{a,b}, P2{a}, P3{a,b,c}, P4{e}; cut at 2 organizations drops P3 only
    om = pd.DataFrame([("a", "D", 1), ("b", "D", 1), ("a", "D", 2), ("a", "D", 3), ("b", "D", 3), ("c", "D", 3),
                       ("e", "D", 4)], columns=["node_id", "doc_id", "page"])
    info = pd.DataFrame({"node_id": list("abce")})
    prep = pipeline.Prepared({}, om, info, om, om.iloc[:0], info)
    full = pipeline.build_network(prep)["nodes"].set_index("node_id")
    cut = pipeline.build_network(prep, max_unit_size=2)["nodes"].set_index("node_id")
    assert full["n_pages_used"].to_dict() == {"a": 3, "b": 2, "c": 1, "e": 1}
    assert cut["n_pages_used"].to_dict() == {"a": 2, "b": 1, "c": 0, "e": 1}     # P2, P4 kept; P3 dropped
    assert cut.loc["e", "degree"] == 0 and cut.loc["c", "degree"] == 0          # isolates still counted

    # real data: recount every node of the page-size scenario from raw mentions + advocacy mentions
    cutoff = json.loads((settings.OUT / "run_metadata.json").read_text())["multi_org_page_cutoff"]
    hyp = pd.read_csv(settings.OUT / "hypothesis_nodes_by_scenario.csv")
    nodes = pd.read_csv(settings.OUT / "nodes_with_advocacy.csv")
    em = raw_org_mentions()
    em = pd.concat([em[em["node_id"].isin(nodes["node_id"])][["node_id", "doc_id", "page"]],
                    pd.read_csv(settings.OUT / "advocacy_mentions.csv")]).drop_duplicates()
    size = em.groupby(["doc_id", "page"])["node_id"].transform("size")
    recount = em[size <= cutoff].groupby("node_id").size()
    scen = hyp[hyp["scenario"].str.contains("without multi-organization")].drop_duplicates("node_id")
    got = scen.set_index("node_id")["n_pages_used"]
    assert (recount.reindex(got.index).fillna(0).astype(int) == got).all(), "page-size n_pages_used differs"
    assert (got <= scen.set_index("node_id")["n_pages"]).all() and (got < scen.set_index("node_id")["n_pages"]).any()
    print(f"8. n_pages_used under the page-size cut: toy (single-organization pages, isolates) correct; "
          f"{len(got)} hypothesis nodes match a recount from raw mentions")


if __name__ == "__main__":
    check_toy()
    nodes, edges = check_outputs()
    check_weights_from_raw(edges)
    check_against_networkx_on_component(nodes, edges)
    check_group_summaries()
    check_window_filter()
    check_pages_used_filter()
    print("all checks passed")
