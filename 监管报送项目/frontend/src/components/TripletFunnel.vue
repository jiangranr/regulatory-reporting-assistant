<template>
  <div class="funnel">
    <div class="funnel-head">
      <div>
        <div class="funnel-eyebrow">三路信号源融合扫描</div>
        <h3 class="funnel-title">{{ headline }}</h3>
        <div class="funnel-sub">
          AI 不是唯一信号源 · 修订对照表 &gt; Excel 结构差异 &gt; 填报说明扫描，按优先级合并去重
        </div>
      </div>
      <div class="funnel-final">
        <div class="final-num">{{ mergedCount }}</div>
        <div class="final-label">指标格命中（合并后）</div>
      </div>
    </div>

    <!-- 三路 SVG 漏斗 -->
    <svg :viewBox="`0 0 ${W} ${H}`" class="funnel-svg" preserveAspectRatio="xMidYMid meet">
      <!-- 三个色条 -->
      <g v-for="(lane, i) in lanes" :key="lane.key">
        <!-- 未提供：虚线轮廓 + 灰底 -->
        <rect
          v-if="lane.count === 0"
          :x="laneX(i)"
          :y="50"
          :width="laneW"
          :height="60"
          fill="#f1f5f9"
          stroke="#cbd5e1"
          stroke-dasharray="5 4"
          stroke-width="1.5"
          rx="6"
        />
        <text
          v-if="lane.count === 0"
          :x="laneX(i) + laneW / 2"
          :y="86"
          text-anchor="middle"
          class="lane-empty"
        >
          未提供此信号源
        </text>
        <!-- 有数据：实色条 -->
        <rect
          v-else
          :x="laneX(i)"
          :y="50"
          :width="laneW"
          :height="laneBarH(lane.count)"
          :fill="lane.color"
          rx="6"
          opacity="0.85"
        />
        <text :x="laneX(i) + laneW / 2" :y="40" text-anchor="middle" class="lane-title">
          {{ lane.title }}
        </text>
        <text
          v-if="lane.count > 0"
          :x="laneX(i) + laneW / 2"
          :y="65"
          text-anchor="middle"
          class="lane-prio"
          fill="#fff"
        >
          ★{{ '★'.repeat(lane.priority - 1) }} 优先级
        </text>
        <text
          v-if="lane.count > 0"
          :x="laneX(i) + laneW / 2"
          :y="50 + laneBarH(lane.count) + 22"
          text-anchor="middle"
          class="lane-count"
          :fill="lane.color"
        >
          {{ lane.count }} 条
        </text>
        <text
          v-if="lane.count > 0"
          :x="laneX(i) + laneW / 2"
          :y="50 + laneBarH(lane.count) + 38"
          text-anchor="middle"
          class="lane-sub"
        >
          采纳 {{ lane.wonCount }} · 覆盖 {{ lane.count - lane.wonCount }}
        </text>

        <!-- 流线汇到漏斗（仅有数据时画） -->
        <path
          v-if="lane.count > 0"
          :d="`M ${laneX(i) + laneW / 2} ${50 + laneBarH(lane.count) + 44} C ${laneX(i) + laneW / 2} ${funnelY - 30}, ${funnelX} ${funnelY - 30}, ${funnelX} ${funnelY}`"
          :stroke="lane.color"
          stroke-width="2"
          fill="none"
          stroke-dasharray="6 4"
          opacity="0.75"
        >
          <animate
            attributeName="stroke-dashoffset"
            from="40"
            to="0"
            dur="1.2s"
            repeatCount="indefinite"
          />
        </path>
      </g>

      <!-- 漏斗节点 -->
      <circle :cx="funnelX" :cy="funnelY" r="32" fill="#0f172a" />
      <circle :cx="funnelX" :cy="funnelY" r="32" fill="none" stroke="#fbbf24" stroke-width="2">
        <animate attributeName="r" from="32" to="38" dur="1.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" from="0.9" to="0" dur="1.6s" repeatCount="indefinite" />
      </circle>
      <text :x="funnelX" :y="funnelY - 4" text-anchor="middle" class="merge-label" fill="#fff">
        去重合并
      </text>
      <text :x="funnelX" :y="funnelY + 10" text-anchor="middle" class="merge-sub" fill="#94a3b8">
        高优先级覆盖
      </text>
    </svg>

    <!-- 明细 -->
    <div class="merge-detail">
      <div class="detail-head">
        <span>合并后明细（{{ mergedCount }} 条）</span>
        <span class="legend">
          <span class="legend-item"><i class="dot blue"></i>修订表</span>
          <span class="legend-item"><i class="dot amber"></i>Excel 差异</span>
          <span class="legend-item"><i class="dot green"></i>填报说明</span>
          <span class="legend-item warn">⚠ 信号冲突</span>
        </span>
      </div>
      <table class="merge-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>变更类型</th>
            <th>胜出来源</th>
            <th>置信度</th>
            <th>覆盖关系</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in mergedRows" :key="r.item_code">
            <td>
              <div class="cell-title">{{ r.row_label || r.item_code }}</div>
              <div class="cell-sub mono">{{ r.item_code }} · {{ r.column_label }}</div>
            </td>
            <td>
              <span :class="['ct-tag', changeTypeClass(r.new_status)]">{{
                changeTypeLabel(r.new_status)
              }}</span>
            </td>
            <td>
              <span :class="['src-tag', sourceClass(r.source)]">
                <i class="dot" :class="sourceDotClass(r.source)"></i>
                {{ sourceLabel(r.source) }}
              </span>
            </td>
            <td>
              <div class="conf-bar">
                <div class="conf-fill" :style="{ width: Math.round(r.confidence * 100) + '%' }" />
                <span class="conf-num">{{ Math.round(r.confidence * 100) }}%</span>
              </div>
            </td>
            <td>
              <span v-if="r.overridden_sources.length" class="override-tag">
                ⚠ 覆盖 {{ r.overridden_sources.map(sourceLabel).join(' / ') }}
              </span>
              <span v-else class="override-tag none">单源命中</span>
            </td>
          </tr>
          <tr v-if="!mergedRows.length">
            <td colspan="5" class="empty">暂无扫描结果</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ItemChangeScanResult, LaneSignal, LaneSource } from '@/types/api'

const props = defineProps<{
  scanResults: ItemChangeScanResult[]
  revisionLane: LaneSignal[]
  excelLane: LaneSignal[]
  instructionLane: LaneSignal[]
  scanSummary?: string
}>()

const W = 720
const H = 280
const laneW = 160
const laneGap = 60
const funnelX = W / 2
const funnelY = 230

const lanes = computed(() => [
  {
    key: 'REVISION_TABLE' as LaneSource,
    title: '修订对照表',
    color: '#2563eb',
    priority: 3,
    count: props.revisionLane.length,
    wonCount: props.revisionLane.filter((s) => s.won).length,
  },
  {
    key: 'EXCEL_DIFF' as LaneSource,
    title: 'Excel 结构差异',
    color: '#d97706',
    priority: 2,
    count: props.excelLane.length,
    wonCount: props.excelLane.filter((s) => s.won).length,
  },
  {
    key: 'INSTRUCTION' as LaneSource,
    title: '填报说明扫描',
    color: '#16a34a',
    priority: 1,
    count: props.instructionLane.length,
    wonCount: props.instructionLane.filter((s) => s.won).length,
  },
])

const maxLaneCount = computed(() =>
  Math.max(1, ...lanes.value.map((l) => l.count)),
)

const laneBarH = (count: number) => {
  const max = 80
  const min = 8
  return min + (max - min) * (count / maxLaneCount.value)
}

const laneX = (i: number) => {
  const totalW = laneW * 3 + laneGap * 2
  const startX = (W - totalW) / 2
  return startX + i * (laneW + laneGap)
}

const mergedCount = computed(() => props.scanResults.length)
const providedLaneCount = computed(() => lanes.value.filter((l) => l.count > 0).length)
const headline = computed(() => {
  const base = props.scanSummary || `合并后命中 ${mergedCount.value} 个指标格`
  if (providedLaneCount.value === 3) return base
  if (providedLaneCount.value === 0) return base
  return `${base} · 当前仅 ${providedLaneCount.value}/3 路信号源已提供`
})
const mergedRows = computed(() =>
  [...props.scanResults].sort((a, b) => b.confidence - a.confidence),
)

const sourceLabel = (src: LaneSource): string =>
  ({
    REVISION_TABLE: '修订对照表',
    EXCEL_DIFF: 'Excel 差异',
    INSTRUCTION: '填报说明',
  })[src] || src
const sourceClass = (src: LaneSource): string =>
  ({ REVISION_TABLE: 'blue', EXCEL_DIFF: 'amber', INSTRUCTION: 'green' })[src] || ''
const sourceDotClass = (src: LaneSource): string =>
  ({ REVISION_TABLE: 'blue', EXCEL_DIFF: 'amber', INSTRUCTION: 'green' })[src] || ''

const changeTypeLabel = (t: string): string =>
  ({ NEW: '新增', MODIFIED: '修改', DELETED: '删除', UNCHANGED: '无变化' })[t] || t
const changeTypeClass = (t: string): string =>
  ({ NEW: 'green', MODIFIED: 'amber', DELETED: 'red', UNCHANGED: '' })[t] || ''
</script>

<style scoped>
.funnel {
  border: 1px solid var(--ink-200, #e2e8f0);
  border-radius: 12px;
  background: linear-gradient(180deg, #fafbfc 0%, #fff 50%);
  padding: 20px 24px;
}
.funnel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.funnel-eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--ink-500, #64748b);
  font-weight: 600;
}
.funnel-title {
  font-size: 18px;
  margin: 4px 0 4px;
  color: var(--ink-900, #0f172a);
}
.funnel-sub {
  font-size: 12px;
  color: var(--ink-500, #64748b);
  max-width: 540px;
}
.funnel-final {
  text-align: right;
  padding: 10px 16px;
  background: #0f172a;
  color: #fff;
  border-radius: 10px;
  min-width: 140px;
}
.final-num {
  font-size: 28px;
  font-weight: 700;
  color: #fbbf24;
  line-height: 1.1;
}
.final-label {
  font-size: 11px;
  color: #cbd5e1;
  margin-top: 2px;
}

.funnel-svg {
  width: 100%;
  height: 280px;
  margin-top: 8px;
}
.lane-title {
  font-size: 12px;
  font-weight: 600;
  fill: var(--ink-700, #334155);
}
.lane-prio {
  font-size: 9px;
}
.lane-count {
  font-size: 14px;
  font-weight: 700;
}
.lane-sub {
  font-size: 10px;
  fill: var(--ink-500, #64748b);
}
.lane-empty {
  font-size: 11px;
  fill: var(--ink-400, #94a3b8);
}
.merge-label {
  font-size: 10px;
  font-weight: 600;
}
.merge-sub {
  font-size: 8px;
}

.merge-detail {
  margin-top: 12px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--ink-700, #334155);
  font-weight: 600;
  margin-bottom: 8px;
}
.legend {
  display: flex;
  gap: 12px;
  font-weight: 400;
  font-size: 11px;
  color: var(--ink-500, #64748b);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.legend-item.warn {
  color: #b45309;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot.blue { background: #2563eb; }
.dot.amber { background: #d97706; }
.dot.green { background: #16a34a; }

.merge-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.merge-table th {
  text-align: left;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  color: var(--ink-500, #64748b);
  border-bottom: 1px solid var(--ink-200, #e2e8f0);
  padding: 6px 8px;
}
.merge-table td {
  padding: 8px;
  border-bottom: 1px solid var(--ink-100, #f1f5f9);
  vertical-align: middle;
}
.cell-title {
  font-weight: 500;
  color: var(--ink-900, #0f172a);
}
.cell-sub {
  font-size: 11px;
  color: var(--ink-400, #94a3b8);
  margin-top: 2px;
}
.mono { font-family: ui-monospace, SFMono-Regular, monospace; }

.ct-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  background: #f1f5f9;
  color: var(--ink-700, #334155);
}
.ct-tag.green { background: #dcfce7; color: #166534; }
.ct-tag.amber { background: #fef3c7; color: #92400e; }
.ct-tag.red   { background: #fee2e2; color: #991b1b; }

.src-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  background: #f8fafc;
  color: var(--ink-700, #334155);
  border: 1px solid var(--ink-200, #e2e8f0);
}
.src-tag.blue  { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
.src-tag.amber { background: #fffbeb; color: #92400e; border-color: #fde68a; }
.src-tag.green { background: #ecfdf5; color: #166534; border-color: #bbf7d0; }

.conf-bar {
  position: relative;
  width: 110px;
  height: 14px;
  background: #f1f5f9;
  border-radius: 6px;
  overflow: hidden;
}
.conf-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, #fbbf24, #16a34a);
}
.conf-num {
  position: relative;
  z-index: 1;
  display: block;
  text-align: center;
  font-size: 10px;
  line-height: 14px;
  color: #0f172a;
  font-weight: 600;
}
.override-tag {
  font-size: 11px;
  color: #b45309;
  background: #fffbeb;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid #fde68a;
}
.override-tag.none {
  color: var(--ink-400, #94a3b8);
  background: transparent;
  border-color: transparent;
}
.empty {
  text-align: center;
  color: var(--ink-400, #94a3b8);
  padding: 18px;
}
</style>
