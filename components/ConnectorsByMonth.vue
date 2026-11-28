<script setup>
// Organizations that connected the response beyond their paperwork volume, month by month.
// Hover a month to preview it, click to keep it. Data: outputs/figures/slides/connectors_by_month.json
import { computed, ref } from 'vue'
import months from '@figures/slides/connectors_by_month.json'
import { KIND_COLOR, INK, INK2, GRID } from './kinds.js'

const W = 560, H = 300, PAD = { l: 8, r: 8, t: 46, b: 44 }
const BREAK = months.findIndex(m => m.month === '2001-12')     // start of the clean-up phase (data-driven)
const maxCount = Math.max(...months.map(m => m.count))
const step = (W - PAD.l - PAD.r) / months.length
const barW = step * 0.72
const y = c => PAD.t + (H - PAD.t - PAD.b) * (1 - c / (maxCount + 1))
const x = i => PAD.l + i * step + (step - barW) / 2

const selected = ref(0)
const hovered = ref(null)
const shown = computed(() => months[hovered.value ?? selected.value])
const MAX_ROWS = 9

function tickLabel(m, i) {
  const [yr, mo] = m.month.split('-')
  const name = m.label.split(' ')[0]
  return { name, year: (mo === '09' || mo === '01' || i === 0) ? yr : '' }
}
</script>

<template>
  <div class="cbm">
    <svg :viewBox="`0 0 ${W} ${H}`" :width="W" :height="H" @mouseleave="hovered = null">
      <line :x1="PAD.l + BREAK * step" :x2="PAD.l + BREAK * step" :y1="PAD.t - 30" :y2="H - PAD.b"
            :stroke="INK" stroke-width="1.5" stroke-dasharray="4 3" />
      <text :x="PAD.l + BREAK * step - 6" :y="PAD.t - 20" text-anchor="end" class="phase" fill="#2a78d6">emergency</text>
      <text :x="PAD.l + BREAK * step + 6" :y="PAD.t - 20" class="phase" :fill="INK2">clean-up and testing</text>
      <line :x1="PAD.l" :x2="W - PAD.r" :y1="H - PAD.b" :y2="H - PAD.b" :stroke="GRID" />
      <g v-for="(m, i) in months" :key="m.month" class="bar"
         @mouseenter="hovered = i" @click="selected = i">
        <rect :x="PAD.l + i * step" :y="PAD.t - 30" :width="step" :height="H - PAD.t - PAD.b + 30 + 40"
              fill="transparent" />
        <rect :x="x(i)" :y="y(m.count)" :width="barW" :height="H - PAD.b - y(m.count)" rx="3"
              :fill="i < BREAK ? '#2a78d6' : '#8db7ea'"
              :stroke="i === (hovered ?? selected) ? INK : 'none'" stroke-width="2" />
        <text :x="x(i) + barW / 2" :y="y(m.count) - 6" text-anchor="middle" class="count">{{ m.count }}</text>
        <text :x="x(i) + barW / 2" :y="H - PAD.b + 16" text-anchor="middle" class="tick">{{ tickLabel(m, i).name }}</text>
        <text :x="x(i) + barW / 2" :y="H - PAD.b + 31" text-anchor="middle" class="tick">{{ tickLabel(m, i).year }}</text>
      </g>
    </svg>

    <div class="panel">
      <div class="panel-h"><b>{{ shown.label }}</b> · {{ shown.count }} organization{{ shown.count === 1 ? '' : 's' }}</div>
      <div class="panel-s">connected beyond their paperwork volume (× = betweenness vs. expected)</div>
      <div v-for="o in shown.orgs.slice(0, MAX_ROWS)" :key="o.name" class="row">
        <span class="dot" :style="{ background: KIND_COLOR[o.kind] }" />
        <span class="nm" :title="o.kind">{{ o.name }}</span>
        <span class="rt">{{ o.ratio }}×</span>
      </div>
      <div v-if="shown.orgs.length > MAX_ROWS" class="more">+ {{ shown.orgs.length - MAX_ROWS }} more</div>
      <div class="hint">hover a month · click to keep it</div>
    </div>
  </div>
</template>

<style scoped>
.cbm { display: flex; gap: 16px; align-items: flex-start; }
.bar { cursor: pointer; }
.count { font-size: 14px; font-weight: 700; fill: #0b0b0b; }
.tick { font-size: 11.5px; fill: #52514e; }
.phase { font-size: 14px; font-weight: 700; }
.panel { width: 300px; min-height: 290px; background: #f7f7f5; border-radius: 12px; padding: 10px 12px; font-size: 13.5px; }
.panel-h { font-size: 16px; margin-bottom: 2px; }
.panel-s { font-size: 11.5px; color: #52514e; margin-bottom: 8px; line-height: 1.3; }
.row { display: flex; align-items: center; gap: 7px; padding: 2px 0; }
.dot { width: 10px; height: 10px; border-radius: 999px; flex: none; }
.nm { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rt { font-variant-numeric: tabular-nums; color: #52514e; }
.more { font-size: 12px; color: #52514e; margin-top: 2px; }
.hint { font-size: 11px; color: #94a3b8; margin-top: 8px; }
</style>
