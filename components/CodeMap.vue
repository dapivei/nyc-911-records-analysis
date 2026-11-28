<script setup>
// Where the code is: lines per step, split by role (pipeline logic, figures, checks, settings).
// Hover a segment to list its modules. Data: outputs/figures/slides/code_map.json
import { computed, ref } from 'vue'
import modules from '@figures/slides/code_map.json'

const ROLES = [
  { id: 'pipeline', label: 'pipeline logic', color: '#2a78d6' },
  { id: 'checks', label: 'checks (verify.py)', color: '#1baf7a' },
  { id: 'figures', label: 'figures', color: '#7c5cd6' },
  { id: 'settings', label: 'settings', color: '#eb6834' },
]
const STEPS = [
  { id: 'ingestion', label: 'ingestion' }, { id: 'processing', label: 'processing' },
  { id: 'analysis/network', label: 'analysis / network' }, { id: 'presentation', label: 'presentation' },
]
const total = (rows, key) => rows.reduce((s, m) => s + m[key], 0)
const bars = computed(() => STEPS.map(s => {
  const mods = modules.filter(m => m.step === s.id)
  return { ...s, lines: total(mods, 'lines'), parts: ROLES.map(r => {
    const ms = mods.filter(m => m.role === r.id)
    return { ...r, lines: total(ms, 'lines'), mods: ms.map(m => m.module) }
  }).filter(p => p.lines > 0) }
}))
const maxLines = Math.max(...bars.value.map(b => b.lines))
const hover = ref(null)
const shown = computed(() => modules.filter(m => STEPS.some(s => s.id === m.step)))
const totals = computed(() => ({ modules: shown.value.length, lines: total(shown.value, 'lines'),
  functions: total(shown.value, 'functions'), asserts: total(shown.value, 'asserts') }))
const f = n => n.toLocaleString('en-US')
</script>

<template>
  <div class="cm">
    <div class="totals">
      <div><b>{{ totals.modules }}</b> modules</div><div><b>{{ f(totals.lines) }}</b> lines</div>
      <div><b>{{ totals.functions }}</b> functions</div><div><b>{{ totals.asserts }}</b> <code>assert</code> checks</div>
    </div>
    <div v-for="b in bars" :key="b.id" class="row">
      <div class="lab">{{ b.label }}</div>
      <div class="bar">
        <div v-for="p in b.parts" :key="p.id" class="seg" :style="{ width: (100 * p.lines / maxLines) + '%', background: p.color }"
             @mouseenter="hover = { step: b.label, ...p }" @mouseleave="hover = null" />
        <span class="n">{{ f(b.lines) }}</span>
      </div>
    </div>
    <div class="legend"><span v-for="r in ROLES" :key="r.id"><i :style="{ background: r.color }" />{{ r.label }}</span></div>
    <div class="tip">
      <template v-if="hover"><b>{{ hover.step }} · {{ hover.label }}</b> ({{ f(hover.lines) }} lines): {{ hover.mods.join(', ') }}</template>
      <template v-else>hover a bar to see its modules</template>
    </div>
  </div>
</template>

<style scoped>
.cm { font-size: 13px; }
.totals { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 10px; }
.totals > div { background: #f4f3f0; border-radius: 8px; padding: 5px 8px; text-align: center; font-size: 12px; }
.totals b { display: block; font-size: 20px; }
.row { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
.lab { width: 118px; text-align: right; font-size: 12.5px; }
.bar { flex: 1; display: flex; align-items: center; gap: 2px; height: 24px; }
.seg { height: 100%; border-radius: 3px; cursor: pointer; }
.n { margin-left: 6px; font-size: 12px; color: #52514e; font-variant-numeric: tabular-nums; }
.legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11.5px; color: #52514e; margin: 6px 0 0 126px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
.tip { margin: 8px 0 0 126px; font-size: 12px; color: #52514e; min-height: 34px; line-height: 1.4; }
</style>
