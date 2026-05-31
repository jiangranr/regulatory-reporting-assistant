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
        <button
          class="btn primary"
          :disabled="busy || !workflow?.document_profile"
          @click="$emit('analyze')"
        >
          {{ busy ? "分析中…" : hasImpactAnalysis ? "重新影响分析" : "开始影响分析" }}
        </button>
        <button class="btn primary" @click="$emit('continue')">
          影响分析
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>

    <!-- 命中概念横幅：本次发文整体命中的监管概念 chips -->
    <div v-if="conceptHits.length || conceptHitsBusy" class="concept-banner mt-16">
      <div class="concept-banner-head">
        <span class="concept-banner-icon">💡</span>
        <span class="concept-banner-title">
          本次发文命中
          <strong>{{ conceptHits.length }}</strong>
          个监管概念
        </span>
        <span v-if="conceptHitsBusy" class="concept-banner-busy">匹配中…</span>
        <span v-else class="concept-banner-sub">点击 chip 跳转到首个辐射的报送项</span>
      </div>
      <div class="concept-banner-chips">
        <button
          v-for="hit in conceptHits"
          :key="hit.concept_code"
          :class="['concept-chip', `concept-chip-${primaryPath(hit)}`]"
          :title="`${hit.canonical_name} (${hit.concept_code})\n召回路径：${(hit.paths || []).join('+') || 'alias'}\n辐射 ${hit.related_reporting_item_codes.length} 个报送项`"
          @click="onConceptChipClick(hit)"
        >
          <span class="concept-chip-name">{{ hit.canonical_name }}</span>
          <!-- alias 优先：字面命中是确定性最强的信号；embedding 只在纯语义召回时单独显示 -->
          <span v-if="hasPath(hit, 'alias')" class="concept-chip-badge concept-chip-badge-alias" :title="hasPath(hit, 'embedding') ? 'alias 字面命中 + AI 语义召回' : 'alias 字面命中'">A<span v-if="hasPath(hit, 'embedding')" class="concept-chip-badge-plus">+✨</span></span>
          <span v-else-if="hasPath(hit, 'embedding')" class="concept-chip-badge" title="AI 语义召回（同义改写，文档中无字面别名）">✨</span>
          <span v-else-if="hasPath(hit, 'definition')" class="concept-chip-badge concept-chip-badge-def" title="定义片段命中">D</span>
          <span class="concept-chip-count">{{ hit.related_reporting_item_codes.length }}</span>
        </button>
      </div>
    </div>

    <div class="lineage-layout mt-24">
      <!-- 左：报表目录树 -->
      <div class="lineage-sidebar">
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
              <template v-for="item in table.items" :key="item.code">
                <div
                  :class="['tree-node', { active: activeItem === item.code }]"
                  @click="selectCatalogItem(table.code, item)"
                >
                  <span class="chev">{{ item.children.length > 1 ? (isGroupExpanded(item.code) ? "▾" : "▸") : "·" }}</span>
                  <span>{{ item.code }} {{ item.displayName }}</span>
                  <span v-if="item.children.length > 1" class="hit">+{{ item.children.length }}</span>
                  <span v-else-if="item.changed" class="hit">!</span>
                </div>
                <div v-if="item.children.length > 1 && isGroupExpanded(item.code)" class="tree-grandchild">
                  <div
                    v-for="child in item.children"
                    :key="child.code"
                    :class="['tree-node', 'tree-node-detail', { active: activeItem === child.code }]"
                    @click.stop="selectCatalogEntry(table.code, child.code)"
                  >
                    <span class="chev">·</span>
                    <span>{{ child.displayName }}</span>
                    <span v-if="child.changed" class="hit">!</span>
                  </div>
                </div>
              </template>
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
                <span :class="['tag', changeTypeColor(effectiveChangeType(activeSignal))]">{{ changeTypeLabel(effectiveChangeType(activeSignal)) }}</span>
              </div>
              <h3 style="margin-top:8px;">{{ displayIndicatorName(activeSignal.indicator_hint) || activeSignal.table_code + " 变更项" }}</h3>
              <div class="sub">{{ activeSignal.section_hint || "相关填报说明变更" }}</div>
            </div>
          </div>

          <!-- 命中此变更证据原文的概念（按 signal.evidence_text 字面包含过滤） -->
          <div v-if="conceptsHittingActiveItem.length" class="active-concepts">
            <h4 class="active-concepts-title">
              📌 本条变更证据原文里命中的概念
              <span class="active-concepts-count">{{ conceptsHittingActiveItem.length }} 个</span>
            </h4>
            <div class="active-concepts-list">
              <div v-for="hit in conceptsHittingActiveItem" :key="hit.concept_code" class="active-concept-row">
                <span :class="['concept-chip', 'concept-chip-sm', `concept-chip-${primaryPath(hit)}`]">
                  <span class="concept-chip-name">{{ hit.canonical_name }}</span>
                  <span v-if="hasPath(hit, 'alias')" class="concept-chip-badge concept-chip-badge-alias">A<span v-if="hasPath(hit, 'embedding')" class="concept-chip-badge-plus">+✨</span></span>
                  <span v-else-if="hasPath(hit, 'embedding')" class="concept-chip-badge" title="AI 语义召回">✨</span>
                  <span v-else-if="hasPath(hit, 'definition')" class="concept-chip-badge concept-chip-badge-def">D</span>
                </span>
                <span class="active-concept-meta">
                  <span class="active-concept-code">{{ hit.concept_code }}</span>
                  <span class="active-concept-via">via {{ pathLabel(hit) }}</span>
                </span>
              </div>
            </div>
          </div>
          <div v-else-if="activeItemNotPinpointed" class="active-concepts active-concepts-empty">
            <span class="active-concepts-empty-icon">ⓘ</span>
            <span>
              本条变更证据原文未命中已建库的监管概念。
              <span class="active-concepts-empty-hint">文档整体命中的概念见顶部横幅。</span>
            </span>
          </div>

          <!-- 变更证据 -->
          <h4 style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--ink-500);font-weight:600;margin:8px 0 10px;">变更证据</h4>
          <div class="quote-list">
            <div class="quote" v-if="activeSignal.evidence_text">
              <span class="loc">原文摘录 · 置信度 {{ Math.round(activeSignal.confidence * 100) }}%</span>
              <div
                v-for="row in displayedEvidenceRows"
                :key="row.key"
                class="evidence-row"
              >
                <span v-if="row.action" class="evidence-meta">
                  {{ row.action }} · {{ row.author || "未知作者" }} · {{ row.date || "日期未知" }}
                </span>
                <span class="evidence-body">
                  <template v-for="(segment, index) in row.segments" :key="index">
                    <mark v-if="segment.highlighted" class="evidence-highlight">{{ segment.text }}</mark>
                    <span v-else>{{ segment.text }}</span>
                  </template>
                </span>
              </div>
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
                <td colspan="5" style="text-align:center;color:var(--ink-400);padding:16px;">
                  {{ hasImpactAnalysis ? "暂无字段映射数据" : "尚未执行影响分析，请先点击开始影响分析生成候选和血缘上下文" }}
                </td>
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
import type { ConceptMatchHit, TaskWorkflow, TableChangeSignal, TableChangeType } from "@/types/api";
import LineageGraph, { type LineageNode, type LineageEdge } from "@/components/LineageGraph.vue";
import { formatReadableEvidence, normalizeEvidenceText, type ReadableEvidenceRow } from "@/utils/evidence";

const props = withDefaults(defineProps<{
  workflow: TaskWorkflow | null;
  busy?: boolean;
  /** 本次发文命中的概念列表（来自 /api/concepts/match） */
  conceptHits?: ConceptMatchHit[];
  conceptHitsBusy?: boolean;
  /** 外部传入要聚焦的指标 item_code（例如从影响分析「查看血缘」跳过来）。 */
  focusItemCode?: string | null;
}>(), {
  busy: false,
  conceptHits: () => [],
  conceptHitsBusy: false,
  focusItemCode: null,
});

defineEmits<{ continue: []; back: []; analyze: [] }>();

const activeTable = ref<string | null>(null);
const activeItem = ref<string | null>(null);
const activeGraphNodeId = ref<string | null>(null);
const expandedGroups = ref<Set<string>>(new Set());

const tableNames: Record<string, string> = {
  G21: "流动性期限缺口统计表",
  G24: "最大百家金融机构同业融入情况表",
  G25: "流动性覆盖率和净稳定融资比例情况表",
  G27: "主要负债项目明细表",
  G31: "投资业务情况表",
};

interface CatalogChild {
  code: string;
  name: string;
  displayName: string;
  changed: boolean;
  signal: TableChangeSignal;
}

interface CatalogItem extends CatalogChild {
  children: CatalogChild[];
}

interface CatalogTable {
  code: string;
  name: string;
  items: CatalogItem[];
}

// Build catalog from change_signals in profile
const catalog = computed<CatalogTable[]>(() => {
  const signals = props.workflow?.document_profile?.change_signals ?? [];
  const byTable = new Map<string, TableChangeSignal[]>();
  for (const s of signals) {
    if (!byTable.has(s.table_code)) byTable.set(s.table_code, []);
    byTable.get(s.table_code)!.push(s);
  }
  return Array.from(byTable.entries()).map(([code, items]) => {
    const byMetric = new Map<
      string,
      {
        metric: string;
        children: Array<{ raw: string; detailName: string; signal: TableChangeSignal }>;
      }
    >();

    for (const signal of items) {
      const raw = signal.indicator_hint || signal.section_hint || "变更项";
      const parsed = parseIndicatorParts(raw);
      const metricKey = normaliseForMatch(parsed.metric) || normaliseForMatch(raw);
      if (!byMetric.has(metricKey)) {
        byMetric.set(metricKey, { metric: parsed.metric, children: [] });
      }
      byMetric.get(metricKey)!.children.push({
        raw,
        detailName: parsed.detailName,
        signal,
      });
    }

    const groupedItems = Array.from(byMetric.values()).map((group, i) => {
      const groupCode = `${code}.${i + 1}`;
      const children = group.children.map((child, childIndex) => ({
        code: `${groupCode}.${childIndex + 1}`,
        name: child.raw,
        displayName: child.detailName,
        changed: true,
        signal: child.signal,
      }));
      return {
        code: groupCode,
        name: group.metric,
        displayName: group.metric,
        changed: true,
        signal: group.children[0].signal,
        children,
      };
    });

    return {
      code,
      name: tableNames[code] ?? "",
      items: groupedItems,
    };
  });
});

const hitCount = computed(() => props.workflow?.document_profile?.change_signals.length ?? 0);
const hasImpactAnalysis = computed(() =>
  Boolean(
    props.workflow?.impact_items?.length ||
      props.workflow?.reporting_candidates?.length ||
      props.workflow?.lineage_candidates?.length ||
      props.workflow?.field_mappings?.length,
  ),
);

// ── 概念命中相关工具 ─────────────────────────────────────────

const _PATH_PRIORITY = ["alias", "embedding", "definition"] as const;

function primaryPath(hit: ConceptMatchHit): string {
  const paths = hit.paths ?? [];
  for (const p of _PATH_PRIORITY) if (paths.includes(p)) return p;
  return "alias";
}

function hasPath(hit: ConceptMatchHit, path: string): boolean {
  return (hit.paths ?? []).includes(path);
}

function pathLabel(hit: ConceptMatchHit): string {
  const paths = hit.paths ?? [];
  if (!paths.length) return "alias 字面命中";
  const labels: string[] = [];
  if (paths.includes("alias")) labels.push("alias");
  if (paths.includes("embedding")) labels.push("embedding 语义召回");
  if (paths.includes("definition")) labels.push("definition 子串");
  return labels.join(" + ");
}

/**
 * 反查"本条变更证据原文里命中了哪些概念"。
 *
 * 设计（2026-05-26 修订二，回应用户反馈）：
 *   - 不再用 item_code 反查 / indicator_hint fuzzy / table 前缀兜底
 *   - 改为：从 signal.evidence_text 原文片段里**真包含**概念 matched_alias / canonical_name
 *           的概念才算命中
 *   - 跨表辐射（reg_concept_reporting_item_map）的价值在**顶部横幅**而非本区块
 *     —— per-item 详情和原文摘录在同屏，用户期望"原文里出现什么就显示什么"，
 *     而不是"历史 map 配置认为这个 item 关联什么"
 *   - 兜底：用 signal.indicator_hint 也做一次包含检查（弥补 evidence_text 没截到的）
 */
const conceptsHittingActiveItem = computed<ConceptMatchHit[]>(() => {
  const signal = activeSignal.value;
  if (!signal || !props.conceptHits?.length) return [];

  // 拼接"原文场景"：evidence_text 是核心；indicator_hint 作为补充（有时 LLM 抽 hint 但 evidence 截得短）
  const scope = `${signal.evidence_text || ""}\n${signal.indicator_hint || ""}`.trim();
  if (!scope) return [];

  return props.conceptHits.filter((h) => {
    const probes = [h.matched_alias, h.canonical_name].filter(Boolean);
    return probes.some((token) => token && scope.includes(token));
  });
});

/** activeSignal 存在但没在原文里命中已建库概念时显示友好提示 */
const activeItemNotPinpointed = computed<boolean>(() => {
  const signal = activeSignal.value;
  if (!signal || !props.conceptHits?.length) return false;
  // 必须有原文场景才显示"未命中"提示；evidence/hint 都空说明 signal 自己就空
  const scope = `${signal.evidence_text || ""}${signal.indicator_hint || ""}`.trim();
  if (!scope) return false;
  return conceptsHittingActiveItem.value.length === 0;
});

/** 点击顶部 chip 时，跳转到该概念辐射的首个报送项 */
function onConceptChipClick(hit: ConceptMatchHit): void {
  const firstItemCode = hit.related_reporting_item_codes[0];
  if (!firstItemCode) return;
  const tableCode = firstItemCode.split(".")[0];
  if (!tableCode) return;
  const table = catalog.value.find((t) => t.code === tableCode);
  if (!table) return;
  activeTable.value = tableCode;
  // 在该报表下找首个匹配的 signal
  const entries = flattenCatalogItems(table.items);
  const hitEntry = entries.find(
    (e) =>
      e.signal.matched_item_code === firstItemCode ||
      e.signal.composite_match?.reporting_item_codes?.includes(firstItemCode),
  );
  if (hitEntry) {
    selectCatalogEntry(tableCode, hitEntry.code);
  } else if (entries[0]) {
    selectCatalogEntry(tableCode, entries[0].code);
  }
}

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

    const entries = flattenCatalogItems(table.items);
    const exactHit = entries.find((it) => it.signal.matched_item_code === code);
    if (exactHit) {
      selectCatalogEntry(tableCode, exactHit.code);
      return;
    }

    const compositeHit = entries.find((it) =>
      it.signal.composite_match?.reporting_item_codes?.includes(code)
    );
    if (compositeHit) {
      selectCatalogEntry(tableCode, compositeHit.code);
      return;
    }

    // 提取最后一段作为关键字（例如 D 列的「因持有非底层资产而间接持有」）
    const tail = code.split(".").slice(-1)[0] || "";
    const keyword = tail.replace(/^[A-Z]_?/, "").replace(/_/g, "").slice(0, 12);
    if (!keyword) return;

    const norm = (s: string) => s.replace(/[-·_\s]/g, "");
    const k = norm(keyword);
    const hit = entries.find((it) => norm(it.signal.indicator_hint || "").includes(k));
    if (hit) selectCatalogEntry(tableCode, hit.code);
  },
  { immediate: true },
);

const activeSignal = computed(() => {
  if (activeItem.value) {
    const found = findCatalogEntry(activeItem.value);
    if (found) return found.signal;
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

const formattedEvidenceRows = computed<ReadableEvidenceRow[]>(() =>
  formatReadableEvidence(activeSignal.value?.evidence_text ?? "", activeEvidenceHighlightTerms.value),
);

const activeEvidenceHighlightTerms = computed(() => {
  const signal = activeSignal.value;
  if (!signal) return [];
  return [
    signal.indicator_hint,
    displayIndicatorName(signal.indicator_hint),
    cleanBusinessLabel(signal.indicator_hint),
    signal.matched_item_code ?? "",
  ].filter(Boolean);
});

const originalEvidenceRows = computed<ReadableEvidenceRow[]>(() => {
  const context = findOriginalContextText(
    activeSignal.value,
    props.workflow?.document?.parsed_text || props.workflow?.document?.text_excerpt || "",
    activeEvidenceHighlightTerms.value,
  );
  return context ? formatReadableEvidence(context, activeEvidenceHighlightTerms.value) : [];
});

const displayedEvidenceRows = computed<ReadableEvidenceRow[]>(() =>
  originalEvidenceRows.value.length ? originalEvidenceRows.value : formattedEvidenceRows.value,
);

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
      // **关键过滤**：indicatorMatchKeywords 用 raw.length>1 过滤，但 cleanBusinessLabel
      // 可能把纯数字片段（如 "1.8.2"）整段 strip 成空串。空串作为 includes() 参数永远返回 true，
      // 会让所有 field_mapping 被误算成"命中"。所以归一化后必须再做一次非空过滤。
      const norm = normaliseForMatch;
      const normKws = keywords.map(norm).filter((kw) => kw.length >= 2);
      if (!normKws.length) {
        // 全部 keyword 归一化后为空（典型场景：indicator_hint 只是数字编号如 "1.8.1/1.8.2"），
        // 没有可靠的字面信号 → 不展示 field mapping（避免误显示全表）
        return [];
      }
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

function selectCatalogItem(tableCode: string, item: CatalogItem) {
  activeTable.value = tableCode;
  activeItem.value = item.code;
  if (item.children.length > 1) {
    setGroupExpanded(item.code, !isGroupExpanded(item.code));
  }
}

function selectCatalogEntry(tableCode: string, itemCode: string) {
  activeTable.value = tableCode;
  activeItem.value = itemCode;
  const groupCode = parentGroupCode(itemCode);
  if (groupCode !== itemCode) {
    setGroupExpanded(groupCode, true);
  }
}

function parentGroupCode(itemCode: string): string {
  const parts = itemCode.split(".");
  if (parts.length < 3) return itemCode;
  return `${parts[0]}.${parts[1]}`;
}

function isGroupExpanded(itemCode: string): boolean {
  return expandedGroups.value.has(itemCode);
}

function setGroupExpanded(itemCode: string, expanded: boolean) {
  const next = new Set(expandedGroups.value);
  if (expanded) next.add(itemCode);
  else next.delete(itemCode);
  expandedGroups.value = next;
}

function flattenCatalogItems(items: CatalogItem[]): CatalogChild[] {
  return items.flatMap((item) => [item, ...item.children]);
}

function findCatalogEntry(itemCode: string): CatalogChild | null {
  for (const table of catalog.value) {
    const found = flattenCatalogItems(table.items).find((item) => item.code === itemCode);
    if (found) return found;
  }
  return null;
}

function parseIndicatorParts(raw = ""): { product: string; metric: string; detailName: string } {
  const parts = raw.split("×").map((part) => cleanBusinessLabel(part)).filter(Boolean);
  if (parts.length >= 2) {
    const product = parts.slice(0, -1).join(" × ");
    const metric = parts[parts.length - 1];
    return {
      product,
      metric,
      detailName: product ? `${product} × ${metric}` : metric,
    };
  }
  const metric = displayIndicatorName(raw) || cleanBusinessLabel(raw) || "变更项";
  return { product: "", metric, detailName: metric };
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

function findOriginalContextText(signal: TableChangeSignal | null, sourceText: string, terms: string[]): string {
  if (!signal || !sourceText.trim()) return "";
  const candidates = Array.from(
    new Set(
      [
        ...terms,
        signal.indicator_hint,
        displayIndicatorName(signal.indicator_hint),
        cleanBusinessLabel(signal.indicator_hint),
      ].filter((term) => term && term.length >= 2),
    ),
  ).sort((a, b) => b.length - a.length);

  for (const term of candidates) {
    const index = sourceText.indexOf(term);
    if (index < 0) continue;
    const start = Math.max(0, index - 160);
    const end = Math.min(sourceText.length, index + term.length + 360);
    return trimContextBoundary(sourceText.slice(start, end));
  }
  return "";
}

function trimContextBoundary(value: string): string {
  const cleaned = normalizeEvidenceText(value);
  if (cleaned.length <= 520) return cleaned;
  return `${cleaned.slice(0, 520).trim()}...`;
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

function effectiveChangeType(signal: TableChangeSignal): TableChangeType {
  if (["INSTRUCTION_ADJUST", "UNCLEAR"].includes(signal.change_type)) {
    const body = (signal.evidence_text || "").replace(/-?\s*\[\s*(?:新增|删除)\s*\|[^\]]+\]\s*/g, "").trim();
    const businessText = `${signal.indicator_hint || ""} ${body}`;
    if (/\[\s*新增\s*\|/.test(signal.evidence_text || "") && /新增\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)/.test(body)) return "ADD";
    if (/\[\s*删除\s*\|/.test(signal.evidence_text || "") && /(?:删除|停报)\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)/.test(body)) return "DELETE";
    if (/(定义|公式|计算|口径|范围|填报|统计)/.test(businessText)) return "SCOPE_ADJUST";
  }
  return signal.change_type;
}

const mappingStatusColor = (s: string): string =>
  ({ CONFIRMED: "green", DRAFT: "amber", PENDING: "amber", MISSING: "red" } as Record<string, string>)[s] ?? "outline";

const mappingStatusLabel = (s: string): string =>
  ({ CONFIRMED: "已确认", DRAFT: "待审核", PENDING: "待确认", MISSING: "未映射" } as Record<string, string>)[s] ?? s;

const lineageRoleColor = (r: string): string =>
  ({ REPORT_FIELD: "blue", SOURCE_FIELD: "outline", FILTER_FIELD: "amber" } as Record<string, string>)[r] ?? "outline";

const lineageRoleLabel = (r: string): string =>
  ({ REPORT_FIELD: "报送字段", SOURCE_FIELD: "来源字段", FILTER_FIELD: "过滤维度" } as Record<string, string>)[r] ?? r;
</script>

<style scoped>
/* ── 命中概念横幅 ───────────────────────────────────────── */
.concept-banner {
  border: 1px solid var(--orange-100, #fde6cf);
  background: linear-gradient(180deg, #fff8f1 0%, #fffefb 100%);
  border-radius: 10px;
  padding: 12px 14px;
}
.concept-banner-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--ink-700, #444);
}
.concept-banner-icon { font-size: 14px; }
.concept-banner-title strong { color: var(--orange-700, #d46a1d); font-weight: 600; }
.concept-banner-sub {
  margin-left: auto;
  color: var(--ink-400, #9aa);
  font-size: 11px;
}
.concept-banner-busy {
  margin-left: auto;
  color: var(--orange-600, #e08a3e);
  font-size: 11px;
}
.concept-banner-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* ── 概念 chip 通用样式 ─────────────────────────────────── */
.concept-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: #fff;
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
  transition: all .15s ease;
}
.concept-chip:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.concept-chip-name { color: var(--ink-800, #333); }
.concept-chip-count {
  background: rgba(0,0,0,.06);
  color: var(--ink-500, #888);
  padding: 0 5px;
  border-radius: 8px;
  font-size: 10px;
  min-width: 14px;
  text-align: center;
}
.concept-chip-badge {
  font-size: 10px;
  font-weight: 600;
  background: rgba(255,255,255,.6);
  color: var(--ink-700);
  padding: 0 4px;
  border-radius: 4px;
}
.concept-chip-badge-alias { background: rgba(48,127,226,.12); color: #2766b8; }
.concept-chip-badge-def { background: rgba(127,127,127,.12); color: #666; }
.concept-chip-badge-plus {
  margin-left: 2px;
  font-size: 9px;
  opacity: .85;
  color: #ba6bd4;
  font-weight: 500;
}
.concept-chip-sm { padding: 2px 8px; font-size: 11px; }

/* 不同召回路径的边框/底色 */
.concept-chip-alias {
  border-color: rgba(48,127,226,.25);
  background: rgba(48,127,226,.05);
}
.concept-chip-embedding {
  border-color: rgba(186,107,212,.35);
  background: rgba(186,107,212,.07);
}
.concept-chip-definition {
  border-color: rgba(160,160,160,.25);
  background: rgba(160,160,160,.05);
}

/* ── 右侧详情：命中此报送项的概念列表 ───────────────────── */
.active-concepts {
  background: rgba(48,127,226,.04);
  border-left: 3px solid rgba(48,127,226,.35);
  padding: 10px 12px;
  border-radius: 4px;
  margin: 4px 0 16px;
}
.active-concepts-title {
  font-size: 12px;
  color: var(--ink-700, #444);
  font-weight: 600;
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.active-concepts-count {
  font-size: 10px;
  color: var(--ink-400, #aaa);
  font-weight: 400;
}
.active-concepts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.active-concept-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.active-concept-meta {
  font-size: 10px;
  color: var(--ink-400, #999);
  font-family: monospace;
  display: flex;
  gap: 8px;
}
.active-concept-code { color: var(--ink-500); }
.active-concept-via { color: var(--ink-400); }

.active-concepts-empty {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: rgba(160,160,160,.04);
  border-left-color: rgba(160,160,160,.25);
  color: var(--ink-500, #888);
  font-size: 12px;
}
.active-concepts-empty-icon { color: var(--ink-400, #aaa); }
.active-concepts-empty-hint { color: var(--ink-400, #aaa); }

.evidence-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.evidence-row + .evidence-row {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border, #e8dfd2);
}

.evidence-meta {
  width: fit-content;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(234, 84, 4, 0.1);
  color: var(--orange-700, #b94400);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
}

.evidence-body {
  color: var(--ink-800);
  line-height: 1.7;
  word-break: break-word;
}

.evidence-highlight {
  background: rgba(234, 84, 4, 0.13);
  border-radius: 4px;
  color: var(--orange-700, #9a3412);
  font-weight: 700;
  padding: 0 3px;
}
</style>
