"""RQ1 organization co-occurrence network: run everything and write outputs.

    python -m src.processing.clean          # once: data/final -> data/processed
    python -m src.analysis.network.run      # tables -> outputs/network/, figures -> outputs/figures/network/

Steps: data checks -> nodes/classification -> main network (page co-occurrence, extracted
organizations) -> supplement with 4 advocacy nodes -> frequency check -> descriptive group
summaries in three network variants (sensitivity) -> figures -> beyond frequency (null models,
hyperbolic weights, validated backbone, network without DEP's files, document bootstrap, monthly
networks, communities; ~25 min on 2 cores the first time, cached afterwards).

    python -m src.analysis.network.run --skip-extensions    # only the original steps (~2 min)
"""
import sys
import json
import platform

import networkx as nx
import pandas as pd

from src.analysis.network import (backbone, bootstrap, build, checks, figures, metrics, nullmodel, pipeline,
                                  robustness, settings, temporal)

NODE_COLS = ["node_id", "entity_id", "name", "node_kind", "group", "group_label", "review_status", "n_docs",
             "n_pages", "first_doc_date", "last_doc_date", "degree", "degree_centrality", "strength",
             "betweenness", "component_size", "in_lcc", "pct_degree_centrality", "pct_strength", "pct_betweenness"]


def write(df: pd.DataFrame, name: str):
    """Write a table to outputs/network/ as csv."""
    settings.OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(settings.OUT / name, index=False)


def frequency_check(nodes: pd.DataFrame) -> pd.DataFrame:
    """Spearman correlation between pages named and each centrality metric (all nodes of a network)."""
    return pd.DataFrame([{"metric": m, "spearman_with_n_pages": nodes["n_pages"].corr(nodes[m], method="spearman"),
                          "nodes": len(nodes)} for m in ("degree", "strength", "betweenness")])


def multi_org_share(net: dict, prep: pipeline.Prepared, cutoff: float) -> pd.DataFrame:
    """Per group: share of a node's pair evidence that comes from pages naming more than `cutoff` organizations."""
    ev = net["evidence"]
    long = pd.concat([ev[["source", "unit_size"]].rename(columns={"source": "node_id"}),
                      ev[["target", "unit_size"]].rename(columns={"target": "node_id"})])
    long["group"] = long["node_id"].map(prep.node_info.set_index("node_id")["group"])
    out = long.assign(from_multi_org_page=long["unit_size"] > cutoff).groupby("group")["from_multi_org_page"]
    return out.agg(share="mean", evidence_rows="size").reset_index().sort_values("share")


def main():
    prep = pipeline.prepare(with_advocacy=True, keep_text=True)
    t = prep.tables

    # --- 1. data checks ------------------------------------------------------------------
    write(checks.key_checks(t), "data_key_checks.csv")
    write(checks.entity_type_overview(t), "data_entity_types.csv")
    write(checks.unit_size_distribution(prep.om), "data_unit_sizes.csv")
    write(checks.largest_units(prep.om, t["documents"], "page"), "data_largest_page_units.csv")
    write(checks.largest_units(prep.om, t["documents"], "doc"), "data_largest_doc_units.csv")
    write(checks.source_bias(prep.om, t["documents"]), "data_source_bias.csv")
    agencies = prep.node_info.loc[prep.node_info["node_kind"] == "agency"].nlargest(8, "n_pages")["node_id"]
    write(checks.citation_share(prep.om, t["pages"], agencies), "data_citation_share.csv")
    write(checks.text_vs_entity_recall(t["pages"], prep.om), "data_text_vs_entity_recall.csv")
    dates = checks.date_coverage(prep.om, t["documents"])
    write(checks.date_extremes(prep.om, t["documents"]), "data_date_extremes.csv")
    t["pages"] = t["pages"].drop(columns="text")

    # --- 2. nodes and classification -----------------------------------------------------
    write(prep.candidates, "nodes_candidates_all.csv")
    write(prep.node_info[["node_id", "entity_id", "name", "node_kind", "group", "group_label", "basis",
                          "review_status", "n_docs", "n_pages"]].sort_values(["group", "n_docs"], ascending=[True, False]),
          "org_classification.csv")

    # --- 3. main network -----------------------------------------------------------------
    main_net = pipeline.build_network(prep, unit=settings.MAIN_UNIT)
    write(main_net["nodes"][NODE_COLS].sort_values("degree_centrality", ascending=False), "nodes_main.csv")
    names = prep.node_info.set_index("node_id")["name"]
    edges = main_net["edges"].assign(source_name=lambda d: d["source"].map(names),
                                     target_name=lambda d: d["target"].map(names))
    write(edges, "edges_main.csv")
    main_net["evidence"].to_parquet(settings.OUT / "edge_evidence_main.parquet", index=False)
    # the network is NOT filtered by date: how much of its pair evidence comes from each period
    write(checks.evidence_by_period(main_net["evidence"], t["documents"]), "evidence_by_date_period.csv")

    # --- 4. supplement with the 4 exploratory advocacy nodes ------------------------------
    sup = pipeline.build_network(prep, unit=settings.MAIN_UNIT, include_advocacy=True)
    write(sup["nodes"][NODE_COLS].sort_values("degree_centrality", ascending=False), "nodes_with_advocacy.csv")
    write(prep.adv[["node_id", "doc_id", "page"]].drop_duplicates(), "advocacy_mentions.csv")   # for verify.py
    doc_net = pipeline.build_network(prep, unit="doc")
    stats = pd.DataFrame([{"network": "main: page co-occurrence", **main_net["stats"]},
                          {"network": "supplement: page + advocacy", **sup["stats"]},
                          {"network": "document co-occurrence", **doc_net["stats"]}])
    write(stats, "network_stats.csv")

    # --- 5. frequency check and multi-organization pages ---------------------------------
    write(frequency_check(main_net["nodes"]), "frequency_check.csv")
    cutoff = build.large_unit_cutoff(prep.om, "page")             # p99 of multi-organization pages
    write(multi_org_share(main_net, prep, cutoff), "multi_org_page_share.csv")

    # --- 6. descriptive group summaries in three network variants ------------------------
    rob, summary, hyp_nodes, nets = robustness.run(prep)
    write(rob, "robustness_summary.csv")
    write(summary, "group_summary_by_scenario.csv")
    write(hyp_nodes, "hypothesis_nodes_by_scenario.csv")
    # study-window network, other node choice: drop nodes with no in-window mention, recompute percentiles
    win = nets[robustness.WINDOW]
    win_ref = metrics.hypothesis_views(robustness.refiltered_ranks(win))
    write(metrics.group_summary(win_ref).assign(nodes=int((win["nodes"]["n_pages_used"] > 0).sum())),
          "group_summary_window_refiltered.csv")
    write(metrics.group_summary(sup["nodes"], ("n_pages", "degree", "pct_degree_centrality", "pct_betweenness"),
                                by="group"), "group_summary_all_groups.csv")

    # --- 7. figures ----------------------------------------------------------------------
    scen = list(nets)
    figures.top_ranking(main_net["nodes"])
    figures.hypothesis_groups(hyp_nodes, scen[:2], ["all pages", f"without pages > {cutoff:.0f} orgs"])
    lab = sup["nodes"]
    label_ids = set(lab.nlargest(4, "n_pages")["node_id"]) | set(lab[lab["group"] == "public_health_advocacy"]["node_id"]) \
        | set(lab[lab["group"] == "private_real_estate"].nlargest(3, "degree")["node_id"]) \
        | set(lab[lab["group"] == "municipal_regulatory"]["node_id"])
    figures.frequency_vs_degree(lab, label_ids)
    figures.network_plot(sup)

    if "--skip-extensions" not in sys.argv:
        extensions(prep, sup)

    meta = {"settings": {k: getattr(settings, k) for k in dir(settings) if k.isupper()},
            "betweenness_main": main_net["betweenness_info"], "date_coverage": dates,
            "multi_org_page_cutoff": cutoff, "scenarios": scen,
            "window_nodes_without_mentions": int((win["nodes"]["n_pages_used"] == 0).sum()),
            "python": platform.python_version(), "pandas": pd.__version__, "networkx": nx.__version__}
    (settings.OUT / "run_metadata.json").write_text(json.dumps(meta, indent=2, default=str))
    print(stats.T.to_string())
    print(f"tables -> {settings.OUT}/, figures -> {settings.FIGURES}/")


def extensions(prep: pipeline.Prepared, sup: dict):
    """Section 6 of the notebook: separate structural position from mention volume."""
    views = metrics.hypothesis_views
    # 6a. frequency-preserving null models (cached .npz)
    for strata in (None, "source_agency"):
        cmp = nullmodel.run(prep, sup, strata=strata)
        tag = strata or "global"
        write(cmp.drop(columns=[c for c in cmp.columns if c in ("basis",)]), f"null_{tag}_nodes.csv")
        write(nullmodel.group_table(cmp, views), f"null_{tag}_group_summary.csv")
        if strata is None:
            figures.raw_vs_adjusted(cmp, figures.FIG8_NAMES)
            figures.observed_vs_null(cmp, {
                "degree": ["NYC Dept. of Environmental Protection", "U.S. EPA", "NYC Dept. of Health and Mental Hygiene",
                           "NYC Dept. of Buildings", "Century Realty Inc.",
                           "NYCOSH (NY Committee for Occupational Safety & Health)"],
                "betweenness": ["NYC Dept. of Environmental Protection", "U.S. EPA",
                                "NYC Dept. of Health and Mental Hygiene", "NYC Dept. of Buildings",
                                "NYC Office of the Mayor", "Port Authority of NY & NJ", "Rj Lee Group Inc.",
                                "Century Realty Inc.", "NYCOSH (NY Committee for Occupational Safety & Health)",
                                "9/11 Environmental Action", "Natural Resources Defense Council"]})
    # 6b. hyperbolic weights
    wm = sup["nodes"].merge(backbone.weighted_metrics(sup["nodes"]["node_id"], backbone.newman_edges(sup["evidence"])),
                            on="node_id")
    write(wm[["node_id", "name", "group", "n_pages", "strength_newman", "betweenness_weighted",
              "pct_strength_newman", "pct_betweenness_weighted"]], "nodes_hyperbolic_weights.csv")
    # 6c. validated backbone, its sensitivity to the rule, DEP's strongest ties
    e_val, bbn, G_bb = backbone.backbone_network(sup, prep)
    write(e_val, "edges_validated.csv")
    write(backbone.backbone_stats(e_val), "backbone_stats.csv")
    write(bbn[["node_id", "name", "group", "n_pages", "degree", "bb_degree", "bb_betweenness",
               "bb_pct_degree_centrality", "bb_pct_betweenness"]], "nodes_backbone.csv")
    rules = backbone.rule_sensitivity(sup, prep)
    write(rules, "backbone_rule_sensitivity.csv")
    names = prep.node_info.set_index("node_id")["name"]
    write(backbone.dep_strongest_ties(e_val, "agency:nyc-dep", names), "backbone_dep_strongest_ties.csv")
    # 6g. consensus blocks, their stability and what their documents are about
    membership, comm, _ = backbone.consensus_communities(G_bb, prep.node_info)
    write(membership, "backbone_communities_membership.csv")
    write(comm.assign(modularity=comm.attrs["modularity"]), "backbone_communities.csv")
    stab, stab_pairs = backbone.community_stability(G_bb, prep.node_info, [("NIOSH", "OSHA")])
    write(stab_pairs.assign(ari_median=stab["ari_median"], ari_min=stab["ari_min"]), "backbone_communities_stability.csv")
    terms = backbone.block_title_terms(sup["evidence"], e_val[e_val["validated_bonferroni"]], membership,
                                       prep.tables["documents"], comm["community"].head(6))
    write(terms, "backbone_block_title_terms.csv")
    adv = list(prep.node_info.loc[prep.node_info["group"] == "public_health_advocacy", "name"])
    loose = rules.set_index("rule").at["validated_fdr", "advocacy_ties"]
    figures.backbone_blocks(
        G_bb, membership, prep.node_info, adv,
        terms={r.community: ", ".join(r.terms.split(", ")[:5]) for r in terms.itertuples()},
        stability=dict(zip(comm["community"], comm["stability"])), adv_ties_loose=int(loose),
        unstable_note=f"The least stable pair is NIOSH and OSHA (same block in "
                      f"{stab_pairs.loc[0, 'same_block_share']:.0%} of single runs).")
    # 6d. without DEP's own files
    nodep = pipeline.build_network(prep, unit="page", include_advocacy=True,
                                   exclude_source_agency=settings.EXCLUDED_SOURCE_AGENCY)
    write(views(robustness.add_ranks(nodep["nodes"])), "hypothesis_nodes_without_dep_files.csv")
    share, base = pipeline.share_in_source(prep, settings.EXCLUDED_SOURCE_AGENCY)
    info = prep.node_info.set_index("node_id")
    figures.whose_files(info[info["name"].isin(figures.FIG9_NAMES)][["name", "group"]].join(share.rename("share")), base)
    # 6e. document bootstrap (cached .npz)
    ids, deg, bt = bootstrap.run(prep, sup)
    iv = bootstrap.rank_intervals(ids, deg, bt, views(sup["nodes"]))
    write(iv, "bootstrap_rank_intervals.csv")
    write(bootstrap.comparison_stability(ids, deg, bt, views(sup["nodes"])), "bootstrap_comparison_stability.csv")
    figures.bootstrap_ranks(iv, "betweenness")
    # 6f. monthly networks (cached csv), data-driven phases, Law Department documents
    tm = temporal.run(prep)
    write(temporal.phase_brokers(tm), "temporal_phase_brokers.csv")
    write(temporal.group_by_month(tm, views), "temporal_groups_by_month.csv")
    write(temporal.phase_table(tm), "temporal_phase_boundaries.csv")
    law = temporal.law_department_documents(prep)
    law.index = law.index.astype(str)
    write(law.reset_index(), "temporal_law_department_documents.csv")
    phases = [(str(a), str(b), name) for (a, b), (_, _, name) in zip(temporal.data_phases(tm, 3), figures.PHASES)]
    figures.relay_chart(tm, figures.RELAY_ROWS, figures.RELAY_ANCHORS, phases=phases)


if __name__ == "__main__":
    main()
