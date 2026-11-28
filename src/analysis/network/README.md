# Network analysis (RQ1): from `data/processed/` to `outputs/network/`

This step turns the cleaned archive into an **organization network** and asks who held the 9/11 environmental response together. Two organizations are linked when they are **named on the same page**. That is co-occurrence in the released record, not proof of communication.

The analysis has two layers:
1. **The network as recorded:** degree and betweenness centrality, group comparisons for Hypothesis 1, and sensitivity checks.
2. **Position vs paperwork volume:** an organization named on many pages is linked to almost everyone, whatever its role. This layer separates real position from volume:
   * frequency-preserving null models;
   * a statistically validated backbone;
   * consensus communities;
   * a network without DEP's own files;
   * a document bootstrap;
   * one network per month.

Results and their interpretation are in [`docs/network_analysis_report.md`](../../../docs/network_analysis_report.md). The step-by-step walkthrough is [`notebooks/network_centrality.ipynb`](../../../notebooks/network_centrality.ipynb).

## How to run

```bash
# after processing (data/processed/ exists), from the repo root:
python -m src.analysis.network.run                     # everything: tables, figures, saved samples
python -m src.analysis.network.run --skip-extensions   # only layer 1 (~2 min)
python -m src.analysis.network.verify                  # assertions; ends with "all checks passed"
```

The first full run takes about 30 minutes on 2 cores. Most of that is the random samples behind layer 2: 2 × 100 null networks, 100 bootstrap networks, 16 months × 100 null networks. The samples are saved in `outputs/network/` (`null_*.npz`, `bootstrap_*.npz`, `temporal_*.csv`), so later runs, and the notebook, take a few minutes. The `.npz` files store the list of organizations they were computed for and are recomputed automatically when that list changes. `temporal_*.csv` is not checked: **delete it after changing the nodes or the monthly settings** (see "Changing things").

Every step is also a plain function you can import in a notebook (`from src.analysis.network import pipeline, nullmodel, …`).

## Files

| File | Role |
| --- | --- |
| `run.py` | The pipeline: runs every step in order and writes all tables and figures |
| `settings.py` | All thresholds and sample sizes, fixed before results were computed |
| `pipeline.py` | `prepare()` loads the data once; `build_network()` builds any network variant with its node metrics |
| `build.py` | Organization mentions, candidate nodes, the 4 advocacy groups found by text search, co-occurrence edges |
| `classify.py` | Hand-curated groups (municipal regulators, real estate, …), name merges and extraction artifacts |
| `metrics.py` | Degree, betweenness, strength, percentiles, Hypothesis 1 group views and summaries |
| `checks.py` | Data checks: keys, date coverage, page sizes, source bias, citation shares |
| `robustness.py` | Sensitivity scenarios for layer 1 (page-size cut, document unit, study window) |
| `nullmodel.py` | Frequency-preserving null model (curveball randomization), observed vs expected centrality |
| `backbone.py` | Hyperbolic weights, validated backbone, consensus communities, block title words, rule sensitivity |
| `bootstrap.py` | Document-level bootstrap of ranks and of the Hypothesis 1 comparisons |
| `temporal.py` | Monthly networks with their own null models, data-driven phases, Law Department document types |
| `figures.py` | Figures 1–10 (static PNG, matplotlib) |
| `verify.py` | Independent checks: toy graphs with hand-computed answers, and recounts from the raw tables |

## What `run.py` does, in order

### Layer 1: the network as recorded

**1. Data checks** (`checks.py`). These cover:
* key uniqueness, and that every mention joins to a page and a document;
* the entity types kept (agency, contractor, lab) and dropped (signatory, address, substance);
* date coverage and the most extreme dates;
* how many organizations a page names;
* whose files the documents come from (`source_bias`: 62% DEP);
* how many agency pages are method citations ("EPA Method", "NIOSH 7400").

**2. Nodes and groups** (`build.py`, `classify.py`).
* **Nodes.** Contractor and lab rows with the same normalized name become one company. OCR and prefix variants are merged (`COMPANY_MERGES`). Job titles and phrases (`ARTIFACT_IDS`) and names with no distinctive word are dropped. A company must appear in ≥ 2 documents.
* **Groups.** These were fixed before any metric was computed:
  * municipal regulators (DEP, DOHMH, DOB, HPD), an a-priori list;
  * real estate: manual entries, plus a keyword rule;
  * other levels from `src/processing/agency_map.py`.
* **Advocacy groups.** Entity extraction never tagged them, so four are added by a name search in page text. They are found by a different method, so any comparison involving them is exploratory.

*Why:* every node and group decision is reviewable in `org_classification.csv`, with its basis and review status.

**3. Main network** (`pipeline.build_network`).
* The unit is the **page**: at document level, the largest 1% of documents produce 70% of all pairs.
* Edges are undirected, with no self-loops; the weight is the number of shared pages.
* Every edge is traceable to its pages in `edge_evidence_main.parquet`.
* Betweenness is exact (Brandes).

**4. Frequency check.** Spearman correlation between pages named and each metric. It shows centrality rises with volume, which motivates layer 2.

**5. Hypothesis 1 groups in four network variants** (`robustness.py`): page co-occurrence; without pages naming more than 7 organizations; document co-occurrence; study window only. Groups are compared descriptively (percentiles, medians), with no significance test.

**6. Figures 1–4.**

### Layer 2: separating position from paperwork volume

**7. Null model** (`nullmodel.py`).
* **How it works.** It shuffles *which* organizations share a page, while keeping exactly how many pages name each organization and how many organizations each page names. This uses the curveball algorithm with 20 trades per page; `mixing_check` shows that is enough.
* **Output per organization:** observed / expected degree and betweenness (`ratio`), and the share of null networks it beats (`null_q`). z-scores are computed but not used to compare organizations: for rarely named firms they explode.
* **Two versions:** shuffling across the whole archive, and shuffling only within each agency's own files (`strata="source_agency"`).

**8. Hyperbolic weights** (`backbone.newman_edges`). A page naming *k* organizations adds 1/(*k* − 1) to each pair: a smooth alternative to the hard "> 7 organizations" cut. Weighted betweenness uses distance = 1/weight.

**9. Validated backbone** (`backbone.backbone_network`).
* **Test.** A tie is kept only if two organizations share more pages than chance predicts: a hypergeometric test, Bonferroni-corrected over all ≈ 1.37 M possible pairs.
* **Rule sensitivity.** `rule_sensitivity` repeats everything with the looser false-discovery-rate rule.
* **DEP's ties.** The test has little power for an organization on 37% of pages, so `dep_strongest_ties` ranks DEP's ties by observed / expected instead.

**10. Network without DEP's files** (`build_network(exclude_source_agency=...)`) and `share_in_source`: whose files each organization is seen through.

**11. Document bootstrap** (`bootstrap.py`). 100 resamples of the documents (a document is released or withheld whole). Output: rank intervals, and how often each Hypothesis 1 comparison holds.

**12. Monthly networks** (`temporal.py`), September 2001 to December 2002.
* **Per month:** one network, with its own 100-sample null model. An organization "connects beyond volume" in a month if it is named on ≥ 20 pages and beats ≥ 95% of that month's null networks.
* **Phases** (`phase_table`, `data_phases`): an exact optimal split of the months into contiguous phases, not our labels.
* **Law Department** (`law_department_documents`): its pages classified by document type.

**13. Consensus blocks** (`backbone.consensus_communities`).
* **Method.** 100 Louvain runs. Pairs that share a block in ≥ 50% of the runs are reclustered until the runs agree. Each block gets a stability score.
* **Seed check.** `community_stability` checks single-run agreement across seeds.
* **Naming check.** `block_title_terms` lists the most distinctive words in each block's document titles. They are used to check the block names.

**14. Figures 5–10.**

## Outputs

**`outputs/network/`** (tables, csv). CSV files are gitignored and regenerated by `run.py`. Five were committed so the report's layer-1 numbers can be checked without running anything: `frequency_check`, `group_summary_by_scenario`, `hypothesis_nodes_by_scenario`, `org_classification` and `robustness_summary`.

| Prefix | Content |
| --- | --- |
| `data_*` | Data checks (keys, entity types, page sizes, source bias, citations, date extremes) |
| `nodes_*`, `edges_*`, `edge_evidence_main.parquet` | Main network, supplement with advocacy groups, hyperbolic weights, backbone |
| `org_classification.csv`, `nodes_candidates_all.csv` | Every node with its group, basis and review status; every candidate with its exclusion reason |
| `frequency_check.csv`, `multi_org_page_share.csv`, `evidence_by_date_period.csv`, `network_stats.csv` | Layer-1 diagnostics |
| `group_summary_*`, `hypothesis_nodes_*`, `robustness_summary.csv` | Hypothesis 1 views in every network variant, including without DEP's files |
| `null_*_nodes.csv`, `null_*_group_summary.csv` | Observed vs expected centrality, per organization and per group |
| `backbone_*` | Backbone statistics, rule sensitivity, DEP's strongest ties, consensus blocks, block stability, block title words |
| `bootstrap_*` | Rank intervals and comparison stability |
| `temporal_*` | Monthly metrics, connectors per month, group shares, phase boundaries, Law Department document types |
| `run_metadata.json` | Settings, library versions and run information |
| `null_global_100.npz`, `null_source_agency_100.npz`, `bootstrap_100.npz` | **Saved samples**, committed so the notebook runs fast. Delete one to recompute it |
| `temporal_100.csv` | Saved monthly samples. Gitignored like all csv files, so the first run on a new machine recomputes it (~4 min) |

**`outputs/figures/network/`**

| Figure | Shows |
| --- | --- |
| `fig1_top_centrality` | Top organizations by degree, strength, betweenness |
| `fig2_hypothesis_groups` | Hypothesis 1 groups, with and without multi-organization pages |
| `fig3_frequency_vs_degree` | Centrality rises with how often an organization is named |
| `fig4_network_subgraph` | Core of the network (agencies, most-documented companies, advocacy groups) |
| `fig5_observed_vs_null` | Observed vs expected centrality |
| `fig6_monthly_relay` | Who connected the response beyond their volume, month by month, with data-driven phases |
| `fig7_bootstrap_betweenness_ranks` | Bootstrap rank intervals for the Hypothesis 1 organizations |
| `fig8_raw_vs_adjusted` | Betweenness percentile before and after holding volume fixed |
| `fig9_whose_files` | Share of each organization's pages from DEP's own files |
| `fig10_backbone_blocks` | Functional blocks of the validated backbone |

## Verification (`verify.py`)

Each check either compares the code to a toy graph with a hand-computed answer, or recounts a result from the raw tables independently:
1. All metrics on a toy graph match hand-computed values.
2. Nodes and edges are unique and ordered, with no self-loops.
3. Evidence rows equal Σ C(k, 2) over pages, so the join does not inflate rows.
4. Edge weights match a recount from raw `entity_mentions`.
5. Betweenness on the agency subgraph matches a separate networkx computation.
6. Group medians match a direct recomputation.
7. Study-window page counts match a recount from the raw tables.
8. Page counts under the page-size cut are correct, on a toy network and on the real data.
9. Layer 2 on toy inputs:
   * the null model keeps both degree sequences, and its projection equals the edge builder;
   * hypergeometric p-values equal a brute-force sum, and hyperbolic weights give each page a total weight of 1 per organization;
   * the bootstrap keeps documents whole;
   * phase segmentation recovers a known break, the adjusted Rand index works, and consensus blocks recover two cliques.

## Changing things

| To change | Edit | Then |
| --- | --- | --- |
| A group assignment (which group a node belongs to) | `classify.py` (`MANUAL_GROUPS`, keyword rules) | re-run; no saved file depends on groups |
| A merge, an artifact, or the minimum number of documents (changes the node list) | `classify.py` (`COMPANY_MERGES`, `ARTIFACT_IDS`), `settings.MIN_NODE_DOCS` | delete `temporal_100.csv`, re-run (the `.npz` files recompute themselves) |
| The advocacy name list (changes the node list) | `build.ADVOCACY_PATTERNS` (run a precision check on page text first) | delete `temporal_100.csv`, re-run |
| A sample size | `settings.NULL_SAMPLES`, `BOOTSTRAP_SAMPLES`, `TEMPORAL_NULL_SAMPLES` | re-run (the file name includes the size, so new samples are drawn) |
| The monthly window or trades per page | `settings.TEMPORAL_START`, `TEMPORAL_END`, `NULL_TRADES_PER_PAGE` | delete the saved files for the null models / months, re-run |
| A reporting threshold (e.g. ≥ 20 pages, ≥ 95% of nulls, backbone α) | `settings.py`, `temporal.py`, `backbone.py` | re-run; computed from the saved samples |
| The organizations shown in fig 6 or fig 8 / fig 9 | `figures.RELAY_ROWS`, `FIG8_NAMES`, `FIG9_NAMES` | re-run |

Groups and thresholds were fixed before results were computed. If you change one, say so in the report.

## Full pipeline at a glance

```
scrape_site → scrape_docs → get_pdfs → extract_text → build_tables   (src/ingestion → data/final/)
          → clean                                                    (src/processing → data/processed/)
          → run → verify                                             (src/analysis/network → outputs/network/, outputs/figures/network/)
          → notebooks/network_centrality.ipynb, docs/network_analysis_report.md
```