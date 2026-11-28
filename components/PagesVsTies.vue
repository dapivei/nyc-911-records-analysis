<script setup>
// Every organization of the network: pages naming it vs organizations it is tied to (log axes).
// Hover any point, or search a name. Data: outputs/figures/slides/pages_vs_ties.json
import { computed, ref } from 'vue'
import orgs from '@figures/slides/pages_vs_ties.json'
import { KIND_COLOR, KINDS, INK2, GRID } from './kinds.js'

const W = 400, H = 320, L = 46, R = 10, T = 10, B = 40
const lx = Math.log10, maxP = Math.max(...orgs.map(o => o.pages)), maxT = Math.max(...orgs.map(o => o.ties))
const X = p => L + (W - L - R) * (lx(p) - 0) / (lx(maxP * 1.3))
const Y = t => T + (H - T - B) * (1 - lx(t) / lx(maxT * 2))
const LABELED = ['DEP', 'U.S. EPA', 'DOHMH']

// draw gray points first so colored ones sit on top
const ordered = [...orgs].sort((a, b) => (a.kind === 'Companies & others' ? 0 : 1) - (b.kind === 'Companies & others' ? 0 : 1))
const hovered = ref(null)
const query = ref('')
const matches = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q.length < 2 ? [] : orgs.filter(o => o.name.toLowerCase().includes(q)).slice(0, 3)
})

function onMove(e) {
  const svg = e.currentTarget
  const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY
  const p = pt.matrixTransform(svg.getScreenCTM().inverse())
  let best = null, bd = 14 * 14
  for (const o of orgs) {
    const dx = X(o.pages) - p.x, dy = Y(o.ties) - p.y, d = dx * dx + dy * dy
    if (d < bd) { bd = d; best = o }
  }
  hovered.value = best
}
const ticksX = [1, 10, 100, 1000, 10000], ticksY = [1, 10, 100, 1000]
const fmt = v => v >= 1000 ? `${v / 1000}k` : `${v}`
</script>

<template>
  <div class="pvt">
    <div class="top">
      <span v-for="k in KINDS" :key="k" class="lg"><span class="dot" :style="{ background: KIND_COLOR[k] }" />{{ k }}</span>
      <input v-model="query" class="search" placeholder="find an organization…" />
    </div>
    <div class="wrap">
      <svg :viewBox="`0 0 ${W} ${H}`" :width="W" :height="H" @mousemove="onMove" @mouseleave="hovered = null">
        <g v-for="t in ticksX" :key="'x' + t">
          <line :x1="X(t)" :x2="X(t)" :y1="T" :y2="H - B" :stroke="GRID" />
          <text :x="X(t)" :y="H - B + 15" text-anchor="middle" class="ax">{{ fmt(t) }}</text>
        </g>
        <g v-for="t in ticksY" :key="'y' + t">
          <line :x1="L" :x2="W - R" :y1="Y(t)" :y2="Y(t)" :stroke="GRID" />
          <text :x="L - 6" :y="Y(t) + 4" text-anchor="end" class="ax">{{ fmt(t) }}</text>
        </g>
        <text :x="(L + W - R) / 2" :y="H - 6" text-anchor="middle" class="axl">pages naming the organization</text>
        <text :x="12" :y="(T + H - B) / 2" text-anchor="middle" class="axl" :transform="`rotate(-90 12 ${(T + H - B) / 2})`">organizations tied to</text>
        <circle v-for="o in ordered" :key="o.name + o.pages" :cx="X(o.pages)" :cy="Y(o.ties)"
                :r="LABELED.includes(o.name) ? 5 : 2.6" :fill="KIND_COLOR[o.kind]"
                :fill-opacity="o.kind === 'Companies & others' ? 0.45 : 0.9" />
        <g v-for="o in orgs.filter(o => LABELED.includes(o.name) || matches.includes(o))" :key="'lab' + o.name">
          <circle :cx="X(o.pages)" :cy="Y(o.ties)" r="6" fill="none" stroke="#0b0b0b" stroke-width="1.5" />
          <text :x="X(o.pages) < W / 2 ? X(o.pages) + 9 : X(o.pages) - 9" :y="Y(o.ties) + 4"
                :text-anchor="X(o.pages) < W / 2 ? 'start' : 'end'" class="lab">{{ o.name }}</text>
        </g>
        <circle v-if="hovered" :cx="X(hovered.pages)" :cy="Y(hovered.ties)" r="7" fill="none" stroke="#0b0b0b" stroke-width="2" />
      </svg>
      <div class="tip" v-if="hovered">
        <div class="tip-n"><span class="dot" :style="{ background: KIND_COLOR[hovered.kind] }" />{{ hovered.name }}</div>
        <div class="tip-k">{{ hovered.kind }}</div>
        <div><b>{{ hovered.pages.toLocaleString() }}</b> pages</div>
        <div><b>{{ hovered.ties.toLocaleString() }}</b> organizations tied to</div>
      </div>
      <div class="tip tip-idle" v-else>
        <div>{{ orgs.length.toLocaleString() }} organizations with at least one tie.</div>
        <div class="hint">hover a point to see which one</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pvt { font-size: 13px; }
.top { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: center; margin-bottom: 2px; font-size: 11.5px; }
.lg { display: inline-flex; align-items: center; color: #0b0b0b; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 999px; margin-right: 4px; flex: none; }
.search { border: 1px solid #cbd5e1; border-radius: 999px; padding: 1px 10px; font-size: 12px; width: 160px; }
.wrap { display: flex; gap: 8px; align-items: flex-start; }
svg { cursor: crosshair; }
.ax { font-size: 11px; fill: #52514e; }
.axl { font-size: 12.5px; fill: #52514e; }
.lab { font-size: 12.5px; font-weight: 700; fill: #0b0b0b; }
.tip { width: 150px; background: #f7f7f5; border-radius: 10px; padding: 8px 10px; line-height: 1.45; margin-top: 10px; font-size: 12.5px; }
.tip-n { font-weight: 700; font-size: 13.5px; display: flex; align-items: center; }
.tip-k { color: #52514e; font-size: 11.5px; margin-bottom: 4px; }
.hint { color: #94a3b8; font-size: 11px; margin-top: 6px; }
</style>
