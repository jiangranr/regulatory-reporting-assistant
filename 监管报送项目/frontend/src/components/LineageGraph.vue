<template>
  <div :class="['lg', { expanded: expandedView }]">
    <div class="lg-head">
      <div class="lg-cols">
        <div v-for="c in columnTitles" :key="c.key" class="lg-col">
          <span class="lg-col-title">{{ c.title }}</span>
          <span class="lg-col-sub">{{ c.sub }}</span>
        </div>
      </div>
      <div class="lg-legend">
        <span><i class="dot blue"></i>已确认</span>
        <span><i class="dot amber"></i>待审核</span>
        <span><i class="dot red"></i>未映射</span>
        <span class="pulse"><i class="dot pulse-dot"></i>变更命中</span>
      </div>
      <div class="lg-tools" aria-label="血缘图缩放工具">
        <button class="lg-tool" type="button" title="缩小" @click="zoomOut">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="8" y1="11" x2="14" y2="11"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </button>
        <span class="lg-zoom">{{ Math.round(zoom * 100) }}%</span>
        <button class="lg-tool" type="button" title="放大" @click="zoomIn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </button>
        <button class="lg-tool text" type="button" title="恢复默认大小" @click="resetZoom">重置</button>
        <button class="lg-tool text strong" type="button" :title="expandedView ? '退出大图' : '打开大图'" @click="toggleExpanded">
          {{ expandedView ? '退出' : '大图' }}
        </button>
      </div>
    </div>

    <div class="lg-canvas">
      <svg
        ref="svgEl"
        :viewBox="`0 0 ${W} ${H}`"
        preserveAspectRatio="xMidYMid meet"
        class="lg-svg"
        :style="{ width: `${W * zoom}px`, height: `${H * zoom}px` }"
      >
        <!-- 边 -->
        <g class="lg-edges">
          <g v-for="e in edges" :key="e.id">
            <path
              :d="edgePath(e)"
              :stroke="edgeColor(e)"
              :stroke-dasharray="e.status === 'DRAFT' ? '6 4' : ''"
              :stroke-width="isOnPath(e) ? 2.5 : 1.5"
              :opacity="dimEdge(e) ? 0.12 : 0.85"
              fill="none"
            />
            <g
              v-if="showEdgeLabel(e)"
              class="edge-label"
              :opacity="dimEdge(e) ? 0.1 : 0.92"
              :transform="`translate(${edgeLabelPos(e).x}, ${edgeLabelPos(e).y})`"
            >
              <rect
                :x="-edgeLabelWidth(e) / 2"
                y="-10"
                :width="edgeLabelWidth(e)"
                height="20"
                rx="10"
                :fill="edgeLabelBg(e)"
                stroke="#ffffff"
                stroke-width="1"
              />
              <text text-anchor="middle" y="4">{{ edgeLabel(e) }}</text>
            </g>
          </g>
        </g>
        <!-- 节点 -->
        <g class="lg-nodes">
          <g
            v-for="n in nodes"
            :key="n.id"
            :transform="`translate(${nx(n)}, ${ny(n)})`"
            :class="['lg-node', { dim: dimNode(n), active: n.id === activeNodeId }]"
            @click="onNodeClick(n)"
          >
            <rect
              :width="NW"
              :height="NH"
              rx="8"
              :fill="nodeBg(n)"
              :stroke="nodeBorder(n)"
              stroke-width="1.5"
            />
            <text :x="12" :y="22" class="n-title">{{ truncate(n.label, 14) }}</text>
            <text :x="12" :y="40" class="n-sub">{{ truncate(n.sublabel || '', 18) }}</text>
            <!-- 状态徽章 -->
            <circle :cx="NW - 14" :cy="14" r="5" :fill="statusFill(n.status)" />
            <!-- 变更命中脉冲 -->
            <g v-if="n.changed">
              <circle :cx="NW - 14" :cy="34" r="5" fill="#ef4444">
                <animate attributeName="r" from="5" to="9" dur="1.5s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="1" to="0" dur="1.5s" repeatCount="indefinite" />
              </circle>
              <circle :cx="NW - 14" :cy="34" r="5" fill="#ef4444" />
            </g>
          </g>
        </g>
      </svg>
    </div>

    <div v-if="hoverHint" class="lg-hint">{{ hoverHint }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

export interface LineageNode {
  id: string
  column: 0 | 1 | 2 | 3
  label: string
  sublabel?: string
  status: 'CONFIRMED' | 'DRAFT' | 'PENDING' | 'MISSING'
  changed?: boolean
}

export interface LineageEdge {
  id?: string
  from: string
  to: string
  status: 'CONFIRMED' | 'DRAFT' | 'PENDING' | 'MISSING'
  relation?: string
}

const props = defineProps<{
  nodes: LineageNode[]
  edges: LineageEdge[]
  activeNodeId?: string | null
}>()

const emit = defineEmits<{ 'select-node': [id: string] }>()

const svgEl = ref<SVGSVGElement | null>(null)
const zoom = ref(1)
const expandedView = ref(false)
const NW = 180
const NH = 56
const COL_W = 220
const PAD_X = 60
const PAD_TOP = 24
const ROW_GAP = 18
const W = PAD_X * 2 + COL_W * 4
const H = computed(() => {
  const maxCount = Math.max(
    1,
    ...[0, 1, 2, 3].map((c) => props.nodes.filter((n) => n.column === c).length),
  )
  return PAD_TOP * 2 + maxCount * (NH + ROW_GAP)
})

const columnTitles = [
  { key: 0, title: '报送指标', sub: 'item_code' },
  { key: 1, title: '报送字段', sub: 'REPORT_FIELD' },
  { key: 2, title: '源字段', sub: 'SOURCE_FIELD' },
  { key: 3, title: '维度/过滤', sub: 'FILTER · DIMENSION' },
]

const colNodes = (c: number) => props.nodes.filter((n) => n.column === c)
const nodeIndex = (n: LineageNode) => colNodes(n.column).findIndex((x) => x.id === n.id)

const nx = (n: LineageNode) => PAD_X + n.column * COL_W + (COL_W - NW) / 2
const ny = (n: LineageNode) => {
  const i = nodeIndex(n)
  const colCount = colNodes(n.column).length
  const totalH = colCount * (NH + ROW_GAP) - ROW_GAP
  const available = H.value - PAD_TOP * 2
  const startY = PAD_TOP + Math.max(0, (available - totalH) / 2)
  return startY + i * (NH + ROW_GAP)
}

const nodeById = computed(() => {
  const m = new Map<string, LineageNode>()
  for (const n of props.nodes) m.set(n.id, n)
  return m
})

const edgePath = (e: LineageEdge) => {
  const a = nodeById.value.get(e.from)
  const b = nodeById.value.get(e.to)
  if (!a || !b) return ''
  const x1 = nx(a) + NW
  const y1 = ny(a) + NH / 2
  const x2 = nx(b)
  const y2 = ny(b) + NH / 2
  const c1 = x1 + 80
  const c2 = x2 - 80
  return `M ${x1},${y1} C ${c1},${y1} ${c2},${y2} ${x2},${y2}`
}

const edgeLabelPos = (e: LineageEdge) => {
  const a = nodeById.value.get(e.from)
  const b = nodeById.value.get(e.to)
  if (!a || !b) return { x: 0, y: 0 }
  const x1 = nx(a) + NW
  const y1 = ny(a) + NH / 2
  const x2 = nx(b)
  const y2 = ny(b) + NH / 2
  return { x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 8 }
}

const edgeLabel = (e: LineageEdge): string => {
  if (e.relation) return e.relation
  const a = nodeById.value.get(e.from)
  const b = nodeById.value.get(e.to)
  if (!a || !b) return '关联'
  if (a.column === 0 && b.column === 1) return '报送映射'
  if (a.column <= 1 && b.column === 2) return '来源血缘'
  if (b.column === 3) return '维度过滤'
  return '字段血缘'
}

const edgeLabelWidth = (e: LineageEdge) => Math.max(58, edgeLabel(e).length * 12 + 18)

const edgeLabelBg = (e: LineageEdge): string => {
  if (e.status === 'CONFIRMED') return '#eff6ff'
  if (e.status === 'MISSING') return '#fef2f2'
  return '#fff7ed'
}

const showEdgeLabel = (e: LineageEdge) => {
  if (!props.activeNodeId) return true
  return isOnPath(e)
}

const edgeColor = (e: LineageEdge): string => {
  const c = {
    CONFIRMED: '#2563eb',
    DRAFT: '#d97706',
    PENDING: '#d97706',
    MISSING: '#dc2626',
  } as const
  return c[e.status] || '#94a3b8'
}

const statusFill = (s: LineageNode['status']) =>
  ({
    CONFIRMED: '#16a34a',
    DRAFT: '#d97706',
    PENDING: '#d97706',
    MISSING: '#dc2626',
  })[s] || '#94a3b8'

const nodeBg = (n: LineageNode) => {
  if (n.id === props.activeNodeId) return '#fff7ed'
  if (n.changed) return '#fef2f2'
  return '#ffffff'
}

const nodeBorder = (n: LineageNode) => {
  if (n.id === props.activeNodeId) return '#f97316'
  if (n.changed) return '#fca5a5'
  return '#e2e8f0'
}

// 上下游路径计算
const pathNodes = computed<Set<string>>(() => {
  const set = new Set<string>()
  const active = props.activeNodeId
  if (!active) return set
  set.add(active)
  // 上游：edge.to == 当前
  const upstream = new Set<string>([active])
  let frontier = [active]
  while (frontier.length) {
    const next: string[] = []
    for (const cur of frontier) {
      for (const e of props.edges) {
        if (e.to === cur && !upstream.has(e.from)) {
          upstream.add(e.from)
          next.push(e.from)
        }
      }
    }
    frontier = next
  }
  // 下游
  const downstream = new Set<string>([active])
  frontier = [active]
  while (frontier.length) {
    const next: string[] = []
    for (const cur of frontier) {
      for (const e of props.edges) {
        if (e.from === cur && !downstream.has(e.to)) {
          downstream.add(e.to)
          next.push(e.to)
        }
      }
    }
    frontier = next
  }
  for (const id of upstream) set.add(id)
  for (const id of downstream) set.add(id)
  return set
})

const dimNode = (n: LineageNode) => {
  if (!props.activeNodeId) return false
  return !pathNodes.value.has(n.id)
}
const dimEdge = (e: LineageEdge) => {
  if (!props.activeNodeId) return false
  return !(pathNodes.value.has(e.from) && pathNodes.value.has(e.to))
}
const isOnPath = (e: LineageEdge) =>
  !!props.activeNodeId && pathNodes.value.has(e.from) && pathNodes.value.has(e.to)

const onNodeClick = (n: LineageNode) => {
  emit('select-node', n.id)
}

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

const zoomIn = () => {
  zoom.value = Math.min(2, Number((zoom.value + 0.15).toFixed(2)))
}

const zoomOut = () => {
  zoom.value = Math.max(0.7, Number((zoom.value - 0.15).toFixed(2)))
}

const resetZoom = () => {
  zoom.value = 1
}

const toggleExpanded = () => {
  expandedView.value = !expandedView.value
  if (expandedView.value && zoom.value < 1.15) zoom.value = 1.15
}

const hoverHint = computed(() => {
  if (!props.activeNodeId) return '点击节点查看上下游血缘 · 红色脉冲表示本次变更命中'
  const n = nodeById.value.get(props.activeNodeId)
  if (!n) return ''
  const upCount = Array.from(pathNodes.value).length - 1
  return `已高亮 ${n.label} 的上下游 ${upCount} 个节点；再次点击该节点取消高亮`
})
</script>

<style scoped>
.lg {
  border: 1px solid var(--ink-200, #e2e8f0);
  border-radius: 12px;
  background: #fff;
  padding: 12px 12px 16px;
}
.lg.expanded {
  position: fixed;
  inset: 18px;
  z-index: 80;
  display: flex;
  flex-direction: column;
  border-color: rgba(249, 115, 22, 0.45);
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.22);
}
.lg-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 8px;
}
.lg-cols {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  flex: 1;
  text-align: center;
  border-bottom: 1px dashed var(--ink-200, #e2e8f0);
  padding-bottom: 6px;
}
.lg-col-title {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-700, #334155);
}
.lg-col-sub {
  display: block;
  font-size: 10px;
  color: var(--ink-400, #94a3b8);
  font-family: ui-monospace, SFMono-Regular, monospace;
  margin-top: 2px;
}
.lg-legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--ink-500, #64748b);
  align-items: center;
  flex-wrap: wrap;
}
.lg-legend .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
}
.lg-legend .blue { background: #2563eb; }
.lg-legend .amber { background: #d97706; }
.lg-legend .red { background: #dc2626; }
.pulse-dot { background: #ef4444; }
.lg-tools {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px;
  border: 1px solid var(--ink-200, #e2e8f0);
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
}
.lg-tool {
  width: 28px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-600, #475569);
  cursor: pointer;
  font: inherit;
}
.lg-tool:hover {
  background: var(--orange-50, #fff7ed);
  color: var(--orange-700, #c2410c);
}
.lg-tool svg {
  width: 15px;
  height: 15px;
}
.lg-tool.text {
  width: auto;
  padding: 0 9px;
  font-size: 12px;
  white-space: nowrap;
}
.lg-tool.strong {
  color: var(--orange-700, #c2410c);
  font-weight: 600;
}
.lg-zoom {
  min-width: 42px;
  text-align: center;
  font-size: 11px;
  color: var(--ink-500, #64748b);
  font-family: ui-monospace, SFMono-Regular, monospace;
}
.lg-canvas {
  width: 100%;
  overflow: auto;
  border-radius: 10px;
  overscroll-behavior: contain;
}
.lg.expanded .lg-canvas {
  flex: 1;
}
.lg-svg {
  display: block;
  min-width: 100%;
  max-height: 480px;
  margin: 0 auto;
}
.lg.expanded .lg-svg {
  max-height: none;
  margin: 0;
}
.lg-node { cursor: pointer; transition: opacity 0.2s; }
.lg-node.dim { opacity: 0.25; }
.edge-label {
  pointer-events: none;
}
.edge-label text {
  font-size: 10px;
  font-weight: 600;
  fill: var(--ink-600, #475569);
}
.n-title {
  font-size: 12px;
  font-weight: 600;
  fill: var(--ink-900, #0f172a);
}
.n-sub {
  font-size: 10px;
  fill: var(--ink-500, #64748b);
  font-family: ui-monospace, SFMono-Regular, monospace;
}
.lg-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--ink-500, #64748b);
  text-align: center;
}

@media (max-width: 900px) {
  .lg-head {
    flex-direction: column;
  }
  .lg-tools {
    align-self: flex-end;
  }
}
</style>
