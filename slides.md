---
theme: neversink
title: 'After the Dust · Reading NYC’s 9/11 records as data'
layout: cover
color: black
routerMode: hash
transition: slide-left
mdc: true
---

<div class="absolute inset-0 cover-photo" style="background-image: linear-gradient(90deg, rgba(10,10,10,.92) 0%, rgba(10,10,10,.75) 45%, rgba(10,10,10,.25) 100%), url('https://commons.wikimedia.org/wiki/Special:FilePath/FEMA_-_4235_-_Photograph_by_Andrea_Booher_taken_on_09-28-2001_in_New_York.jpg?width=1920');"></div>

<div class="relative z-10">

<div class="text-sm tracking-widest uppercase opacity-70 mb-2">DS-GA 1007 · Programming for Data Science · Fall 2026</div>

# After the Dust

<div class="text-2xl font-light mt-2 mb-8 max-w-[34rem] leading-snug">Reading New York City’s 9/11 records as data: networks, testing and the language of liability</div>

**Daniela Pinto Veizaga · Beibei Xia · You Fan · Betty Cui**

</div>

<div class="photo-credit absolute bottom-3 left-14 z-10 text-white/70">Ground Zero, 28 Sep 2001 · Andrea Booher / FEMA · public domain</div>

<!--
0:00–0:25. Title. One sentence: "In September the City finally released its 9/11 environmental records. We turned them into data."
Timing plan: 0–2:25 motivation and questions · 2:25–6:00 the archive, pipeline, code and cleaning · 6:00–8:25 RQ1 network · 8:25–9:25 RQ2 and RQ3 (in progress) · 9:25–10 takeaways. Backup slides after “Thank you”.
-->

---
layout: two-cols-title
columns: is-5
color: white
---

:: title ::

# 8 September 2026: the City opens its 9/11 records

:: left ::

<div class="relative h-[355px] rounded-xl overflow-hidden photo-frame">
<img src="https://commons.wikimedia.org/wiki/Special:FilePath/September_17_2001_Ground_Zero_04.jpg?width=1400" class="w-full h-full object-cover" alt="Aerial view of Ground Zero and damaged surrounding buildings, 17 September 2001" />
</div>
<div class="photo-credit mt-1">Ground Zero, 17 Sep 2001 · U.S. Navy (Eric J. Tilford) · public domain</div>

:: right ::

<div class="grid grid-cols-2 gap-3 mt-1">
<div v-click class="stat">
<div class="stat-n">~170,000</div>
<div class="stat-l">pages on air quality, health concerns and the City’s response, in the first release</div>
</div>
<div v-click class="stat">
<div class="stat-n">68 boxes</div>
<div class="stat-l">of Department of Environmental Protection files, part of the release</div>
</div>
<div v-click class="stat">
<div class="stat-n">2 lawsuits</div>
<div class="stat-l">brought by 9/11 Health Watch, settled with the release</div>
</div>
<div v-click class="stat stat-warn">
<div class="stat-n">More deaths</div>
<div class="stat-l">from 9/11-related illnesses than on the day itself</div>
</div>
</div>

<div v-click class="mt-4 text-[15px] leading-snug">
Coverage focused on <b>single documents</b> (e.g. the Harding memo on possible lawsuits). We read the release <b class="text-sky-700">as data</b>.
</div>

<div class="source-line">Sources: NYC Office of the Mayor, 8 Sep 2026 · CBS News · CNN, Sep 2026</div>

<!--
0:25–1:50. The story in order: Sep 18, 2001 “safe to breathe” → 2003 EPA Inspector General: not enough data to say so → Oct 2001 liability memo to the deputy mayor (35,000 potential plaintiffs) → 2023 records request, City says no records → 68 boxes found at DEP during the lawsuit → May 2026 judge: denial “arbitrary and capricious” → Sep 8, 2026 portal and settlement. End: the 68 boxes are in our data.
Point: the news reads one memo at a time. Our questions need the whole archive.
-->

---
layout: top-title
color: white
---

:: title ::

# Three questions no single document can answer

:: content ::

<div class="grid grid-cols-3 gap-4 mt-1">
<div v-click class="rq-card border-sky-500">
<div class="rq-tag bg-sky-600">RQ1 · Network</div>

### Who held the response together?
Which organizations connected the different parts of the response, and when did that change?

<div class="rq-h"><b>H1</b> Regulators and real-estate firms are more central than advocacy groups.</div>
<div class="status done">✓ Done</div>
</div>
<div v-click class="rq-card border-emerald-500">
<div class="rq-tag bg-emerald-600">RQ2 · Spatial</div>

### Where did testing go?
Which Lower Manhattan buildings were tested, and how soon?

<div class="rq-h"><b>H2</b> Commercial hubs were tested earlier than residential zones.</div>
<div class="status wip">In progress</div>
</div>
<div v-click class="rq-card border-amber-500">
<div class="rq-tag bg-amber-600">RQ3 · Language</div>

### What were officials worried about?
Did internal language about risk and liability move ahead of what the public was told?

<div class="rq-h"><b>H3</b> Liability terms spike in internal memos weeks before public guidance changes.</div>
<div class="status wip">In progress</div>
</div>
</div>

<div v-click class="mt-5 text-center text-[16px]">Reading the archive as data also shows its <b>limits</b>: whose files were released, and who is missing from them.</div>

<!--
1:50–2:25. Read the three questions only. RQ2 and RQ3 are being finished by teammates; we show what is ready for them at the end.
-->

---
layout: section
color: sky
---

# 1 · From scanned pages to a dataset

How we built, cleaned and checked the archive

---
layout: top-title
color: white
---

:: title ::

# What we are working with: from the release down to one page

:: content ::

<ArchiveAnatomy />

<!--
2:25–3:25. Interactive: walk down the ladder. Release (where the pages are) → Collections (the 68 boxes: 71% of all pages; lab results, letters, inspections; 2001–2002) → Folders (organized by building, lab batch, person) → Page (one real page: its text, contaminants, organizations, building).
-->

---
layout: top-title
color: white
---

:: title ::

# One pipeline, from scraped pages to answers

:: content ::

<PipelineExplorer />

<div class="text-center text-[12.5px] mt-2 opacity-75">every step ships with a <b>README</b> (how to run it) · a <b>report</b> (what it found) · a <b>notebook</b> (walkthrough) · a <b>verify.py</b> (checks)</div>

<!--
3:25–4:15. Interactive: hover the stages left to right; stop on Scrape (polite, cached, resumable), Text (99.6% from the PDFs’ own text) and Checks (counts match the site’s own totals).
-->

---
layout: two-cols-title
columns: is-6
color: white
---

:: title ::

# Modular code: every step is a module you can run or import

:: left ::

<CodeMap class="mt-1" />

:: right ::

<div class="space-y-2 text-[13px] mt-1">
<div v-click class="py-row"><b>Structure</b> one folder per step · small functions with type hints and docstrings · one <code>settings.py</code> per step</div>
<div v-click class="py-row"><b>Text</b> compiled regular expressions (<code>re</code>) · <code>pathlib</code> · f-strings · comprehensions</div>
<div v-click class="py-row"><b>Data</b> pandas <code>merge</code> · <code>groupby</code> · <code>explode</code> · <code>str.extract</code> · NumPy vectorization</div>
<div v-click class="py-row"><b>Speed</b> <code>ProcessPoolExecutor</code> in parallel · <code>scipy.sparse</code> matrices · cached HTML · resumable steps · saved samples</div>
<div v-click class="py-row"><b>Trust</b> <code>assert</code>-based checks on toy inputs and real recounts · fixed seeds (<code>np.random.default_rng</code>) · <code>with</code> blocks for files and workers</div>
</div>

<!--
4:15–4:40. Code slide: hover a bar to list its modules. Same layout in every step; any function can be imported in a notebook (the notebooks do this); verify scripts make every number checkable.
-->

---
layout: top-title
color: white
---

:: title ::

# The site’s dates invent history

:: content ::

<img src="@figures/slides/s_dates_per_year.png" class="fig h-[285px] mx-auto" alt="Documents per year before and after the date correction" />

<div class="grid grid-cols-3 gap-3 mt-3 text-[14px]">
<div v-click class="mini-card"><b>The bug.</b> The site dates a document by the <i>earliest</i> date in its text: a lab-method date, a fax clock, a mention of 9/11.</div>
<div v-click class="mini-card"><b>The fix.</b> Cross-check with the title’s month and year; drop dates repeated across documents that never match.</div>
<div v-click class="mini-card mini-accent"><b>1994: 198 → 20 docs.</b> 6,638 dates filled in, 2,670 replaced, 1,270 flagged.</div>
</div>

<!--
4:40–5:15. The 1994 spike is asbestos results from 2001–2003 that print a 1994 NIOSH method date on every sheet. Without this, any time series has events that never happened.
-->

---
layout: top-title
color: white
---

:: title ::

# Cleaning, step by step: what we fixed and why

:: content ::

<CleaningExplorer />

<!--
5:15–6:00. Interactive, one tab per fix (the date fix was the slide before). Page text: stamps removed from the text, kept as data. Usable text: move the words slider to show why 40%. Then Names, and Off-topic if time allows.
-->

---
layout: section
color: amber
---

# 2 · RQ1: Who held the response together?

A network of organizations named on the same pages

---
layout: two-cols-title
columns: is-5
color: white
---

:: title ::

# A network from shared pages, and its trap

:: left ::

<div class="text-[15px] leading-snug space-y-3 mt-1">
<div v-click><b>Tie</b> = two organizations named on the <b>same page</b>.<br><span class="opacity-70">1,652 organizations · 18,998 documents</span></div>
<div v-click class="trap"><b>The trap.</b> An organization named on many pages is linked to almost everyone, whatever its role. A naive network ranks <b>paperwork</b>, not <b>position</b>.</div>
<div v-click><b>The fix.</b> Compare each organization with <b>100 random networks</b> that keep every page count and shuffle who appears with whom.<br><span class="opacity-70">+ validated ties, consensus blocks, bootstrap, one network per month</span></div>
<div v-click class="new-tag">New for this archive: separating <b>position</b> from <b>paperwork volume</b>, month by month.</div>
</div>

:: right ::

<PagesVsTies class="mt-1" />
<div class="caption">Organizations named on more pages tend to have more ties (Spearman ρ = 0.44).</div>

<!--
6:00–6:35. This is the methodological heart: "position beyond volume" = observed centrality divided by what the random networks give for the same page count.
-->

---
layout: top-title
color: white
---

:: title ::

# The raw center is mostly paperwork

:: content ::

<BeyondVolume />

<div class="grid grid-cols-2 gap-3 mt-1 text-[14px] leading-snug">
<div v-click class="mini-card mini-accent"><b>City regulators 98 → 37</b> (median percentile) once volume is fixed. DEP, EPA and the Health Department top the raw ranking because <b>the record is mostly theirs</b>: 79% of pages naming an organization come from DEP’s files.</div>
<div v-click class="mini-card">Who connects <b>beyond</b> their volume: <b>coordinators</b> (Port Authority, Mayor’s Office, FDNY), a utility and testing labs.</div>
</div>

<!--
6:35–7:10. Interactive: hover a line for one organization; the chips switch groups on and off; the search box answers “where is X?”. Blue lines (regulators) fall; coordinators stay high.
-->

---
layout: top-title
color: white
---

:: title ::

# Many connectors in fall 2001, very few in 2002

:: content ::

<ConnectorsByMonth class="mx-auto" />

<div class="grid grid-cols-3 gap-3 mt-2 text-[14px] leading-snug">
<div v-click class="mini-card mini-accent"><b>13 → 1</b> organizations a month connecting the response beyond their paperwork volume, Sep 2001 → Dec 2002.</div>
<div v-click class="mini-card">The main break, at the <b>end of 2001</b>, is found by the data, not by us: the hand-off from emergency to clean-up.</div>
<div v-click class="mini-card">The Law Department moves toward the center through <b>contract paperwork</b>, not litigation.</div>
</div>

<!--
7:10–7:50. Interactive: hover a month to list the organizations; click Sep 2001, then Dec 2002. A month counts an organization when it is named on 20+ pages and beats 95% of that month’s random networks.
-->

---
layout: two-cols-title
columns: is-8
color: white
---

:: title ::

# Functional blocks, and an empty seat for the public

:: left ::

<div class="grid grid-cols-3 gap-2 text-[12.5px] leading-tight mt-1">
<div class="blk"><b>Air monitoring</b><br>NIOSH, OSHA<div class="blk-n">49 orgs · 7 ties to hub</div></div>
<div class="blk"><b>EPA + sampling labs</b><br>EPA, FEMA, labs<div class="blk-n">56 orgs · 21 ties to hub</div></div>
<div class="blk"><b>Asbestos abatement</b><br>removal contractors<div class="blk-n">25 orgs · 13 ties to hub</div></div>
<div class="blk"><b>Building owners</b><br>exterior clean-up program<div class="blk-n">199 orgs · 20 ties to hub</div></div>
<div class="blk blk-hub"><b>City / state public health</b><br>DEP, Health Dept., Buildings, NYS Health<div class="blk-n">hub: 70 of 114 ties between blocks</div></div>
<div class="blk"><b>WTC site operations</b><br>OEM, Mayor, DCAS, FDNY<div class="blk-n">48 orgs · 9 ties to hub</div></div>
<div></div>
<div class="blk blk-adv"><b>Advocacy groups</b><br>9/11 Env. Action, NRDC, Am. Lung Assn., NYCOSH<div class="blk-n">0 ties beyond chance</div></div>
<div></div>
</div>
<div class="caption mt-1">Blocks of the validated network: ties kept only if more frequent than chance; 100 consensus runs.</div>

:: right ::

<div class="space-y-4 mt-6 text-[15px] leading-snug">
<div v-click>Five working blocks, joined mainly through a sixth: <b>city and state public health</b>.</div>
<div v-click class="big-shift"><span class="text-emerald-700">Advocacy groups</span><br><span class="shift-n">0 ties</span><br><span class="opacity-70 text-[13px]">beyond chance (strict test); 13–38 per city regulator</span></div>
<div v-click class="takeaway"><b>H1:</b> the regulators’ lead is real but mostly volume; the real-estate claim is not supported; advocacy groups sit at the edge.</div>
</div>

<!--
7:50–8:25. Ties here are only those more frequent than chance. The affected public is largely missing from the City's own record.
-->

---
layout: section
color: emerald
---

# 3 · In progress

Spatial testing (RQ2) and the language of liability (RQ3)

---
layout: two-cols-title
columns: is-5
color: white
---

:: title ::

# RQ2 · Where did testing go?

:: left ::

<div class="relative h-[330px] rounded-xl overflow-hidden photo-frame">
<img src="https://commons.wikimedia.org/wiki/Special:FilePath/Wtc-photo.jpg?width=1400" class="w-full h-full object-cover" alt="Aerial photograph of Ground Zero and Lower Manhattan, 23 September 2001" />
</div>
<div class="photo-credit mt-1">Lower Manhattan, 23 Sep 2001 · NOAA · public domain</div>

:: right ::

<div class="rq-h mb-3"><b>H2</b> Commercial hubs show a concentration of early testing records compared with residential zones.</div>

<div class="text-[14px] font-bold mb-1">Ready from the pipeline</div>
<div class="grid grid-cols-2 gap-2 text-[13px]">
<div class="ready">984 buildings with class, size, coordinates</div>
<div class="ready">27,606 pages tagged with a building</div>
<div class="ready">corrected dates, with day / month / year precision</div>
<div class="ready warn">use page tags: <code>building_mentions</code> undercounts the most-tested buildings</div>
</div>

<div class="placeholder mt-4">
<div class="font-bold">Results</div>
<div class="opacity-70 text-[13px]">map of first test date by building class · commercial vs residential timing</div>
</div>

<!--
8:25–8:55. Teammates' analysis. Replace the dashed box with the main map or result when ready.
-->

---
layout: two-cols-title
columns: is-7
color: white
---

:: title ::

# RQ3 · What were officials worried about?

:: left ::

<div class="rq-h mb-3"><b>H3</b> Internal memos show an early spike in liability and risk terms weeks before public-facing guidance adopts restrictive language.</div>

<div class="text-[14px] font-bold mb-1">Ready from the pipeline</div>
<div class="grid grid-cols-2 gap-2 text-[13px]">
<div class="ready">150,550 usable pages, stamps removed</div>
<div class="ready">corrected document dates for weekly series</div>
<div class="ready">litigation stamp per page: why it was released</div>
<div class="ready warn">no document-type label yet: memos vs. public guidance must be classified</div>
</div>

<div class="placeholder mt-4">
<div class="font-bold">Results</div>
<div class="opacity-70 text-[13px]">liability / risk terms per week · internal vs. public</div>
</div>

:: right ::

<div class="relative h-[330px] rounded-xl overflow-hidden photo-frame">
<img src="https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/particles.jpg" class="w-full h-full object-cover" alt="Magnified World Trade Center dust: concrete, glass fiber and chrysotile asbestos" />
</div>
<div class="photo-credit mt-1">WTC dust under the microscope: concrete, glass fiber, chrysotile asbestos · USGS · public domain</div>

<!--
8:55–9:25. Teammates' analysis. Asbestos and its fiber types are the most common contaminant tags in the archive (44% of pages carry a tag).
-->

---
layout: top-title
color: white
---

:: title ::

# What the records show, and what they can’t

:: content ::

<div class="grid grid-cols-2 gap-5 mt-1">
<div>
<div class="text-[15px] font-bold text-sky-700 mb-2">What we learned</div>
<div class="space-y-2 text-[15px] leading-snug">
<div v-click class="learn">The archive needed <b>cleaning before counting</b>: its dates alone invent events.</div>
<div v-click class="learn">The response was held together by <b>many organizations in fall 2001</b>, and by very few in 2002.</div>
<div v-click class="learn">Raw centrality mostly measures <b>whose paperwork</b> was released.</div>
</div>
</div>
<div>
<div class="text-[15px] font-bold text-rose-700 mb-2">What the record can’t show</div>
<div class="space-y-2 text-[15px] leading-snug">
<div v-click class="limit">A shared page is <b>not</b> communication or responsibility.</div>
<div v-click class="limit">It is mostly <b>DEP’s view</b> of the response.</div>
<div v-click class="limit">The <b>affected public</b> is largely missing from it.</div>
</div>
</div>
</div>

<div v-click class="mt-5 text-center text-[17px] font-light">Recovery needs an owner as clear as the emergency, and the public needs a seat in the record.</div>

<!--
9:25–9:50. Three things we learned, three limits. End on the policy line from the network report.
-->

---
layout: cover
color: black
---

<div class="absolute inset-0 cover-photo" style="background-image: linear-gradient(90deg, rgba(10,10,10,.94) 0%, rgba(10,10,10,.8) 55%, rgba(10,10,10,.45) 100%), url('https://commons.wikimedia.org/wiki/Special:FilePath/Wtc-photo.jpg?width=1920');"></div>

<div class="relative z-10">

# Thank you

<div class="text-lg font-light mt-2 mb-6">Code, data, reports and notebooks:<br><b>github.com/dapivei/nyc-911-records-analysis</b></div>

<div class="text-[12px] opacity-75 max-w-[38rem] leading-relaxed">
Photos (public domain, U.S. federal government): Andrea Booher / FEMA · U.S. Navy, Eric J. Tilford · NOAA · USGS Denver Microbeam Laboratory.<br>
Sources: NYC Office of the Mayor, “25 Years Later, Mamdani Administration Opens City’s 9/11 Records to the Public”, 8 Sep 2026 · CBS News · CNN, Sep 2026.<br>
Data: NYC 9/11 Document Portal and the 911records.org mirror.
</div>

</div>

<!--
9:50–10:00. Questions; backup slides follow.
-->

---
layout: section
color: slate
---

# Backup

For questions

---
layout: two-cols-title
columns: is-6
color: white
---

:: title ::

# Backup · How sure are we?

:: left ::

<img src="@figures/network/fig7_bootstrap_betweenness_ranks.png" class="fig h-[340px] mx-auto" alt="Bootstrap intervals of betweenness rank" />
<div class="caption">100 document bootstraps: DEP (rank 1) and DOHMH (rank 3) never move.</div>

:: right ::

<img src="@figures/network/fig5_observed_vs_null.png" class="fig mt-6" alt="Observed vs expected centrality" />
<div class="caption">Observed vs. expected centrality from 100 frequency-preserving null networks.</div>

<div class="takeaway mt-4 text-[13px]">“Every regulator above every advocacy group”: 100% of resamples on degree, 95% on betweenness. “All real-estate firms above advocacy”: only 39%.</div>

---
layout: two-cols-title
columns: is-6
color: white
---

:: title ::

# Backup · How do we know the data is right?

:: left ::

<div class="space-y-2 text-[13px]">
<div class="py-row"><b>Ingestion</b> every document has all its pages; Bates numbers consistent; entity links equal the site’s own counts for 15,583 of 15,586 entities</div>
<div class="py-row"><b>Processing</b> raw documents = kept + removed; dates in range; date rules tested on hand-made titles; <code>has_usable_text</code> recomputed from settings</div>
<div class="py-row"><b>Network</b> metrics on toy graphs with hand-computed answers; edge weights recounted from raw mentions; null model keeps both degree sequences</div>
<div class="py-row warn-row"><b>Known issues, written down</b> 234 ID-only documents; lost change type; <code>building_mentions</code> undercount</div>
</div>

:: right ::

<img src="@figures/network/fig9_whose_files.png" class="fig h-[350px] mx-auto" alt="Share of each organization's pages from DEP's own files" />
<div class="caption">79% of pages naming an organization come from DEP’s files; coordinators are named across agencies.</div>
