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
          复核并拆单
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

    <!-- AI 分析中 banner -->
    <div v-if="busy" class="ai-analyzing-banner mt-24">
      <div class="ai-analyzing-icon">
        <span class="ai-pulse"></span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;position:relative;z-index:1;"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
      </div>
      <div class="ai-analyzing-text">
        <div class="ai-analyzing-title">AI 正在分析影响范围…</div>
        <div class="ai-analyzing-sub">LLM 正在读取变更证据和血缘上下文，生成 8 种影响类型的智能研判，预计 15-30 秒</div>
      </div>
      <div class="ai-analyzing-dots">
        <span></span><span></span><span></span>
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
        <span class="count">{{ displayImpacts.length }} 组 / {{ impacts.length }} 项</span>
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
          <tr v-for="(item, i) in displayImpacts" :key="item.aggregate_key ?? item.reporting_item_code ?? i">
            <td class="mono" style="color:var(--ink-400);">{{ padIdx(i) }}</td>
            <td>
              <div style="font-weight:500;color:var(--ink-900);">{{ item.aggregate_title || item.impacted_reporting_field || item.reporting_item_code }}</div>
              <!-- ROW axis：展示受影响的列度量 -->
              <div v-if="item.aggregate_axis === 'ROW' && item.aggregate_columns?.length" class="impact-rows">
                涉及列：{{ item.aggregate_columns.join("、") }}
              </div>
              <!-- COLUMN / UNCLEAR axis：展示受影响的行指标 -->
              <div v-else-if="item.aggregate_rows?.length" class="impact-rows">
                影响行：{{ item.aggregate_rows.join("、") }}
              </div>
              <div v-if="item.aggregate_item_codes?.length" class="mono impact-code-line">
                {{ item.aggregate_item_codes.length > 1 ? `${item.aggregate_item_codes.length} 个报表 cell` : item.aggregate_item_codes[0] }}
              </div>
              <div v-else-if="item.reporting_item_code" class="mono impact-code-line">{{ item.reporting_item_code }}</div>
            </td>
            <td>
              <div class="impact-type-cell">
                <span :class="['tag', impactTypeColor(item.impact_type)]">{{ impactTypeLabel(item.impact_type) }}</span>
                <span v-if="item.llm_analyzed" class="ai-badge" title="本条影响分析由 LLM 根据血缘上下文智能生成">✦ AI</span>
              </div>
            </td>
            <td>
              <div class="radius-popover">
                <div
                  :class="['radius-cell', { 'radius-cell-unmapped': !hasMappedLineage(item) }]"
                  :title="radiusTooltip(item)"
                  :aria-label="radiusAriaLabel(item)"
                  tabindex="0"
                  data-test="impact-radius-trigger"
                >
                  <template v-if="hasMappedLineage(item)">
                    <span class="radius-badge sys">{{ systemCount(item) }} 系统</span>
                    <span class="radius-badge fld">{{ fieldCount(item) }} 字段</span>
                  </template>
                  <template v-else>
                    <span class="radius-badge unmapped">血缘未配置</span>
                    <span class="radius-badge pending">待补映射</span>
                  </template>
                </div>

                <div
                  v-if="hasMappedLineage(item)"
                  class="radius-panel"
                  role="tooltip"
                  data-test="impact-radius-panel"
                >
                  <div class="radius-panel-title">系统与字段范围</div>
                  <div
                    v-for="group in impactRadiusGroups(item)"
                    :key="group.systemKey"
                    class="radius-system"
                  >
                    <div class="radius-system-head">
                      <span class="radius-system-name">{{ group.systemName }}</span>
                      <span v-if="group.systemCode" class="radius-system-code mono">{{ group.systemCode }}</span>
                      <span class="radius-system-count">{{ group.fields.length }} 字段</span>
                    </div>
                    <div class="radius-field-list">
                      <div
                        v-for="field in group.fields"
                        :key="field.fieldCode"
                        class="radius-field-row"
                      >
                        <div class="radius-field-main">
                          <span class="radius-field-name">{{ field.fieldName }}</span>
                          <span v-if="field.roleLabel" :class="['role-chip', field.roleClass]">{{ field.roleLabel }}</span>
                        </div>
                        <div class="radius-field-code mono">{{ field.fieldCode }}</div>
                        <div v-if="field.tableName || field.columnName" class="radius-field-meta">
                          {{ [field.tableName, field.columnName].filter(Boolean).join(".") }}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
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
            <td><span :class="['tag', changeTypeColor(effectiveChangeType(s))]">{{ changeTypeLabel(effectiveChangeType(s)) }}</span></td>
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

interface DisplayImpactItem extends Record<string, any> {
  aggregate_key?: string;
  aggregate_title?: string;
  aggregate_axis?: string;        // ROW | COLUMN | CELL | UNCLEAR
  aggregate_rows?: string[];      // COLUMN axis：受影响的行指标名列表
  aggregate_columns?: string[];   // ROW axis：受影响的列度量名列表
  aggregate_item_codes?: string[];
}

interface RadiusFieldDetail {
  fieldCode: string;
  fieldName: string;
  systemName: string;
  systemCode: string;
  tableName: string;
  columnName: string;
  roleLabel: string;
  roleClass: string;
}

interface RadiusSystemGroup {
  systemKey: string;
  systemName: string;
  systemCode: string;
  fields: RadiusFieldDetail[];
}

const props = defineProps<{
  workflow: TaskWorkflow | null;
  busy: boolean;
}>();

const emit = defineEmits<{ continue: []; back: []; analyze: []; "view-lineage": [string] }>();

// Backend impact items (if available)
const impacts = computed(() => (props.workflow as any)?.impact_items ?? []);
const displayImpacts = computed<DisplayImpactItem[]>(() => aggregateImpactsForDisplay(impacts.value, props.workflow));
const fieldMetadataByCode = computed(() => buildFieldMetadataByCode(props.workflow));

// ── 建议 1：影响半径聚合 ────────────────────────────────────
// 不再把原始字段列表堆在表格里。改成"N 系统 / N 字段 + 角色徽章"。
// 原始字段通过 tooltip 暴露，需要细节时鼠标悬停看。
function systemCount(item: any): number {
  return impactRadiusGroups(item).length;
}
function fieldCount(item: any): number {
  return impactRadiusGroups(item).reduce((sum, group) => sum + group.fields.length, 0);
}
function hasMappedLineage(item: any): boolean {
  return fieldCount(item) > 0 || roleChips(item).length > 0 || Boolean(item.impacted_reporting_field);
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
function radiusTooltip(item: any): string {
  const groups = impactRadiusGroups(item);
  if (groups.length) {
    return groups
      .map((group) => `${group.systemName}：${group.fields.map((field) => field.fieldCode).join("、")}`)
      .join("\n");
  }
  const codes = item.aggregate_item_codes?.length ? item.aggregate_item_codes.join("\n") : item.reporting_item_code ?? "";
  return `当前指标未查到字段血缘映射；这表示元数据未覆盖，不代表业务上没有影响。\n${codes}`;
}
function radiusAriaLabel(item: any): string {
  if (!hasMappedLineage(item)) return "影响半径：血缘未配置，待补映射";
  return `查看影响半径明细：${systemCount(item)} 个系统，${fieldCount(item)} 个字段`;
}

function impactRadiusGroups(item: any): RadiusSystemGroup[] {
  const fieldCodes = uniqueNonEmpty([
    ...(item.impacted_source_fields ?? []),
    item.impacted_reporting_field,
  ]);
  const groups = new Map<string, RadiusSystemGroup>();

  for (const fieldCode of fieldCodes) {
    const meta = fieldMetadataByCode.value.get(fieldCode);
    const systemName = meta?.system_name || inferSystemName(fieldCode);
    const systemCode = meta?.system_code || "";
    const systemKey = systemCode || systemName;
    const tableName = meta?.table_name || inferTableName(fieldCode);
    const columnName = meta?.column_name || inferColumnName(fieldCode);
    const role = roleMeta(meta?.lineage_role || "");

    if (!groups.has(systemKey)) {
      groups.set(systemKey, {
        systemKey,
        systemName,
        systemCode,
        fields: [],
      });
    }
    groups.get(systemKey)!.fields.push({
      fieldCode,
      fieldName: meta?.field_name || meta?.business_meaning || columnName || fieldCode,
      systemName,
      systemCode,
      tableName,
      columnName,
      roleLabel: role.label,
      roleClass: role.cls,
    });
  }

  return [...groups.values()];
}

function buildFieldMetadataByCode(wf: TaskWorkflow | null): Map<string, Record<string, any>> {
  const byCode = new Map<string, Record<string, any>>();
  for (const mapping of wf?.field_mappings ?? []) {
    if (mapping.field_code) byCode.set(mapping.field_code, mapping as unknown as Record<string, any>);
  }
  for (const field of wf?.lineage_candidates ?? []) {
    if (!field.field_code || byCode.has(field.field_code)) continue;
    byCode.set(field.field_code, field as unknown as Record<string, any>);
  }
  return byCode;
}

function inferSystemName(fieldCode: string): string {
  return inferTableName(fieldCode) || fieldCode || "未知系统";
}

function inferTableName(fieldCode: string): string {
  return String(fieldCode || "").split(".")[0] || "";
}

function inferColumnName(fieldCode: string): string {
  const parts = String(fieldCode || "").split(".");
  return parts.length > 1 ? parts.slice(1).join(".") : "";
}

function roleMeta(role: string): { label: string; cls: string } {
  const map: Record<string, { label: string; cls: string }> = {
    SOURCE_FIELD: { label: "来源", cls: "role-source" },
    DIMENSION_FIELD: { label: "维度", cls: "role-dim" },
    FILTER_FIELD: { label: "过滤", cls: "role-filter" },
    REPORT_FIELD: { label: "报送", cls: "role-report" },
  };
  return map[role] ?? { label: "", cls: "" };
}

/**
 * 从 item_code 取第 2 段（index 2）作为行标签，第 3 段以后作为列标签。
 * 适配 G01_IV 风格（11_1通过互联网...）和 G31 风格（1_0）两种编码。
 */
function rawRowSegment(code: string): string {
  const parts = String(code ?? "").split(".");
  return parts.length >= 3 ? parts[2] : "";
}
function rawColSegment(code: string): string {
  const parts = String(code ?? "").split(".");
  return parts.length >= 4 ? parts.slice(3).join(".") : "";
}
/** 将行段 11_1通过互联网... 格式化为可读标签 11.1通过互联网... */
function formatRowLabel(segment: string): string {
  if (!segment) return "";
  // 数字_字母/数字前缀（如 11_1、11_a_1）用点替换首个下划线
  return segment.replace(/^(\d+)_/, "$1.").replace(/_/g, ".");
}

/**
 * 当 change_axis 为 UNCLEAR（旧数据 / LLM 未判断）时，从 item_code 结构推断：
 * - 同列不同行 → ROW（新增/删除了产品类别行，如 G01_IV 新增活期/定期行）
 * - 同行不同列 → COLUMN（修改了某度量列，如 G31 修改修正久期列）
 * 两个都有或都没有 → UNCLEAR，保持原逻辑
 */
function inferAxisFromCodes(allItems: any[]): Map<any, string> {
  const axisMap = new Map<any, string>();
  for (const item of allItems) {
    if (item.change_axis && item.change_axis !== "UNCLEAR") {
      axisMap.set(item, item.change_axis);
      continue;
    }
    const myRow = rawRowSegment(item.reporting_item_code);
    const myCol = rawColSegment(item.reporting_item_code);
    if (!myRow || !myCol) { axisMap.set(item, "UNCLEAR"); continue; }

    const sameColDiffRow = allItems.some(
      (other) =>
        other !== item &&
        rawColSegment(other.reporting_item_code) === myCol &&
        rawRowSegment(other.reporting_item_code) !== myRow,
    );
    const sameRowDiffCol = allItems.some(
      (other) =>
        other !== item &&
        rawRowSegment(other.reporting_item_code) === myRow &&
        rawColSegment(other.reporting_item_code) !== myCol,
    );

    if (sameColDiffRow && !sameRowDiffCol) axisMap.set(item, "ROW");
    else if (sameRowDiffCol && !sameColDiffRow) axisMap.set(item, "COLUMN");
    else axisMap.set(item, "UNCLEAR");
  }
  return axisMap;
}

function aggregateImpactsForDisplay(items: any[], wf: TaskWorkflow | null): DisplayImpactItem[] {
  const signalByItemCode = new Map<string, { row: string; column: string }>();
  for (const signal of wf?.document_profile?.change_signals ?? []) {
    if (!signal.matched_item_code) continue;
    const parsed = parseIndicatorHint(signal.indicator_hint);
    if (parsed.column || parsed.row) signalByItemCode.set(signal.matched_item_code, parsed);
  }

  const axisMap = inferAxisFromCodes(items);

  const groups = new Map<string, DisplayImpactItem[]>();
  for (const item of items) {
    const axis: string = axisMap.get(item) ?? "UNCLEAR";
    const signal = signalByItemCode.get(item.reporting_item_code);
    const lineageState = hasMappedLineage(item) ? "mapped" : "unmapped";

    let groupDimension: string;
    if (axis === "ROW") {
      // 以行指标为父级：相同指标的不同列合并成 1 行
      groupDimension = normalizeRowLabel(
        item.reporting_item_name || signal?.row || formatRowLabel(rawRowSegment(item.reporting_item_code)) || item.reporting_item_code,
      );
    } else {
      // COLUMN / CELL / UNCLEAR：以列度量为父级（原行为）
      groupDimension = normalizeColumnLabel(
        signal?.column || parseColumnFromCode(item.reporting_item_code) || item.impacted_reporting_field || item.reporting_item_code,
      );
    }

    const groupKey = [item.impact_type, item.risk_level, item.confidence_level, lineageState, axis, groupDimension].join("|");
    if (!groups.has(groupKey)) groups.set(groupKey, []);
    groups.get(groupKey)!.push(item);
  }

  const result: DisplayImpactItem[] = [];
  for (const [key, group] of groups) {
    const first = group[0];
    const axis: string = first.change_axis || "UNCLEAR";
    const codes = uniqueNonEmpty(group.map((item) => item.reporting_item_code));
    const sourceFields = uniqueNonEmpty(group.flatMap((item) => item.impacted_source_fields ?? []));
    const roles = uniqueNonEmpty(group.flatMap((item) => item.impacted_lineage_roles ?? []));

    let aggregateTitle: string;
    let aggregateRows: string[] = [];
    let aggregateColumns: string[] = [];

    if (axis === "ROW") {
      // 父级 = 行指标名；子级 = 受影响的列
      const firstSig = signalByItemCode.get(first.reporting_item_code);
      aggregateTitle = normalizeRowLabel(
        first.reporting_item_name
          || firstSig?.row
          || formatRowLabel(rawRowSegment(first.reporting_item_code))
          || first.reporting_item_code,
      );
      aggregateColumns = uniqueNonEmpty(
        group.map((item) => {
          const sig = signalByItemCode.get(item.reporting_item_code);
          return normalizeColumnLabel(sig?.column || parseColumnFromCode(item.reporting_item_code) || item.impacted_reporting_field || "");
        }),
      );
    } else {
      // 父级 = 列度量名；子级 = 受影响的行
      const firstSig = signalByItemCode.get(first.reporting_item_code);
      aggregateTitle = normalizeColumnLabel(
        firstSig?.column || parseColumnFromCode(first.reporting_item_code) || first.impacted_reporting_field || first.reporting_item_code,
      );
      aggregateRows = uniqueNonEmpty(
        group.map((item) => {
          const sig = signalByItemCode.get(item.reporting_item_code);
          return normalizeRowLabel(
            sig?.row
              || item.reporting_item_name
              || formatRowLabel(rawRowSegment(item.reporting_item_code))
              || "",
          );
        }),
      );
    }

    result.push({
      ...first,
      aggregate_key: key,
      aggregate_title: aggregateTitle,
      aggregate_axis: axis,
      aggregate_rows: aggregateRows,
      aggregate_columns: aggregateColumns,
      aggregate_item_codes: codes,
      impacted_source_fields: sourceFields,
      impacted_lineage_roles: roles,
      impacted_reporting_field: first.impacted_reporting_field || "",
      impact_reason: group.map((item) => item.impact_reason).join("\n"),
    });
  }
  return result;
}

function parseIndicatorHint(hint?: string): { row: string; column: string } {
  const text = (hint ?? "").trim();
  const parts = text.split("×");
  if (parts.length >= 2) {
    return {
      row: normalizeRowLabel(parts[0]),
      column: normalizeColumnLabel(parts.slice(1).join("×")),
    };
  }
  return { row: "", column: "" };
}

function parseColumnFromCode(code?: string): string {
  const raw = String(code ?? "").split(".").slice(3).join(".");
  if (!raw) return "";
  const match = raw.match(/^\d+_0\.(.+)$/);
  const tail = match?.[1] ?? raw;
  if (tail.startsWith("单位_万元_E_")) return `E·${tail.replace(/^单位_万元_E_/, "").replaceAll("_", "·")}`;
  return tail.replace("_", "·").replaceAll("_", "");
}

function parseRowFromCode(code?: string): string {
  const match = String(code ?? "").match(/\.([0-9]+)_0\./);
  return match ? `${match[1]}.0` : "";
}

function normalizeRowLabel(value?: string): string {
  return String(value ?? "").replace(/\s+/g, "").trim();
}

function normalizeColumnLabel(value?: string): string {
  return String(value ?? "")
    .replace(/\s+/g, "")
    .replace(/·（/g, "（")
    .replace(/^单位：万元·E·/, "E·")
    .replace(/^单位_万元_E_/, "E·")
    .replaceAll("_", "·")
    .trim();
}

function uniqueNonEmpty(values: Array<unknown>): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const text = String(value ?? "").trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    result.push(text);
  }
  return result;
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

// ── 影响类型：8 种中文标签 + 颜色 ─────────────────────────────
const IMPACT_TYPE_LABELS: Record<string, string> = {
  INDICATOR_SCOPE:     "指标口径调整",
  REPORT_STRUCTURE:    "报表结构调整",
  SOURCE_FIELD_CHANGE: "源字段变更",
  ETL_LOGIC_CHANGE:    "加工逻辑变更",
  INSTITUTION_SCOPE:   "机构范围调整",
  VALIDATION_RULE:     "校验规则变更",
  SUPPLEMENT_DATA:     "补录要求新增",
  FREQUENCY_DEADLINE:  "频度/时限调整",
  // semantic fallback 类型
  SEMANTIC_FIELD_SCOPE:    "语义字段命中",
  COMPOSITE_SEMANTIC_SCOPE:"组合语义命中",
  INDICATOR_SCOPE_CHANGE:  "指标口径调整",
};
const IMPACT_TYPE_COLORS: Record<string, string> = {
  INDICATOR_SCOPE:     "amber",
  REPORT_STRUCTURE:    "blue",
  SOURCE_FIELD_CHANGE: "violet",
  ETL_LOGIC_CHANGE:    "orange",
  INSTITUTION_SCOPE:   "amber",
  VALIDATION_RULE:     "red",
  SUPPLEMENT_DATA:     "outline",
  FREQUENCY_DEADLINE:  "green",
};
const impactTypeLabel = (t: string) => IMPACT_TYPE_LABELS[t] ?? t;
const impactTypeColor = (t: string) => IMPACT_TYPE_COLORS[t] ?? "outline";

const riskLabel = (r: RiskLevel | string): string =>
  ({ LOW: "低", MEDIUM: "中", HIGH: "高" } as Record<string, string>)[r] ?? r;
const riskColor = (r: RiskLevel | string): string =>
  ({ LOW: "green", MEDIUM: "amber", HIGH: "red" } as Record<string, string>)[r] ?? "outline";
const changeTypeLabel = (t: TableChangeType): string =>
  ({ ADD: "新增", MODIFY: "修改", DELETE: "删除", SCOPE_ADJUST: "口径调整", INSTRUCTION_ADJUST: "说明调整", UNCLEAR: "待确认" } as Record<string, string>)[t] ?? t;
function padIdx(i: unknown): string { return String(Number(i) + 1).padStart(2, "0"); }
const changeTypeColor = (t: TableChangeType): string =>
  ({ ADD: "green", MODIFY: "amber", DELETE: "red", SCOPE_ADJUST: "amber", INSTRUCTION_ADJUST: "blue", UNCLEAR: "outline" } as Record<string, string>)[t] ?? "outline";

function effectiveChangeType(signal: { change_type: TableChangeType; evidence_text?: string; indicator_hint?: string }): TableChangeType {
  if (["INSTRUCTION_ADJUST", "UNCLEAR"].includes(signal.change_type)) {
    const body = (signal.evidence_text || "").replace(/-?\s*\[\s*(?:新增|删除)\s*\|[^\]]+\]\s*/g, "").trim();
    const businessText = `${signal.indicator_hint || ""} ${body}`;
    if (/\[\s*新增\s*\|/.test(signal.evidence_text || "") && /新增\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)/.test(body)) return "ADD";
    if (/\[\s*删除\s*\|/.test(signal.evidence_text || "") && /(?:删除|停报)\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)/.test(body)) return "DELETE";
    if (/(定义|公式|计算|口径|范围|填报|统计)/.test(businessText)) return "SCOPE_ADJUST";
  }
  return signal.change_type;
}
</script>

<style scoped>
/* ── 影响半径单元格 ─ */
.radius-popover {
  position: relative;
  display: inline-block;
}
.radius-cell {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  cursor: help;
  outline: none;
  border-radius: 7px;
}
.radius-cell:focus-visible {
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.22);
}
.radius-cell-unmapped {
  max-width: 160px;
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
.radius-badge.unmapped {
  background: rgba(100, 116, 139, 0.08);
  border-color: rgba(100, 116, 139, 0.25);
  color: rgba(71, 85, 105, 1);
}
.radius-badge.pending {
  background: rgba(234, 84, 4, 0.08);
  border-color: rgba(234, 84, 4, 0.22);
  color: rgba(194, 65, 12, 1);
}
.radius-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  z-index: 20;
  width: min(420px, 76vw);
  max-height: 360px;
  overflow: auto;
  padding: 12px;
  background: var(--surface, #fff);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.16);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-2px);
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.radius-popover:hover .radius-panel,
.radius-popover:focus-within .radius-panel {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}
.radius-panel-title {
  color: var(--ink-900);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 9px;
}
.radius-system + .radius-system {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.radius-system-head {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  margin-bottom: 6px;
}
.radius-system-name {
  color: var(--ink-900);
  font-size: 12px;
  font-weight: 650;
}
.radius-system-code,
.radius-system-count {
  color: var(--ink-500);
  font-size: 11px;
}
.radius-system-count {
  margin-left: auto;
}
.radius-field-list {
  display: grid;
  gap: 6px;
}
.radius-field-row {
  padding: 7px 8px;
  background: var(--surface-alt);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 6px;
}
.radius-field-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.radius-field-name {
  color: var(--ink-800);
  font-size: 12px;
  font-weight: 550;
}
.radius-field-code {
  margin-top: 3px;
  color: var(--ink-600);
  font-size: 11px;
  word-break: break-all;
}
.radius-field-meta {
  margin-top: 2px;
  color: var(--ink-400);
  font-size: 11px;
}
.impact-rows {
  color: var(--ink-600);
  font-size: 12px;
  line-height: 1.55;
  margin-top: 5px;
  max-width: 620px;
}
.impact-code-line {
  color: var(--ink-400);
  font-size: 11px;
  margin-top: 3px;
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

/* ── AI 分析中 banner ──────────────────────────────────────── */
.ai-analyzing-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #fff8f1 0%, #fffcfa 100%);
  border: 1px solid rgba(234, 84, 4, 0.2);
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(234, 84, 4, 0.08);
}
.ai-analyzing-icon {
  position: relative;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: var(--orange-600, #ea580c);
}
.ai-pulse {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(234, 84, 4, 0.12);
  animation: ai-pulse-ring 1.8s ease-out infinite;
}
@keyframes ai-pulse-ring {
  0%   { transform: scale(0.8); opacity: 0.9; }
  70%  { transform: scale(1.4); opacity: 0; }
  100% { transform: scale(1.4); opacity: 0; }
}
.ai-analyzing-text { flex: 1; min-width: 0; }
.ai-analyzing-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--orange-700, #c2410c);
  margin-bottom: 3px;
}
.ai-analyzing-sub {
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.5;
}
.ai-analyzing-dots {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.ai-analyzing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--orange-400, #fb923c);
  animation: ai-dot-bounce 1.2s ease-in-out infinite;
}
.ai-analyzing-dots span:nth-child(2) { animation-delay: 0.2s; }
.ai-analyzing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes ai-dot-bounce {
  0%, 80%, 100% { transform: translateY(0);    opacity: 0.4; }
  40%            { transform: translateY(-6px); opacity: 1; }
}

/* ── 影响类型列：AI 徽章 ────────────────────────────────────── */
.impact-type-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
  align-items: flex-start;
}
.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: 700;
  color: var(--orange-700, #c2410c);
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  border: 1px solid rgba(234, 84, 4, 0.25);
  border-radius: 6px;
  padding: 1px 6px;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
</style>
