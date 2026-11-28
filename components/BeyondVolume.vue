<script setup>
// Betweenness percentile before and after holding paperwork volume fixed, for every organization
// named on >= 20 pages. Toggle groups, hover a line, or search a name.
// Data: outputs/figures/slides/beyond_volume.json
import { computed, ref } from 'vue'
import orgs from '@figures/slides/beyond_volume.json'
import { KIND_COLOR, KINDS, INK, INK2, GRID } from './kinds.js'

const W = 540, H = 360, X0 = 70, X1 = 330, T = 14, B = 34
const yy = p => T + (H - T - B) * (1 - p / 100)
const LABELED = ['DEP', 'DOHMH', 'DOB', 'U.S. EPA', 'Port Auth.', 'FDNY', 'Mayor']

const active = ref(new Set(['City regulators', 'Other city agencies', 'State & federal']))
const hovered = ref(null)
const query = ref('')

const counts = computed(() => Object.fromEntries(KINDS.map(k => [k, orgs.filter(o => o.kind === k).length])))
const median = (a) => { const s = [...a].sort((p, q) => p - q); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0 }
const medians = computed(() => Object.fromEntries(KINDS.map(k => {
  const g = orgs.filter(o => o.kind === k)
  return [k, { raw: Math.round(median(g.map(o => o.raw))), adj: Math.round(median(g.map(o => o.adj))) }]
})))

const matches = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q.length < 2 ? [] : orgs.filter(o => o.name.toLowerCase().includes(q)).slice(0, 5)
})
const isOn = o => active.value.has(o.kind) || matches.value.includes(o)
const visible = computed(() => orgs.filter(isOn))

// right-hand labels: the default set plus search matches, spread so they do not overlap
const labels = computed(() => {
  const pick = orgs.filter(o => (LABELED.includes(o.name) && active.value.has(o.kind)) || matches.value.includes(o))
  const sorted = [...pick].sort((a, b) => b.adj - a.adj).map(o => ({ o, y: yy(o.adj) }))
  for (let k = 1; k < sorted.length; k++) sorted[k].y = Math.max(sorted[k].y, sorted[k - 1].y + 15)
  return sorted
})

function toggle(k) {
  const s = new Set(active.value)
  s.has(k) ? s.delete(k) : s.add(k)
  active.value = s
}
</script>

<template>
  <div class="bv">
    <div class="chips">
      <button v-for="k in KINDS" :key="k" class="chip" :class="{ off: !active.has(k) }" @click="toggle(k)"
              :title="`median percentile ${medians[k].raw} → ${medians[k].adj}`">
        <span class="dot" :style="{ background: KIND_COLOR[k] }" />{{ k }} <span class="n">{{ counts[k] }}</span>
      </button>
      <input v-model="query" class="search" placeholder="find an organization…" />
    </div>

    <div class="wrap">
      <svg :viewBox="`0 0 ${W} ${H}`" :width="W" :height="H" @mouseleave="hovered = null">
        <g v-for="p in [0, 25, 50, 75, 100]" :key="p">
          <line :x1="X0" :x2="X1" :y1="yy(p)" :y2="yy(p)" :stroke="GRID" />
          <text :x="X0 - 8" :y="yy(p) + 4" text-anchor="end" class="ax">{{ p }}</text>
        </g>
        <text :x="X0" :y="H - 10" text-anchor="middle" class="axl">raw</text>
        <text :x="X1" :y="H - 10" text-anchor="middle" class="axl">beyond volume</text>
        <text :x="14" :y="(T + H - B) / 2" class="ax" :transform="`rotate(-90 14 ${(T + H - B) / 2})`" text-anchor="middle">betweenness percentile</text>

        <g v-for="o in visible" :key="o.name" @mouseenter="hovered = o" class="ln">
          <line :x1="X0" :x2="X1" :y1="yy(o.raw)" :y2="yy(o.adj)" stroke="transparent" stroke-width="10" />
          <line :x1="X0" :x2="X1" :y1="yy(o.raw)" :y2="yy(o.adj)" :stroke="KIND_COLOR[o.kind]"
                :stroke-width="hovered === o || matches.includes(o) || LABELED.includes(o.name) ? 3 : 1.4"
                :stroke-opacity="hovered && hovered !== o ? 0.15 : (LABELED.includes(o.name) || matches.includes(o) ? 1 : 0.45)" />
          <circle :cx="X1" :cy="yy(o.adj)" r="3" :fill="KIND_COLOR[o.kind]"
                  :fill-opacity="hovered && hovered !== o ? 0.2 : 1" />
        </g>
        <g v-for="l in labels" :key="'l' + l.o.name">
          <line :x1="X1 + 4" :x2="X1 + 14" :y1="yy(l.o.adj)" :y2="l.y" :stroke="GRID" />
          <text :x="X1 + 17" :y="l.y + 4" class="lab">{{ l.o.name }}</text>
        </g>
      </svg>

      <div class="tip" v-if="hovered">
        <div class="tip-n"><span class="dot" :style="{ background: KIND_COLOR[hovered.kind] }" />{{ hovered.name }}</div>
        <div class="tip-k">{{ hovered.kind }} · {{ hovered.pages.toLocaleString() }} pages</div>
        <div>percentile <b>{{ Math.round(hovered.raw) }} → {{ Math.round(hovered.adj) }}</b></div>
        <div>betweenness <b>{{ hovered.ratio }}×</b> what its volume predicts</div>
      </div>
      <div class="tip tip-idle" v-else>
        <div v-for="k in KINDS.filter(k => active.has(k))" :key="k">
          <span class="dot" :style="{ background: KIND_COLOR[k] }" />{{ k }}: <b>{{ medians[k].raw }} → {{ medians[k].adj }}</b>
        </div>
        <div class="hint">median percentile · hover a line for one organization</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bv { font-size: 13px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 4px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 5px; border: 1px solid #cbd5e1; border-radius: 999px; padding: 1px 9px; background: #fff; font-size: 12px; }
.chip.off { opacity: 0.4; }
.chip .n { color: #52514e; font-size: 11px; }
.search { border: 1px solid #cbd5e1; border-radius: 999px; padding: 1px 10px; font-size: 12px; width: 170px; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 999px; margin-right: 4px; flex: none; }
.wrap { display: flex; gap: 10px; align-items: flex-start; }
.ln { cursor: pointer; }
.ax { font-size: 11px; fill: #52514e; }
.axl { font-size: 13px; fill: #0b0b0b; }
.lab { font-size: 12.5px; fill: #0b0b0b; font-weight: 600; }
.tip { width: 230px; background: #f7f7f5; border-radius: 10px; padding: 9px 11px; line-height: 1.45; margin-top: 12px; }
.tip-n { font-weight: 700; font-size: 14px; display: flex; align-items: center; }
.tip-k { color: #52514e; font-size: 12px; margin-bottom: 4px; }
.hint { color: #94a3b8; font-size: 11px; margin-top: 6px; }
</style>
