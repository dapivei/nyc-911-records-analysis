"""Figures for the RQ1 network analysis (static PNG, matplotlib).

Color carries only the three hypothesis groups (validated palette: worst all-pairs CVD
dE 9.2); every other group is neutral gray. Group names are always printed as text
(axis labels / direct labels), so identity never depends on color alone.
"""
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.network import classify, settings  # noqa: E402

SURFACE, INK, INK2, GRID, OTHER = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#a9a8a2"
GROUP_COLOR = {"municipal_regulatory": "#2a78d6", "private_real_estate": "#eb6834",
               "public_health_advocacy": "#1baf7a"}
SHORT = {  # short labels for the network plot
    "NYC Dept. of Environmental Protection": "DEP", "NYC Dept. of Health and Mental Hygiene": "DOHMH",
    "NYC Dept. of Buildings": "DOB", "NYC Dept. of Housing Preservation and Development": "HPD",
    "NYC Office of Emergency Management": "OEM", "NYC Board of Education": "Bd. of Ed.",
    "NYC Office of the Mayor": "Mayor", "NYC Law Department": "Law Dept.",
    "NYC Dept. of Citywide Administrative Services": "DCAS", "NYC Dept. of Design and Construction": "DDC",
    "NYC Dept. of Sanitation": "DSNY", "NYC Dept. of Records and Information Services": "DORIS",
    "NYS Dept. of Health": "NYS DOH", "NYS Dept. of Environmental Conservation": "NYS DEC",
    "Lower Manhattan Development Corporation": "LMDC", "Battery Park City Authority": "BPCA",
    "Port Authority of NY & NJ": "Port Auth.", "U.S. Army Corps of Engineers": "USACE",
    "American Red Cross": "Red Cross", "NYCOSH (NY Committee for Occupational Safety & Health)": "NYCOSH",
    "Natural Resources Defense Council": "NRDC", "American Lung Association": "Am. Lung Assn.",
    "9/11 Environmental Action": "9/11 Env. Action",
}


def color_of(group: str) -> str:
    """Hex color for a group; every group outside the hypothesis groups is gray."""
    return GROUP_COLOR.get(group, OTHER)


def short(name: str, width: int = 34) -> str:
    """Display name: a hand-shortened label if one exists, else the name truncated to width."""
    return SHORT.get(name, textwrap.shorten(name, width, placeholder="…"))


def _style(ax):
    """Recessive axes: no top/right spines, light x grid, secondary-ink ticks."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _legend_handles(groups=GROUP_COLOR, other_label="Any other group"):
    """Square legend markers for the hypothesis groups plus one gray 'other' entry."""
    hs = [plt.Line2D([], [], marker="s", ls="", ms=8, color=c, label=classify.GROUP_LABELS[g])
          for g, c in groups.items()]
    hs.append(plt.Line2D([], [], marker="s", ls="", ms=8, color=OTHER, label=other_label))
    return hs


def _footer(fig, text):
    """Caption text in the bottom-left corner of the figure."""
    fig.text(0.01, 0.005, textwrap.fill(text, 170), fontsize=7, color=INK2, va="bottom", ha="left")


def _save(fig, name):
    """Write the figure as PNG to outputs/figures/network/ and close it."""
    settings.FIGURES.mkdir(parents=True, exist_ok=True)
    path = settings.FIGURES / name
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


# --- 1. ranking --------------------------------------------------------------------------

def top_ranking(nodes: pd.DataFrame, n: int = settings.TOP_N_RANKING):
    """Fig 1: top-n organizations by degree centrality, strength and betweenness, colored by group."""
    metrics = [("degree_centrality", "Degree centrality (degree / (n-1))"),
               ("strength", "Strength (sum of shared pages)"),
               ("betweenness", "Betweenness (unweighted, normalised)")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 7.2), facecolor=SURFACE)
    for ax, (m, title) in zip(axes, metrics):
        top = nodes.nlargest(n, m).iloc[::-1]
        labels = [f"{short(r.name, 30)}  ({r.n_pages:,} p.)" for r in top.itertuples()]
        ax.barh(labels, top[m], color=[color_of(g) for g in top["group"]], height=0.7)
        _style(ax)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.tick_params(axis="y", labelsize=7.5)
    fig.suptitle(f"Top {n} organizations in the page co-occurrence network (extracted entities)",
                 x=0.01, ha="left", y=0.985, fontsize=12, color=INK)
    fig.legend(handles=_legend_handles(), loc="upper left", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.005, 0.95))
    _footer(fig, "Label = organization (pages on which it is named). An edge = both organizations named on "
                 "the same page; rankings describe co-occurrence in this archive, not communication, influence or "
                 "power. Agencies' page counts are large partly because their names appear in method / regulation "
                 "citations and because most files come from DEP.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    return _save(fig, "fig1_top_centrality.png")


# --- 2. hypothesis groups, baseline vs without multi-organization pages --------------

VIEW_GROUP = {"municipal regulatory": "municipal_regulatory",
              "private real estate: all": "private_real_estate",
              "private real estate: manually confirmed": "private_real_estate",
              "public-health advocacy (exploratory)": "public_health_advocacy"}


def hypothesis_groups(views: pd.DataFrame, scenarios: list[str], scenario_labels: list[str]):
    """Fig 2: every node of the hypothesis groups, as percentile ranks, in two network variants.

    views: rows from metrics.hypothesis_views() with a 'scenario' column (robustness.run output).
    Filled dots = first scenario, hollow dots = second; black tick = median of the row.
    """
    metric_titles = [("pct_degree_centrality", "Degree centrality, percentile in network"),
                     ("pct_betweenness", "Betweenness, percentile in network")]
    rows = [(v, s, lab) for v in VIEW_GROUP for s, lab in zip(scenarios, scenario_labels)]
    y_of = {}
    y = 0.0
    for i, (v, s, _) in enumerate(rows):
        if i and rows[i - 1][0] != v:
            y += 0.6                                         # gap between groups
        y_of[(v, s)] = y
        y += 1
    rng = np.random.default_rng(settings.SEED)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.6), sharey=True, facecolor=SURFACE)
    for ax, (m, title) in zip(axes, metric_titles):
        for v, s, _ in rows:
            vals = views.loc[(views["view"] == v) & (views["scenario"] == s), m].to_numpy()
            yy = y_of[(v, s)] + (rng.uniform(-0.25, 0.25, len(vals)) if len(vals) > 10 else np.zeros(len(vals)))
            c = color_of(VIEW_GROUP[v])
            filled = s == scenarios[0]
            ax.scatter(vals, yy, s=16 if len(vals) > 10 else 40, alpha=0.6 if len(vals) > 10 else 1,
                       facecolors=c if filled else "none", edgecolors=c, linewidths=1.2, zorder=3)
            if len(vals):
                ax.plot([np.median(vals)], [y_of[(v, s)]], marker="|", ms=18, mew=2.5, color=INK, zorder=4)
        _style(ax)
        ax.set_xlim(0, 101)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("percentile rank among all nodes of that network (0-100)")
    n_of = views[views["scenario"] == scenarios[0]].groupby("view").size()
    axes[0].set_yticks([y_of[(v, s)] for v, s, _ in rows])
    axes[0].set_yticklabels([f"{v} (n={n_of.get(v, 0)})  ·  {lab}" for v, s, lab in rows], fontsize=8)
    axes[0].invert_yaxis()
    fig.suptitle("Hypothesis groups: all pages (filled) vs without multi-organization pages (hollow)",
                 x=0.01, ha="left", fontsize=12, color=INK)
    _footer(fig, "Each dot is one organization; black tick = median of the row. Percentiles are recomputed in each "
                 "network. 'Without multi-organization pages' drops pages naming more organizations than the p99 of "
                 "pages with >= 2 organizations; it is a page-size rule, not a document type. 'Manually confirmed' = "
                 "real-estate nodes whose group was checked by hand (the others were assigned by a keyword rule). "
                 "Advocacy nodes come from a fixed name list searched in page text, so their recall differs from the "
                 "extracted organizations; with n = 4 per group the comparison is descriptive only.")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    return _save(fig, "fig2_hypothesis_groups.png")


# --- 3. frequency vs centrality ------------------------------------------------------

def frequency_vs_degree(nodes: pd.DataFrame, label_ids=()):
    """Fig 3: documents naming an organization vs its degree (log-log), to show frequency effects."""
    fig, ax = plt.subplots(figsize=(9.5, 6.5), facecolor=SURFACE)
    base = nodes[~nodes["group"].isin(GROUP_COLOR)]
    ax.scatter(base["n_pages"], base["degree"] + 1, s=10, color=OTHER, alpha=0.5, linewidths=0)
    for g, c in GROUP_COLOR.items():
        sub = nodes[nodes["group"] == g]
        ax.scatter(sub["n_pages"], sub["degree"] + 1, s=28, color=c, edgecolors=SURFACE, linewidths=1.2, zorder=3)
    offsets = [(5, 4), (5, -11), (-8, 6), (5, 12)]
    for i, r in enumerate(nodes[nodes["node_id"].isin(label_ids)].sort_values("n_pages").itertuples()):
        dx, dy = {"U.S. EPA": (-7, -3), "NYC Dept. of Environmental Protection": (-7, 4)}.get(
            r.name, offsets[i % len(offsets)])
        ax.annotate(short(r.name, 24), (r.n_pages, r.degree + 1), xytext=(dx, dy), textcoords="offset points",
                    fontsize=7.5, color=INK, ha="right" if dx < 0 else "left")
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_xlabel("pages on which the organization is named (log)")
    ax.set_ylabel("degree + 1 (log)")
    ax.legend(handles=_legend_handles(), frameon=False, fontsize=8, loc="upper left")
    rho = nodes["n_pages"].corr(nodes["degree"], method="spearman")
    ax.set_title(f"Degree rises with how often an organization is named (Spearman rho = {rho:.2f})",
                 fontsize=12, color=INK, loc="left")
    _footer(fig, "Each dot is one organization. Points far above the trend gain many co-occurrence partners from "
                 "few pages, typically because those pages name many organizations at once.")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return _save(fig, "fig3_frequency_vs_degree.png")


# --- 4. network subgraph -------------------------------------------------------------

def network_plot(net: dict, n_companies: int = settings.NETWORK_FIG_TOP_COMPANIES, min_weight: int = 10):
    """All agencies + the n most-documented companies + advocacy nodes; edges with weight >= min_weight."""
    nodes = net["nodes"]
    keep = pd.concat([nodes[nodes["node_kind"].isin(["agency", "advocacy"])],
                      nodes[nodes["node_kind"] == "company"].nlargest(n_companies, "n_docs")])
    keep_ids = set(keep["node_id"])
    G = net["graph"]
    H = nx.Graph()
    H.add_nodes_from(keep_ids)
    H.add_edges_from((u, v, d) for u, v, d in G.edges(data=True)
                     if u in keep_ids and v in keep_ids and d["weight"] >= min_weight)
    info = keep.set_index("node_id")
    isolated = sorted(short(info.loc[v, "name"], 22) for v in H.nodes() if H.degree(v) == 0)
    H.remove_nodes_from([v for v in list(H.nodes()) if H.degree(v) == 0])
    # Kamada-Kawai is deterministic given the graph; the seed only matters for the spring fallback
    pos = nx.kamada_kawai_layout(H, weight=None) if nx.is_connected(H) else \
        nx.spring_layout(H, weight=None, k=0.6, iterations=500, seed=settings.SEED)
    fig, ax = plt.subplots(figsize=(13, 11), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    w = np.array([d["weight"] for *_, d in H.edges(data=True)], float)
    nx.draw_networkx_edges(H, pos, ax=ax, width=0.3 + 2.2 * np.log10(w) / np.log10(w.max()),
                           edge_color="#c9c8c2", alpha=0.7)
    sizes = 25 + 900 * np.sqrt(info.loc[list(H.nodes()), "n_pages"] / info["n_pages"].max())
    colors = [color_of(info.loc[v, "group"]) for v in H.nodes()]
    shapes = {"agency": "s", "company": "o", "advocacy": "D"}
    for kind, marker in shapes.items():
        nl = [v for v in H.nodes() if info.loc[v, "node_kind"] == kind]
        idx = [list(H.nodes()).index(v) for v in nl]
        nx.draw_networkx_nodes(H, pos, nodelist=nl, ax=ax, node_shape=marker,
                               node_size=[sizes.iloc[i] for i in idx], node_color=[colors[i] for i in idx],
                               edgecolors=SURFACE, linewidths=1.5)
    labels = {v: short(info.loc[v, "name"], 22) for v in H.nodes()}
    for v, (x, y) in pos.items():
        ax.text(x, y + 0.035, labels[v], fontsize=7, color=INK, ha="center", va="bottom")
    ax.axis("off")
    handles = _legend_handles() + [
        plt.Line2D([], [], marker=m, ls="", ms=8, color=INK2, label=lab)
        for m, lab in (("s", "agency (portal extractor)"), ("o", "company (portal extractor)"),
                       ("D", "advocacy (text name list, exploratory)"))]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="lower left", ncol=2)
    ax.set_title(f"Page co-occurrence among all 30 agencies, the {n_companies} most-documented companies and "
                 f"4 advocacy groups (edges: >= {min_weight} shared pages)", fontsize=11, color=INK, loc="left")
    _footer(fig, f"Shown: {H.number_of_nodes()} of {G.number_of_nodes()} nodes, {H.number_of_edges()} of "
                 f"{G.number_of_edges()} edges. Node size ~ sqrt(pages named); edge width ~ log(shared pages). "
                 f"Layout: Kamada-Kawai on unweighted graph distance (deterministic): position and distance carry no "
                 f"geographic or organizational meaning. Edges are co-occurrence, not verified communication. "
                 f"Selected nodes with no edge at this threshold (not drawn): {', '.join(isolated) if isolated else 'none'}.")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return _save(fig, "fig4_network_subgraph.png")


# --- 5. observed vs frequency-preserving null ---------------------------------------------

LABEL_OFFSETS = {("degree", "U.S. EPA"): (6, -8), ("degree", "NYCOSH (NY Committee for Occupational Safety & Health)"): (6, -9),
                 ("betweenness", "U.S. EPA"): (6, -8), ("betweenness", "Port Authority of NY & NJ"): (-6, 4),
                 ("betweenness", "NYC Office of the Mayor"): (-6, 6), ("betweenness", "NYC Dept. of Buildings"): (6, -6),
                 ("betweenness", "Rj Lee Group Inc."): (6, -4)}


def observed_vs_null(cmp: pd.DataFrame, label_names=(), min_pages: int = 20, title_suffix: str = ""):
    """Fig 5: observed degree and betweenness against their null-model expectation (log-log).

    The diagonal is 'exactly what the node's mention count predicts'. Above it = more partners /
    more brokerage than volume alone gives; below = fewer.
    """
    d = cmp[cmp["n_pages"] >= min_pages]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.6), facecolor=SURFACE)
    panels = [("degree", "distinct partners (degree)"), ("betweenness", "betweenness")]
    for ax, (m, lab) in zip(axes, panels):
        x, y = d[f"null_mean_{m}"], d[m]
        ok = (x > 0) & (y > 0)
        base = d[ok & ~d["group"].isin(GROUP_COLOR)]
        ax.scatter(base[f"null_mean_{m}"], base[m], s=10, color=OTHER, alpha=0.55, linewidths=0)
        for g, c in GROUP_COLOR.items():
            sub = d[ok & (d["group"] == g)]
            ax.scatter(sub[f"null_mean_{m}"], sub[m], s=30, color=c, edgecolors=SURFACE, linewidths=1.2, zorder=3)
        lo, hi = min(x[ok].min(), y[ok].min()), max(x[ok].max(), y[ok].max())
        ax.plot([lo, hi], [lo, hi], color=INK2, lw=1, ls="--", zorder=2)
        mid = lo * (hi / lo) ** 0.12
        ax.text(mid, mid, "  observed = expected from volume", fontsize=7.5, color=INK2, va="top", ha="left",
                rotation=0)
        names = label_names.get(m, ()) if isinstance(label_names, dict) else label_names
        for k, r in enumerate(d[ok & d["name"].isin(names)].sort_values(m).itertuples()):
            dx, dy = LABEL_OFFSETS.get((m, r.name), (6, 2))
            ax.annotate(SHORT.get(r.name, short(r.name, 22)), (getattr(r, f"null_mean_{m}"), getattr(r, m)),
                        xytext=(dx, dy), textcoords="offset points", fontsize=7.5, color=INK,
                        ha="right" if dx < 0 else "left")
        ax.set_xscale("log")
        ax.set_yscale("log")
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_xlabel(f"{lab} expected from mention volume (null-model mean, log)")
        ax.set_ylabel(f"observed {lab} (log)")
    axes[0].set_title("Every large agency has FEWER partners than its volume predicts", fontsize=10, color=INK, loc="left")
    axes[1].set_title("Betweenness: a few organizations broker more than volume predicts", fontsize=10, color=INK, loc="left")
    axes[0].legend(handles=_legend_handles(), frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("Centrality relative to a frequency-preserving null model" + title_suffix,
                 x=0.01, ha="left", y=0.985, fontsize=12, color=INK)
    _footer(fig, f"Organizations named on >= {min_pages} pages with non-zero observed and expected values. Null: "
                 f"{settings.NULL_SAMPLES} curveball randomizations of the page-organization incidence keeping every "
                 "organization's page count and every page's organization count fixed. Points on the dashed line have "
                 "exactly the centrality their mention volume predicts.")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    return _save(fig, "fig5_observed_vs_null.png")


# --- 7. bootstrap rank intervals ------------------------------------------------------------

def bootstrap_ranks(iv: pd.DataFrame, metric: str = "betweenness"):
    """Fig 7: 95% bootstrap interval of each hypothesis node's rank (log scale, 1 = top)."""
    view_group = {"municipal regulatory": "municipal_regulatory",
                  "private real estate: manually confirmed": "private_real_estate",
                  "public-health advocacy (exploratory)": "public_health_advocacy"}
    d = iv[iv["view"].isin(view_group)].copy()
    d["group"] = d["view"].map(view_group)
    d = d.sort_values(["group", f"rank_{metric}_med"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.32 * len(d) + 1.8), facecolor=SURFACE)
    for i, r in d.iterrows():
        c = GROUP_COLOR[r["group"]]
        ax.plot([r[f"rank_{metric}_lo"], r[f"rank_{metric}_hi"]], [i, i], color=c, lw=2.5, solid_capstyle="round")
        ax.plot([r[f"rank_{metric}_med"]], [i], "o", color=c, ms=8, mec=SURFACE, mew=2)
    ax.set_yticks(range(len(d)), [short(n, 36) for n in d["name"]], fontsize=8, color=INK2)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ticks = [1, 3, 10, 30, 100, 300, 1000]
    ax.set_xticks(ticks, [str(x) for x in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.invert_xaxis()
    _style(ax)
    ax.set_xlabel(f"{metric} rank among 1,656 organizations (log; right = higher)")
    ax.legend(handles=_legend_handles(other_label=None)[:-1], frameon=False, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.45, 1.0))
    ax.set_title(f"Document bootstrap: 95% interval of each hypothesis organization's {metric} rank",
                 fontsize=11, color=INK, loc="left")
    _footer(fig, f"{settings.BOOTSTRAP_SAMPLES} resamples of the documents (with replacement), page network rebuilt "
                 "each time. Dot = median rank, bar = 2.5-97.5 percentile.")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return _save(fig, f"fig7_bootstrap_{metric}_ranks.png")


# --- 6 (revised). the relay: who brokers beyond volume, month by month ------------------------

RELAY_ROWS = ["NYC Board of Education", "NYPD", "NYC Dept. of Sanitation", "FDNY", "Port Authority of NY & NJ", "Verizon",
              "NYC Office of the Mayor", "NYC Law Department", "NYC Dept. of Design and Construction", "FEMA",
              "NYC Office of Emergency Management", "NYS Dept. of Health", "Lower Manhattan Development Corporation",
              "NYC Dept. of Buildings", "Ambient Group Inc.", "Warren And Panzer Engineers", "Atc Associates Inc."]
RELAY_ANCHORS = ["NYC Dept. of Environmental Protection", "U.S. EPA", "NYC Dept. of Health and Mental Hygiene"]
RELAY_BLUES = matplotlib.colors.LinearSegmentedColormap.from_list("relay", ["#cfe2f7", "#7fb1ea", "#2a78d6", "#123f80"])
PHASES = [("2001-09", "2001-09", "First weeks"), ("2001-10", "2001-11", "Fall 2001"),
          ("2001-12", "2002-12", "Clean-up and testing: one long phase, fewer connectors over time")]  # = temporal.data_phases(k=3)
EVENTS = [("2002-05", "May 8: EPA–City indoor\nclean-up plan"), ("2002-09", "Sep: clean-up contracts\n(ATC monitoring)"),
          ("2002-12", "Dec 28: sign-up\ncloses")]


def relay_chart(tm: pd.DataFrame, names: list[str], anchors: list[str], min_pages: int = 20, q: float = 0.95,
                phases: list[tuple] | None = None):
    """Fig 6: months in which an organization brokers reliably MORE than its volume predicts.

    A cell is colored only if the organization is named on >= min_pages pages that month and its
    betweenness beats >= q of that month's null networks; shade = observed / expected. Rows are
    sorted by the first month an organization breaks out (ties: by the weighted center of its
    blue months), so the order in which organizations come in reads top to bottom. `anchors`
    (the most-named agencies) are drawn separately below for contrast. The right column gives each
    organization's median raw betweenness rank over the months it is named.
    """
    months = sorted(tm["month"].unique())
    col = {m: j for j, m in enumerate(months)}
    d = tm[tm["name"].isin(names + anchors)].copy()
    d["sig"] = (d["pages"] >= min_pages) & (d["null_q_betweenness"] >= q) & (d["ratio_betweenness"] > 1)
    d["j"] = d["month"].map(col)
    w = d[d["sig"]].assign(wt=lambda x: np.log2(x["ratio_betweenness"].clip(upper=16)))
    first = w.groupby("name")["j"].min()
    center = (w["j"] * w["wt"]).groupby(w["name"]).sum() / w.groupby("name")["wt"].sum()
    order = sorted(names, key=lambda n: (first.get(n, 99), center.get(n, 99)))
    med_rank = d.groupby("name")["rank_betweenness"].median()
    gap = 0.9                                           # vertical gap before the anchor rows
    ypos = {n: i for i, n in enumerate(order)} | {n: len(order) + gap + k for k, n in enumerate(anchors)}
    bottom = len(order) + gap + len(anchors)

    fig, ax = plt.subplots(figsize=(14, 0.36 * bottom + 3.0), facecolor=SURFACE)
    norm = matplotlib.colors.LogNorm(vmin=1, vmax=16)
    for name, i in ypos.items():
        rows = d[d["name"] == name].set_index("j")
        for j in range(len(months)):
            if j in rows.index:
                r = rows.loc[j]
                fc = RELAY_BLUES(norm(min(r["ratio_betweenness"], 16))) if r["sig"] else "#ecebe7"
            else:
                fc = SURFACE
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, facecolor=fc, edgecolor="none"))
        ax.text(len(months) + 0.3, i + 0.5, f"{med_rank.get(name, np.nan):.0f}", va="center", fontsize=8, color=INK2)
    ax.text(0.04, len(order) + gap - 0.12, "The three most-named agencies, for contrast:", fontsize=8, color=INK2,
            va="bottom", style="italic")
    ax.set_xlim(0, len(months) + 1.4)
    ax.set_ylim(bottom, -4.0)
    ax.set_yticks([i + 0.5 for i in ypos.values()], [SHORT.get(n, short(n, 28)) for n in ypos], fontsize=8.5, color=INK)
    ax.set_xticks([j + 0.5 for j in range(len(months))],
                  [m.strftime("%b\n%Y") if (m.month in (1, 9) or j == 0) else m.strftime("%b") for j, m in enumerate(months)],
                  fontsize=8, color=INK2)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.text(len(months) + 0.3, -0.15, "median\nmonthly\nrank", fontsize=7.5, color=INK2, va="bottom")
    # phase bands (top row) and dated events (below them)
    for a, b, label in (phases or PHASES):
        x0, x1 = col[pd.Period(a, "M")], col[pd.Period(b, "M")] + 1
        ax.plot([x0 + 0.08, x1 - 0.08], [-3.1, -3.1], color=INK, lw=2, solid_capstyle="butt")
        ax.text((x0 + x1) / 2, -3.25, label, ha="center", va="bottom", fontsize=9, color=INK)
    for m, label in EVENTS:
        x = col[pd.Period(m, "M")] + 0.5
        ax.plot([x, x], [-0.8, -1.3], color=INK2, lw=0.8, ls=":")
        ax.text(x, -1.35, label, ha="center", va="bottom", fontsize=7, color=INK2)
    # all organizations (not only the rows shown): how many broker beyond volume each month
    allsig = tm[(tm["pages"] >= min_pages) & (tm["null_q_betweenness"] >= q) & (tm["ratio_betweenness"] > 1)]
    counts = allsig.groupby("month").size().reindex(months, fill_value=0)
    for j, c in enumerate(counts):
        ax.text(j + 0.5, -0.35, str(c), ha="center", va="center", fontsize=9, color=INK, weight="bold")
    ax.text(-0.15, -0.5, "how many organizations\n(of all, not just rows below)\nconnected beyond volume", ha="right",
            va="center", fontsize=7.5, color=INK2)
    cax = fig.add_axes([0.80, 0.035, 0.15, 0.018])
    cb = fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=RELAY_BLUES), cax=cax, orientation="horizontal",
                      ticks=[1, 2, 4, 8, 16])
    cb.ax.set_xticklabels(["1×", "2×", "4×", "8×", "16×+"], fontsize=7, color=INK2)
    cb.outline.set_visible(False)
    cb.ax.set_title("betweenness vs. expected from volume", fontsize=7.5, color=INK2, loc="left")
    fig.suptitle("Many organizations connected the response in fall 2001; by late 2002 almost none did beyond DEP and EPA",
                 x=0.01, ha="left", y=0.995, fontsize=12, color=INK)
    _footer(fig, f"Blue = that month the organization was named on ≥ {min_pages} pages and its betweenness beat ≥ {q:.0%} "
                 f"of {settings.TEMPORAL_NULL_SAMPLES} frequency-preserving null networks; darker = further above expectation. "
                 "Gray = named, but not reliably above expectation. Blank = not named. Bold numbers = count of ALL organizations "
                 "meeting the blue criterion that month. Rows ordered by the first blue month. Phase boundaries: optimal "
                 "split of the months into 3 contiguous phases by which organizations connect beyond volume (phase names "
                 "are ours). Event dates from EPA press releases. Documents dated to the day or month only.")
    fig.subplots_adjust(left=0.16, right=0.97, top=0.93, bottom=0.12)
    return _save(fig, "fig6_monthly_relay.png")


FIG8_NAMES = ["NYC Dept. of Environmental Protection", "U.S. EPA", "NYC Dept. of Health and Mental Hygiene",
              "NYC Dept. of Buildings", "NYC Dept. of Housing Preservation and Development", "NIOSH",
              "9/11 Environmental Action", "American Lung Association", "Natural Resources Defense Council",
              "NYCOSH (NY Committee for Occupational Safety & Health)", "Silverstein Properties Inc.",
              "Rockrose Development Corp.", "Century Realty Inc.", "Port Authority of NY & NJ", "NYC Office of the Mayor",
              "FDNY", "Rj Lee Group Inc."]
FIG9_NAMES = [n for n in FIG8_NAMES if n != "Rj Lee Group Inc."] + [
    "NYC Office of Emergency Management", "Verizon", "OSHA", "NYC Law Department", "NYC Dept. of Design and Construction"]


# --- 8. the gap closes: raw vs volume-adjusted betweenness ------------------------------------

def _spread(values, min_gap, lo=0.0, hi=100.0):
    """Label positions at least min_gap apart, in the order of `values`, kept inside [lo, hi]."""
    order = np.argsort(values)
    pos = np.clip(np.array(values, float)[order], lo, hi)
    for i in range(1, len(pos)):                      # push up
        pos[i] = max(pos[i], pos[i - 1] + min_gap)
    if pos[-1] > hi:                                  # then push back down from the ceiling
        pos[-1] = hi
        for i in range(len(pos) - 2, -1, -1):
            pos[i] = min(pos[i], pos[i + 1] - min_gap)
    out = np.empty_like(pos)
    out[order] = pos
    return out


def raw_vs_adjusted(cmp: pd.DataFrame, names: list[str], min_pages: int = 20):
    """Fig 8: percentile of raw betweenness vs percentile of betweenness beyond volume (observed / expected).

    Population: organizations named on >= min_pages pages with a defined ratio, so both columns rank
    the same organizations. Lines connect each selected organization's two percentiles.
    """
    pop = cmp[(cmp["n_pages"] >= min_pages) & cmp["ratio_betweenness"].notna() & (cmp["betweenness"] > 0)].copy()
    pop["raw"] = pop["betweenness"].rank(pct=True) * 100
    pop["adj"] = pop["ratio_betweenness"].rank(pct=True) * 100
    sel = pop[pop["name"].isin(names)].copy()
    fig, ax = plt.subplots(figsize=(11, 9), facecolor=SURFACE)
    x0, x1 = 0, 1
    for r in sel.itertuples():
        c = GROUP_COLOR.get(r.group, INK2)
        lw = 2.2 if r.group in GROUP_COLOR else 1.4
        ax.plot([x0, x1], [r.raw, r.adj], color=c, lw=lw, alpha=0.9 if r.group in GROUP_COLOR else 0.6, zorder=2)
        ax.scatter([x0, x1], [r.raw, r.adj], s=36, color=c, edgecolors=SURFACE, linewidths=1.5, zorder=3)
    lab = _spread(sel["adj"].to_numpy(), 2.6)
    for (r, y) in zip(sel.itertuples(), lab):
        ax.plot([x1 + 0.02, x1 + 0.08], [r.adj, y], color=GRID, lw=0.8)
        ax.text(x1 + 0.1, y, f"{SHORT.get(r.name, short(r.name, 30))}  ({r.ratio_betweenness:.1f}×)", va="center",
                fontsize=8, color=INK)
    labl = _spread(sel["raw"].to_numpy(), 2.6)
    for (r, y) in zip(sel.itertuples(), labl):
        ax.plot([x0 - 0.02, x0 - 0.08], [r.raw, y], color=GRID, lw=0.8)
        ax.text(x0 - 0.1, y, SHORT.get(r.name, short(r.name, 30)), va="center", ha="right", fontsize=8, color=INK)
    ax.set_xlim(-0.75, 1.85)
    ax.set_ylim(0, 104)
    ax.set_xticks([x0, x1], ["raw betweenness", "betweenness beyond volume\n(observed / expected)"], fontsize=9.5, color=INK)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel(f"percentile among the {len(pop)} organizations named on ≥ {min_pages} pages", color=INK2, fontsize=9)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.tick_params(axis="y", colors=INK2, labelsize=8)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    med = {g: (pop.loc[pop["group"] == g, "raw"].median(), pop.loc[pop["group"] == g, "adj"].median()) for g in GROUP_COLOR}
    fig.legend(handles=_legend_handles(other_label="Other organizations")[:3] +
               [plt.Line2D([], [], color=INK2, lw=1.4, label="Other organizations")],
               frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0.01, 0.925), ncol=4)
    m, a = med["municipal_regulatory"], med["public_health_advocacy"]
    fig.suptitle("Once paperwork volume is held fixed, the regulators lose their lead", x=0.01, ha="left", y=0.985,
                 fontsize=12, color=INK)
    fig.text(0.01, 0.945, f"Median percentile, municipal regulators: {m[0]:.0f} → {m[1]:.0f};  advocacy groups: "
                          f"{a[0]:.0f} → {a[1]:.0f}.  Coordinators (Port Authority, Mayor, FDNY) stay high.",
             fontsize=9, color=INK2)
    _footer(fig, "Left: rank of raw betweenness. Right: rank of observed / expected betweenness, where 'expected' is the "
                 f"mean of {settings.NULL_SAMPLES} frequency-preserving null networks (same page counts, shuffled "
                 "co-mentions). Number in brackets = observed / expected. Advocacy groups rest on 20-57 pages each, so "
                 "their positions are the least certain (see fig 7).")
    fig.subplots_adjust(left=0.08, right=0.98, top=0.87, bottom=0.1)
    return _save(fig, "fig8_raw_vs_adjusted.png")


# --- 9. whose files ------------------------------------------------------------------------

def whose_files(share: pd.DataFrame, baseline: float):
    """Fig 9: share of each organization's pages that sit in DEP's own files, against the archive-wide share."""
    d = share.sort_values("share")
    fig, ax = plt.subplots(figsize=(10, 0.36 * len(d) + 1.9), facecolor=SURFACE)
    y = np.arange(len(d))
    ax.barh(y, d["share"] * 100, color=[GROUP_COLOR.get(g, OTHER) for g in d["group"]], height=0.6, zorder=2)
    for yi, v in zip(y, d["share"]):
        ax.text(v * 100 + 1, yi, f"{v:.0%}", va="center", fontsize=8, color=INK, zorder=4,
                bbox=dict(boxstyle="square,pad=0.1", fc=SURFACE, ec="none"))
    ax.axvline(baseline * 100, color=INK, lw=1, ls="--", zorder=3)
    ax.text(baseline * 100 - 1, len(d) - 0.2, f"all organization pages: {baseline:.0%}", ha="right", va="bottom",
            fontsize=8, color=INK)
    ax.set_yticks(y, [SHORT.get(n, short(n, 34)) for n in d["name"]], fontsize=8.5, color=INK)
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    _style(ax)
    ax.set_xlabel("share of the organization's pages that come from DEP's own files")
    fig.legend(handles=_legend_handles(), frameon=False, fontsize=8, loc="upper left", ncol=4,
               bbox_to_anchor=(0.01, 0.955))
    fig.suptitle("Almost everyone is seen through DEP's files; the coordinators are the exception",
                 x=0.01, ha="left", y=0.99, fontsize=12, color=INK)
    _footer(fig, "Pages naming each organization, by the agency whose files the document came from (`documents.agency`). "
                 "Without DEP's files the network keeps 1,773 of 11,227 edges and its largest component falls from 91% to "
                 "29% of organizations.")
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return _save(fig, "fig9_whose_files.png")


# --- 10. functional blocks of the validated backbone ------------------------------------------------

BLOCKS = [("Century Realty Inc.", "Building owners: exterior clean-up"),
          ("U.S. EPA", "EPA + sampling laboratories"),
          ("NYC Office of Emergency Management", "WTC site operations and contracts"),
          ("NIOSH", "Air monitoring (NIOSH, OSHA)"),
          ("NYC Dept. of Health and Mental Hygiene", "City / state public health"),
          ("Trio Asbestos Removal Corp.", "Asbestos abatement contractors")]   # names checked against title terms (6g)


def backbone_blocks(G: nx.Graph, membership: pd.DataFrame, info: pd.DataFrame, adv_names: list[str],
                    min_link: int = 5, unstable_note: str | None = None, terms: dict | None = None,
                    stability: dict | None = None, adv_ties_loose: int | None = None):
    """Fig 10: the six largest blocks of the validated backbone as a block diagram.

    Each box is a Louvain community (named by us from its members) with its size, number of agencies,
    validated ties inside it, and key members (agencies first, then the most-named companies). Links
    = validated ties between two blocks (only links with >= min_link ties, width and number = ties).
    The public-health hub is outlined. The advocacy groups sit apart: none has a validated tie.
    """
    info = info.set_index("node_id")
    comm = membership.set_index("node_id")["community"]
    name_to_id = {n: i for i, n in info["name"].items()}
    layout = {"NYC Dept. of Health and Mental Hygiene": (0.0, 0.0), "U.S. EPA": (0.0, 1.35),
              "NIOSH": (-1.85, 1.0), "Trio Asbestos Removal Corp.": (1.85, 1.0),
              "Century Realty Inc.": (-1.85, -0.85), "NYC Office of Emergency Management": (1.85, -0.85)}
    labels = dict(BLOCKS)
    blocks, hub = {}, None
    for anchor, xy in layout.items():
        cid = comm.get(name_to_id.get(anchor), -1)
        if cid >= 0:
            blocks[cid] = (labels[anchor], xy)
            if anchor == "NYC Dept. of Health and Mental Hygiene":
                hub = cid
    W, H = 1.4, 0.9
    between, inside = {}, {}
    for u, v in G.edges():
        a, b = comm.get(u, -1), comm.get(v, -1)
        if a == b and a in blocks:
            inside[a] = inside.get(a, 0) + 1
        elif a in blocks and b in blocks:
            k = tuple(sorted((a, b)))
            between[k] = between.get(k, 0) + 1
    fig, ax = plt.subplots(figsize=(14, 10.2), facecolor=SURFACE)
    for (a, b), n in sorted(between.items(), key=lambda kv: kv[1]):
        if n < min_link:
            continue
        (xa, ya), (xb, yb) = blocks[a][1], blocks[b][1]
        ax.plot([xa, xb], [ya, yb], color="#8d8c86", lw=0.8 + 0.42 * n, alpha=0.55, solid_capstyle="round", zorder=1)

        def inside_box(px, py):
            return any(abs(px - bx) < W / 2 + 0.06 and abs(py - by) < H / 2 + 0.06 for _, (bx, by) in blocks.values())
        t = next((t for t in (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74) if not inside_box(
            xa + t * (xb - xa), ya + t * (yb - ya))), 0.5)
        ax.text(xa + t * (xb - xa), ya + t * (yb - ya), str(n), ha="center", va="center", fontsize=9, color=INK,
                zorder=4, bbox=dict(boxstyle="circle,pad=0.3", fc=SURFACE, ec="#8d8c86", lw=0.8))
    for cid, (label, (x, y)) in blocks.items():
        nodes = list(comm.index[comm == cid])
        sub = info.loc[nodes]
        is_hub = cid == hub
        ax.add_patch(matplotlib.patches.FancyBboxPatch((x - W / 2, y - H / 2), W, H,
                     boxstyle="round,pad=0.02,rounding_size=0.06", fc="#ffffff",
                     ec=GROUP_COLOR["municipal_regulatory"] if is_hub else GRID, lw=2.2 if is_hub else 1.2, zorder=2))
        left, top = x - W / 2 + 0.07, y + H / 2 - 0.07
        ax.text(left, top, label, ha="left", va="top", fontsize=11, color=INK, weight="bold", zorder=3)
        if is_hub:
            ax.text(x + W / 2 - 0.07, top, "HUB", ha="right", va="top", fontsize=8, weight="bold",
                    color=GROUP_COLOR["municipal_regulatory"], zorder=3)
        n_ag = int((sub["node_kind"] == "agency").sum())
        facts = f"{len(nodes)} orgs · {n_ag} agencies · {inside.get(cid, 0):,} ties inside"
        if stability and cid in stability:
            facts += f" · stable {stability[cid]:.0%}"
        ax.text(left, top - 0.13, facts, ha="left", va="top", fontsize=8.3, color=INK2, zorder=3)
        if terms and cid in terms:
            ax.text(left, top - 0.24, "titles: " + terms[cid], ha="left", va="top", fontsize=8.3, color=INK,
                    style="italic", zorder=3)
        agencies = sub[sub["node_kind"] == "agency"].sort_values("n_pages", ascending=False)
        companies = sub[sub["node_kind"] != "agency"].sort_values("n_pages", ascending=False)
        members = (list(agencies.index[:4]) + list(companies.index))[:4]
        for k, m in enumerate(members):
            yy = top - 0.42 - k * 0.09
            g = info.at[m, "group"]
            ax.scatter([left + 0.03], [yy], s=30, color=GROUP_COLOR.get(g, OTHER),
                       marker="s" if info.at[m, "node_kind"] == "agency" else "o", zorder=3)
            ax.text(left + 0.09, yy, SHORT.get(info.at[m, "name"], short(info.at[m, "name"], 34)), va="center",
                    fontsize=9, color=INK, zorder=3)
    # advocacy groups: apart, no links
    bx, by, bw, bh = 0.0, -1.42, W + 0.08, 0.56
    ax.add_patch(matplotlib.patches.FancyBboxPatch((bx - bw / 2, by - bh / 2), bw, bh,
                 boxstyle="round,pad=0.02,rounding_size=0.06", fc="#f3f2ee", ec="#c9c7c0", lw=1.2, ls="--", zorder=2))
    ax.text(bx - bw / 2 + 0.07, by + bh / 2 - 0.07, "Advocacy groups: barely tied in", ha="left", va="top",
            fontsize=11, color=INK, weight="bold")
    loose = f"; {adv_ties_loose} under a looser test" if adv_ties_loose is not None else ""
    ax.text(bx - bw / 2 + 0.07, by + bh / 2 - 0.2, f"0 ties beyond chance (strict test){loose}",
            ha="left", va="top", fontsize=8.5, color=INK2)
    for k, n in enumerate(adv_names):
        xx = bx - bw / 2 + 0.1 + (k % 2) * 0.66
        yy = by - 0.07 - (k // 2) * 0.12
        ax.scatter([xx], [yy], s=30, color=GROUP_COLOR["public_health_advocacy"], zorder=3)
        ax.text(xx + 0.06, yy, SHORT.get(n, short(n, 26)), va="center", fontsize=9, color=INK)
    ax.set_xlim(-2.62, 2.62)
    ax.set_ylim(-1.76, 1.85)
    ax.set_aspect("equal")
    ax.axis("off")
    hs = [plt.Line2D([], [], marker="s", ls="", ms=8, color=GROUP_COLOR[g], label=classify.GROUP_LABELS[g])
          for g in GROUP_COLOR] + [
        plt.Line2D([], [], marker="s", ls="", ms=8, color=OTHER, label="other agency"),
        plt.Line2D([], [], marker="o", ls="", ms=8, color=OTHER, label="other company"),
        plt.Line2D([], [], color="#8d8c86", lw=4, alpha=0.6, label=f"ties between blocks (≥ {min_link})")]
    fig.legend(handles=hs, frameon=False, fontsize=8.5, loc="upper left", ncol=6, bbox_to_anchor=(0.01, 0.905))
    fig.suptitle("The response ran in separate blocks joined through city and state public health; "
                 "the advocacy groups were barely tied in", x=0.01, ha="left", y=0.985, fontsize=12.5, color=INK)
    total_between = sum(between.values())
    hub_between = sum(n for (a, b), n in between.items() if hub in (a, b))
    strong = {k for k, n in between.items() if n >= min_link}
    n_strong = {c: sum(1 for k in strong if c in k) for c in blocks}
    others = len(blocks) - 1
    only = [c for c, n in n_strong.items() if n == others]
    claim = (f", the only block with strong links (≥ {min_link} ties) to all {others} others" if only == [hub]
             else f", with strong links (≥ {min_link} ties) to {n_strong[hub]} of the {others} others")
    fig.text(0.01, 0.952, textwrap.fill(
        f"Organizations are linked when named on the same pages more often than chance. Most ties stay inside a block; of "
        f"the {total_between} ties between blocks, {hub_between} run through the public-health block{claim}.", 150),
        fontsize=9.5, color=INK2, va="top")
    note = (" " + unstable_note) if unstable_note else ""
    _footer(fig, "Validated backbone: a tie is kept only if two organizations share more pages than chance predicts "
                 "(hypergeometric test, Bonferroni over all pairs, α = 0.01; 2,382 of 11,227 ties). Blocks = the six largest "
                 "consensus communities over 100 Louvain runs (modularity 0.60); 'stable' = share of runs in which two "
                 "members of the block share a block. 'titles' = the most distinctive words in the titles of the block's "
                 "documents, which back the block names. Members appear on the same documents, which does not mean they "
                 f"worked together. Members listed: agencies first, then the most-named companies.{note}")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.87, bottom=0.075)
    return _save(fig, "fig10_backbone_blocks.png")
