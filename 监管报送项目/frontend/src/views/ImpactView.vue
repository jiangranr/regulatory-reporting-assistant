<template>
  <div>
    <div class="row between">
      <div>
        <div class="h-eyebrow">第 4 步</div>
        <h1 class="h-title">影响分析</h1>
        <p class="h-sub">基于字段定位结果，输出影响项清单：影响类型、范围、置信度和待确认问题。</p>
      </div>
      <div class="row">
        <button class="btn secondary" @click="$emit('back')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          字段定位
        </button>
        <button class="btn primary" @click="$emit('continue')">
          生成工单
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </div>
    </div>

    <!-- 命中监管概念 (概念库辐射) -->
    <div class="card mt-24" v-if="conceptHits.length">
      <div class="sec-h">
        <h2>命中监管概念</h2>
        <span class="line"></span>
        <span class="count">{{ conceptHits.length }} 个</span>
        <span style="font-size:11px;color:var(--ink-400);margin-left:auto;">
          辐射 {{ radiatedObjectCodes.length }} 张报表 / {{ radiatedItemCount }} 项指标
        </span>
      </div>
      <p style="font-size:12px;color:var(--ink-600);margin-bottom:10px;">
        从本次发文中识别到的术语，通过概念库自动辐射到所有相关报送项。命中概念越多，意味着潜在影响越广。
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        <div
          v-for="hit in conceptHits"
          :key="hit.concept_code"
          class="concept-chip"
          :title="`匹配自原文「${hit.matched_alias}」 · 辐射到 ${hit.related_reporting_item_codes.length} 个报送项`"
        >
          <span class="concept-chip-name">{{ hit.canonical_name }}</span>
          <span class="concept-chip-radar" v-if="hit.related_reporting_item_codes.length">
            <span
              v-for="obj in uniqueObjectsFor(hit)"
              :key="obj"
              class="concept-chip-obj"
            >{{ obj }}</span>
          </span>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="impact-summary mt-24">
      <div class="impact-stat hot">
        <div class="lbl">高风险影响项</div>
        <div class="val">{{ highCount }}</div>
        <div class="delta">需优先处理</div>
      </div>
      <div class="impact-stat">
        <div class="lbl">中风险影响项</div>
        <div class="val">{{ medCount }}</div>
        <div class="delta">字段映射 / 口径类</div>
      </div>
      <div class="impact-stat">
        <div class="lbl">低风险 · 参考</div>
        <div class="val">{{ lowCount }}</div>
        <div class="delta">建议归档</div>
      </div>
      <div class="impact-stat">
        <div class="lbl">影响变更信号</div>
        <div class="val">{{ signalCount }}</div>
        <div class="delta">来自文档画像</div>
      </div>
    </div>

    <!-- 影响项清单 -->
    <div class="card mt-16">
      <div class="sec-h">
        <h2>影响项清单</h2>
        <span class="line"></span>
        <span class="count">{{ impacts.length }} 项</span>
        <button v-if="!impacts.length" class="btn primary sm" :disabled="busy" @click="$emit('analyze')">
          {{ busy ? "分析中…" : "开始影响分析" }}
        </button>
      </div>

      <table class="tbl" v-if="impacts.length">
        <thead>
          <tr>
            <th style="width:28px;">#</th>
            <th>影响对象</th>
            <th>影响类型</th>
            <th>影响半径</th>
            <th>血缘角色</th>
            <th style="width:84px;">风险</th>
            <th style="width:120px;">置信度</th>
            <th style="width:160px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, i) in impacts" :key="i">
            <td class="mono" style="color:var(--ink-400);">{{ padIdx(i) }}</td>
            <td>
              <div style="font-weight:500;color:var(--ink-900);">{{ item.impacted_reporting_field || item.reporting_item_code }}</div>
              <div v-if="item.reporting_item_code" class="mono" style="font-size:11px;color:var(--ink-400);margin-top:2px;">{{ item.reporting_item_code }}</div>
            </td>
            <td><span class="tag outline">{{ item.impact_type }}</span></td>
            <td>
              <div class="radius-cell" :title="fieldListTooltip(item)">
                <span class="radius-badge sys">{{ systemCount(item) }} 系统</span>
                <span class="radius-badge fld">{{ fieldCount(item) }} 字段</span>
              </div>
            </td>
            <td>
              <div class="role-chips">
                <span
                  v-for="chip in roleChips(item)"
                  :key="chip.key"
                  :class="['role-chip', chip.cls]"
                >{{ chip.label }}</span>
                <span v-if="!roleChips(item).length" class="muted">-</span>
              </div>
            </td>
            <td>
              <span :class="['tag', riskColor(item.risk_level)]">
                <span class="dot"></span>{{ riskLabel(item.risk_level) }}
              </span>
            </td>
            <td>
              <span class="confidence">
                <b class="mono">{{ item.confidence_level === "HIGH" ? "90%" : item.confidence_level === "MEDIUM" ? "70%" : "50%" }}</b>
                <span class="bar" style="width:40px;">
                  <span :style="{ width: item.confidence_level === 'HIGH' ? '90%' : item.confidence_level === 'MEDIUM' ? '70%' : '50%' }"></span>
                </span>
              </span>
            </td>
            <td>
              <div class="op-cell">
                <span class="tag blue">待复核</span>
                <button
                  class="link-btn"
                  type="button"
                  :disabled="!item.reporting_item_code"
                  @click="openLineage(item)"
                  title="跳转到字段定位查看该指标的完整血缘"
                >查看血缘 →</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 从变更信号生成的简化影响项（无真实数据时使用） -->
      <table class="tbl" v-else-if="signalImpacts.length">
        <thead>
          <tr><th>#</th><th>涉及报表/指标</th><th>变更类型</th><th>影响估计</th><th>风险</th></tr>
        </thead>
        <tbody>
          <tr v-for="(s, i) in signalImpacts" :key="i">
            <td class="mono" style="color:var(--ink-400);">{{ padIdx(i) }}</td>
            <td>
              <span class="tag orange mono" style="font-size:12px;">{{ s.table_code }}</span>
              <span style="margin-left:8px;font-weight:500;">{{ s.indicator_hint || s.section_hint }}</span>
            </td>
            <td><span :class="['tag', changeTypeColor(s.change_type)]">{{ changeTypeLabel(s.change_type) }}</span></td>
            <td style="font-size:12px;color:var(--ink-600);">报送字段 / 口径调整 / 校验规则</td>
            <td><span class="tag amber"><span class="dot"></span>中</span></td>
          </tr>
        </tbody>
      </table>

      <div v-else style="text-align:center;padding:40px 0;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px;height:40px;margin:0 auto 12px;display:block;opacity:.4;color:var(--ink-400);"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
        <p style="color:var(--ink-400);">尚未执行影响分析</p>
        <button class="btn primary" style="margin-top:16px;" :disabled="busy" @click="$emit('analyze')">
          {{ busy ? "分析中…" : "开始影响分析" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { apiClient } from "@/api/client";
import type {
  ConceptMatchHit,
  RiskLevel,
  TableChangeType,
  TaskWorkflow,
} from "@/types/api";

const props = defineProps<{
  workflow: TaskWorkflow | null;
  busy: boolean;
}>();

const emit = defineEmits<{ continue: []; back: []; analyze: []; "view-lineage": [string] }>();

// Backend impact items (if available)
const impacts = computed(() => (props.workflow as any)?.impact_items ?? []);

// ── 建议 1：影响半径聚合 ────────────────────────────────────
// 不再把原始字段列表堆在表格里。改成"N 系统 / N 字段 + 角色徽章"。
// 原始字段通过 tooltip 暴露，需要细节时鼠标悬停看。
function systemCount(item: any): number {
  const fields = (item.impacted_source_fields ?? []) as string[];
  const systems = new Set<string>();
  for (const f of fields) {
    // field code 形如 "table.column"，取 table 作为系统层标识；如有 schema 前缀则再切一层
    const tbl = (f.split(".")[0] || "").trim();
    if (tbl) systems.add(tbl);
  }
  return systems.size;
}
function fieldCount(item: any): number {
  return (item.impacted_source_fields ?? []).length;
}
function roleChips(item: any): { key: string; label: string; cls: string }[] {
  const roles: string[] = item.impacted_lineage_roles ?? [];
  const map: Record<string, { label: string; cls: string }> = {
    SOURCE_FIELD: { label: "来源", cls: "role-source" },
    DIMENSION_FIELD: { label: "维度", cls: "role-dim" },
    FILTER_FIELD: { label: "过滤", cls: "role-filter" },
    REPORT_FIELD: { label: "报送", cls: "role-report" },
  };
  return roles
    .filter((r) => r in map)
    .map((r) => ({ key: r, label: map[r].label, cls: map[r].cls }));
}
function fieldListTooltip(item: any): string {
  return ((item.impacted_source_fields ?? []) as string[]).join("\n");
}

// ── 建议 2：跳转字段定位 ────────────────────────────────────
function openLineage(item: any): void {
  if (!item?.reporting_item_code) return;
  emit("view-lineage", item.reporting_item_code);
}

// 命中监管概念 (调 /api/concepts/match)
const conceptHits = ref<ConceptMatchHit[]>([]);

// 从 workflow 中推断本次涉及的报送对象代码(G31/G24/G21 等),用于补充规则卡片正文作匹配源
const inferredReportingObjects = (wf: TaskWorkflow | null): string[] => {
  if (!wf) return [];
  const codes = new Set<string>();
  for (const imp of impacts.value) {
    if (imp.reporting_item_code && imp.reporting_item_code.includes(".")) {
      codes.add(imp.reporting_item_code.split(".")[0]);
    }
  }
  for (const cand of wf.reporting_candidates ?? []) {
    if (cand.reporting_object_code) codes.add(cand.reporting_object_code);
  }
  for (const tbl of wf.document_profile?.affected_table_codes ?? []) {
    if (tbl) codes.add(tbl);
  }
  // 任务标题/文档标题里的 G31 等代码
  const titleRe = /\b(G[0-9]{1,3}[A-Z]*)\b/g;
  for (const src of [wf.task?.title, wf.document?.title].filter(Boolean) as string[]) {
    for (const m of src.matchAll(titleRe)) codes.add(m[1]);
  }
  return [...codes];
};

const buildMatchText = async (): Promise<string> => {
  const wf = props.workflow;
  if (!wf) return "";
  const parts: string[] = [];
  if (wf.document?.parsed_text) parts.push(wf.document.parsed_text);
  if (wf.document?.text_excerpt) parts.push(wf.document.text_excerpt);
  if (wf.document?.title) parts.push(wf.document.title);
  if (wf.task?.title) parts.push(wf.task.title);
  for (const imp of impacts.value) {
    if (imp.impact_reason) parts.push(imp.impact_reason);
    if (imp.impacted_reporting_field) parts.push(imp.impacted_reporting_field);
  }
  for (const sig of wf.document_profile?.change_signals ?? []) {
    if (sig.evidence_text) parts.push(sig.evidence_text);
    if (sig.indicator_hint) parts.push(sig.indicator_hint);
  }
  if (wf.document_profile?.evidence_text) parts.push(wf.document_profile.evidence_text);
  if (wf.document_profile?.reason) parts.push(wf.document_profile.reason);
  for (const cand of wf.reporting_candidates ?? []) {
    if (cand.evidence_text) parts.push(cand.evidence_text);
  }
  // 增强:把本次涉及对象(G31/G24/G21)的规则卡片正文也作为匹配源
  // 这样即使发文 parsed_text 很短,也能稳定命中报表的口径概念
  const objects = inferredReportingObjects(wf);
  for (const obj of objects) {
    try {
      const cards = await apiClient.listRuleCards({ reporting_object_code: obj });
      for (const card of cards) {
        if (card.card_text) parts.push(card.card_text);
      }
    } catch {
      // 后端没起就跳过
    }
  }
  return parts.join("\n");
};

const refreshConceptHits = async (): Promise<void> => {
  const text = await buildMatchText();
  if (!text) {
    conceptHits.value = [];
    return;
  }
  try {
    conceptHits.value = await apiClient.matchConcepts(text, 30);
  } catch {
    conceptHits.value = [];
  }
};

const uniqueObjectsFor = (hit: ConceptMatchHit): string[] => {
  const objs = new Set<string>();
  for (const code of hit.related_reporting_item_codes) {
    const obj = code.split(".")[0];
    if (obj) objs.add(obj);
  }
  return [...objs];
};

const radiatedObjectCodes = computed(() => {
  const set = new Set<string>();
  for (const hit of conceptHits.value) {
    for (const obj of uniqueObjectsFor(hit)) set.add(obj);
  }
  return [...set];
});

const radiatedItemCount = computed(() => {
  const set = new Set<string>();
  for (const hit of conceptHits.value) {
    for (const code of hit.related_reporting_item_codes) set.add(code);
  }
  return set.size;
});

watch(
  () => props.workflow,
  () => {
    refreshConceptHits();
  },
  { immediate: true },
);

// Fallback: use change signals from profile
const signalImpacts = computed(() =>
  props.workflow?.document_profile?.change_signals ?? []
);

const signalCount = computed(() => props.workflow?.document_profile?.change_signals.length ?? 0);
const highCount = computed(() => impacts.value.filter((i: any) => i.risk_level === "HIGH").length || Math.ceil(Number(signalCount.value) * 0.4) || 0);
const medCount = computed(() => impacts.value.filter((i: any) => i.risk_level === "MEDIUM").length || Math.ceil(Number(signalCount.value) * 0.6) || 0);
const lowCount = computed(() => impacts.value.filter((i: any) => i.risk_level === "LOW").length || 0);

const riskLabel = (r: RiskLevel | string): string =>
  ({ LOW: "低", MEDIUM: "中", HIGH: "高" } as Record<string, string>)[r] ?? r;
const riskColor = (r: RiskLevel | string): string =>
  ({ LOW: "green", MEDIUM: "amber", HIGH: "red" } as Record<string, string>)[r] ?? "outline";
const changeTypeLabel = (t: TableChangeType): string =>
  ({ ADD: "新增", MODIFY: "修改", DELETE: "删除", SCOPE_ADJUST: "口径调整", INSTRUCTION_ADJUST: "说明调整", UNCLEAR: "待确认" } as Record<string, string>)[t] ?? t;
function padIdx(i: unknown): string { return String(Number(i) + 1).padStart(2, "0"); }
const changeTypeColor = (t: TableChangeType): string =>
  ({ ADD: "green", MODIFY: "amber", DELETE: "red", SCOPE_ADJUST: "amber", INSTRUCTION_ADJUST: "blue", UNCLEAR: "outline" } as Record<string, string>)[t] ?? "outline";
</script>

<style scoped>
/* ── 影响半径单元格 ─ */
.radius-cell {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  cursor: help;
}
.radius-badge {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid transparent;
  white-space: nowrap;
}
.radius-badge.sys {
  background: rgba(245, 158, 11, 0.08);
  border-color: rgba(245, 158, 11, 0.25);
  color: rgba(180, 83, 9, 1);
}
.radius-badge.fld {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.25);
  color: rgba(29, 78, 216, 1);
}

/* ── 血缘角色徽章 ─ */
.role-chips {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
}
.role-chip {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 999px;
  font-weight: 500;
  letter-spacing: 0.3px;
}
.role-chip.role-report  { background: rgba(99, 102, 241, 0.12); color: rgba(67, 56, 202, 1); }
.role-chip.role-source  { background: rgba(16, 185, 129, 0.12); color: rgba(4, 120, 87, 1); }
.role-chip.role-dim     { background: rgba(245, 158, 11, 0.15); color: rgba(180, 83, 9, 1); }
.role-chip.role-filter  { background: rgba(244, 63, 94, 0.10); color: rgba(190, 18, 60, 1); }
.muted { color: var(--ink-400); font-size: 12px; }

/* ── 操作单元格 ─ */
.op-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.link-btn {
  background: transparent;
  border: none;
  color: var(--brand-600, #6366f1);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  text-decoration: none;
}
.link-btn:hover:not(:disabled) {
  text-decoration: underline;
}
.link-btn:disabled {
  color: var(--ink-400);
  cursor: not-allowed;
}

.concept-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(99, 102, 241, 0.02));
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 999px;
  font-size: 12px;
  color: var(--ink-800);
  transition: all 0.15s;
}
.concept-chip:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(99, 102, 241, 0.05));
  border-color: rgba(99, 102, 241, 0.4);
}
.concept-chip-name {
  font-weight: 500;
}
.concept-chip-radar {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding-left: 6px;
  border-left: 1px solid rgba(99, 102, 241, 0.2);
}
.concept-chip-obj {
  font-family: monospace;
  font-size: 10px;
  background: rgba(99, 102, 241, 0.15);
  color: rgba(67, 56, 202, 1);
  padding: 1px 5px;
  border-radius: 4px;
}
</style>
