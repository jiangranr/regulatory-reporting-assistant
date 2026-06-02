<template>
  <div class="rlg">
    <!-- 图例 -->
    <div class="rlg-legend">
      <span><i class="d" style="background:#16a34a" />已确认</span>
      <span><i class="d" style="background:#2563eb" />种子确认</span>
      <span><i class="d" style="background:#d97706" />待审核</span>
      <span><i class="d" style="background:#dc2626" />未映射</span>
      <span class="rlg-flow">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        监管指标依赖源字段
      </span>
    </div>

    <!-- SVG 图 -->
    <div class="rlg-canvas">
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        class="rlg-svg"
        :style="{ width: `${W}px`, height: `${H}px` }"
      >
        <defs>
          <marker id="rlg-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3"
            orient="auto" markerUnits="userSpaceOnUse">
            <path d="M0,0 L7,3 L0,6 z" fill="#94a3b8" />
          </marker>
        </defs>

        <!-- 列底纹 + 列标题 -->
        <g v-for="(col, c) in COL_TITLES" :key="c">
          <rect
            :x="PAD_X + c * COL_W + 5" :y="PAD_TOP - 12"
            :width="COL_W - 10" :height="H - PAD_TOP - PAD_BOT + 18"
            rx="12"
            :fill="c === 3 ? 'rgba(234,84,4,0.05)' : 'transparent'"
            :stroke="c === 3 ? 'rgba(234,84,4,0.18)' : 'transparent'"
            stroke-dasharray="4 4"
          />
          <text :x="colCenter(c)" :y="22" text-anchor="middle" :class="['rlg-ct', { anchor: c === 3 }]">{{ col.title }}</text>
          <text :x="colCenter(c)" :y="37" text-anchor="middle" class="rlg-cs">{{ col.sub }}</text>
        </g>

        <!-- 边 -->
        <g>
          <path
            v-for="(e, i) in graph.edges" :key="i"
            :d="edgePath(e)"
            fill="none"
            marker-end="url(#rlg-arrow)"
            :stroke="edgeColor(e.status)"
            :stroke-width="isHighlightedEdge(e) ? 2.5 : 1.5"
            :stroke-dasharray="e.status === 'DRAFT' ? '6 4' : ''"
            :opacity="dimEdge(e) ? 0.1 : 0.85"
          />
        </g>

        <!-- 节点 -->
        <g>
          <g
            v-for="n in graph.nodes" :key="n.id"
            :transform="`translate(${nx(n)}, ${ny(n)})`"
            :class="['rlg-node', { dim: dimNode(n), clickable: n.column === 0 }]"
            @mouseenter="n.column === 0 && $emit('hover', n.id)"
            @mouseleave="n.column === 0 && $emit('hover', null)"
          >
            <rect
              :width="NW" :height="NH" rx="9"
              :fill="n.changed ? '#FFF6EF' : '#ffffff'"
              :stroke="n.changed ? '#EA5404' : '#ECE5DC'"
              :stroke-width="n.changed ? 1.6 : 1.3"
            />
            <text :x="12" :y="21" class="rn-t">{{ trunc(n.label, 12) }}</text>
            <text :x="12" :y="38" class="rn-s">{{ trunc(n.sublabel || '', 20) }}</text>
            <!-- 状态圆点 -->
            <circle :cx="NW - 13" :cy="14" r="5" :fill="statusFill(n.status)" />
            <!-- 变更脉冲 -->
            <g v-if="n.changed">
              <circle :cx="NW - 13" :cy="36" r="5" fill="#EA5404">
                <animate attributeName="r" from="5" to="9" dur="1.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="0.9" to="0" dur="1.6s" repeatCount="indefinite" />
              </circle>
              <circle :cx="NW - 13" :cy="36" r="5" fill="#EA5404" />
            </g>
          </g>
        </g>
      </svg>
    </div>

    <div class="rlg-hint">
      {{ props.highlight
        ? '已高亮该监管指标回溯到本源字段的依赖链路'
        : '悬停右侧「依赖指标」列表，高亮其回溯到本字段的依赖链路 · 红色脉冲为本次变更命中' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { SourceFieldDependency } from '@/types/api';

// ── props / emits ─────────────────────────────────────────────
const props = defineProps<{
  fieldCode: string;
  fieldName: string;
  dependencies: SourceFieldDependency[];
  highlight: string | null;
}>();

defineEmits<{ hover: [id: string | null] }>();

// ── 布局常量（与 LineageGraph.vue 对齐） ─────────────────────
const NW = 166, NH = 52;
const COL_W = 198, PAD_X = 20, PAD_TOP = 56, PAD_BOT = 18, ROW_GAP = 18;

const COL_TITLES = [
  { title: '监管指标', sub: 'item_code' },
  { title: '报送字段', sub: 'REPORT_FIELD' },
  { title: '加工 / 汇总', sub: 'DM · ETL' },
  { title: '源字段', sub: 'SOURCE_FIELD' },
];

// ── 图数据构建 ────────────────────────────────────────────────
interface GraphNode {
  id: string;
  column: 0 | 1 | 2 | 3;
  label: string;
  sublabel: string;
  status: string;
  changed?: boolean;
}
interface GraphEdge {
  from: string;
  to: string;
  status: string;
}

const graph = computed(() => {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  // col3 — 源字段锚点（当前字段，始终有脉冲）
  const SRC = 'src';
  nodes.push({
    id: SRC, column: 3,
    label: props.fieldName,
    sublabel: props.fieldCode,
    status: 'CONFIRMED',
    changed: true,
  });

  // 每个依赖生成一个报送字段节点 (col1) + 一个指标节点 (col0)
  // col2（加工/汇总）暂时不展示，可后续接入 transform_expression
  props.dependencies.forEach((dep, i) => {
    const fId = `f${i}`;
    const iId = `i${i}`;

    // 报送字段节点（col1）
    nodes.push({
      id: fId, column: 1,
      label: dep.lineage_role === 'REPORT_FIELD' ? '报送字段' : dep.lineage_role === 'FILTER_FIELD' ? '过滤条件' : dep.lineage_role === 'DIMENSION_FIELD' ? '维度字段' : '来源字段',
      sublabel: dep.reporting_item_code,
      status: dep.mapping_status,
    });

    // 监管指标节点（col0）
    nodes.push({
      id: iId, column: 0,
      label: dep.reporting_object_code,
      sublabel: dep.reporting_item_code,
      status: dep.mapping_status,
      changed: dep.mapping_status === 'CONFIRMED' && dep.confidence_level === 'HIGH',
    });

    // 边：源字段 → 报送字段（从右到左，但 edgePath 会处理方向）
    edges.push({ from: SRC, to: fId, status: dep.mapping_status });
    edges.push({ from: fId, to: iId, status: dep.mapping_status });
  });

  return { nodes, edges };
});

// ── 尺寸计算 ─────────────────────────────────────────────────
const W = computed(() => PAD_X * 2 + COL_W * 4);
const H = computed(() => {
  const maxCount = Math.max(1, ...[0, 1, 2, 3].map((c) => graph.value.nodes.filter((n) => n.column === c).length));
  return PAD_TOP + maxCount * (NH + ROW_GAP) - ROW_GAP + PAD_BOT;
});

const colCenter = (c: number) => PAD_X + c * COL_W + COL_W / 2;

const colNodes = (c: number) => graph.value.nodes.filter((n) => n.column === c);

const nx = (n: GraphNode) => PAD_X + n.column * COL_W + (COL_W - NW) / 2;
const ny = (n: GraphNode) => {
  const list = colNodes(n.column);
  const i = list.findIndex((x) => x.id === n.id);
  const totalH = list.length * (NH + ROW_GAP) - ROW_GAP;
  const available = H.value - PAD_TOP - PAD_BOT;
  const startY = PAD_TOP + Math.max(0, (available - totalH) / 2);
  return startY + i * (NH + ROW_GAP);
};

const byId = computed(() => {
  const m: Record<string, GraphNode> = {};
  graph.value.nodes.forEach((n) => (m[n.id] = n));
  return m;
});

// ── 边路径（源端在右，消费端在左，箭头向左） ────────────────
function edgePath(e: GraphEdge): string {
  const a = byId.value[e.from], b = byId.value[e.to];
  if (!a || !b) return '';
  // 较高列（col数字大）= 源侧；较低列 = 指标侧
  const right = a.column > b.column ? a : b;
  const left  = a.column > b.column ? b : a;
  const xs = nx(right),      ys = ny(right) + NH / 2;   // 右节点左边缘
  const xe = nx(left) + NW,  ye = ny(left) + NH / 2;    // 左节点右边缘
  const c1 = xs - 76, c2 = xe + 76;
  return `M ${xs},${ys} C ${c1},${ys} ${c2},${ye} ${xe},${ye}`;
}

// ── 高亮路径（反向 BFS：从指标节点往上游找） ────────────────
const pathSet = computed<Set<string> | null>(() => {
  if (!props.highlight) return null;
  const set = new Set<string>([props.highlight]);
  let frontier = [props.highlight];
  while (frontier.length) {
    const next: string[] = [];
    for (const cur of frontier) {
      for (const e of graph.value.edges) {
        if (e.to === cur && !set.has(e.from)) { set.add(e.from); next.push(e.from); }
      }
    }
    frontier = next;
  }
  return set;
});

const dimNode = (n: GraphNode) => pathSet.value !== null && !pathSet.value.has(n.id);
const dimEdge = (e: GraphEdge) => pathSet.value !== null && !(pathSet.value.has(e.from) && pathSet.value.has(e.to));
const isHighlightedEdge = (e: GraphEdge) => pathSet.value !== null && pathSet.value.has(e.from) && pathSet.value.has(e.to);

// ── 样式工具 ──────────────────────────────────────────────────
const STATUS_COLOR: Record<string, string> = {
  CONFIRMED: '#16a34a', SEED_CONFIRMED: '#2563eb',
  DRAFT: '#d97706', PENDING: '#d97706', MISSING: '#dc2626',
};
const statusFill = (s: string) => STATUS_COLOR[s] ?? '#94a3b8';
const edgeColor  = (s: string) => STATUS_COLOR[s] ?? '#94a3b8';

const trunc = (s: string, n: number) => s && s.length > n ? s.slice(0, n - 1) + '…' : s;
</script>

<style scoped>
.rlg {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  padding: 12px 12px 14px;
}
.rlg-legend {
  display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
  font-size: 11px; color: var(--ink-500);
  padding: 2px 4px 10px;
  border-bottom: 1px dashed var(--border);
  margin-bottom: 6px;
}
.rlg-legend .d {
  width: 8px; height: 8px; border-radius: 50%;
  display: inline-block; margin-right: 4px;
}
.rlg-legend span { display: inline-flex; align-items: center; }
.rlg-flow {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--orange-600, #ea580c); font-weight: 600;
  margin-left: auto; padding-left: 12px; border-left: 1px solid var(--border);
}
.rlg-canvas {
  width: 100%; overflow-x: auto; overscroll-behavior-x: contain;
}
.rlg-canvas::-webkit-scrollbar { height: 7px; }
.rlg-canvas::-webkit-scrollbar-thumb { background: var(--ink-200); border-radius: 4px; }
.rlg-svg { display: block; }

.rlg-ct { font-size: 12px; font-weight: 600; fill: var(--ink-700); }
.rlg-ct.anchor { fill: var(--orange-600, #ea580c); }
.rlg-cs { font-size: 9.5px; fill: var(--ink-400); font-family: var(--font-mono, monospace); }

.rlg-node { transition: opacity .2s; }
.rlg-node.dim { opacity: 0.22; }
.rlg-node.clickable { cursor: pointer; }
.rn-t { font-size: 12px; font-weight: 600; fill: var(--ink-900); }
.rn-s { font-size: 10px; fill: var(--ink-500); font-family: var(--font-mono, monospace); }

.rlg-hint {
  margin-top: 8px; font-size: 11px;
  color: var(--ink-500); text-align: center;
}
</style>
