<script setup>
// The cleaning step, one tab per fix, each with a real before -> after example from the archive.
// Data: outputs/figures/slides/cleaning.json (src/presentation/data.py)
import { computed, ref } from 'vue'
import C from '@figures/slides/cleaning.json'

const TABS = [
  { id: 'offtopic', label: 'Off-topic documents' },
  { id: 'dates', label: 'Dates' },
  { id: 'text', label: 'Page text & stamps' },
  { id: 'usable', label: 'Usable text' },
  { id: 'names', label: 'Names' },
]
const tab = ref('text')          // the slide before shows the date fix
const fmt = n => n.toLocaleString('en-US')

// --- usable text: thresholds as sliders, share recomputed from the letters x words distribution
const U = C.usable
const nb = U.grid.length
const alpha = ref(U.alpha)
const words = ref(U.words)
const usableCount = computed(() => {
  const a0 = Math.round(alpha.value / U.bin), w0 = Math.round(words.value / U.bin)
  let s = 0
  for (let i = a0; i < nb; i++) for (let j = w0; j < nb; j++) s += U.grid[i][j]
  return s
})
const share = computed(() => usableCount.value / U.total)
const maxCell = Math.max(...U.grid.flat())
const cellColor = n => n === 0 ? '#f4f3f0' : `rgba(42,120,214,${0.12 + 0.88 * Math.log(1 + n) / Math.log(1 + maxCell)})`
const passes = ex => ex.chars >= U.min_chars && ex.alpha >= alpha.value - 1e-9 && ex.words >= words.value - 1e-9

const SEG = { header: 'portal header', bates: 'Bates number', stamp: 'litigation stamp' }
const squares = Array.from({ length: C.offtopic.in_boxes }, (_, i) => i < C.offtopic.removed)
</script>

<template>
  <div class="ce">
    <div class="tabs">
      <button v-for="(t, i) in TABS" :key="t.id" class="tab" :class="{ on: tab === t.id }" @click="tab = t.id">
        <span class="tn">{{ i + 1 }}</span>{{ t.label }}
      </button>
    </div>

    <!-- 1. off-topic documents -->
    <div v-if="tab === 'offtopic'" class="pane two">
      <div>
        <div class="big">{{ C.offtopic.removed }} <span>documents removed · {{ fmt(C.offtopic.pages_removed) }} pages</span></div>
        <div class="rule"><b>Rule</b> drop the two boxes of City legal and insurance files, <i>unless</i> the title or description mentions the WTC, Ground Zero or 9/11.</div>
        <div class="sq-wrap">
          <span v-for="(r, i) in squares" :key="i" class="sq" :class="r ? 'sq-out' : 'sq-in'" />
        </div>
        <div class="legend"><span class="sq sq-out" /> removed {{ C.offtopic.removed }} <span class="sq sq-in ml" /> kept {{ C.offtopic.kept }} (they mention the WTC) · {{ C.offtopic.in_boxes }} documents in the two boxes</div>
      </div>
      <div class="card">
        <div class="ch">What was in those boxes</div>
        <div v-for="f in C.offtopic.folders" :key="f.folder" class="frow"><span>{{ f.folder }}</span><b>{{ f.docs }}</b></div>
        <div class="note">Each removed document is listed in <code>removed_documents.parquet</code>: removed, not hidden.</div>
      </div>
    </div>

    <!-- 2. dates -->
    <div v-if="tab === 'dates'" class="pane">
      <div class="rule"><b>Problem</b> the site dates a document by the <i>earliest</i> date anywhere in its text. <b>Fix</b> check it against the date in the title.</div>
      <div class="dates">
        <div v-for="e in C.dates.examples" :key="e.title" class="dcard">
          <div class="dt">{{ e.title }}</div>
          <div class="dchange"><span class="old">{{ e.site }}</span><span class="arrow">→</span><span class="new">{{ e.fixed }}</span>
            <span class="prec">{{ e.precision }}</span></div>
          <div class="drule">{{ e.rule }}</div>
        </div>
      </div>
      <div class="stats">
        <div><b>{{ fmt(C.dates.filled) }}</b> missing dates filled in</div>
        <div><b>{{ fmt(C.dates.replaced) }}</b> wrong dates replaced</div>
        <div><b>{{ fmt(C.dates.flagged) }}</b> flagged as conflicts</div>
        <div>undated <b>{{ fmt(C.dates.undated_before) }} → {{ fmt(C.dates.undated_after) }}</b></div>
      </div>
    </div>

    <!-- 3. page text -->
    <div v-if="tab === 'text'" class="pane two">
      <div>
        <div class="ph">Raw page <span class="muted">({{ C.text.doc_id }}, page {{ C.text.page }})</span></div>
        <pre class="page"><template v-for="(s, i) in C.text.segments" :key="i"><span :class="'seg-' + s.k" :title="SEG[s.k]">{{ s.t }}</span></template></pre>
        <div class="legend"><span class="hl seg-header">portal header</span> <span class="hl seg-bates">Bates number</span> <span class="hl seg-stamp">litigation stamp</span> removed from the text</div>
      </div>
      <div>
        <div class="ph">Cleaned page</div>
        <pre class="page clean">{{ C.text.cleaned }}</pre>
        <div class="kept">kept as data: <code>litigation_stamp</code> = {{ C.text.stamp }} → <code>litigation_source</code> = <b>{{ C.text.source }}</b>
          <div class="muted">{{ Math.round(C.text.stamped_docs_share * 100) }}% of documents carry such a stamp: it records why the page was released.</div></div>
      </div>
    </div>

    <!-- 4. usable text -->
    <div v-if="tab === 'usable'" class="pane two">
      <div>
        <div class="big">{{ (share * 100).toFixed(1) }}% <span>of pages usable · {{ fmt(usableCount) }} of {{ fmt(U.total) }}</span></div>
        <div class="sliders">
          <label><span>letters ≥ <b>{{ Math.round(alpha * 100) }}%</b> of characters</span>
            <input type="range" min="0" max="0.9" step="0.05" v-model.number="alpha" /></label>
          <label><span>real words ≥ <b>{{ Math.round(words * 100) }}%</b> of tokens</span>
            <input type="range" min="0" max="0.9" step="0.05" v-model.number="words" /></label>
        </div>
        <div class="muted small">and at least {{ U.min_chars }} characters ({{ fmt(U.too_short) }} pages are shorter). Our choice: 50% and 40%.</div>
        <div class="excards">
          <div v-for="ex in U.examples" :key="ex.doc_id" class="ex" :class="passes(ex) ? 'ok' : 'no'">
            <div class="exh">{{ passes(ex) ? '✓ usable' : '✗ not usable' }} · {{ ex.label }}</div>
            <div class="exm">letters {{ Math.round(ex.alpha * 100) }}% · words {{ Math.round(ex.words * 100) }}%</div>
          </div>
        </div>
      </div>
      <div class="heat-wrap">
        <svg viewBox="0 0 260 250" width="300" height="288">
          <g transform="translate(34,6)">
            <template v-for="(row, i) in U.grid" :key="'g' + i">
              <rect v-for="(n, j) in row" :key="j" :x="j * 11" :y="(nb - 1 - i) * 11" width="10.4" height="10.4" :fill="cellColor(n)">
                <title>{{ fmt(n) }} pages</title>
              </rect>
            </template>
            <rect :x="Math.round(words / U.bin) * 11 - 0.6" :y="0" :width="(nb - Math.round(words / U.bin)) * 11"
                  :height="(nb - Math.round(alpha / U.bin)) * 11" fill="none" stroke="#0b0b0b" stroke-width="2" />
            <text x="110" y="236" text-anchor="middle" class="axl">real words (share of tokens) →</text>
            <text x="-28" y="110" text-anchor="middle" class="axl" transform="rotate(-90 -28 110)">letters (share of characters) →</text>
          </g>
        </svg>
        <div class="muted small c">each cell = pages with that mix; the box = usable</div>
      </div>
    </div>

    <!-- 5. names -->
    <div v-if="tab === 'names'" class="pane">
      <div class="stats">
        <div><b>{{ C.names.agency_names }} → {{ C.names.agencies }}</b> agency names → agencies (hand-checked map, with a level: city, state, federal…)</div>
        <div><b>{{ fmt(C.names.company_names) }} → {{ fmt(C.names.companies) }}</b> contractor names → companies (suffixes like Inc., LLC removed)</div>
      </div>
      <div class="merges">
        <div v-for="m in [...C.names.agency_examples, ...C.names.company_examples]" :key="m.into" class="merge">
          <span v-for="n in m.names" :key="n" class="nm">{{ n }}</span>
          <span class="arrow">→</span><b>{{ m.into }}</b>
        </div>
      </div>
      <div class="rule"><b>Why</b> without this, one organization is several nodes of the network. A new, unmapped agency name stops the run.</div>
    </div>
  </div>
</template>

<style scoped>
.ce { font-size: 13.5px; }
.tabs { display: flex; gap: 6px; margin-bottom: 10px; }
.tab { border: 1.5px solid #cbd5e1; border-radius: 999px; padding: 3px 12px; background: #fff; font-size: 13px; }
.tab.on { background: #0b0b0b; color: #fff; border-color: #0b0b0b; }
.tn { font-weight: 700; margin-right: 5px; opacity: .6; }
.pane { min-height: 330px; }
.two { display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px; }
.big { font-size: 30px; font-weight: 700; line-height: 1.1; margin-bottom: 6px; }
.big span { font-size: 14px; font-weight: 400; color: #52514e; }
.rule { background: #f7f7f5; border-radius: 8px; padding: 7px 10px; line-height: 1.4; margin-bottom: 10px; }
.card { background: #f7f7f5; border-radius: 10px; padding: 10px 12px; }
.ch { font-weight: 700; margin-bottom: 6px; }
.frow { display: flex; justify-content: space-between; gap: 10px; padding: 2px 0; font-size: 12.5px; }
.note { margin-top: 8px; font-size: 12px; color: #52514e; }
.sq-wrap { display: grid; grid-template-columns: repeat(22, 14px); gap: 3px; margin: 8px 0; }
.sq { display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: middle; }
.sq-out { background: #eb6834; } .sq-in { background: #2a78d6; }
.legend { font-size: 12px; color: #52514e; margin-top: 4px; line-height: 1.8; }
.ml { margin-left: 10px; }
.dates { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.dcard { border: 1.5px solid #e4e3df; border-radius: 10px; padding: 10px 12px; background: #fff; }
.dt { font-size: 13px; font-weight: 600; min-height: 38px; }
.dchange { margin-top: 8px; font-size: 17px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.old { text-decoration: line-through; color: #eb6834; }
.new { color: #2a78d6; font-weight: 700; }
.arrow { color: #94a3b8; }
.prec { font-size: 11px; background: #eef4fc; color: #2a78d6; border-radius: 999px; padding: 0 7px; }
.drule { margin-top: 6px; font-size: 11.5px; color: #52514e; font-family: ui-monospace, monospace; }
.stats { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 12px; }
.stats > div { background: #f7f7f5; border-radius: 8px; padding: 6px 10px; }
.ph { font-weight: 700; margin-bottom: 4px; }
.muted { color: #52514e; font-weight: 400; }
.small { font-size: 12px; }
.c { text-align: center; }
.page { font-family: ui-monospace, monospace; font-size: 10.5px; line-height: 1.35; white-space: pre-wrap; background: #fff;
        border: 1.5px solid #e4e3df; border-radius: 8px; padding: 8px; max-height: 250px; overflow: auto; margin: 0; }
.page.clean { border-color: #2a78d6; }
.seg-header, .seg-bates, .seg-stamp { text-decoration: line-through; border-radius: 3px; padding: 0 2px; }
.seg-header { background: #fde68a; } .seg-bates { background: #fed7aa; } .seg-stamp { background: #fecaca; }
.hl { font-size: 11px; padding: 1px 5px; }
.kept { margin-top: 8px; font-size: 12.5px; background: #eef4fc; border-radius: 8px; padding: 7px 10px; line-height: 1.45; }
.sliders { display: flex; flex-direction: column; gap: 8px; margin: 8px 0 4px; }
.sliders label { display: flex; flex-direction: column; font-size: 13px; }
.sliders input { width: 100%; accent-color: #2a78d6; }
.excards { display: flex; gap: 8px; margin-top: 10px; }
.ex { flex: 1; border-radius: 8px; padding: 6px 9px; font-size: 12.5px; }
.ex.ok { background: #e8f6ef; } .ex.no { background: #fdf0eb; }
.exh { font-weight: 700; }
.exm { color: #52514e; font-size: 12px; }
.heat-wrap { display: flex; flex-direction: column; align-items: center; }
.axl { font-size: 9.5px; fill: #52514e; }
.merges { display: flex; flex-direction: column; gap: 7px; margin: 12px 0; }
.merge { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.nm { background: #f4f3f0; border-radius: 6px; padding: 1px 8px; font-size: 12.5px; }
</style>
