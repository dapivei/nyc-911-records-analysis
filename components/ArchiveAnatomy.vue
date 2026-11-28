<script setup>
// How the release is organized, from the whole release down to one page, with a real example at
// every level. Click or hover a level. Data: outputs/figures/slides/anatomy.json (src/presentation/data.py)
import { computed, ref } from 'vue'
import A from '@figures/slides/anatomy.json'

const f = n => n.toLocaleString('en-US')
const pct = x => `${Math.round(x * 100)}%`
const sel = ref('release')
const L = computed(() => A.levels.find(l => l.id === sel.value))
const maxLog = Math.log10(A.levels[A.levels.length - 1].count)
const barW = c => 8 + 92 * Math.log10(Math.max(c, 1)) / maxLog
const maxPages = Math.max(...A.collections.map(c => c.pages))
const maxYear = Math.max(...Object.values(A.big.years))
const ex = A.example
const TYPE_COLOR = { agency: '#2a78d6', contractor: '#eb6834', lab: '#7c5cd6', substance: '#52514e', address: '#1baf7a', signatory: '#c2417a' }
</script>

<template>
  <div class="aa">
    <div class="ladder">
      <button v-for="(l, i) in A.levels" :key="l.id" class="lvl" :class="{ on: sel === l.id }"
              @click="sel = l.id" @mouseenter="sel = l.id">
        <div class="lt"><span class="idx">{{ i + 1 }}</span>{{ l.label }}</div>
        <div class="lb"><span class="bar" :style="{ width: barW(l.count) + '%' }" /><b>{{ f(l.count) }}</b></div>
      </button>
      <div class="scale">bar length: log scale</div>
    </div>

    <div class="panel">
      <!-- release and volumes: where the pages are -->
      <template v-if="sel === 'release' || sel === 'volume'">
        <div class="ph">{{ sel === 'release' ? 'One release, four very different parts' : `${A.levels[1].count} production volumes` }}</div>
        <div class="sub" v-if="sel === 'release'">Files from {{ A.documents.agencies }} City agencies. Most pages come from one place:</div>
        <div class="sub" v-else>The City released the files in numbered batches (NYC-WTC0001 … 0010). Volume 0008 alone holds
          {{ f(A.unfiled.docs) }} documents with no box or collection, most of them school air-sample records, and {{ pct(A.unfiled.stamped_share) }} of its pages carry a litigation stamp.</div>
        <div v-for="c in A.collections" :key="c.name" class="crow">
          <div class="cn">{{ c.name }}</div>
          <div class="cb"><span class="cbar" :style="{ width: (100 * c.pages / maxPages) + '%' }" /></div>
          <div class="cv"><b>{{ f(c.pages) }}</b> pages · {{ f(c.docs) }} docs</div>
        </div>
      </template>

      <!-- collection: the 68 boxes -->
      <template v-if="sel === 'collection'">
        <div class="ph">The “68 boxes”: {{ pct(A.big.share_pages) }} of all pages</div>
        <div class="sub">DEP’s hard-copy files, located at DEP while the City fought the records lawsuit: {{ f(A.big.docs) }} documents,
          {{ f(A.big.pages) }} pages, filed in {{ f(A.big.folders) }} folders. None of these pages carries a litigation stamp, unlike the school records.</div>
        <div class="two">
          <div>
            <div class="mini-h">What they are (by title words, overlapping)</div>
            <div v-for="k in A.big.kinds" :key="k.kind" class="krow"><span class="kn">{{ k.kind }}</span>
              <span class="kbar" :style="{ width: (k.share * 220) + 'px' }" /><span class="kv">{{ pct(k.share) }}</span></div>
          </div>
          <div>
            <div class="mini-h">When (corrected dates)</div>
            <div class="years">
              <div v-for="(n, y) in A.big.years" :key="y" class="yc">
                <div class="yb" :style="{ height: (70 * n / maxYear + 2) + 'px' }" /><div class="yn">{{ f(n) }}</div><div class="yl">{{ y }}</div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- boxes and folders -->
      <template v-if="sel === 'box' || sel === 'folder'">
        <div class="ph">{{ sel === 'box' ? `${f(A.levels[3].count)} boxes` : `${f(A.levels[4].count)} folders` }}</div>
        <div class="sub" v-if="sel === 'box'">Physical boxes as the agencies stored them, e.g. <code>{{ A.big.box_names[0] }}</code>,
          <code>{{ ex.box }}</code>. In the release, the 68-box collection appears under {{ A.big.boxes }} box labels. Only 38% of documents keep a box at all.</div>
        <div class="sub" v-else>Inside each box, folders follow the agency’s own logic: by <b>building</b> (address and building ID),
          by <b>lab batch</b>, by <b>person’s e-mails</b>. The folder is often the only structure a document has.</div>
        <div class="folders" v-if="sel === 'folder'">
          <div v-for="fo in A.big.folder_examples" :key="fo" class="fo">📁 {{ fo }}</div>
          <div class="fo on">📁 {{ ex.folder }} <span class="tag">our example</span></div>
        </div>
      </template>

      <!-- document -->
      <template v-if="sel === 'document'">
        <div class="ph">{{ f(A.levels[5].count) }} documents, from 1 to {{ A.documents.max_pages }} pages</div>
        <div class="sub">Median {{ A.documents.median_pages }} page; {{ f(A.documents.single_page) }} documents are a single page.
          Every document is named by the Bates number of its first page, the key that joins all our tables.</div>
        <div class="doccard">
          <div class="dpath">{{ ex.volume }} › {{ ex.collection }} › {{ ex.box }} › 📁 {{ ex.folder.slice(0, 40) }}…</div>
          <div class="dtitle">{{ ex.title }}</div>
          <div class="dmeta"><code>{{ ex.doc_id }}</code> · {{ ex.n_pages }} pages · Bates {{ ex.bates_range }} · {{ ex.agency }}</div>
        </div>
      </template>

      <!-- page anatomy -->
      <template v-if="sel === 'page'">
        <div class="ph">Anatomy of one page <span class="muted">({{ ex.bates_page }}, page {{ ex.page }} of {{ ex.n_pages }})</span></div>
        <div class="pagegrid">
          <pre class="ptext">{{ ex.text }}…</pre>
          <div class="links">
            <div class="mini-h">Text</div><div class="lk">from the PDF’s own text layer (<code>{{ ex.source }}</code>)</div>
            <div class="mini-h">Contaminants tagged</div>
            <div class="chips"><span v-for="c in ex.contaminants" :key="c" class="chip">{{ c }}</span></div>
            <div class="mini-h">Organizations and substances named</div>
            <div class="chips"><span v-for="e in ex.entities" :key="e.name" class="chip" :style="{ borderColor: TYPE_COLOR[e.type] }">
              <i :style="{ background: TYPE_COLOR[e.type] }" />{{ e.name }}</span></div>
            <div class="mini-h">Building</div>
            <div class="lk" v-for="b in ex.buildings" :key="b.bin">{{ b.name }} · BIN {{ b.bin }} · {{ b.class }}, built {{ b.year }}</div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.aa { display: grid; grid-template-columns: 300px 1fr; gap: 16px; font-size: 13px; }
.ladder { display: flex; flex-direction: column; gap: 4px; }
.lvl { text-align: left; border: 1.5px solid #e4e3df; border-radius: 9px; padding: 4px 9px; background: #fff; cursor: pointer; }
.lvl.on { border-color: #0b0b0b; background: #f7f7f5; }
.lt { font-weight: 700; font-size: 13px; }
.idx { display: inline-block; width: 16px; color: #94a3b8; }
.lb { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.bar { height: 7px; border-radius: 4px; background: #2a78d6; display: inline-block; max-width: 180px; }
.lb b { font-size: 12.5px; font-variant-numeric: tabular-nums; }
.scale { font-size: 10.5px; color: #94a3b8; margin-top: 2px; }
.panel { background: #f7f7f5; border-radius: 12px; padding: 12px 14px; min-height: 345px; }
.ph { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.sub { color: #3f3e3b; line-height: 1.45; margin-bottom: 10px; }
.muted { color: #52514e; font-weight: 400; font-size: 13px; }
.crow { display: grid; grid-template-columns: 210px 1fr 170px; gap: 8px; align-items: center; margin: 7px 0; }
.cn { font-size: 12.5px; }
.cb { background: #fff; border-radius: 4px; height: 14px; }
.cbar { display: block; height: 14px; border-radius: 4px; background: #2a78d6; }
.cv { font-size: 12px; color: #52514e; }
.two { display: grid; grid-template-columns: 1.3fr 1fr; gap: 14px; }
.mini-h { font-weight: 700; font-size: 12px; margin: 6px 0 4px; }
.krow { display: flex; align-items: center; gap: 6px; margin: 4px 0; font-size: 12px; }
.kn { width: 150px; } .kbar { height: 10px; background: #2a78d6; border-radius: 3px; display: inline-block; } .kv { color: #52514e; }
.years { display: flex; gap: 8px; align-items: flex-end; height: 110px; }
.yc { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
.yb { width: 28px; background: #2a78d6; border-radius: 3px 3px 0 0; }
.yn { font-size: 10.5px; color: #52514e; } .yl { font-size: 11.5px; }
.folders { display: flex; flex-direction: column; gap: 5px; }
.fo { background: #fff; border-radius: 7px; padding: 4px 9px; font-size: 12.5px; border: 1px solid #e4e3df; }
.fo.on { border-color: #2a78d6; }
.tag { font-size: 10.5px; color: #2a78d6; margin-left: 6px; }
.doccard { background: #fff; border-radius: 10px; border: 1.5px solid #2a78d6; padding: 10px 12px; }
.dpath { font-size: 11.5px; color: #52514e; }
.dtitle { font-size: 16px; font-weight: 700; margin: 4px 0; }
.dmeta { font-size: 12px; color: #52514e; }
.pagegrid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 12px; }
.ptext { font-family: ui-monospace, monospace; font-size: 10px; line-height: 1.35; white-space: pre-wrap; background: #fff;
         border: 1.5px solid #e4e3df; border-radius: 8px; padding: 8px; margin: 0; max-height: 290px; overflow: hidden; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip { display: inline-flex; align-items: center; gap: 4px; background: #fff; border: 1.5px solid #cbd5e1; border-radius: 999px; padding: 0 8px; font-size: 11.5px; }
.chip i { width: 7px; height: 7px; border-radius: 999px; display: inline-block; }
.lk { font-size: 12px; }
</style>
