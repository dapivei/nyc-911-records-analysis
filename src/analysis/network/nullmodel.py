"""Frequency-preserving null model: is a node central beyond what its mention count predicts?

The notebook's frequency check (Spearman rho 0.44-0.56) shows that centrality and how often an
organization is named move together, but it cannot say how much centrality a node would have
from frequency ALONE. This module answers that directly.

Null model (bipartite configuration model, sampled with the curveball algorithm,
Strona et al. 2014; Carstens 2015):
  * the data are a bipartite incidence: page <-> organizations named on it
  * a randomized incidence keeps, EXACTLY, (a) how many pages name each organization and
    (b) how many organizations each page names. Everything else -- WHICH organizations share
    a page -- is shuffled.
  * the randomized incidence is projected to a co-occurrence network exactly as the observed
    one is (pairs per page, no self-loops), and degree and betweenness are recomputed.

Repeating this gives, for every node, the degree and betweenness it would have if organizations
were named on pages independently of each other, given their frequency and the page sizes.
    z = (observed - null mean) / null sd
    p_upper = share of null samples >= observed (with the +1 correction)
A node with high raw betweenness but z ~ 0 is central because it is named often; a node with
high z sits between groups of organizations MORE than its frequency predicts.

Stratified variant (strata="source_agency"): curveball trades only between pages of documents
from the same source agency's files. This also preserves how each organization's mentions are
spread across the released archives (62% of documents with an organization are DEP's), so the
"whose files were released" bias is held fixed in the null as well.

Interpretation limits: the null is a reference, not a generative model of the archive.
Real co-occurrence is clustered (organizations named on the same kinds of forms), so most
nodes have FEWER distinct partners than the null; compare z-scores across nodes, not to 0.
"""
from __future__ import annotations

import os
import random
from concurrent.futures import ProcessPoolExecutor

import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp

from src.analysis.network import build, settings


# --- incidence ------------------------------------------------------------------------------

def incidence(om: pd.DataFrame, node_ids, documents: pd.DataFrame | None = None,
              strata: str | None = None, unit: str = "page"):
    """Page -> node index lists, plus a stratum label per page.

    om        organization mentions (node_id, doc_id, page)
    node_ids  fixed node order (isolates included; they simply have no page)
    strata    None (one stratum) or "source_agency" (documents.agency of the page's document)
    Returns (pages, page_strata, index) where pages is a list of int lists.
    """
    keys = build.UNIT_KEYS[unit]
    index = {n: i for i, n in enumerate(node_ids)}
    u = om[["node_id"] + keys].drop_duplicates()
    u = u[u["node_id"].isin(index)].assign(i=lambda d: d["node_id"].map(index))
    grouped = u.groupby(keys, sort=True)["i"].apply(list)
    pages = [list(x) for x in grouped.values]
    if strata is None:
        page_strata = np.zeros(len(pages), dtype=int)
    elif strata == "source_agency":
        doc_ids = grouped.index.get_level_values("doc_id") if unit == "page" else grouped.index
        agency = pd.Series(doc_ids).map(documents.set_index("doc_id")["agency"]).fillna("(none)")
        page_strata = pd.factorize(agency)[0]
    else:
        raise ValueError(f"unknown strata {strata!r}")
    return pages, page_strata, index


def curveball(pages, n_trades: int, rng: random.Random, page_strata=None):
    """Curveball randomization of a bipartite incidence (list of node lists per page).

    Each trade picks two pages (from the same stratum if page_strata is given), keeps the
    nodes they share and randomly redistributes the rest, preserving both pages' sizes and
    every node's page count. Returns a new list of sets.
    """
    P = [set(x) for x in pages]
    m = len(P)
    if page_strata is None:
        by_stratum = None
    else:
        page_strata = np.asarray(page_strata)
        by_stratum = {s: np.flatnonzero(page_strata == s).tolist() for s in np.unique(page_strata)}
    for _ in range(n_trades):
        a = rng.randrange(m)
        if by_stratum is None:
            b = rng.randrange(m)
        else:
            members = by_stratum[page_strata[a]]
            b = members[rng.randrange(len(members))]
        if a == b:
            continue
        A, B = P[a], P[b]
        ua, ub = A - B, B - A
        if not ua or not ub:
            continue
        pool = list(ua | ub)
        rng.shuffle(pool)
        shared, k = A & B, len(ua)
        P[a] = shared | set(pool[:k])
        P[b] = shared | set(pool[k:])
    return P


def project(pages, n_nodes: int) -> sp.csr_matrix:
    """Node x node co-occurrence counts (shared pages), zero diagonal: same rule as build.cooccurrence."""
    rows = [p for p, s in enumerate(pages) for _ in s]
    cols = [x for s in pages for x in s]
    B = sp.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(pages), n_nodes))
    C = (B.T @ B).tocsr()
    C.setdiag(0)
    C.eliminate_zeros()
    return C


def graph_metrics(C: sp.csr_matrix) -> tuple[np.ndarray, np.ndarray]:
    """Degree and exact normalized betweenness (unweighted, as in metrics.py) of a projected graph."""
    G = nx.from_scipy_sparse_array(C)
    G.add_nodes_from(range(C.shape[0]))
    degree = np.diff(C.indptr).astype(float)
    bt = nx.betweenness_centrality(G, normalized=True)
    return degree, np.array([bt[i] for i in range(C.shape[0])])


# --- sampling -------------------------------------------------------------------------------

def _one_sample(args):
    pages, page_strata, n_nodes, n_trades, seed = args
    rng = random.Random(seed)
    P = curveball(pages, n_trades, rng, page_strata)
    return graph_metrics(project(P, n_nodes))


def sample_null(pages, page_strata, n_nodes: int, n_samples: int = settings.NULL_SAMPLES,
                trades_per_page: int = settings.NULL_TRADES_PER_PAGE, seed: int = settings.SEED,
                n_jobs: int | None = None, stratified: bool = False):
    """n_samples independent randomizations (each from the observed incidence).

    Returns arrays degree[n_samples, n_nodes], betweenness[n_samples, n_nodes].
    """
    n_trades = trades_per_page * len(pages)
    strata_arg = page_strata if stratified else None
    jobs = [(pages, strata_arg, n_nodes, n_trades, seed + k) for k in range(n_samples)]
    n_jobs = n_jobs or max(1, (os.cpu_count() or 1))
    if n_jobs == 1:
        out = [_one_sample(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            out = list(ex.map(_one_sample, jobs))
    return np.vstack([d for d, _ in out]), np.vstack([b for _, b in out])


def mixing_check(pages, page_strata=None, multipliers=(1, 2, 5, 10, 20, 40), seed: int = settings.SEED):
    """Share of observed (page, node) incidences still present after k * n_pages trades.

    Once this share stops falling, further trades no longer move the sample away from the data:
    the chain has mixed. Used to justify settings.NULL_TRADES_PER_PAGE.
    """
    orig = {(p, n) for p, lst in enumerate(pages) for n in lst}
    rows = []
    for k in multipliers:
        P = curveball(pages, k * len(pages), random.Random(seed), page_strata)
        kept = sum((p, n) in orig for p, s in enumerate(P) for n in s) / len(orig)
        rows.append({"trades_per_page": k, "share_incidences_unchanged": kept})
    return pd.DataFrame(rows)


def compare(nodes: pd.DataFrame, node_ids, null_degree: np.ndarray, null_bt: np.ndarray) -> pd.DataFrame:
    """Observed vs null per node, for degree and betweenness.

    ratio_<m>   observed / null mean  (1 = exactly what frequency predicts; NaN if the null mean is 0)
    null_q_<m>  share of null networks in which the node's value is BELOW the observed one
                (ties count half): 1.0 = above every null sample, 0.5 = typical of the null.
                Bounded and comparable across nodes, so it is the frequency-adjusted score used
                for the group comparison.
    z_<m>       (observed - null mean) / null sd. Reported for completeness only: for rarely named
                nodes the null betweenness is ~0 with a tiny sd, so z explodes (values in the
                thousands) and is not comparable across nodes.
    p_upper_<m> one-sided Monte Carlo p-value, (#null >= observed + 1) / (S + 1).
    """
    out = nodes.set_index("node_id").loc[list(node_ids)].reset_index()
    S = null_degree.shape[0]
    tol = 1e-12
    for name, obs, null in (("degree", out["degree"].to_numpy(float), null_degree),
                            ("betweenness", out["betweenness"].to_numpy(float), null_bt)):
        mu, sd = null.mean(0), null.std(0, ddof=1)
        below = (null < obs[None, :] - tol).sum(0)
        ties = (np.abs(null - obs[None, :]) <= tol).sum(0)
        out[f"null_mean_{name}"] = mu
        out[f"null_sd_{name}"] = sd
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"ratio_{name}"] = np.where(mu > 0, obs / mu, np.nan)
            out[f"z_{name}"] = np.where(sd > 0, (obs - mu) / sd, np.nan)
        out[f"null_q_{name}"] = (below + 0.5 * ties) / S
        out[f"p_upper_{name}"] = ((null >= obs[None, :] - tol).sum(0) + 1) / (S + 1)
    return out


def group_table(cmp: pd.DataFrame, views_fn) -> pd.DataFrame:
    """Per hypothesis view: n, median raw percentile, median ratio and median null quantile."""
    v = views_fn(cmp)
    agg = {"n": ("node_id", "size")}
    for m in ("degree", "betweenness"):
        raw = "pct_degree_centrality" if m == "degree" else "pct_betweenness"
        agg.update({f"raw_pct_{m}": (raw, "median"), f"ratio_{m}": (f"ratio_{m}", "median"),
                    f"null_q_{m}": (f"null_q_{m}", "median")})
    return v.groupby("view", sort=False).agg(**agg).reset_index()


def run(prep, net: dict, strata: str | None = None, n_samples: int = settings.NULL_SAMPLES,
        cache: bool = True, n_jobs: int | None = None) -> pd.DataFrame:
    """Null-model comparison for every node of `net` (a pipeline.build_network result, page unit).

    Results are cached in outputs/network/null_<strata>_<n>.npz so the notebook does not redo
    the ~5 minutes of sampling; delete the file to resample.
    """
    if net["params"]["unit"] != "page":
        raise ValueError("null model is implemented for the page unit")
    node_ids = net["nodes"]["node_id"].tolist()
    om = pd.concat([prep.om, prep.adv]) if net["params"]["include_advocacy"] else prep.om
    pages, page_strata, _ = incidence(om, node_ids, prep.tables["documents"], strata or None)
    tag = strata or "global"
    path = settings.OUT / f"null_{tag}_{n_samples}.npz"
    if cache and path.exists():
        z = np.load(path, allow_pickle=True)
        if list(z["node_ids"]) == node_ids:
            return compare(net["nodes"], node_ids, z["degree"], z["betweenness"])
    deg, bt = sample_null(pages, page_strata, len(node_ids), n_samples, n_jobs=n_jobs,
                          stratified=strata is not None)
    settings.OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, degree=deg, betweenness=bt, node_ids=np.array(node_ids, dtype=object))
    return compare(net["nodes"], node_ids, deg, bt)
