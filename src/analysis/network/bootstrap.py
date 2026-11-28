"""Document-level bootstrap: how stable are the ranks and the group comparisons?

The released archive is one sample of what the agencies produced. Resampling DOCUMENTS with
replacement (the unit that was released or withheld as a whole) and rebuilding the page network
each time shows how much a node's rank -- and each Hypothesis 1 comparison -- depends on which
documents happen to be in the release. Pages of a document drawn twice become distinct pages.

This is a stability check, not a significance test: it does not make the nodes independent,
and it cannot fix the advocacy groups' different detection method.
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from src.analysis.network import build, metrics, settings


def resample(om: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """om with documents drawn with replacement; copy c of document d gets doc_id 'd#c'."""
    docs = om["doc_id"].unique()
    draws = rng.integers(0, len(docs), len(docs))
    counts = pd.Series(np.bincount(draws, minlength=len(docs)), index=docs)
    c = om["doc_id"].map(counts).to_numpy()
    rep = om.loc[om.index.repeat(c)].copy()
    rep["copy"] = rep.groupby(["node_id", "doc_id", "page"]).cumcount()
    rep["doc_id"] = rep["doc_id"] + "#" + rep["copy"].astype(str)
    return rep.drop(columns="copy")


def _one(args):
    om, node_ids, seed = args
    rng = np.random.default_rng(seed)
    edges, _ = build.cooccurrence(resample(om, rng), unit="page")
    G = metrics.to_graph(node_ids, edges)
    nd, _ = metrics.node_metrics(G)
    nd = nd.set_index("node_id").loc[node_ids]
    return nd["degree"].to_numpy(float), nd["betweenness"].to_numpy(float)


def run(prep, net: dict, n_boot: int = settings.BOOTSTRAP_SAMPLES, seed: int = settings.SEED,
        n_jobs: int | None = None, cache: bool = True):
    """degree[n_boot, n_nodes], betweenness[n_boot, n_nodes] for the nodes of `net` (cached)."""
    node_ids = net["nodes"]["node_id"].tolist()
    path = settings.OUT / f"bootstrap_{n_boot}.npz"
    if cache and path.exists():
        z = np.load(path, allow_pickle=True)
        if list(z["node_ids"]) == node_ids:
            return node_ids, z["degree"], z["betweenness"]
    om = pd.concat([prep.om, prep.adv]) if net["params"]["include_advocacy"] else prep.om
    om = om[om["node_id"].isin(node_ids)][["node_id", "doc_id", "page"]].reset_index(drop=True)
    jobs = [(om, node_ids, seed + 10_000 + b) for b in range(n_boot)]
    n_jobs = n_jobs or max(1, os.cpu_count() or 1)
    if n_jobs == 1:
        out = [_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            out = list(ex.map(_one, jobs))
    deg, bt = np.vstack([d for d, _ in out]), np.vstack([b for _, b in out])
    settings.OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, degree=deg, betweenness=bt, node_ids=np.array(node_ids, dtype=object))
    return node_ids, deg, bt


def _pct(a: np.ndarray) -> np.ndarray:
    """Row-wise percentile rank (0-100, ties averaged), as metrics.add_percentiles."""
    return pd.DataFrame(a).T.rank(pct=True, method="average").T.to_numpy() * 100


def _rank(a: np.ndarray) -> np.ndarray:
    """Row-wise rank, 1 = highest, ties share the best rank (as robustness.add_ranks)."""
    return pd.DataFrame(a).T.rank(ascending=False, method="min").T.to_numpy()


def rank_intervals(node_ids, deg, bt, views: pd.DataFrame) -> pd.DataFrame:
    """Median and 95% interval of rank and percentile for each node of the hypothesis views."""
    pos = {n: i for i, n in enumerate(node_ids)}
    r_d, r_b, p_d, p_b = _rank(deg), _rank(bt), _pct(deg), _pct(bt)
    rows = []
    for _, v in views.drop_duplicates(["view", "node_id"]).iterrows():
        i = pos[v["node_id"]]
        row = {"view": v["view"], "name": v["name"]}
        for lab, a in (("rank_degree", r_d), ("rank_betweenness", r_b),
                       ("pct_degree", p_d), ("pct_betweenness", p_b)):
            lo, med, hi = np.percentile(a[:, i], [2.5, 50, 97.5])
            row.update({f"{lab}_lo": lo, f"{lab}_med": med, f"{lab}_hi": hi})
        rows.append(row)
    return pd.DataFrame(rows)


def comparison_stability(node_ids, deg, bt, views: pd.DataFrame) -> pd.DataFrame:
    """Share of bootstrap networks in which each Hypothesis 1 comparison (as worded in section 4) holds.

    'min > max' = every node of group A ranks above every node of group B;
    'median >'  = group A's median percentile is above group B's.
    """
    pos = {n: i for i, n in enumerate(node_ids)}
    idx = {g: [pos[n] for n in d["node_id"].unique()] for g, d in views.groupby("view")}
    adv = idx["public-health advocacy (exploratory)"]
    pcts = {"degree": _pct(deg), "betweenness": _pct(bt)}
    tests = [("municipal regulatory", "min > max"), ("municipal regulatory", "median >"),
             ("private real estate: all", "median >"), ("private real estate: manually confirmed", "median >"),
             ("private real estate: manually confirmed", "min > max")]
    rows = []
    for metric, P in pcts.items():
        for g, kind in tests:
            A, B = P[:, idx[g]], P[:, adv]
            holds = (A.min(1) > B.max(1)) if kind == "min > max" else (np.median(A, 1) > np.median(B, 1))
            rows.append({"metric": metric, "comparison": f"{g} {kind} advocacy", "share_of_bootstraps": holds.mean(),
                         "n_boot": len(P)})
    return pd.DataFrame(rows)
