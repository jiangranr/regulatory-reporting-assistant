<template>
  <div>
    <div class="row between">
      <div>
        <div class="h-eyebrow">第 3 步</div>
        <h1 class="h-title">报表字段定位</h1>
        <p class="h-sub">将文档画像中的变更条款，定位到 1104 报表的具体行列项目、报送字段和源系统字段血缘。</p>
      </div>
      <div class="row">
        <button class="btn secondary" @click="$emit('back')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          画像
        </button>
        <button class="btn primary" @click="$emit('continue')">
          影响分析
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>

    <div class="lineage-layout mt-24">
      <!-- 左：报表目录树 -->
      <div>
        <div class="tree">
          <div class="tree-header">
            <span>1104 报表目录</span>
            <span class="mono" style="color:var(--orange-600);">{{ hitCount }} 命中</span>
          </div>
          <div v-for="table in catalog" :key="table.code">
            <div
              :class="['tree-node', { active: activeTable === table.code }]"
              @click="activeTable = table.code; activeItem = null"
            >
              <span class="chev">▾</span>
              <span>{{ table.code }} {{ table.name }}</span>
              <span v-if="table.items.length" class="hit">+{{ table.items.length }}</span>
            </div>
            <div class="tree-child">
              <div
                v-for="item in table.items"
                :key="item.code"
                :class="['tree-node', { active: activeItem === item.code }]"
                @click="activeTable = table.code; activeItem = item.code"
              >
                <span class="chev">·</span>
                <span>{{ item.code }} {{ item.displayName }}</span>
                <span v-if="item.changed" class="hit">!</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：血缘图 + 字段详情 -->
      <div class="field-detail">
        <!-- 血缘可视化 -->
        <LineageGraph
          v-if="lineageNodes.length"
          class="mb-12"
          :nodes="lineageNodes"
          :edges="lineageEdges"
          :active-node-id="activeGraphNodeId"
          @select-node="onSelectGraphNode"
        />

        <div v-if="activeSignal" class="card">
          <div class="card-head">
            <div>
              <div class="row" style="gap:6px;">
                <span class="tag outline mono">{{ activeSignal.table_code }}</span>
                <span :class="['tag', changeTypeColor(activeSignal.change_type)]">{{ changeTypeLabel(activeSignal.change_type) }}</span>
              </div>
              <h3 style="margin-top:8px;">{{ displayIndicatorName(activeSignal.indicator_hint) || activeSignal.table_code + " 变更项" }}</h3>
              <div class="sub">{{ activeSignal.section_hint || "相关填报说明变更" }}</div>
            </div>
          </div>

          <!-- 变更证据 -->
          <h4 style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink-500);font-weight:600;margin:8px 0 10px;">变更证据</h4>
          <div class="quote-list">
            <div class="quote" v-if="activeSignal.evidence_text">
              <span class="loc">原文摘录 · 置信度 {{ Math.round(activeSignal.confidence * 100) }}%</span>
              <span>{{ activeSignal.evidence_text }}</span>
            </div>
            <div class="quote" v-else>
              <span class="loc">暂无原文摘录</span>
              <span style="color:var(--ink-400);">请在文档画像步骤扫描后获取更详细的证据。</span>
            </div>
          </div>

          <!-- 语义候选命中 -->
          <div v-if="activeCompositeMatch" style="margin-top:20px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
              <h4 style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink-500);font-weight:600;margin:0;">{{ semanticMatchTitle }}</h4>
              <span class="tag amber">
                <span class="dot"></span>{{ mappingStatusLabel(activeCompositeMatch.review_status) }}
              </span>
            </div>
            <div class="quote-list">
              <div class="quote">
                <span class="loc">
                  {{ semanticMatchSummary }}
                  · 置信度 {{ Math.round(activeCompositeMatch.confidence * 100) }}%
                </span>
                <span>{{ semanticMatchDescription }}</span>
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
              <div>
                <h4 style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink-500);font-weight:600;margin:0 0 10px;">{{ semanticFieldsTitle }}</h4>
                <div class="quote-list">
                  <div v-for="field in activeCompositeMatch.measure_fields" :key="field.field_code" class="quote">
                    <span class="loc">{{ field.field_role }}</span>
                    <span>{{ field.field_name }}</span>
                    <span class="mono" style="font-size:11px;color:var(--ink-400);">{{ field.field_code }}</span>
                  </div>
                </div>
              </div>
              <div v-if="compositeConditions.length">
                <h4 style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink-500);font-weight:600;margin:0 0 10px;">过滤条件</h4>
                <div class="quote-list">
                  <div v-for="condition in compositeConditions" :key="condition.field_code + condition.value_code" class="quote">
                    <span class="loc">{{ condition.field_code }}</span>
                    <span>{{ condition.field_name }} {{ condition.operator }} {{ condition.value_name }}</span>
                    <span class="mono" style="font-size:11px;color:var(--ink-400);">{{ condition.value_code }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 字段映射 -->
          <div v-if="!activeCompositeMatch" style="display:flex;align-items:center;justify-content:space-between;margin:20px 0 10px;">
            <h4 style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink-500);font-weight:600;margin:0;">关联字段映射</h4>
            <span v-if="fieldMappings.length" style="font-size:12px;color:var(--ink-400);">{{ fieldMappings.length }} 条</span>
          </div>
          <table v-if="!activeCompositeMatch" class="tbl">
            <thead>
              <tr><th>报送指标</th><th>内部字段</th><th>源系统</th><th>角色</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="(m, i) in fieldMappings" :key="i">
                <td style="max-width:200px;">
                  <div style="font-size:12px;color:var(--ink-700);line-height:1.4;">{{ m.regulatory_term }}</div>
                  <div style="font-size:11px;color:var(--ink-400);font-family:monospace;margin-top:2px;">{{ m.item_code }}</div>
                </td>
                <td>
                  <div style="font-weight:500;">{{ m.field_name }}</div>
                  <div class="mono" style="font-size:11px;color:var(--ink-400);">{{ m.table_name }}.{{ m.column_name }}</div>
                </td>
                <td style="white-space:nowrap;">{{ m.system_name }}</td>
                <td>
                  <span :class="['tag', lineageRoleColor(m.lineage_role)]" style="font-size:11px;">
                    {{ lineageRoleLabel(m.lineage_role) }}
                  </span>
                </td>
                <td>
                  <span :class="['tag', mappingStatusColor(m.mapping_status)]">
                    <span class="dot"></span>{{ mappingStatusLabel(m.mapping_status) }}
                  </span>
                </td>
              </tr>
              <tr v-if="!fieldMappings.length">
                <td colspan="5" style="text-align:center;color:var(--ink-400);padding:16px;">暂无字段映射数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 无选中 -->
        <div class="card" v-else>
          <div style="text-align:center;padding:48px 0;color:var(--ink-400);">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px;height:40px;margin:0 auto 12px;display:block;opacity:.4;"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
            从左侧目录选择一个变更项查看定位证据
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { TaskWorkflow, TableChangeType } from "@/types/api";
import LineageGraph, { type LineageNode, type LineageEdge } from "@/components/LineageGraph.vue";

const props = defineProps<{
  workflow: TaskWorkflow | null;
  /** 外部传入要聚焦的指标 item_code（例如从影响分析「查看血缘」跳过来）。 */
  focusItemCode?: string | null;
}>();

defineEmits<{ continue: []; back: [] }>();

const activeTable = ref<string | null>(null);
const activeItem = ref<string | null>(null);
const activeGraphNodeId = ref<string | null>(null);

const tableNames: Record<string, string> = {
  G21: "流动性期限缺口统计表",
  G24: "最大百家金融机构同业融入情况表",
  G25: "流动性覆盖率和净稳定融资比例情况表",
  G27: "主要负债项目明细表",
  G31: "投资业务情况表",
};

// Build catalog from change_signals in profile
const catalog = computed(() => {
  const signals = props.workflow?.document_profile?.change_signals ?? [];
  const byTable = new Map<string, typeof signals>();
  for (const s of signals) {
    if (!byTable.has(s.table_code)) byTable.set(s.table_code, []);
    byTable.get(s.table_code)!.push(s);
  }
  return Array.from(byTable.entries()).map(([code, items]) => ({
    code,
    name: tableNames[code] ?? "",
    items: items.map((s, i) => ({
      code: `${code}.${i + 1}`,
      name: s.indicator_hint || s.section_hint || "变更项",
      displayName: displayIndicatorName(s.indicator_hint || s.section_hint || "变更项"),
      changed: true,
      signal: s,
    })),
  }));
});

const hitCount = computed(() => props.workflow?.document_profile?.change_signals.length ?? 0);

/**
 * 处理"从影响分析跳转过来"的聚焦请求。
 *
 * focusItemCode 形如 "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额"。
 * 本视图的 catalog 索引并不是 item_code，而是基于变更信号生成的 "${table}.${index}"，
 * 所以做多层定位：
 *   1. table_code 取前缀（"G31"），先选中报表
 *   2. 优先按 matched_item_code 精确匹配已落格信号
 *   3. 对组合命中按 composite_match.reporting_item_codes 匹配
 *   4. 最后用 item_code 末段关键字模糊匹配 signal.indicator_hint
 */
watch(
  [() => props.focusItemCode, catalog],
  ([code]) => {
    if (!code) return;
    const tableCode = code.split(".")[0];
    if (!tableCode) return;
    activeTable.value = tableCode;

    const table = catalog.value.find((t) => t.code === tableCode);
    if (!table) return;

    const exactHit = table.items.find((it) => it.signal.matched_item_code === code);
    if (exactHit) {
      activeItem.value = exactHit.code;
      return;
    }

    const compositeHit = table.items.find((it) =>
      it.signal.composite_match?.reporting_item_codes?.includes(code)
    );
    if (compositeHit) {
      activeItem.value = compositeHit.code;
      return;
    }

    // 提取最后一段作为关键字（例如 D 列的「因持有非底层资产而间接持有」）
    const tail = code.split(".").slice(-1)[0] || "";
    const keyword = tail.replace(/^[A-Z]_?/, "").replace(/_/g, "").slice(0, 12);
    if (!keyword) return;

    const norm = (s: string) => s.replace(/[-·_\s]/g, "");
    const k = norm(keyword);
    const hit = table.items.find((it) => norm(it.signal.indicator_hint || "").includes(k));
    if (hit) activeItem.value = hit.code;
  },
  { immediate: true },
);

const activeSignal = computed(() => {
  if (activeItem.value) {
    for (const t of catalog.value) {
      const found = t.items.find((i) => i.code === activeItem.value);
      if (found) return found.signal;
    }
  }
  if (activeTable.value) {
    const t = catalog.value.find((x) => x.code === activeTable.value);
    if (t?.items[0]) return t.items[0].signal;
  }
  // default to first signal
  return props.workflow?.document_profile?.change_signals[0] ?? null;
});

const activeCompositeMatch = computed(() => {
  const signal = activeSignal.value;
  if (
    (signal?.match_status === "COMPOSITE_SEMANTIC_MATCH" ||
      signal?.match_status === "SEMANTIC_FIELD_MATCH") &&
    signal.composite_match
  ) {
    return signal.composite_match;
  }
  return null;
});

const semanticMatchTitle = computed(() =>
  activeCompositeMatch.value?.match_type === "SEMANTIC_FIELD_MATCH" ? "语义字段命中" : "组合命中",
);

const semanticFieldsTitle = computed(() =>
  activeCompositeMatch.value?.match_type === "SEMANTIC_FIELD_MATCH" ? "关联字段" : "金额字段",
);

const semanticMatchSummary = computed(() => {
  const match = activeCompositeMatch.value;
  if (!match) return "";
  if (match.match_type === "SEMANTIC_FIELD_MATCH") return match.condition_phrase;
  return `${match.condition_phrase} + ${match.measure_phrase}`;
});

const semanticMatchDescription = computed(() =>
  activeCompositeMatch.value?.match_type === "SEMANTIC_FIELD_MATCH"
    ? "未精确落格，按报表范围内的维度/过滤字段生成语义字段候选，需人工确认。"
    : "未精确落格，按分类概念和度量概念生成组合候选，需人工确认。",
);

const compositeConditions = computed(() => {
  const match = activeCompositeMatch.value;
  return match?.filter_conditions ?? match?.conditions ?? [];
});

const fieldMappings = computed(() => {
  const all = props.workflow?.field_mappings ?? [];
  if (!all.length) return [];
  const signal = activeSignal.value;
  if (!signal) return all;
  if (activeCompositeMatch.value) return [];

  // 第一层过滤：按 table_code（报表代码）
  const byTable = all.filter((m) => m.object_code === signal.table_code);
  if (signal.matched_item_code) {
    const matched = byTable.filter((m) => m.item_code === signal.matched_item_code);
    if (matched.length) return matched;
  }
  if (signal.match_status?.startsWith("UNMATCHED_")) {
    return [];
  }

  // 第二层过滤：按画像信号中的业务行/列提示定位具体指标。
  // 兼容两类格式：
  // 1. "行名 × E_穿透后_期末余额"（修订对照表）
  // 2. "A. 穿透前-期末余额 / B. 投资收入"（LLM/说明型提示）
  if (activeItem.value && signal.indicator_hint) {
    const keywords = indicatorMatchKeywords(signal.indicator_hint);

    if (keywords.length) {
      // 归一化：去掉 -·_空格，再做包含匹配
      const norm = normaliseForMatch;
      const normKws = keywords.map(norm);
      const filtered = byTable.filter((m) =>
        normKws.some(
          (kw) =>
            norm(m.regulatory_term ?? "").includes(kw) ||
            norm(m.item_code ?? "").includes(kw) ||
            norm(m.field_name ?? "").includes(kw)
        )
      );
      if (filtered.length) return filtered;
    }
  }

  if (activeItem.value) {
    return [];
  }

  return byTable;
});

// ── 血缘图节点 / 边构造 ────────────────────────────────────────
function normStatus(s: string): LineageNode["status"] {
  if (s === "CONFIRMED") return "CONFIRMED";
  if (s === "MISSING") return "MISSING";
  return "DRAFT";
}

function roleToColumn(role: string): 1 | 2 | 3 {
  if (role === "REPORT_FIELD") return 1;
  if (role === "SOURCE_FIELD") return 2;
  return 3; // FILTER_FIELD / DIMENSION_FIELD
}

interface LineageGraphData {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

const lineageGraphData = computed<LineageGraphData>(() => {
  const signal = activeSignal.value;
  const composite = activeCompositeMatch.value;
  if (signal && composite) {
    const nodes: LineageNode[] = [
      {
        id: "item:composite",
        column: 0,
        label: displayIndicatorName(signal.indicator_hint) || "组合命中",
        sublabel: composite.pattern_code,
        status: "DRAFT",
        changed: true,
      },
    ];
    const edges: LineageEdge[] = [];
    for (const field of composite.measure_fields) {
      const id = `measure:${field.field_code}`;
      nodes.push({
        id,
        column: field.field_role === "REPORT_MEASURE_FIELD" ? 1 : 2,
        label: field.field_name,
        sublabel: field.field_code,
        status: "DRAFT",
        changed: false,
      });
      edges.push({
        id: `item:composite->${id}`,
        from: "item:composite",
        to: id,
        status: "DRAFT",
        relation: "金额字段",
      });
    }
    for (const condition of compositeConditions.value) {
      const id = `filter:${condition.field_code}:${condition.value_code}`;
      nodes.push({
        id,
        column: 3,
        label: `${condition.field_name}=${condition.value_name}`,
        sublabel: condition.field_code,
        status: "DRAFT",
        changed: false,
      });
      edges.push({
        id: `item:composite->${id}`,
        from: "item:composite",
        to: id,
        status: "DRAFT",
        relation: "过滤条件",
      });
    }
    return { nodes, edges };
  }
  const mappings = fieldMappings.value;
  if (!signal || !mappings.length) return { nodes: [], edges: [] };

  const nodes: LineageNode[] = [];
  const edges: LineageEdge[] = [];
  const seen = new Set<string>();
  const add = (n: LineageNode) => {
    if (seen.has(n.id)) return;
    seen.add(n.id);
    nodes.push(n);
  };

  // 指标节点（第 0 列）
  // 按 regulatory_term 聚合：同一指标可能多条 field_mapping
  const itemKeys = new Set<string>();
  for (const m of mappings) {
    itemKeys.add(m.item_code || m.regulatory_term || "ITEM");
  }
  for (const key of itemKeys) {
    const sample = mappings.find((m) => (m.item_code || m.regulatory_term) === key);
    add({
      id: `item:${key}`,
      column: 0,
      label: sample?.regulatory_term?.slice(0, 12) || key,
      sublabel: sample?.item_code || key,
      status: "CONFIRMED",
      changed: true,
    });
  }

  // 字段节点
  for (const m of mappings) {
    const itemId = `item:${m.item_code || m.regulatory_term}`;
    const col = roleToColumn(m.lineage_role);
    const fieldId = `f${col}:${m.system_name}.${m.table_name}.${m.column_name}`;
    add({
      id: fieldId,
      column: col,
      label: m.field_name || m.column_name,
      sublabel: `${m.table_name}.${m.column_name}`,
      status: normStatus(m.mapping_status || "DRAFT"),
      changed: false,
    });
    if (col === 1) {
      edges.push({
        id: `${itemId}->${fieldId}`,
        from: itemId,
        to: fieldId,
        status: normStatus(m.mapping_status || "DRAFT"),
        relation: "报送映射",
      });
    } else {
      // 找该指标的 REPORT_FIELD 作为上游；若没有则直接挂指标
      const reportUpstream = mappings.find(
        (x) =>
          (x.item_code || x.regulatory_term) === (m.item_code || m.regulatory_term) &&
          x.lineage_role === "REPORT_FIELD",
      );
      if (reportUpstream) {
        const upId = `f1:${reportUpstream.system_name}.${reportUpstream.table_name}.${reportUpstream.column_name}`;
        edges.push({
          id: `${upId}->${fieldId}`,
          from: upId,
          to: fieldId,
          status: normStatus(m.mapping_status || "DRAFT"),
          relation: col === 3 ? lineageRoleLabel(m.lineage_role) : "来源血缘",
        });
      } else {
        edges.push({
          id: `${itemId}->${fieldId}`,
          from: itemId,
          to: fieldId,
          status: normStatus(m.mapping_status || "DRAFT"),
          relation: col === 3 ? lineageRoleLabel(m.lineage_role) : "来源血缘",
        });
      }
    }
  }

  return { nodes, edges };
});

const lineageNodes = computed(() => lineageGraphData.value.nodes);
const lineageEdges = computed(() => lineageGraphData.value.edges);

function onSelectGraphNode(id: string) {
  activeGraphNodeId.value = activeGraphNodeId.value === id ? null : id;
}

function displayIndicatorName(raw = ""): string {
  if (!raw.trim()) return "";
  const parts = raw.split("×").map((part) => cleanBusinessLabel(part)).filter(Boolean);
  return parts.join(" × ");
}

function cleanBusinessLabel(raw = ""): string {
  return raw
    .trim()
    .replace(/^[（(]?[一二三四五六七八九十]+[）)]?[、.．]\s*/, "")
    .replace(/^\d+(?:\.\d+)*[、.．]?\s*/, "")
    .replace(/^[A-Z]_\s*/, "")
    .replace(/^[A-Z][.．、]\s*/, "")
    .replace(/_/g, "")
    .replace(/\s+/g, "");
}

function indicatorMatchKeywords(raw = ""): string[] {
  const keywords = raw
    .split(/\s*\/\s*|\s*×\s*/)
    .flatMap((part) => {
      const cleaned = cleanBusinessLabel(part);
      return [part.trim(), cleaned];
    })
    .filter((part) => part.length > 1);
  return Array.from(new Set(keywords));
}

function normaliseForMatch(raw = ""): string {
  return cleanBusinessLabel(raw).replace(/[-·_\s]/g, "");
}

const changeTypeLabel = (t: TableChangeType): string =>
  ({ ADD: "新增", MODIFY: "修改", DELETE: "删除", SCOPE_ADJUST: "口径调整", INSTRUCTION_ADJUST: "说明调整", UNCLEAR: "待确认" } as Record<string, string>)[t] ?? t;

const changeTypeColor = (t: TableChangeType): string =>
  ({ ADD: "green", MODIFY: "amber", DELETE: "red", SCOPE_ADJUST: "amber", INSTRUCTION_ADJUST: "blue", UNCLEAR: "outline" } as Record<string, string>)[t] ?? "outline";

const mappingStatusColor = (s: string): string =>
  ({ CONFIRMED: "green", DRAFT: "amber", PENDING: "amber", MISSING: "red" } as Record<string, string>)[s] ?? "outline";

const mappingStatusLabel = (s: string): string =>
  ({ CONFIRMED: "已确认", DRAFT: "待审核", PENDING: "待确认", MISSING: "未映射" } as Record<string, string>)[s] ?? s;

const lineageRoleColor = (r: string): string =>
  ({ REPORT_FIELD: "blue", SOURCE_FIELD: "outline", FILTER_FIELD: "amber" } as Record<string, string>)[r] ?? "outline";

const lineageRoleLabel = (r: string): string =>
  ({ REPORT_FIELD: "报送字段", SOURCE_FIELD: "来源字段", FILTER_FIELD: "过滤维度" } as Record<string, string>)[r] ?? r;
</script>
