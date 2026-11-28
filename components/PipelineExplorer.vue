<script setup>
// The whole pipeline as clickable stages: what each stage does, its modules, its numbers and the
// choices behind it. Numbers: outputs/figures/slides/pipeline.json (src/presentation/data.py)
import { computed, ref } from 'vue'
import N from '@figures/slides/pipeline.json'

const f = n => n.toLocaleString('en-US')
const STAGES = [
  { id: 'scrape', step: '0', name: 'Scrape', where: '911records.org', color: '#475569',
    does: 'Walks the mirror’s indexes and every document page: metadata, entity and building links, catalog changes.',
    modules: ['scrape_site', 'scrape_docs', 'parsers', 'web', 'files'],
    stats: [[f(N.doc_ids), 'document IDs'], [f(N.pages), 'page records'], [f(N.entity_links), 'entity links']],
    choices: ['1 request per second, robots.txt respected, identifiable user agent',
              'every page cached: nothing is fetched twice', 'resumable: stop and re-run any time',
              'stops at a human check instead of getting around it'] },
  { id: 'pdfs', step: '0', name: 'PDFs', where: 'City 9/11 portal', color: '#475569',
    does: 'Gets one PDF per document: the mirror’s bulk ZIPs first, then the City portal for the rest.',
    modules: ['get_pdfs'],
    stats: [[f(N.documents), 'PDFs'], ['ZIPs', 'first, no server load']],
    choices: ['the official City copy is the source of the text', 'file paths rebuilt from the doc_id, never trusted from a ZIP'] },
  { id: 'text', step: '0', name: 'Text', where: 'pdftotext · OCR', color: '#475569',
    does: 'Reads each page’s text: the PDF’s own text layer, OCR for image-only pages, the site only as a last resort.',
    modules: ['extract_text'],
    stats: [[f(N.pdftotext), 'pages from the text layer'], [f(N.tesseract), `by our OCR (confidence ${N.ocr_conf_median})`], [f(N.site_text), 'needed the site']],
    choices: ['cheapest and most faithful source first', 'pages processed in parallel (ProcessPoolExecutor)', 'source and OCR confidence kept per page'] },
  { id: 'tables', step: '0', name: 'Tables', where: 'data/final', color: '#475569',
    does: 'Joins everything into 7 Parquet tables with one key everywhere: the Bates number of the first page.',
    modules: ['build_tables'],
    stats: [['7', 'tables (Git LFS)'], [f(N.entities), 'entities'], [f(N.buildings), 'buildings']],
    choices: ['nothing is corrected here: a faithful copy', 'join keys: doc_id + page · entity_type + slug · bin'] },
  { id: 'clean', step: '1', name: 'Clean', where: 'data/processed', color: '#2a78d6',
    does: 'Removes unrelated documents, corrects dates, strips stamps, flags usable text, merges names.',
    modules: ['clean', 'dates', 'agency_map', 'settings'],
    stats: [[f(N.removed_docs), 'documents removed'], [f(N.dates_changed_or_flagged), 'dates filled, replaced or flagged'], [f(N.usable_pages), 'usable pages']],
    choices: ['the original value is kept next to every fix', 'every threshold in one settings.py', 'plain DataFrame → DataFrame functions'] },
  { id: 'checks', step: '0–2', name: 'Checks', where: 'verify.py', color: '#1baf7a',
    does: 'Each step has a verify.py: rules tested on hand-made inputs, outputs recounted independently.',
    modules: ['ingestion.verify', 'processing.verify', 'network.verify'],
    stats: [['15,583 / 15,586', 'entity counts match the site'], ['100+', 'assert checks'], ['3', 'known issues printed']],
    choices: ['compare our copy with the site’s own totals', 'known problems are counted and written down, not hidden'] },
  { id: 'analysis', step: '2', name: 'Analyses', where: 'outputs/', color: '#eb6834',
    does: 'RQ1 network is done; spatial testing (RQ2) and the language of liability (RQ3) build on the same tables.',
    modules: ['build', 'metrics', 'nullmodel', 'backbone', 'bootstrap', 'temporal'],
    stats: [['1,652', 'organizations'], ['100', 'random networks per test'], ['16', 'monthly networks']],
    choices: ['position separated from paperwork volume', 'fixed seeds; random samples saved so reruns are fast'] },
]
const sel = ref('text')
const S = computed(() => STAGES.find(s => s.id === sel.value))
</script>

<template>
  <div class="pe">
    <div class="rail">
      <template v-for="(s, i) in STAGES" :key="s.id">
        <button class="node" :class="{ on: sel === s.id }" :style="{ '--c': s.color }" @click="sel = s.id" @mouseenter="sel = s.id">
          <div class="nn">{{ s.name }}</div>
          <div class="nw">{{ s.where }}</div>
        </button>
        <div v-if="i < STAGES.length - 1" class="link">›</div>
      </template>
    </div>
    <div class="steps">
      <span style="grid-column: span 4">step 0 · ingestion: <code>src/ingestion/</code></span>
      <span>step 1 · <code>src/processing/</code></span>
      <span>every step</span>
      <span>step 2 · <code>src/analysis/</code></span>
    </div>

    <div class="detail" :style="{ '--c': S.color }">
      <div class="left">
        <div class="dh">{{ S.name }} <span>· {{ S.where }}</span></div>
        <div class="does">{{ S.does }}</div>
        <div class="mods"><span v-for="m in S.modules" :key="m" class="mod">{{ m }}.py</span></div>
        <div class="ch">Choices we made</div>
        <ul><li v-for="c in S.choices" :key="c">{{ c }}</li></ul>
      </div>
      <div class="right">
        <div v-for="st in S.stats" :key="st[1]" class="stat"><div class="sn">{{ st[0] }}</div><div class="sl">{{ st[1] }}</div></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pe { font-size: 13.5px; }
.rail { display: flex; align-items: stretch; gap: 3px; }
.node { flex: 1; border: 2px solid var(--c); border-radius: 10px; padding: 6px 4px; background: #fff; text-align: center; cursor: pointer; }
.node.on { background: var(--c); color: #fff; }
.node.on .nw { color: #fff; opacity: .85; }
.nn { font-weight: 700; font-size: 14px; }
.nw { font-size: 10.5px; color: #52514e; }
.link { display: flex; align-items: center; color: #94a3b8; font-size: 20px; }
.steps { display: grid; grid-template-columns: repeat(7, 1fr); gap: 12px; font-size: 10.5px; color: #52514e; margin: 4px 0 10px; text-align: center; }
.detail { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; border-left: 5px solid var(--c); background: #f7f7f5;
          border-radius: 10px; padding: 12px 16px; min-height: 230px; }
.dh { font-size: 20px; font-weight: 700; }
.dh span { font-size: 14px; font-weight: 400; color: #52514e; }
.does { margin: 4px 0 8px; line-height: 1.4; }
.mods { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
.mod { font-family: ui-monospace, monospace; font-size: 11.5px; background: #fff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 1px 7px; }
.ch { font-weight: 700; font-size: 13px; }
ul { margin: 2px 0 0 18px; padding: 0; list-style: disc; line-height: 1.45; font-size: 13px; }
.right { display: flex; flex-direction: column; gap: 8px; justify-content: center; }
.stat { background: #fff; border-radius: 8px; padding: 6px 10px; border-left: 4px solid var(--c); }
.sn { font-size: 22px; font-weight: 700; line-height: 1.1; }
.sl { font-size: 12px; color: #52514e; }
</style>
