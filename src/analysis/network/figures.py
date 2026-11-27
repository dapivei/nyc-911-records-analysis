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
