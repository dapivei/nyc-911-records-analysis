"""Centrality over time: one page co-occurrence network per calendar month.

Why: the pooled network mixes very different moments of the response (emergency coordination,
air / dust testing, the residential clean-up program, litigation). A node can be a broker in one
phase and peripheral in another; pooling averages that away. Month-by-month networks show WHEN
each organization held its position.

Windows: calendar months 2001-09 .. 2002-12 (every month has >= 900 dated pages naming an
organization; 2003 onward is too thin for a monthly network). Only documents dated to the day or
month are used (year-only dates cannot be placed in a month).

Per month and node:
  pages         pages that month naming the node
  page_share    pages / all organization pages that month (volume)
  degree, betweenness   on that month's network (normalized within the month's active nodes)
  rank_betweenness      1 = highest that month
  ratio_betweenness, null_q_betweenness
                observed vs a frequency-preserving null for THAT month (nullmodel.py, curveball on
                the month's incidence; settings.TEMPORAL_NULL_SAMPLES samples), so a month with
                many DEP files does not by itself make DEP look central.
"""
from __future__ import annotations

import os
import random
from concurrent.futures import ProcessPoolExecutor

import networkx as nx
import numpy as np
import pandas as pd

from src.analysis.network import build, metrics, nullmodel, settings


def dated_mentions(prep, include_advocacy: bool = True) -> pd.DataFrame:
    """Organization mentions with the document's month (day- or month-precision dates only)."""
    om = pd.concat([prep.om, prep.adv]) if include_advocacy else prep.om
    d = prep.tables["documents"][["doc_id", "doc_date", "date_precision"]]
    om = om.merge(d, on="doc_id")
    om = om[om["date_precision"].isin(["day", "month"])].copy()
    om["month"] = pd.to_datetime(om["doc_date"]).dt.to_period("M")
    start, end = pd.Period(settings.TEMPORAL_START, "M"), pd.Period(settings.TEMPORAL_END, "M")
    return om[(om["month"] >= start) & (om["month"] <= end)]


def month_metrics(om_m: pd.DataFrame, n_null: int, seed: int) -> pd.DataFrame:
    """Metrics of one month's network (active nodes only) with a frequency-preserving null."""
    node_ids = sorted(om_m["node_id"].unique())
    edges, _ = build.cooccurrence(om_m, unit="page")
    G = metrics.to_graph(node_ids, edges)
    nd, _ = metrics.node_metrics(G)
    pages = om_m.drop_duplicates(["node_id", "doc_id", "page"]).groupby("node_id").size()
    n_pages_month = om_m[["doc_id", "page"]].drop_duplicates().shape[0]
    nd["pages"] = nd["node_id"].map(pages)
    nd["page_share"] = nd["pages"] / n_pages_month
    nd["rank_betweenness"] = nd["betweenness"].rank(ascending=False, method="min").astype(int)
    nd["rank_degree"] = nd["degree"].rank(ascending=False, method="min").astype(int)
    # frequency-preserving null for this month
    inc, _, _ = nullmodel.incidence(om_m, nd["node_id"].tolist())
    rng = random.Random(seed)
    null_bt = []
    for _ in range(n_null):
        P = nullmodel.curveball(inc, settings.NULL_TRADES_PER_PAGE * len(inc), rng)
        null_bt.append(nullmodel.graph_metrics(nullmodel.project(P, len(nd)))[1])
    null_bt = np.vstack(null_bt)
    obs = nd["betweenness"].to_numpy(float)
    mu = null_bt.mean(0)
    with np.errstate(divide="ignore", invalid="ignore"):
        nd["ratio_betweenness"] = np.where(mu > 0, obs / mu, np.nan)
    tol = 1e-12
    nd["null_q_betweenness"] = ((null_bt < obs - tol).sum(0) + 0.5 * (np.abs(null_bt - obs) <= tol).sum(0)) / n_null
    nd["n_nodes_month"], nd["n_pages_month"] = len(nd), n_pages_month
    return nd


def _month_job(args):
    month, om_m, n_null, seed = args
    return month_metrics(om_m, n_null, seed).assign(month=month)


def run(prep, n_null: int = settings.TEMPORAL_NULL_SAMPLES, cache: bool = True,
        n_jobs: int | None = None) -> pd.DataFrame:
    """One row per (month, active node). Cached in outputs/network/temporal_<n_null>.csv."""
    path = settings.OUT / f"temporal_{n_null}.csv"
    if cache and path.exists():
        out = pd.read_csv(path)
        out["month"] = pd.PeriodIndex(out["month"], freq="M")
    else:
        om = dated_mentions(prep)
        jobs = [(month, om_m[["node_id", "doc_id", "page"]], n_null, settings.SEED + 100 * k)
                for k, (month, om_m) in enumerate(om.groupby("month", sort=True))]
        n_jobs = n_jobs or max(1, os.cpu_count() or 1)
        if n_jobs == 1:
            rows = [_month_job(j) for j in jobs]
        else:
            with ProcessPoolExecutor(max_workers=n_jobs) as ex:
                rows = list(ex.map(_month_job, jobs))
        out = pd.concat(rows, ignore_index=True)
        settings.OUT.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
    info = prep.node_info.set_index("node_id")[["name", "group", "node_kind", "review_status"]]
    return out.drop(columns=[c for c in info.columns if c in out.columns]).join(info, on="node_id")


def group_by_month(tm: pd.DataFrame, views_fn) -> pd.DataFrame:
    """Per month and hypothesis view: nodes active, total page share, median null quantile of betweenness."""
    v = views_fn(tm)
    return (v.groupby(["view", "month"])
            .agg(active=("node_id", "size"), page_share=("page_share", "sum"),
                 median_null_q_betweenness=("null_q_betweenness", "median"),
                 best_rank_betweenness=("rank_betweenness", "min"))
            .reset_index())


def phase_brokers(tm: pd.DataFrame, k: int = 5, min_pages: int = 20) -> pd.DataFrame:
    """Per month: the k nodes whose betweenness most exceeds the null (ratio, among nodes with >= min_pages)."""
    t = tm[(tm["pages"] >= min_pages) & (tm["null_q_betweenness"] >= 0.95)]
    top = (t.sort_values(["month", "ratio_betweenness"], ascending=[True, False])
           .groupby("month").head(k))
    return (top.groupby("month")
            .apply(lambda g: "; ".join(f"{n} ({r:.1f}x)" for n, r in zip(g["name"], g["ratio_betweenness"])),
                   include_groups=False)
            .rename("brokers_above_null").reset_index())


# --- what the Law Department's pages are ------------------------------------------------------

LAW_DOC_TYPES = [   # first match wins; patterns on document titles (checked against a page sample, notebook 6f)
    ("emergency contract / procurement", r"emergenc|procure|contract|bid|purchase"),
    ("license agreement with a building owner", r"licen[cs]e agreement|license|cleaning agreement|cleanup agreement"),
    ("document preservation / legal hold", r"preserv|legal hold|custody notice|retention|divider|slip sheet|records folder|folder"),
    ("legal correspondence / inquiry / claim", r"legal|claim|inquir|subpoena|litigation|counsel|foil|court"),
]


def law_department_documents(prep, node_id: str = "agency:nyc-law") -> pd.DataFrame:
    """Law Department pages per month by document type (from document titles), dated documents only."""
    om = dated_mentions(prep)
    law = om[om["node_id"] == node_id].drop_duplicates(["doc_id", "page"])
    titles = law["doc_id"].map(prep.tables["documents"].set_index("doc_id")["title"]).fillna("").str.lower()
    kind = pd.Series("other (reports, inspections, monitoring, misc.)", index=law.index)
    for label, pattern in reversed(LAW_DOC_TYPES):
        kind[titles.str.contains(pattern, regex=True)] = label
    return law.assign(doc_type=kind).groupby(["month", "doc_type"]).size().unstack(fill_value=0)


# --- phases from the data -----------------------------------------------------------------

def broker_profiles(tm: pd.DataFrame, min_pages: int = 20, q: float = 0.95) -> pd.DataFrame:
    """Month x organization matrix: log2(observed / expected betweenness) where the organization connects
    the response beyond its volume that month (>= min_pages pages, beats >= q of the nulls), else 0.
    Columns = organizations that do so in at least one month."""
    sig = (tm["pages"] >= min_pages) & (tm["null_q_betweenness"] >= q) & (tm["ratio_betweenness"] > 1)
    ratio = tm["ratio_betweenness"].fillna(1.0).clip(lower=1.0, upper=16)
    v = tm.assign(val=np.where(sig, np.log2(ratio), 0.0))
    cols = v.loc[sig, "name"].unique()
    return v[v["name"].isin(cols)].pivot_table(index="month", columns="name", values="val", fill_value=0.0)


def segment_months(X: pd.DataFrame, k: int) -> list[int]:
    """Exact optimal split of the ordered months into k contiguous phases (minimum within-phase sum of squared
    distances to the phase mean; dynamic programming, Fisher 1958). Returns the start index of each phase."""
    A = X.to_numpy(float)
    n = len(A)
    cost = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            seg = A[i:j + 1]
            cost[i, j] = ((seg - seg.mean(0)) ** 2).sum()
    best = np.full((k + 1, n + 1), np.inf)
    arg = np.zeros((k + 1, n + 1), dtype=int)
    best[0, 0] = 0.0
    for m in range(1, k + 1):
        for j in range(1, n + 1):
            for i in range(m - 1, j):
                c = best[m - 1, i] + cost[i, j - 1]
                if c < best[m, j]:
                    best[m, j], arg[m, j] = c, i
    starts, j = [], n
    for m in range(k, 0, -1):
        i = arg[m, j]
        starts.append(i)
        j = i
    return sorted(starts)


def _profiles(tm: pd.DataFrame, method: str) -> pd.DataFrame:
    X = broker_profiles(tm)
    if method == "presence":        # which organizations connect beyond volume (robust to extreme ratios)
        return (X > 0).astype(float)
    if method == "strength":        # how far above expectation (log2 ratio)
        return X
    raise ValueError(method)


def data_phases(tm: pd.DataFrame, k: int = 3, method: str = "presence") -> list[tuple]:
    """(first_month, last_month) of each data-driven phase."""
    X = _profiles(tm, method)
    months = list(X.index)
    st = segment_months(X, k) + [len(months)]
    return [(months[a], months[b - 1]) for a, b in zip(st[:-1], st[1:])]


def phase_table(tm: pd.DataFrame, ks=(2, 3, 4, 5, 6), methods=("presence", "strength")) -> pd.DataFrame:
    """Data-driven phase boundaries for several k and both profile definitions, with the share of
    month-to-month variation the split explains."""
    return pd.concat([_phase_table(_profiles(tm, m), ks).assign(profile=m) for m in methods], ignore_index=True)


def _phase_table(X: pd.DataFrame, ks) -> pd.DataFrame:
    total = ((X.to_numpy() - X.to_numpy().mean(0)) ** 2).sum()
    months = list(X.index)
    rows = []
    for k in ks:
        st = segment_months(X, k)
        bounds = st + [len(months)]
        within = sum(((X.iloc[a:b] - X.iloc[a:b].mean()) ** 2).to_numpy().sum() for a, b in zip(bounds[:-1], bounds[1:]))
        rows.append({"phases": k,
                     "phase_starts": ", ".join(months[s].strftime("%b %Y") for s in st),
                     "variation_explained": 1 - within / total})
    return pd.DataFrame(rows)
