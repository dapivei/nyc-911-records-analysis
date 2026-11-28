"""Edge weighting, statistically validated backbone and communities.

Three refinements of the raw page co-occurrence network (all page unit, node set fixed):

1. Hyperbolic (Newman 2001) weights -- a smooth replacement for the hard "> 7 organizations"
   page cut. A page naming k organizations contributes 1 / (k - 1) to each of its pairs, so
   every page gives each organization on it a total weight of 1 however long the list is.
   A 23-organization property list then counts as much as a two-party letter per organization,
   instead of creating 253 full-weight edges.
       weighted betweenness: shortest paths with distance = 1 / weight (strong ties are short)

2. Statistically validated network (Tumminello et al. 2011, PLoS ONE 6:e17994). For each pair
   with w shared pages, given that i is named on n_i pages, j on n_j, out of N pages:
       p = P(X >= w),  X ~ Hypergeometric(N, n_i, n_j)
   i.e. how surprising the overlap is if i and j were placed on pages independently. An edge is
   kept if p < alpha / (number of possible pairs) (Bonferroni over ALL n(n-1)/2 pairs, not only
   observed ones). Edges between two very frequent organizations need many shared pages to pass;
   one-off co-mentions of a frequent agency with a rare firm do not. This removes most of the
   "named on the same page because the agency is on every page" edges.

3. Communities (Louvain, networkx) on the validated backbone, to describe HOW the network is
   organized (which organizations form blocks) rather than only who ranks highest.
"""
from __future__ import annotations

import re

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import hypergeom

from src.analysis.network import build, metrics, settings


# --- 1. hyperbolic weights ---------------------------------------------------------------

def newman_edges(evidence: pd.DataFrame) -> pd.DataFrame:
    """Edges with weight_newman = sum over shared pages of 1 / (k - 1), k = organizations on the page."""
    return (evidence.assign(w=1.0 / (evidence["unit_size"] - 1))
            .groupby(["source", "target"]).agg(weight_newman=("w", "sum"), weight=("w", "size"))
            .reset_index())


def weighted_metrics(node_ids, edges: pd.DataFrame, weight_col: str = "weight_newman") -> pd.DataFrame:
    """Weighted strength and weighted betweenness (distance = 1 / weight), exact (Dijkstra-Brandes)."""
    G = nx.Graph()
    G.add_nodes_from(node_ids)
    for s, t, w in zip(edges["source"], edges["target"], edges[weight_col].astype(float)):
        G.add_edge(s, t, weight=w, distance=1.0 / w)
    bt = nx.betweenness_centrality(G, weight="distance", normalized=True)
    out = pd.DataFrame({"node_id": list(G.nodes())})
    out["strength_newman"] = out["node_id"].map(dict(G.degree(weight="weight")))
    out["betweenness_weighted"] = out["node_id"].map(bt)
    for m in ("strength_newman", "betweenness_weighted"):
        out[f"pct_{m}"] = out[m].rank(pct=True, method="average") * 100
    return out


# --- 2. validated backbone -----------------------------------------------------------------

def validate_edges(edges: pd.DataFrame, node_pages: pd.Series, n_units: int, n_nodes: int,
                   alpha: float = settings.BACKBONE_ALPHA) -> pd.DataFrame:
    """Add hypergeometric p-values and Bonferroni / Benjamini-Hochberg validation flags.

    edges       source, target, weight (= shared pages)
    node_pages  pages naming each node (index node_id), counted on the same mention rows
    n_units     pages with at least one organization (the population pages are drawn from)
    n_nodes     nodes in the network: the Bonferroni family is every possible pair
    """
    e = edges.copy()
    ni = e["source"].map(node_pages).to_numpy()
    nj = e["target"].map(node_pages).to_numpy()
    w = e["weight"].to_numpy()
    e["expected_weight"] = ni * nj / n_units
    e["p_hypergeom"] = hypergeom.sf(w - 1, n_units, ni, nj)
    n_tests = n_nodes * (n_nodes - 1) / 2
    e["validated_bonferroni"] = e["p_hypergeom"] < alpha / n_tests
    # BH over all possible pairs: unobserved pairs have p = 1 and never pass, so rank among observed
    order = np.argsort(e["p_hypergeom"].to_numpy())
    ranks = np.empty(len(e), dtype=float)
    ranks[order] = np.arange(1, len(e) + 1)
    passed = e["p_hypergeom"].to_numpy() <= alpha * ranks / n_tests
    cutoff = ranks[passed].max() if passed.any() else 0
    e["validated_fdr"] = ranks <= cutoff
    return e


def backbone_network(net: dict, prep, alpha: float = settings.BACKBONE_ALPHA, rule: str = "validated_bonferroni"):
    """Validated edges of a page network and node metrics recomputed on the backbone only.

    Returns (edges_with_tests, backbone_nodes). backbone_nodes has degree / betweenness /
    percentiles on the validated graph (prefix bb_) next to the original columns.
    """
    nodes = net["nodes"]
    om = pd.concat([prep.om, prep.adv]) if net["params"]["include_advocacy"] else prep.om
    om = om[om["node_id"].isin(nodes["node_id"])]
    keys = build.UNIT_KEYS["page"]
    n_units = om[keys].drop_duplicates().shape[0]
    node_pages = nodes.set_index("node_id")["n_pages_used"]
    e = validate_edges(net["edges"], node_pages, n_units, len(nodes), alpha)
    kept = e[e[rule]]
    G = metrics.to_graph(nodes["node_id"], kept)
    bb, _ = metrics.node_metrics(G)
    bb = metrics.add_percentiles(bb, ("degree_centrality", "betweenness"))
    bb = bb.rename(columns={c: f"bb_{c}" for c in bb.columns if c != "node_id"})
    return e, nodes.merge(bb, on="node_id", validate="one_to_one"), G


def backbone_stats(e: pd.DataFrame) -> pd.DataFrame:
    """How many edges / how much pair evidence survive each validation rule."""
    rows = []
    for rule in ("validated_bonferroni", "validated_fdr"):
        k = e[e[rule]]
        rows.append({"rule": rule, "edges_kept": len(k), "share_edges": len(k) / len(e),
                     "share_weight": k["weight"].sum() / e["weight"].sum(),
                     "median_weight_kept": k["weight"].median(),
                     "median_weight_dropped": e.loc[~e[rule], "weight"].median()})
    return pd.DataFrame(rows)


# --- 3. communities ------------------------------------------------------------------------

def communities(G: nx.Graph, node_info: pd.DataFrame, seed: int = settings.SEED, min_size: int = 10):
    """Louvain communities of the backbone (weighted by shared pages); summary of the larger ones.

    Returns (membership, summary): membership has node_id -> community (isolates = -1);
    summary lists each community with >= min_size nodes: size, modularity contribution not
    reported (Louvain is a heuristic), the 6 highest-degree members and the group mix.
    """
    H = G.subgraph([v for v in G if G.degree(v) > 0])
    comms = nx.community.louvain_communities(H, weight="weight", seed=seed)
    comms = sorted(comms, key=len, reverse=True)
    q = nx.community.modularity(H, comms, weight="weight")
    member = {v: i for i, c in enumerate(comms) for v in c}
    info = node_info.set_index("node_id")
    membership = pd.DataFrame({"node_id": list(G.nodes())})
    membership["community"] = membership["node_id"].map(member).fillna(-1).astype(int)
    deg = dict(H.degree())
    rows = []
    for i, c in enumerate(comms):
        if len(c) < min_size:
            continue
        top = sorted(c, key=lambda v: -deg[v])[:6]
        groups = info.loc[list(c), "group"].value_counts()
        rows.append({"community": i, "size": len(c),
                     "top_members": "; ".join(info.loc[top, "name"]),
                     "agencies": int((info.loc[list(c), "node_kind"] == "agency").sum()),
                     "group_mix": ", ".join(f"{g} {n}" for g, n in groups.head(4).items())})
    summary = pd.DataFrame(rows)
    summary.attrs["modularity"] = q
    summary.attrs["n_communities"] = len(comms)
    return membership, summary


def _ari(a, b) -> float:
    """Adjusted Rand index between two labelings (same node order), without sklearn."""
    from scipy.special import comb
    a, b = np.asarray(a), np.asarray(b)
    _, ai = np.unique(a, return_inverse=True)
    _, bi = np.unique(b, return_inverse=True)
    table = np.zeros((ai.max() + 1, bi.max() + 1), dtype=np.int64)
    np.add.at(table, (ai, bi), 1)
    sum_ij = comb(table, 2).sum()
    sum_a, sum_b = comb(table.sum(1), 2).sum(), comb(table.sum(0), 2).sum()
    expected = sum_a * sum_b / comb(len(a), 2)
    return float((sum_ij - expected) / (0.5 * (sum_a + sum_b) - expected))


def community_stability(G: nx.Graph, info: pd.DataFrame, pairs, n_seeds: int = 20):
    """Louvain is a heuristic: rerun it with n_seeds seeds.

    Returns (summary, pair_table): ARI of every run against seed settings.SEED (1 = identical
    partition), and for each named pair the share of runs that put both in the same block.
    """
    H = G.subgraph([v for v in G if G.degree(v) > 0])
    nodes = list(H)
    runs = []
    for s in [settings.SEED] + [settings.SEED + k for k in range(1, n_seeds)]:
        comms = nx.community.louvain_communities(H, weight="weight", seed=s)
        lab = {v: i for i, c in enumerate(comms) for v in c}
        runs.append(np.array([lab[v] for v in nodes]))
    aris = [_ari(runs[0], r) for r in runs[1:]]
    pos = {info.set_index("node_id").at[v, "name"]: i for i, v in enumerate(nodes)}
    rows = [{"pair": f"{a} + {b}", "same_block_share": float(np.mean([r[pos[a]] == r[pos[b]] for r in runs]))}
            for a, b in pairs if a in pos and b in pos]
    summary = pd.Series({"runs": len(runs), "ari_median": float(np.median(aris)), "ari_min": float(min(aris))})
    return summary, pd.DataFrame(rows)


# --- consensus blocks (Lancichinetti & Fortunato 2012) -------------------------------------

def coassignment(H: nx.Graph, n_runs: int, seed: int = settings.SEED, weight: str | None = "weight"):
    """n_runs Louvain partitions of H; returns (nodes, D) with D[i, j] = share of runs placing i and j together."""
    nodes = list(H)
    idx = {v: i for i, v in enumerate(nodes)}
    D = np.zeros((len(nodes), len(nodes)))
    for k in range(n_runs):
        for c in nx.community.louvain_communities(H, weight=weight, seed=seed + k):
            ii = np.fromiter((idx[v] for v in c), dtype=int)
            D[np.ix_(ii, ii)] += 1
    return nodes, D / n_runs


def consensus_communities(G: nx.Graph, info: pd.DataFrame, n_runs: int = settings.CONSENSUS_RUNS,
                          tau: float = settings.CONSENSUS_TAU, max_iter: int = 10, min_size: int = 10):
    """Blocks that do not depend on one Louvain seed (consensus clustering, Lancichinetti & Fortunato 2012).

    1. run Louvain n_runs times on the backbone; D = share of runs in which each pair shares a block
    2. keep pairs with D >= tau, run Louvain n_runs times on that consensus graph (weights = D), repeat
       until every run gives the same partition (or max_iter)
    Returns (membership, summary, D_first) like communities(); summary also has each block's
    'stability' = mean share of the ORIGINAL runs in which two of its members share a block.
    """
    H = G.subgraph([v for v in G if G.degree(v) > 0])
    nodes, D0 = coassignment(H, n_runs)
    D = D0.copy()
    for it in range(max_iter):
        C = nx.Graph()
        C.add_nodes_from(range(len(nodes)))
        ii, jj = np.where(np.triu(D, 1) >= tau)
        C.add_weighted_edges_from(zip(ii, jj, D[ii, jj]))
        parts = [nx.community.louvain_communities(C, weight="weight", seed=settings.SEED + 1000 + k)
                 for k in range(n_runs)]
        keys = {tuple(sorted(tuple(sorted(c)) for c in p)) for p in parts}
        if len(keys) == 1:
            break
        D = np.zeros_like(D)
        for p in parts:
            for c in p:
                c = np.fromiter(c, dtype=int)
                D[np.ix_(c, c)] += 1
        D /= n_runs
    final = sorted(parts[0], key=len, reverse=True)
    comms = [{nodes[i] for i in c} for c in final]
    member = {v: k for k, c in enumerate(comms) for v in c}
    membership = pd.DataFrame({"node_id": list(G.nodes())})
    membership["community"] = membership["node_id"].map(member).fillna(-1).astype(int)
    pos = {v: i for i, v in enumerate(nodes)}
    inf = info.set_index("node_id")
    deg = dict(H.degree())
    rows = []
    for k, c in enumerate(comms):
        if len(c) < min_size:
            continue
        ii = np.array([pos[v] for v in c])
        sub = D0[np.ix_(ii, ii)]
        stab = (sub.sum() - len(ii)) / (len(ii) * (len(ii) - 1))
        top = sorted(c, key=lambda v: -deg[v])[:6]
        rows.append({"community": k, "size": len(c), "stability": stab,
                     "top_members": "; ".join(inf.loc[top, "name"]),
                     "agencies": int((inf.loc[list(c), "node_kind"] == "agency").sum())})
    summary = pd.DataFrame(rows)
    summary.attrs["modularity"] = nx.community.modularity(H, [c for c in comms], weight="weight")
    summary.attrs["n_communities"] = len(comms)
    summary.attrs["iterations"] = it + 1
    summary.attrs["converged"] = len(keys) == 1
    return membership, summary, (nodes, D0)


# --- what each block's documents are about ---------------------------------------------------

_TITLE_STOP = set("""a an the and or of for to in on at by with from as is are was were be this that these those it its
into per via re vs not no all any each other than after before during within without between under over about
new york nyc city state ny inc llc corp co company dept department office bureau division agency page pages
letter memo memorandum report reports document documents form forms list lists record records file files
date dated undated jan feb mar apr may jun jul aug sep sept oct nov dec january february march april june
july august september october november december 2001 2002 2003 2004 2005 1999 2000 regarding concerning re
attached copy copies cover sheet sheets various miscellaneous misc unknown name names
world trade center wtc street avenue place lower manhattan""".split())   # every address / the site itself


def _title_words(t: str) -> set:
    return {w for w in re.findall(r"[a-z][a-z\-]{3,}", str(t).lower()) if w not in _TITLE_STOP}


def block_title_terms(evidence: pd.DataFrame, edges_validated: pd.DataFrame, membership: pd.DataFrame,
                      documents: pd.DataFrame, blocks, k: int = 6, min_docs: int = 5) -> pd.DataFrame:
    """Most distinctive document-title words for each block.

    Documents behind a block = documents with a page on which two members of the block share a
    VALIDATED tie. Score = share of the block's documents whose title has the word x log(that share /
    share of all documents in the archive with the word). Words in fewer than min_docs documents are skipped.
    """
    comm = membership.set_index("node_id")["community"]
    val = edges_validated[["source", "target"]].assign(v=True)
    ev = evidence.merge(val, on=["source", "target"])
    ev = ev.assign(cs=ev["source"].map(comm), ct=ev["target"].map(comm))
    ev = ev[ev["cs"] == ev["ct"]]
    titles = documents.set_index("doc_id")["title"]
    words_all = titles.map(_title_words)
    n_all = len(words_all)
    df_all = pd.Series([w for s in words_all for w in s]).value_counts()
    rows = []
    for cid in blocks:
        docs = ev.loc[ev["cs"] == cid, "doc_id"].unique()
        ws = words_all.reindex(docs).dropna()
        if len(ws) == 0:
            continue
        cnt = pd.Series([w for s in ws for w in s]).value_counts()
        cnt = cnt[cnt >= min_docs]
        share = cnt / len(ws)
        base = df_all.reindex(cnt.index) / n_all
        score = share * np.log(share / base)
        top = score.sort_values(ascending=False).head(k)
        rows.append({"community": cid, "documents": len(ws),
                     "terms": ", ".join(top.index),
                     "share_with_top_term": float(share[top.index[0]]) if len(top) else np.nan})
    return pd.DataFrame(rows)


# --- sensitivity of the backbone rule ------------------------------------------------------

def dep_strongest_ties(e: pd.DataFrame, node: str, names: pd.Series, min_weight: int = 20, k: int = 10):
    """A node's ties ranked by observed / expected shared pages (min_weight shared pages)."""
    t = e[(e["source"] == node) | (e["target"] == node)].copy()
    t["partner"] = np.where(t["source"] == node, t["target"], t["source"])
    t["partner_name"] = t["partner"].map(names)
    t["obs_over_exp"] = t["weight"] / t["expected_weight"]
    t = t[t["weight"] >= min_weight]
    return t.nlargest(k, "obs_over_exp")[["partner_name", "weight", "expected_weight", "obs_over_exp",
                                          "p_hypergeom", "validated_bonferroni", "validated_fdr"]]


def rule_sensitivity(net: dict, prep, rules=("validated_bonferroni", "validated_fdr")) -> pd.DataFrame:
    """Do the backbone conclusions depend on the validation rule? One row per rule."""
    nodes = net["nodes"]
    adv = set(nodes.loc[nodes["group"] == "public_health_advocacy", "node_id"])
    names = nodes.set_index("node_id")["name"]
    rows = []
    for rule in rules:
        e, bbn, G = backbone_network(net, prep, rule=rule)
        mem, comm = communities(G, prep.node_info)
        c = mem.set_index("node_id")["community"]
        hub = c[names[names == "NYC Dept. of Health and Mental Hygiene"].index[0]]
        top = set(comm["community"].head(6))
        between = [(c[u], c[v]) for u, v in G.edges() if c[u] != c[v] and c[u] in top and c[v] in top]
        bb = bbn.set_index("name")
        rows.append({"rule": rule, "edges_kept": G.number_of_edges(),
                     "advocacy_ties": sum(1 for u, v in G.edges() if u in adv or v in adv),
                     "modularity": comm.attrs["modularity"],
                     "ties_between_top6_blocks": len(between),
                     "share_between_ties_via_hub": float(np.mean([hub in p for p in between])) if between else np.nan,
                     "DEP_degree": int(bb.at["NYC Dept. of Environmental Protection", "bb_degree"]),
                     "DEP_and_DOHMH_same_block": bool(c[names[names == "NYC Dept. of Environmental Protection"].index[0]] == hub),
                     "EPA_and_DEP_same_block": bool(c[names[names == "U.S. EPA"].index[0]] ==
                                                    c[names[names == "NYC Dept. of Environmental Protection"].index[0]])})
    return pd.DataFrame(rows)
