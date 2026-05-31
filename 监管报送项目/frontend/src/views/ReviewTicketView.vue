<template>
  <div class="tv2-shell">
    <div class="row between tv2-page-head">
      <div>
        <div class="h-eyebrow">第 5 步 · 终</div>
        <h1 class="h-title">工单草稿审核</h1>
        <p class="h-sub">按后端生成的母子单、任务卡、质量评分和证据链逐项复核，缺失字段统一标注接口待完善。</p>
      </div>
      <button class="btn secondary sm" @click="$emit('back')">
        <ArrowLeft :size="12" />影响分析
      </button>
    </div>

    <section v-if="busy && !tickets.length" class="tv2-loading">
      <div class="tv2-hero compact">
        <span class="skbar title"></span>
        <span class="ai-bar"><Sparkles :size="12" /> 后端正在生成工单草稿</span>
      </div>
      <div class="tv2-tbl-wrap tv2-skeleton">
        <table class="tv2-tbl">
          <thead>
            <tr>
              <th class="col-check"></th>
              <th class="col-num">#</th>
              <th class="col-type">子单类型</th>
              <th>摘要</th>
              <th class="col-sys">责任系统</th>
              <th class="col-ar">A · 出口</th>
              <th class="col-ar">R · 执行</th>
              <th class="col-flags">标记</th>
              <th class="col-quality">质量</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="i in 6" :key="i">
              <td><span class="skbar box"></span></td>
              <td><span class="skbar short"></span></td>
              <td><span class="skbar mid"></span></td>
              <td><span class="skbar long"></span><span class="skbar mid sub"></span></td>
              <td><span class="skbar mid"></span></td>
              <td><span class="skbar short"></span></td>
              <td><span class="skbar short"></span></td>
              <td><span class="skbar short"></span></td>
              <td><span class="skbar mid"></span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else-if="!tickets.length" class="tv2-empty">
      <div class="glyph"><ClipboardList :size="28" /></div>
      <h3>还没有工单草稿</h3>
      <p>
        页面只展示后端接口返回的数据。当前 `workflow.ticket_drafts` 为空；
        执行规划、流转状态、导出记录等字段属于接口待完善。
      </p>
      <div class="pending-row">
        <span class="pending-chip">工单列表接口待完善</span>
        <span class="pending-chip">执行规划接口待完善</span>
        <span class="pending-chip">批量流转接口待完善</span>
      </div>
      <button class="btn primary" :disabled="busy" @click="$emit('generate')">
        <Sparkles :size="13" />{{ busy ? "生成中..." : "AI 生成工单草稿" }}
      </button>
    </section>

    <template v-else>
      <section class="tv2-hero">
        <div class="hero-row1">
          <div class="title-block">
            <h1>{{ parentTitle }}</h1>
            <div class="ticket-id">{{ parentTicketNo }} · 关联 {{ documentRef }}</div>
          </div>
          <div class="row action-row">
            <button
              class="btn ghost sm"
              :disabled="busy"
              title="基于最新影响分析重新生成，后端会覆盖当前草稿"
              @click="onRegenerate"
            >
              <RefreshCcw :size="12" />{{ busy ? "生成中..." : "重新生成" }}
            </button>
            <button class="btn secondary sm" title="导出接口待完善">
              <Download :size="12" />导出全部 <span class="mini-pending">待完善</span>
            </button>
            <button class="btn primary sm" title="正式流转接口待完善，当前仅返回工作台" @click="$emit('finish')">
              <Send :size="12" />提交流转 <span class="mini-pending light">待完善</span>
            </button>
          </div>
        </div>

        <div class="hero-row2">
          <span :class="['sev-pill', parentSeverity.level.toLowerCase()]">
            <span class="dot"></span>
            {{ parentSeverity.text }}
            <span class="score">{{ parentSeverity.scoreText }}</span>
          </span>
          <TypeChip :label="changeTypeLabel(parentChangeType)" :tone="typeTone(parentChangeType)" :dot="false" />
          <span class="sep-v"></span>
          <div class="tv2-owner">
            <div class="avatar">江</div>
            <div>
              <div class="nm">人员接口待完善</div>
              <div class="role">{{ roleLabel(parentTicket?.owner_role ?? "") }}</div>
            </div>
          </div>
          <span class="sep-v"></span>
          <div class="stat-mini"><span class="v">{{ childRows.length }}</span><span class="l">子单</span></div>
          <div class="stat-mini"><span class="v warn">{{ stats.pendingConfirm }}</span><span class="l">待确认</span></div>
          <div class="stat-mini"><span class="v bad">{{ stats.blocked }}</span><span class="l">阻塞</span></div>
          <div class="stat-mini"><span class="v">{{ stats.avgQuality }}</span><span class="l">平均质量</span></div>
        </div>

        <div class="tv2-signals">
          <span class="label">触发信号</span>
          <span v-for="signal in severitySignals" :key="signal" class="signal">{{ signal }}</span>
          <span v-if="!severitySignals.length" class="signal pending">严重度信号接口待完善</span>
          <span v-if="parentTicket?.severity_forced_reason" class="signal forced">
            强制升级：{{ parentTicket.severity_forced_reason }}
          </span>
        </div>
      </section>

      <nav class="sub-tabs">
        <button :class="['sub-tab', activeTab === 'plan' ? 'active' : '']" @click="activeTab = 'plan'">
          <Target :size="12" />执行规划
          <span v-if="stats.blocked" class="badge danger">{{ stats.blocked }} 阻塞</span>
        </button>
        <button :class="['sub-tab', activeTab === 'audit' ? 'active' : '']" @click="activeTab = 'audit'">
          <ClipboardList :size="12" />工单审核
          <span class="badge">{{ childRows.length }} 子单</span>
          <span v-if="stats.pendingConfirm" class="badge danger">{{ stats.pendingConfirm }} 待确认</span>
        </button>
      </nav>

      <section v-if="activeTab === 'plan'" class="ai-plan as-page">
        <ExecutionPlanCard
          v-if="validParentTaskId !== null"
          :key="validParentTaskId"
          :task-id="validParentTaskId"
        />
        <div v-else class="ai-plan-body">
          <p class="pending-text">母单 task_id 缺失，暂无法加载执行规划。</p>
        </div>
      </section>

      <section v-else class="audit-panel">
        <ImpactScopeReview
          v-if="validParentTaskId !== null"
          :task-id="validParentTaskId"
          :active-stage="auditStage"
          @stage-change="auditStage = $event"
          @confirmed="onImpactReviewConfirmed"
        />
        <div v-if="auditStage === 3" class="ticket-grid">
          <aside class="layer-panel">
            <div class="sec-h">
              <h2>分层工单</h2>
              <span class="line"></span>
              <span class="count">{{ childRows.length }} 个草稿</span>
            </div>
            <div class="ticket-list">
              <section v-for="group in ticketTypeGroups" :key="group.key" class="ticket-type-group">
                <button
                  type="button"
                  :class="['ticket-group-head', group.hasActive ? 'active' : '']"
                  data-test="ticket-type-group-toggle"
                  @click="toggleTypeGroup(group.key)"
                >
                  <span :class="['fold-caret', isTypeGroupCollapsed(group.key) ? 'collapsed' : '']"></span>
                  <TypeChip :label="group.label" :tone="group.tone" />
                  <span class="group-count">{{ group.rows.length }} 个子单</span>
                  <span v-if="group.pendingConfirm" class="group-flag">{{ group.pendingConfirm }} 待确认</span>
                </button>
                <div v-show="!isTypeGroupCollapsed(group.key)" class="ticket-group-body">
                  <article
                    v-for="row in group.rows"
                    :key="row.idKey"
                    :class="['ticket-item', activeRow?.idKey === row.idKey ? 'active' : '']"
                    @click="openId = row.idKey"
                  >
                    <div class="row between">
                      <span class="ticket-no">#{{ row.index + 1 }}</span>
                      <span class="tag outline mono">{{ priorityLabel(row) }}</span>
                    </div>
                    <div class="title">{{ row.summary }}</div>
                    <div class="desc">{{ row.caption }}</div>
                    <div class="ticket-team">{{ row.systemLabel }} · {{ row.executorLabel }}</div>
                  </article>
                </div>
              </section>
              <div v-if="!childRows.length" class="empty-ticket-list">
                子单拆分接口待完善：当前仅返回母单或旧版草稿。
              </div>
            </div>
          </aside>

          <article v-if="activeRow" class="ticket-doc">
            <div class="doc-head">
              <div>
                <div class="row tags-row">
                  <TypeChip :label="activeRow.typeLabel" :tone="activeRow.typeTone" />
                  <span class="tag outline mono">{{ priorityLabel(activeRow) }}</span>
                  <span :class="['quality-pill', qualityTone(activeRow.qualityScore)]">
                    质量 {{ activeRow.qualityScore || "待完善" }}
                  </span>
                </div>
                <h2>{{ activeRow.summary }}</h2>
                <div class="doc-meta">
                  TK-{{ activeRow.ticket.id ?? "接口待完善" }} · 关联 {{ documentRef }} · 责任 {{ activeRow.systemLabel }}
                </div>
              </div>
              <div class="row doc-actions">
                <button class="btn ghost sm" title="复制接口待完善"><FileText :size="12" /></button>
                <button class="btn secondary sm" title="编辑接口待完善"><Pencil :size="12" />编辑</button>
              </div>
            </div>

            <div class="doc-body">
              <section class="doc-section">
                <h4>背景与变更来源</h4>
                <div class="reg-summary">
                  <div class="reg-summary-label">监管原文摘要</div>
                  <div v-if="regulatorySummaryItems.length" class="reg-evidence-list">
                    <article v-for="item in regulatorySummaryItems" :key="item.key" class="reg-evidence-card">
                      <div v-if="item.label" class="reg-evidence-label">{{ item.label }}</div>
                      <div v-for="row in item.rows" :key="row.key" class="reg-evidence-row">
                        <span v-if="row.action" class="reg-evidence-meta">
                          {{ row.action }} · {{ row.author || "未知作者" }} · {{ row.date || "日期未知" }}
                        </span>
                        <span class="reg-evidence-body">
                          <template v-for="(segment, index) in row.segments" :key="index">
                            <mark
                              v-if="segment.operation"
                              :class="['reg-revision-mark', revisionClass(segment.operation)]"
                              :title="segment.title || revisionSegmentTitle(segment)"
                            >{{ segment.text }}</mark>
                            <mark v-else-if="segment.highlighted" class="reg-evidence-highlight">{{ segment.text }}</mark>
                            <span v-else>{{ segment.text }}</span>
                          </template>
                        </span>
                      </div>
                    </article>
                  </div>
                  <p v-else class="pending-text">监管原文摘要接口待完善。</p>
                </div>
              </section>

              <section class="doc-section">
                <h4>影响范围</h4>
                <div v-if="activeRow.scopeFields.length" class="impact-scope-block">
                  <div class="scope-field-list">
                    <div v-for="field in activeRow.scopeFields" :key="field.code" class="scope-field">
                      <code>{{ field.code }}</code>
                      <span v-if="field.name && field.name !== field.code" class="scope-field-name">{{ field.name }}</span>
                      <span v-else class="scope-field-name pending">中文名接口待完善</span>
                    </div>
                  </div>
                  <button
                    v-if="activeRow.assetEntries.length"
                    class="btn ghost sm lineage-btn"
                    type="button"
                    @click="lineageModalRowId = activeRow.idKey"
                  >
                    查看血缘
                  </button>
                </div>
                <p v-else class="pending-text">影响范围接口待完善。</p>
              </section>

              <section v-if="activeRow.ticket.business_note" class="doc-section">
                <h4>业务备注</h4>
                <p>{{ activeRow.ticket.business_note }}</p>
              </section>

              <section v-if="activeRow.ticket.id" class="doc-section sql-section">
                <h4>参考 SQL</h4>
                <ReferenceSqlCard :key="activeRow.ticket.id" :ticket-id="activeRow.ticket.id" />
              </section>

              <section class="doc-section">
                <h4>后端正文回退</h4>
                <pre class="ticket-content">{{ cleanedTicketContent(activeRow.ticket.content) || "content 接口待完善" }}</pre>
              </section>
            </div>
          </article>
        </div>
        <div v-else class="audit-stage-hint">
          完成业务勾选后，点击上方 <strong>3 拆分子单 · 派发</strong> 查看系统子单和工单详情。
        </div>
      </section>
    </template>

    <div
      v-if="lineageModalRow"
      class="ticket-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="血缘明细"
      @click.self="lineageModalRowId = null"
    >
      <article class="ticket-detail-modal lineage-modal">
        <header class="dr-head">
          <div class="row row1">
            <TypeChip :label="lineageModalRow.typeLabel" :tone="lineageModalRow.typeTone" />
            <span class="tag outline mono">{{ priorityLabel(lineageModalRow) }}</span>
            <span class="modal-spacer"></span>
            <button class="close" type="button" aria-label="关闭" @click="lineageModalRowId = null">×</button>
          </div>
          <h2>{{ lineageModalRow.summary }}</h2>
          <div class="summary">完整展示该子单关联的报送项、字段和血缘角色，便于需要时追溯。</div>
        </header>
        <div class="dr-body">
          <section class="dr-section">
            <h4>血缘明细</h4>
            <table class="detail-table asset-table">
              <thead>
                <tr>
                  <th>类型</th>
                  <th>编码</th>
                  <th>中文名</th>
                  <th>角色</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="entry in lineageModalRow.assetEntries" :key="entry.key">
                  <tr v-for="value in entry.values" :key="entry.key + value.code + value.name">
                    <td>{{ entry.key }}</td>
                    <td><code>{{ value.code || value.name }}</code></td>
                    <td>{{ value.name || "中文名接口待完善" }}</td>
                    <td>{{ value.role || "-" }}</td>
                  </tr>
                  <tr v-if="entry.hiddenCount" :key="entry.key + '-hidden'" class="note-row">
                    <td colspan="4">还有 {{ entry.hiddenCount }} 条 {{ entry.key }} 未在工单正文展开。</td>
                  </tr>
                </template>
              </tbody>
            </table>
          </section>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref, watch } from "vue";
import {
  ArrowLeft,
  ClipboardList,
  Download,
  FileText,
  Pencil,
  RefreshCcw,
  Send,
  Sparkles,
  Target,
} from "lucide-vue-next";
import ExecutionPlanCard from "@/components/ExecutionPlanCard.vue";
import ImpactScopeReview from "@/components/ImpactScopeReview.vue";
import ReferenceSqlCard from "@/components/ReferenceSqlCard.vue";
import type { TaskWorkflow, TicketDraft } from "@/types/api";
import { formatReadableEvidence, normalizeEvidenceText, shortenText, type EvidenceSegment, type ReadableEvidenceRow } from "@/utils/evidence";

const props = defineProps<{
  workflow: TaskWorkflow | null;
  busy: boolean;
}>();

const emit = defineEmits<{ back: []; finish: []; generate: []; "impact-review-confirmed": [] }>();

interface EvidenceRef {
  src: string;
  text: string;
}

interface HistoryCase {
  id: string;
  title: string;
  date: string;
  match: string | number;
  rationale: string;
  matchedCodes: string[];
}

interface AssetValue {
  code: string;
  name: string;
  role: string;
}

interface AssetEntry {
  key: string;
  values: AssetValue[];
  hiddenCount: number;
  note: string;
}

interface RegulatorySummaryItem {
  key: string;
  label: string;
  rows: ReadableEvidenceRow[];
}

interface ScopeField {
  code: string;
  name: string;
}

interface TicketRow {
  ticket: TicketDraft;
  idKey: string;
  index: number;
  typeLabel: string;
  typeTone: string;
  summary: string;
  caption: string;
  systemLabel: string;
  ownerLabel: string;
  executorLabel: string;
  codes: string[];
  mustDo: string[];
  mustConfirm: string[];
  outputs: string[];
  acceptance: string[];
  blockers: string[];
  evidence: EvidenceRef[];
  history: HistoryCase[];
  assetEntries: AssetEntry[];
  scopeFields: ScopeField[];
  qualityScore: number;
  qualityFlags: string[];
}

interface TicketTypeGroup {
  key: string;
  label: string;
  tone: string;
  rows: TicketRow[];
  hasActive: boolean;
  pendingConfirm: number;
}

const activeTab = ref<"plan" | "audit">("plan");
const openId = ref<string | null>(null);
const collapsedTypeGroups = ref<Set<string>>(new Set());
const lineageModalRowId = ref<string | null>(null);
const auditStage = ref<2 | 3>(2);

const tickets = computed(() => props.workflow?.ticket_drafts ?? []);
const parentTickets = computed(() => tickets.value.filter((ticket) => ticket.ticket_role === "PARENT"));
const parentTicket = computed(() => parentTickets.value[0] ?? null);
const childTickets = computed(() => tickets.value.filter((ticket) => ticket.ticket_role === "CHILD"));

const childRows = computed<TicketRow[]>(() =>
  childTickets.value.map((ticket, index) => normalizeTicket(ticket, index)),
);

const selectedRow = computed(() => childRows.value.find((row) => row.idKey === openId.value) ?? null);
const activeRow = computed(() => selectedRow.value ?? childRows.value[0] ?? null);
const lineageModalRow = computed(() => childRows.value.find((row) => row.idKey === lineageModalRowId.value) ?? null);
const blockedRows = computed(() => childRows.value.filter((row) => row.blockers.length > 0));
const ticketTypeGroups = computed<TicketTypeGroup[]>(() => {
  const groups = new Map<string, TicketRow[]>();
  for (const row of childRows.value) {
    const key = row.typeLabel || "未分类";
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return Array.from(groups.entries()).map(([key, rows]) => ({
    key,
    label: key,
    tone: rows[0]?.typeTone ?? "slate",
    rows,
    hasActive: rows.some((row) => row.idKey === activeRow.value?.idKey),
    pendingConfirm: rows.filter((row) => row.mustConfirm.length > 0 || row.ticket.business_signoff_required).length,
  }));
});

const stats = computed(() => {
  const scored = childRows.value.filter((row) => row.qualityScore > 0);
  const avgQuality = scored.length
    ? Math.round(scored.reduce((sum, row) => sum + row.qualityScore, 0) / scored.length).toString()
    : "待完善";
  return {
    pendingConfirm: childRows.value.filter((row) => row.mustConfirm.length > 0 || row.ticket.business_signoff_required).length,
    blocked: blockedRows.value.length,
    avgQuality,
  };
});

const parentTitle = computed(() => parentTicket.value?.title || `${props.workflow?.document?.title || "母单标题"}接口待完善`);
const parentTicketNo = computed(() => (parentTicket.value?.id ? `TKM-${parentTicket.value.id}` : "母单编号接口待完善"));
const validParentTaskId = computed(() => {
  const taskId = parentTicket.value?.task_id;
  return typeof taskId === "number" && Number.isFinite(taskId) && taskId > 0 ? taskId : null;
});
const documentRef = computed(() => {
  const doc = props.workflow?.document;
  if (!doc) return "发文接口待完善";
  return `DOC-${doc.id} · ${doc.title || doc.filename || "标题接口待完善"}`;
});
const parentChangeType = computed(() => parentTicket.value?.change_ticket_type ?? "");
const severitySignals = computed(() => textArray(parentTicket.value?.severity_signals));
const regulatorySummaryItems = computed(() => buildRegulatorySummaryItems(props.workflow, parentTicket.value, activeRow.value));
const parentSeverity = computed(() => {
  const level = parentTicket.value?.severity_level || "L?";
  const score = parentTicket.value?.severity_score ?? 0;
  return {
    level: parentTicket.value?.severity_level || "l0",
    text: level === "L?" ? "等级接口待完善" : severityLabel(level),
    scoreText: score ? `${score} 分` : "评分接口待完善",
  };
});

function onRegenerate(): void {
  if (props.busy) return;
  const ok = window.confirm("确定基于最新影响分析重新生成工单吗？\n\n当前任务下的所有母单和子单草稿（含人工修改）将被覆盖删除。");
  if (ok) emit("generate");
}

function onImpactReviewConfirmed(): void {
  auditStage.value = 3;
  emit("impact-review-confirmed");
}

function priorityLabel(row: TicketRow): string {
  if (row.blockers.length) return "P0";
  if (row.ticket.business_signoff_required || row.mustConfirm.length) return "P1";
  return row.qualityScore > 0 && row.qualityScore < 80 ? "P1" : "P2";
}

function revisionClass(operation: NonNullable<EvidenceSegment["operation"]>): string {
  return {
    ADD: "reg-revision-add",
    DELETE: "reg-revision-delete",
    MODIFY: "reg-revision-modify",
    ADJUST: "reg-revision-modify",
  }[operation];
}

function revisionSegmentTitle(segment: EvidenceSegment): string {
  const action = {
    ADD: "新增",
    DELETE: "删除",
    MODIFY: "修改",
    ADJUST: "调整",
  }[segment.operation ?? "ADJUST"];
  return [action, segment.author || "未知作者", segment.date || "日期未知"].join(" · ");
}

function isTypeGroupCollapsed(key: string): boolean {
  return collapsedTypeGroups.value.has(key);
}

function toggleTypeGroup(key: string): void {
  const next = new Set(collapsedTypeGroups.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  collapsedTypeGroups.value = next;
}

function normalizeTicket(ticket: TicketDraft, index: number): TicketRow {
  const codes = textArray(ticket.related_impact_codes);
  const summary = ticket.summary || firstContentLine(ticket.content) || ticket.title || "摘要接口待完善";
  const actionLabel = actionTypeLabel(ticket.action_ticket_type);
  return {
    ticket,
    idKey: ticket.id ? String(ticket.id) : `tmp-${index}-${ticket.title}`,
    index,
    typeLabel: actionLabel,
    typeTone: actionTone(ticket.action_ticket_type),
    summary,
    caption: codes.length ? codes.join(" · ") : `${actionLabel} · 关联报送项接口待完善`,
    systemLabel: systemLabel(ticket.responsible_system),
    ownerLabel: roleLabel(ticket.owner_role),
    executorLabel: roleLabel(ticket.executor_role),
    codes,
    mustDo: textArray(ticket.must_do),
    mustConfirm: textArray(ticket.must_confirm),
    outputs: textArray(ticket.output_artifacts),
    acceptance: textArray(ticket.acceptance_criteria_structured),
    blockers: textArray(ticket.blockers),
    evidence: evidenceRefs(ticket.evidence_refs),
    history: historyCases(ticket.historical_cases),
    assetEntries: assetEntries(ticket.affected_assets),
    scopeFields: scopeFields(ticket.affected_assets),
    qualityScore: ticket.quality_score || 0,
    qualityFlags: textArray(ticket.quality_flags),
  };
}

function firstContentLine(value: string): string {
  return value
    .split(/\n+/)
    .map((line) => line.replace(/^#+\s*/, "").trim())
    .find(Boolean) ?? "";
}

function buildRegulatorySummaryItems(workflow: TaskWorkflow | null, parent: TicketDraft | null, active: TicketRow | null): RegulatorySummaryItem[] {
  const relatedScope = active ? ticketScope(active.ticket) : null;
  const hasStructuredEvidence = Boolean(
    workflow?.document_profile?.change_signals?.length || workflow?.reporting_candidates?.length,
  );
  const items: RegulatorySummaryItem[] = [];
  const signals = workflow?.document_profile?.change_signals ?? [];
  const hasDirectSignalMatch = Boolean(
    relatedScope && signals.some((signal) => isDirectChangeSignalMatch(signal, relatedScope.itemCodes)),
  );
  for (const signal of signals) {
    const documentContextSignal = isDocumentLevelRevisionSignal(signal);
    if (relatedScope) {
      const related = hasDirectSignalMatch
        ? isDirectChangeSignalMatch(signal, relatedScope.itemCodes)
        : isRelatedChangeSignal(signal, relatedScope);
      if (!related && !documentContextSignal) continue;
    }
    const label = [signal.table_code, signal.indicator_hint].map((item) => item.trim()).filter(Boolean).join(" · ");
    const rows = formatReadableEvidence(signal.evidence_text, [], { contextualRevisions: true });
    if (!rows.length) continue;
    const item = { key: `signal-${items.length}-${label}`, label, rows };
    if (documentContextSignal) items.unshift(item);
    else items.push(item);
  }

  if (!items.length) {
    for (const candidate of workflow?.reporting_candidates ?? []) {
      if (relatedScope?.itemCodes.size && !relatedScope.itemCodes.has(normalizeScopeCode(candidate.reporting_item_code))) {
        continue;
      }
      const label = [candidate.reporting_object_code, candidate.reporting_item_code].map((item) => item.trim()).filter(Boolean).join(" · ");
      const rows = formatReadableEvidence(candidate.evidence_text, [], { contextualRevisions: true });
      if (!rows.length) continue;
      items.push({ key: `candidate-${items.length}-${label}`, label, rows });
    }
  }

  if (!items.length && hasStructuredEvidence && active?.evidence.length) {
    for (const evidence of active.evidence) {
      const rows = formatReadableEvidence(evidence.text, [], { contextualRevisions: true });
      if (rows.length) items.push({ key: `active-evidence-${items.length}`, label: evidence.src, rows });
    }
  }
  if (!items.length && !hasStructuredEvidence) {
    items.push(...summaryTextItems(splitSummaryText(workflow?.document_profile?.evidence_text ?? "")));
  }
  if (!items.length && !hasStructuredEvidence) {
    items.push(...summaryTextItems(splitSummaryText(workflow?.document_profile?.reason ?? "")));
  }
  if (!items.length) {
    items.push(...summaryTextItems(splitSummaryText(active?.ticket.content || active?.ticket.summary || parent?.summary || parent?.content || "")));
  }

  return uniqueSummaryItems(items).slice(0, 4);
}

function splitSummaryText(value: string): string[] {
  const cleaned = cleanedTicketContent(value);
  if (!cleaned) return [];
  return cleaned
    .split(/\n+|；+/)
    .map((item) => cleanRegulatoryEvidence(item))
    .filter(Boolean);
}

function summaryTextItems(items: string[]): RegulatorySummaryItem[] {
  return items.map((item, index) => ({
    key: `fallback-${index}-${item}`,
    label: "",
    rows: formatReadableEvidence(item),
  })).filter((item) => item.rows.length);
}

function uniqueSummaryItems(items: RegulatorySummaryItem[]): RegulatorySummaryItem[] {
  const unique: RegulatorySummaryItem[] = [];
  for (const item of items) {
    const cleaned = itemSummaryText(item);
    if (!cleaned) continue;
    const existing = unique.find((candidate) => areOverlappingSummaryItems(candidate, item));
    if (existing) {
      existing.label = mergeSummaryLabels(existing.label, item.label);
      existing.rows = mergeEvidenceRows(existing.rows, item.rows);
      continue;
    }
    unique.push(item);
  }
  return unique;
}

function itemSummaryText(item: RegulatorySummaryItem): string {
  return normalizeScopeCode(item.rows.map((row) => row.text).join("；"));
}

function areOverlappingSummaryItems(left: RegulatorySummaryItem, right: RegulatorySummaryItem): boolean {
  const a = itemSummaryText(left);
  const b = itemSummaryText(right);
  if (!a || !b) return false;
  if (a === b || a.includes(b) || b.includes(a)) return true;
  const common = longestCommonSubstringLength(a, b);
  return common >= Math.min(80, Math.floor(Math.min(a.length, b.length) * 0.45));
}

function longestCommonSubstringLength(a: string, b: string): number {
  const previous = new Array(b.length + 1).fill(0);
  let best = 0;
  for (let i = 1; i <= a.length; i += 1) {
    let diagonal = 0;
    for (let j = 1; j <= b.length; j += 1) {
      const old = previous[j];
      previous[j] = a[i - 1] === b[j - 1] ? diagonal + 1 : 0;
      if (previous[j] > best) best = previous[j];
      diagonal = old;
    }
  }
  return best;
}

function mergeSummaryLabels(left: string, right: string): string {
  const labels = [...left.split(" / "), ...right.split(" / ")]
    .map((label) => label.trim())
    .filter(Boolean);
  return Array.from(new Set(labels)).join(" / ");
}

function mergeEvidenceRows(left: ReadableEvidenceRow[], right: ReadableEvidenceRow[]): ReadableEvidenceRow[] {
  const rows = [...left];
  for (const row of right) {
    const text = normalizeScopeCode(row.text);
    const existing = rows.find((candidate) => {
      const candidateText = normalizeScopeCode(candidate.text);
      if (candidateText === text) return true;
      if (candidate.hasRevisionMarks && row.hasRevisionMarks) {
        const common = longestCommonSubstringLength(candidateText, text);
        const threshold = Math.min(80, Math.floor(Math.min(candidateText.length, text.length) * 0.6));
        return candidateText.includes(text) || text.includes(candidateText) || common >= threshold;
      }
      return candidateText.includes(text) || text.includes(candidateText);
    });
    if (!existing) rows.push(row);
    else if (!existing.hasRevisionMarks && row.hasRevisionMarks) {
      const index = rows.indexOf(existing);
      rows[index] = row;
    } else if (
      existing.hasRevisionMarks
      && row.hasRevisionMarks
      && text.length > normalizeScopeCode(existing.text).length
      && sameRevisionOperationSet(existing, row)
    ) {
      const index = rows.indexOf(existing);
      rows[index] = row;
    } else if (existing.hasRevisionMarks && row.hasRevisionMarks && !sameRevisionOperationSet(existing, row)) {
      rows.push(row);
    }
  }
  return rows;
}

function sameRevisionOperationSet(left: ReadableEvidenceRow, right: ReadableEvidenceRow): boolean {
  const leftOps = new Set(left.segments.map((segment) => segment.operation).filter(Boolean));
  const rightOps = new Set(right.segments.map((segment) => segment.operation).filter(Boolean));
  if (leftOps.size !== rightOps.size) return false;
  return [...leftOps].every((operation) => rightOps.has(operation));
}

function cleanedTicketContent(value: string): string {
  return value
    .split(/\n+/)
    .map((line) => cleanRegulatoryEvidence(line))
    .filter(Boolean)
    .join("\n");
}

function cleanRegulatoryEvidence(value: string): string {
  const leadingMarker = value.match(/^\s*[-*]?\s*\[\s*(新增|删除|修改|调整)\s*\|[^\]]+\]\s*/);
  const markerPrefix = leadingMarker ? `${leadingMarker[1]}：` : "";
  const withoutLeading = leadingMarker ? value.slice(leadingMarker[0].length) : value;
  return normalizeEvidenceText(`${markerPrefix}${withoutLeading}`
    .replace(/^\s{0,3}#{1,6}\s*/g, "")
    .replace(/^\s*[-*]\s+/g, "")
    .replace(/\s*\[\s*(?:新增|删除|修改|调整)\s*\|[^\]]+\]\s*/g, ""));
}

function shortenSummary(value: string, maxLength = 180): string {
  return shortenText(value, maxLength);
}

function parseJson(value: string | null | undefined): unknown {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function ticketScope(ticket: TicketDraft): { itemCodes: Set<string>; fieldCodes: Set<string>; terms: string[] } {
  const itemCodes = new Set(textArray(ticket.related_impact_codes).map(normalizeScopeCode).filter(Boolean));
  const fieldCodes = new Set<string>();
  const terms: string[] = [];
  const parsed = parseJson(ticket.affected_assets);
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    for (const [key, raw] of Object.entries(parsed as Record<string, unknown>)) {
      const normalizedKey = normalizeAssetKey(key);
      const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
      for (const value of values) {
        const asset = assetValue(normalizedKey, value);
        if (!asset.code && !asset.name) continue;
        if (isReportingItemKey(normalizedKey)) {
          const itemCode = normalizeScopeCode(asset.code);
          if (itemCode) itemCodes.add(itemCode);
        }
        if (isFieldKey(normalizedKey)) {
          const fieldCode = normalizeScopeCode(asset.code);
          if (fieldCode) fieldCodes.add(fieldCode);
        }
        terms.push(asset.code, asset.name);
      }
    }
  }
  terms.push(ticket.summary, ticket.title);
  return {
    itemCodes,
    fieldCodes,
    terms: uniqueScopeTerms(terms),
  };
}

function isRelatedChangeSignal(
  signal: NonNullable<TaskWorkflow["document_profile"]>["change_signals"][number],
  scope: { itemCodes: Set<string>; fieldCodes: Set<string>; terms: string[] },
): boolean {
  const signalItemCodes = new Set<string>();
  const matchedItem = normalizeScopeCode(signal.matched_item_code ?? "");
  if (matchedItem) signalItemCodes.add(matchedItem);
  for (const code of signal.composite_match?.reporting_item_codes ?? []) {
    const normalized = normalizeScopeCode(code);
    if (normalized) signalItemCodes.add(normalized);
  }
  if ([...signalItemCodes].some((code) => scope.itemCodes.has(code))) return true;

  const signalFieldCodes = new Set<string>();
  for (const code of signal.composite_match?.measure_field_codes ?? []) {
    const normalized = normalizeScopeCode(code);
    if (normalized) signalFieldCodes.add(normalized);
  }
  for (const code of signal.composite_match?.condition_field_codes ?? []) {
    const normalized = normalizeScopeCode(code);
    if (normalized) signalFieldCodes.add(normalized);
  }
  for (const field of signal.composite_match?.measure_fields ?? []) {
    const normalized = normalizeScopeCode(field.field_code);
    if (normalized) signalFieldCodes.add(normalized);
  }
  for (const condition of signal.composite_match?.conditions ?? signal.composite_match?.filter_conditions ?? []) {
    const normalized = normalizeScopeCode(condition.field_code);
    if (normalized) signalFieldCodes.add(normalized);
  }
  if ([...signalFieldCodes].some((code) => scope.fieldCodes.has(code))) return true;

  const haystack = [
    signal.table_code,
    signal.section_hint,
    signal.indicator_hint,
    signal.evidence_text,
    signal.composite_match?.indicator_hint,
    signal.composite_match?.measure_phrase,
    signal.composite_match?.condition_phrase,
    signal.composite_match?.evidence_text,
  ].map(normalizeScopeCode).join(" ");
  return scope.terms.some((term) => term && haystack.includes(normalizeScopeCode(term)));
}

function isDirectChangeSignalMatch(
  signal: NonNullable<TaskWorkflow["document_profile"]>["change_signals"][number],
  itemCodes: Set<string>,
): boolean {
  const matchedItem = normalizeScopeCode(signal.matched_item_code ?? "");
  return Boolean(matchedItem && itemCodes.has(matchedItem));
}

function isDocumentLevelRevisionSignal(
  signal: NonNullable<TaskWorkflow["document_profile"]>["change_signals"][number],
): boolean {
  const hint = `${signal.section_hint} ${signal.indicator_hint}`;
  return /填报机构|机构范围|一般说明/.test(hint) && /\[\s*(?:新增|删除|修改|调整)\s*\|/.test(signal.evidence_text);
}

function uniqueScopeTerms(values: string[]): string[] {
  const seen = new Set<string>();
  const terms: string[] = [];
  for (const value of values) {
    const normalized = normalizeScopeCode(value);
    if (!normalized || normalized.length < 2 || seen.has(normalized)) continue;
    seen.add(normalized);
    terms.push(value.trim());
  }
  return terms;
}

function normalizeScopeCode(value: unknown): string {
  return String(value ?? "").trim().toLowerCase().replace(/\s+/g, "");
}

function textArray(value: string | null | undefined): string[] {
  const parsed = parseJson(value);
  if (Array.isArray(parsed)) {
    return parsed
      .flatMap((item) => {
        if (typeof item === "string") return [item];
        if (item && typeof item === "object") return [Object.values(item).join(" · ")];
        return [];
      })
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (typeof parsed === "string" && parsed && parsed !== "[]" && parsed !== "{}") return [parsed];
  return [];
}

function scopeFields(value: string): ScopeField[] {
  const entries = assetEntries(value);
  const fields = entries
    .filter((entry) => isFieldLabel(entry.key))
    .flatMap((entry) => entry.values)
    .filter((value) => value.code || value.name);
  const seen = new Set<string>();
  const result: ScopeField[] = [];
  for (const field of fields) {
    const key = field.code || field.name;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push({ code: field.code || field.name, name: field.name });
  }
  return result;
}

function evidenceRefs(value: string): EvidenceRef[] {
  const parsed = parseJson(value);
  if (!Array.isArray(parsed)) return [];
  return parsed.map((item) => {
    if (item && typeof item === "object") {
      const record = item as Record<string, unknown>;
      return {
        src: String(record.src ?? record.source ?? record.ref ?? ""),
        text: String(record.text ?? record.evidence ?? record.content ?? ""),
      };
    }
    return { src: "", text: String(item ?? "") };
  });
}

function historyCases(value: string): HistoryCase[] {
  const parsed = parseJson(value);
  if (!Array.isArray(parsed)) return [];
  return parsed.map((item) => {
    if (item && typeof item === "object") {
      const record = item as Record<string, unknown>;
      return {
        id: String(record.id ?? ""),
        title: String(record.title ?? record.name ?? ""),
        date: String(record.date ?? record.decided_at ?? record.created_at ?? ""),
        match: (record.match ?? record.reuse_score ?? record.score ?? "") as string | number,
        rationale: String(record.decision_rationale ?? record.rationale ?? record.summary ?? ""),
        matchedCodes: Array.isArray(record.matched_item_codes)
          ? record.matched_item_codes.map((code) => String(code)).filter(Boolean)
          : [],
      };
    }
    return { id: "", title: String(item ?? ""), date: "", match: "", rationale: "", matchedCodes: [] };
  });
}

function assetEntries(value: string): AssetEntry[] {
  const parsed = parseJson(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return [];
  return Object.entries(parsed as Record<string, unknown>)
    .map(([key, raw]) => {
      const normalizedKey = normalizeAssetKey(key);
      const values = Array.isArray(raw)
        ? raw.map((item) => assetValue(normalizedKey, item)).filter((item) => item.code || item.name)
        : raw ? [assetValue(normalizedKey, raw)].filter((item) => item.code || item.name) : [];
      return {
        key: assetLabel(normalizedKey),
        values,
        hiddenCount: 0,
        note: assetNote(normalizedKey, values),
      };
    })
    .filter((entry) => entry.values.length);
}

const ASSET_LABELS: Record<string, string> = {
  REPORTING_ITEM: "受影响报送项",
  REPORTING_ITEMS: "受影响报送项",
  REPORTING_ITEM_CODE: "受影响报送项",
  REPORTING_ITEM_CODES: "受影响报送项",
  REPORTING_FIELD: "报送字段",
  REPORTING_FIELDS: "报送字段",
  REPORTING_FIELD_CODE: "报送字段",
  REPORTING_FIELD_CODES: "报送字段",
  SOURCE_FIELD: "源字段",
  SOURCE_FIELDS: "源字段",
  SOURCE_FIELD_CODE: "源字段",
  SOURCE_FIELD_CODES: "源字段",
  LINEAGE_ROLE: "血缘角色",
  LINEAGE_ROLES: "血缘角色",
};

function isReportingItemKey(value: string): boolean {
  return [
    "REPORTING_ITEM",
    "REPORTING_ITEMS",
    "REPORTING_ITEM_CODE",
    "REPORTING_ITEM_CODES",
  ].includes(normalizeAssetKey(value));
}

function isFieldKey(value: string): boolean {
  return [
    "REPORTING_FIELD",
    "REPORTING_FIELDS",
    "REPORTING_FIELD_CODE",
    "REPORTING_FIELD_CODES",
    "SOURCE_FIELD",
    "SOURCE_FIELDS",
    "SOURCE_FIELD_CODE",
    "SOURCE_FIELD_CODES",
  ].includes(normalizeAssetKey(value));
}

function isFieldLabel(value: string): boolean {
  return ["报送字段", "源字段"].includes(value);
}

const LINEAGE_ROLE_LABELS: Record<string, string> = {
  REPORT_FIELD: "报送结果字段",
  REPORTING_FIELD: "报送结果字段",
  SOURCE_FIELD: "源数据字段",
  DIMENSION_FIELD: "维度字段",
  FILTER_FIELD: "过滤条件字段",
};

function assetLabel(value: string): string {
  return ASSET_LABELS[normalizeAssetKey(value)] || value;
}

function assetNote(value: string, values: AssetValue[]): string {
  const normalizedKey = normalizeAssetKey(value);
  const needsName = values.some((item) => !item.name && item.code);
  if (needsName && (normalizedKey.includes("CODE") || normalizedKey.includes("FIELD") || normalizedKey.includes("ITEM"))) {
    return "中文名称接口待完善，当前后端仅返回技术编码";
  }
  return "";
}

function assetValue(key: string, raw: unknown): AssetValue {
  if (raw && typeof raw === "object") {
    const record = raw as Record<string, unknown>;
    const code = String(record.code ?? record.value ?? record.id ?? "").trim();
    const name = String(record.name ?? record.label ?? record.title ?? "").trim();
    const role = String(record.role ?? record.lineage_role ?? "").trim();
    return {
      code: code || name,
      name,
      role: role ? displayAssetValue("LINEAGE_ROLE", role) : "",
    };
  }
  const value = String(raw ?? "").trim();
  if (!value) return { code: "", name: "", role: "" };
  if (normalizeAssetKey(key) === "LINEAGE_ROLE" || normalizeAssetKey(key) === "LINEAGE_ROLES") {
    return {
      code: value,
      name: displayAssetValue(key, value),
      role: "",
    };
  }
  return { code: value, name: "", role: "" };
}

function displayAssetValue(key: string, value: string): string {
  const normalizedKey = normalizeAssetKey(key);
  const normalizedValue = normalizeAssetKey(value);
  if (normalizedKey === "LINEAGE_ROLE" || normalizedKey === "LINEAGE_ROLES") {
    return LINEAGE_ROLE_LABELS[normalizedValue] || value;
  }
  return value;
}

function normalizeAssetKey(value: string): string {
  return value.trim().toUpperCase().replace(/[\s-]+/g, "_");
}

const CHANGE_TYPE_LABELS: Record<string, string> = {
  REPORT_ONBOARDING: "报表新增",
  REPORT_REVISION: "报表修订",
  SCOPE_ADJUSTMENT: "口径/范围调整",
  INDICATOR_ADD: "指标新增",
  VALIDATION_CHANGE: "校验规则变更",
  INSTITUTION_FREQ_CHANGE: "机构/频度调整",
  REPORT_DECOMMISSION: "报表停报",
  MANUAL_REVIEW: "人工复核",
};

const ACTION_TYPE_LABELS: Record<string, string> = {
  SCOPE_CONFIRM: "口径确认",
  DATA_MAPPING: "数据映射",
  LINEAGE_BUILD: "血缘建链",
  CATALOG_INIT: "目录初始化",
  SOURCE_SYSTEM_CHANGE: "源系统改造",
  REPORT_PROCESSING: "报送加工",
  VALIDATION_RULE: "校验规则",
  HISTORICAL_DATA: "历史数据",
  TASK_INIT: "任务初始化",
  TEST_ACCEPTANCE: "测试验收",
  ARCHIVE_REVIEW: "归档复盘",
  MERGED_LIGHTWEIGHT: "合并轻量",
};

const ROLE_LABELS: Record<string, string> = {
  BUSINESS: "业务",
  REPORTING_MGMT: "报送管理",
  DATA_GOVERNANCE: "数据治理",
  SOURCE_SYSTEM: "源系统",
  DATA_DEV: "数据开发",
  DATA_QUALITY: "数据质量",
  QA: "测试",
  COMPLIANCE: "合规",
};

const SYSTEM_LABELS: Record<string, string> = {
  REG_REPORTING_SYSTEM: "监管报送系统",
  DATA_GOVERNANCE_PLATFORM: "数据治理平台",
  DATA_MART_ETL: "数据集市 ETL",
  SOURCE_SYSTEM: "源系统",
  DATA_QUALITY_PLATFORM: "数据质量平台",
  TEST_ACCEPTANCE: "测试验收",
  KNOWLEDGE_ARCHIVE: "知识归档",
};

function changeTypeLabel(value: string): string {
  return CHANGE_TYPE_LABELS[value] || value || "母单类型接口待完善";
}

function actionTypeLabel(value: string): string {
  return ACTION_TYPE_LABELS[value] || value || "子单类型接口待完善";
}

function roleLabel(value: string): string {
  return ROLE_LABELS[value] || value || "角色接口待完善";
}

function systemLabel(value: string): string {
  return SYSTEM_LABELS[value] || value || "责任系统接口待完善";
}

function severityLabel(value: string): string {
  return ({ L1: "L1 · 微调", L2: "L2 · 轻量", L3: "L3 · 标准", L4: "L4 · 重大" } as Record<string, string>)[value] || value;
}

function typeTone(value: string): string {
  return ({
    REPORT_ONBOARDING: "green",
    REPORT_REVISION: "orange",
    SCOPE_ADJUSTMENT: "violet",
    INDICATOR_ADD: "blue",
    VALIDATION_CHANGE: "amber",
    INSTITUTION_FREQ_CHANGE: "blue",
    REPORT_DECOMMISSION: "red",
    MANUAL_REVIEW: "slate",
  } as Record<string, string>)[value] || "slate";
}

function actionTone(value: string): string {
  return ({
    SCOPE_CONFIRM: "violet",
    DATA_MAPPING: "blue",
    LINEAGE_BUILD: "blue",
    CATALOG_INIT: "orange",
    SOURCE_SYSTEM_CHANGE: "red",
    REPORT_PROCESSING: "green",
    VALIDATION_RULE: "amber",
    HISTORICAL_DATA: "amber",
    TASK_INIT: "orange",
    TEST_ACCEPTANCE: "green",
    ARCHIVE_REVIEW: "slate",
    MERGED_LIGHTWEIGHT: "slate",
  } as Record<string, string>)[value] || "slate";
}

function qualityTone(score: number): string {
  if (!score) return "pending";
  if (score >= 90) return "";
  if (score >= 70) return "amber";
  return "red";
}

watch(
  childRows,
  (rows) => {
    const exists = rows.some((row) => row.idKey === openId.value);
    if (!exists) openId.value = null;
  },
  { immediate: true },
);

const TypeChip = defineComponent({
  props: {
    label: { type: String, required: true },
    tone: { type: String, default: "slate" },
    dot: { type: Boolean, default: true },
  },
  setup(props) {
    return () => h("span", { class: ["type-chip", props.tone] }, [
      props.dot ? h("span", { class: "dot" }) : null,
      props.label,
    ]);
  },
});

</script>

<style scoped>
.tv2-shell { display: flex; flex-direction: column; gap: 14px; }
.tv2-page-head { align-items: flex-start; }
.action-row { gap: 6px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
.btn svg { flex-shrink: 0; }

.tv2-hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 16px 20px;
}
.tv2-hero.compact { display: flex; justify-content: space-between; gap: 14px; align-items: center; }
.tv2-hero .hero-row1 {
  display: flex; align-items: flex-start; gap: 16px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px dashed var(--border);
}
.tv2-hero .title-block { flex: 1; min-width: 0; }
.tv2-hero h1 {
  margin: 0; font-size: 20px; font-weight: 700; color: var(--ink-900);
  letter-spacing: -0.3px; line-height: 1.35;
}
.tv2-hero .ticket-id { font-family: var(--font-mono); font-size: 12px; color: var(--ink-500); margin-top: 6px; }
.hero-row2 { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.sep-v { width: 1px; height: 22px; background: var(--border); }
.stat-mini { display: flex; flex-direction: column; line-height: 1.2; }
.stat-mini .v { font-family: var(--font-mono); font-size: 16px; font-weight: 700; color: var(--ink-900); letter-spacing: -0.3px; }
.stat-mini .v.bad { color: var(--red); }
.stat-mini .v.warn { color: var(--amber); }
.stat-mini .l { font-size: 10.5px; color: var(--ink-500); letter-spacing: 0.3px; text-transform: uppercase; font-weight: 500; margin-top: 2px; }

.sev-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px 3px 8px; border-radius: 999px;
  font-size: 12px; font-weight: 600; font-family: var(--font-mono);
  background: var(--amber-bg); color: var(--amber);
  border: 1px solid rgba(177,116,0,0.22);
}
.sev-pill.l1 { background: var(--green-bg); color: var(--green); border-color: rgba(31,122,87,0.22); }
.sev-pill.l2 { background: var(--blue-bg); color: var(--blue); border-color: rgba(42,93,170,0.22); }
.sev-pill.l3 { background: var(--amber-bg); color: var(--amber); border-color: rgba(177,116,0,0.22); }
.sev-pill.l4 { background: var(--red-bg); color: var(--red); border-color: rgba(180,50,51,0.22); }
.sev-pill.l0 { background: var(--bg-elev); color: var(--ink-500); border-color: var(--border); }
.sev-pill .score { opacity: 0.75; font-weight: 500; }
.sev-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

.tv2-owner { display: flex; align-items: center; gap: 8px; }
.tv2-owner .avatar {
  width: 26px; height: 26px; border-radius: 50%;
  background: linear-gradient(135deg, #FFCFA3, var(--orange-500));
  color: #1A1410; display: grid; place-items: center;
  font-weight: 600; font-size: 11.5px;
}
.tv2-owner .nm { font-size: 12.5px; color: var(--ink-900); font-weight: 600; line-height: 1.2; }
.tv2-owner .role { font-size: 11px; color: var(--ink-500); line-height: 1.2; margin-top: 2px; }

.tv2-signals {
  display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px;
  border-top: 1px dashed var(--border); align-items: center;
}
.tv2-signals .label {
  font-size: 10.5px; color: var(--ink-500);
  letter-spacing: 0.5px; text-transform: uppercase; font-weight: 600; margin-right: 2px;
}
.signal {
  font-size: 11.5px; color: var(--ink-700); background: var(--bg-elev);
  padding: 3px 9px; border-radius: 4px; border: 1px solid var(--border);
  display: inline-flex; align-items: center; gap: 5px;
}
.signal::before { content: ""; width: 4px; height: 4px; border-radius: 50%; background: var(--orange-500); display: inline-block; }
.signal.forced { color: var(--red); border-color: rgba(180,50,51,0.22); background: var(--red-bg); }
.signal.pending { color: var(--ink-500); }

.sub-tabs {
  display: flex; align-items: center; gap: 6px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.sub-tab {
  border: 1px solid transparent; background: transparent; color: var(--ink-600);
  border-radius: 7px; padding: 7px 10px; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600;
}
.sub-tab:hover { background: var(--surface-alt); color: var(--ink-900); }
.sub-tab.active { background: var(--surface); border-color: var(--border); color: var(--ink-900); box-shadow: var(--sh-1); }
.badge {
  font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-500);
  padding: 1px 5px; background: var(--bg-elev); border-radius: 3px;
}
.badge.danger { color: var(--red); background: var(--red-bg); }

.tv2-empty {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
  min-height: 320px; display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 36px; gap: 12px;
}
.tv2-empty .glyph {
  width: 54px; height: 54px; border-radius: 14px;
  background: var(--orange-50); color: var(--orange-600);
  display: grid; place-items: center;
}
.tv2-empty h3 { margin: 0; font-size: 18px; color: var(--ink-900); }
.tv2-empty p { max-width: 620px; margin: 0; color: var(--ink-600); font-size: 13px; line-height: 1.7; }
.pending-row { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
.pending-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11.5px; color: var(--ink-600); background: var(--bg-elev);
  border: 1px dashed var(--border-strong); padding: 3px 8px; border-radius: 5px;
}
.pending-chip.inline { padding: 1px 5px; font-size: 10.5px; }
.mini-pending { font-size: 10px; opacity: .7; margin-left: 2px; }
.mini-pending.light { color: rgba(255,255,255,.9); }

.ai-plan {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
}
.ai-plan-head {
  padding: 14px 18px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px; justify-content: space-between;
}
.ai-plan-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ai-plan-title h3 { margin: 0; font-size: 15px; color: var(--ink-900); }
.ai-plan-icon {
  width: 28px; height: 28px; border-radius: 8px;
  display: grid; place-items: center; background: var(--orange-50); color: var(--orange-600);
}
.ai-plan-meta { font-size: 12px; color: var(--ink-500); }
.ai-plan-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }
.ai-plan-summary {
  display: grid; grid-template-columns: 108px 1fr; gap: 12px;
  font-size: 13px; line-height: 1.7; color: var(--ink-700);
  background: var(--surface-alt); border: 1px solid var(--border); border-radius: 8px; padding: 12px;
}
.label-col { color: var(--ink-500); font-size: 11.5px; font-weight: 600; display: inline-flex; gap: 5px; align-items: center; }
.plan-grid { display: grid; grid-template-columns: 1.25fr 1fr; gap: 12px; }
.plan-card {
  border: 1px solid var(--border); border-radius: 8px; background: #fff; padding: 14px;
}
.plan-card.critical { border-color: rgba(180,50,51,0.25); background: linear-gradient(180deg, #FFF8F8, #fff 70%); }
.plan-card h4 { margin: 0 0 10px; display: flex; gap: 6px; align-items: center; font-size: 12px; color: var(--ink-700); }
.plan-card p { margin: 0; color: var(--ink-500); font-size: 12.5px; }
.plan-list, .risk-list { display: flex; flex-direction: column; gap: 8px; }
.plan-item { display: grid; grid-template-columns: auto auto 1fr; gap: 8px; font-size: 12.5px; align-items: start; color: var(--ink-800); }
.ck-box { width: 13px; height: 13px; border-radius: 3px; border: 1px solid var(--border-strong); margin-top: 2px; }
.team { color: var(--orange-600); font-weight: 600; white-space: nowrap; }
.risk { display: grid; grid-template-columns: auto 1fr; gap: 8px; align-items: start; font-size: 12.5px; color: var(--ink-800); line-height: 1.6; }
.risk .lev { background: var(--red); color: #fff; border-radius: 4px; padding: 1px 5px; font-size: 10.5px; }
.ai-plan-foot { display: flex; gap: 8px; align-items: center; color: var(--ink-500); font-size: 12px; border-top: 1px dashed var(--border); padding-top: 12px; }

.audit-panel { display: flex; flex-direction: column; gap: 12px; }
.audit-stage-hint {
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  background: var(--surface-alt);
  color: var(--ink-600);
  font-size: 12.5px;
  line-height: 1.7;
  padding: 14px 16px;
}
.audit-stage-hint strong {
  color: var(--ink-900);
}
.ticket-grid {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.layer-panel { min-width: 0; }
.sec-h {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.sec-h h2 {
  margin: 0;
  color: var(--ink-900);
  font-size: 15px;
  font-weight: 700;
}
.sec-h .line {
  flex: 1;
  height: 1px;
  background: var(--border);
}
.sec-h .count {
  color: var(--ink-500);
  font-size: 11.5px;
  white-space: nowrap;
}
.ticket-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ticket-type-group {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  overflow: hidden;
  box-shadow: var(--sh-1);
}
.ticket-group-head {
  width: 100%;
  min-height: 42px;
  border: 0;
  background: linear-gradient(180deg, #fff, var(--surface-alt));
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  text-align: left;
  color: var(--ink-800);
}
.ticket-group-head:hover {
  background: var(--surface-alt);
}
.ticket-group-head.active {
  box-shadow: inset 3px 0 0 var(--orange-500);
}
.fold-caret {
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid var(--ink-500);
  transition: transform .14s ease;
  flex-shrink: 0;
}
.fold-caret.collapsed {
  transform: rotate(-90deg);
}
.group-count {
  margin-left: auto;
  color: var(--ink-500);
  font-size: 11.5px;
  white-space: nowrap;
}
.group-flag {
  background: var(--red-bg);
  border: 1px solid rgba(180,50,51,0.18);
  border-radius: 999px;
  color: var(--red);
  font-family: var(--font-mono);
  font-size: 10.5px;
  padding: 1px 6px;
  white-space: nowrap;
}
.ticket-group-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid var(--border);
  background: rgba(251,248,243,0.62);
}
.ticket-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color .12s, background .12s, box-shadow .12s;
}
.ticket-item:hover {
  border-color: var(--border-strong);
  box-shadow: var(--sh-1);
}
.ticket-item.active {
  border-color: rgba(234,84,4,0.45);
  background: #FFFAF4;
  box-shadow: inset 3px 0 0 var(--orange-500), var(--sh-1);
}
.ticket-no {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-400);
  font-weight: 700;
}
.ticket-item .title {
  margin-top: 8px;
  color: var(--ink-900);
  font-size: 13.5px;
  font-weight: 700;
  line-height: 1.45;
  word-break: break-word;
}
.ticket-item .desc {
  margin-top: 5px;
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.45;
  word-break: break-word;
}
.ticket-team {
  margin-top: 9px;
  color: var(--ink-600);
  font-size: 12px;
  line-height: 1.5;
}
.empty-ticket-list {
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  background: var(--surface-alt);
  color: var(--ink-500);
  font-size: 12.5px;
  line-height: 1.7;
  padding: 16px;
}
.ticket-doc {
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  overflow: hidden;
  box-shadow: var(--sh-1);
}
.doc-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px 16px;
  background: linear-gradient(180deg, #FFFCF8, var(--surface));
  border-bottom: 1px solid var(--border);
}
.tags-row {
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.doc-head h2 {
  margin: 10px 0 6px;
  color: var(--ink-900);
  font-size: 18px;
  line-height: 1.45;
  font-weight: 700;
}
.doc-meta {
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  word-break: break-word;
}
.doc-actions {
  gap: 6px;
  flex-shrink: 0;
}
.doc-body {
  display: flex;
  flex-direction: column;
}
.doc-section {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.doc-section:last-child { border-bottom: none; }
.sql-section { padding: 16px 0; }
.sql-section h4 { padding: 0 20px 9px; }
.doc-section h4 {
  margin: 0 0 9px;
  color: var(--ink-700);
  font-size: 12.5px;
  font-weight: 700;
}
.doc-section p {
  margin: 0;
  color: var(--ink-700);
  font-size: 13px;
  line-height: 1.75;
}
.reg-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.reg-summary-label {
  color: var(--ink-500);
  font-size: 11.5px;
  font-weight: 700;
}
.reg-evidence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.reg-evidence-card {
  border-left: 3px solid var(--orange-500);
  background: var(--surface-alt);
  border-radius: 6px;
  padding: 11px 13px;
  overflow: hidden;
}
.reg-evidence-label {
  margin-bottom: 8px;
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11.5px;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.reg-evidence-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 0;
  border-top: 1px dashed var(--border);
}
.reg-evidence-label + .reg-evidence-row {
  border-top: none;
  padding-top: 0;
}
.reg-evidence-row:first-child {
  border-top: none;
  padding-top: 0;
}
.reg-evidence-row:last-child {
  padding-bottom: 0;
}
.reg-evidence-meta {
  width: fit-content;
  max-width: 100%;
  border-radius: 5px;
  background: #fff1e9;
  color: #8f2f10;
  padding: 3px 7px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.reg-evidence-body {
  color: var(--ink-800);
  font-size: 13px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}
.reg-evidence-highlight {
  border-radius: 4px;
  background: #ffe0d2;
  color: #8f2f10;
  padding: 0 3px;
  font-weight: 700;
}
.reg-revision-mark {
  border-radius: 4px;
  padding: 0 3px;
  font-weight: 750;
  cursor: help;
}
.reg-revision-add {
  background: #dcfce7;
  color: #166534;
}
.reg-revision-delete {
  background: #fee2e2;
  color: #991b1b;
  text-decoration: line-through;
  text-decoration-thickness: 1.5px;
}
.reg-revision-modify {
  background: #dbeafe;
  color: #1d4ed8;
}
.asset-chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.impact-scope-block {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  justify-content: space-between;
}
.scope-field-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}
.scope-field {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}
.scope-field code {
  display: inline-block;
  max-width: 100%;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 3px 7px;
  color: var(--ink-800);
  font-family: var(--font-mono);
  font-size: 12.5px;
  white-space: normal;
  overflow-wrap: anywhere;
}
.scope-field-name {
  color: var(--ink-700);
  font-size: 12.5px;
  line-height: 1.6;
}
.scope-field-name.pending {
  color: var(--ink-500);
}
.lineage-btn {
  flex-shrink: 0;
}
.lineage-modal .detail-table code {
  white-space: normal;
  overflow-wrap: anywhere;
}
.doc-list {
  margin: 0;
  padding-left: 18px;
  color: var(--ink-800);
  font-size: 13px;
  line-height: 1.75;
}
.doc-list li + li { margin-top: 4px; }
.tv2-filterbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 0 2px;
}
.tv2-filterbar .grow { flex: 1; min-width: 8px; }
.tv2-filter-chip {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; padding: 5px 11px; border-radius: 6px;
  background: var(--surface); border: 1px solid var(--border); color: var(--ink-700);
  font-weight: 500; cursor: pointer;
}
.tv2-filter-chip.active { background: var(--ink-900); color: #fff; border-color: var(--ink-900); }
.tv2-filter-chip.danger.active { background: #B43233; border-color: #B43233; }
.tv2-filter-chip .ct {
  color: var(--ink-400); font-family: var(--font-mono); font-size: 10.5px;
  padding: 1px 5px; background: var(--bg-elev); border-radius: 3px;
}
.tv2-filter-chip.active .ct { color: rgba(255,255,255,0.85); background: rgba(255,255,255,0.12); }

.tv2-bulk {
  display: flex; align-items: center; gap: 10px; padding: 8px 14px;
  background: var(--ink-900); color: #F0E6D8; border-radius: 8px; font-size: 12.5px;
}
.tv2-bulk b { color: #fff; font-family: var(--font-mono); }
.tv2-bulk .spacer { flex: 1; }
.tv2-bulk .btn { color: #fff; padding: 4px 10px; }
.tv2-bulk .btn.primary { background: var(--orange-500); }

.tv2-tbl-wrap {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
  overflow: hidden; min-width: 0;
}
.ticket-list-table {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}
.ticket-list-table .tv2-tbl {
  min-width: 1320px;
}
.tv2-tbl {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  font-size: 13px;
}
.tv2-tbl thead th {
  text-align: left; font-weight: 600; font-size: 10.5px; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--ink-500); padding: 10px;
  background: var(--surface-alt); border-bottom: 1px solid var(--border);
  user-select: none; white-space: nowrap;
}
.tv2-tbl thead th.sortable { cursor: pointer; }
.sort-i { font-size: 9px; margin-left: 4px; color: var(--orange-500); }
.col-check { width: 32px; padding-left: 14px !important; }
.col-num { width: 36px; }
.col-type { width: 110px; }
.col-sys { width: 130px; }
.col-ar { width: 96px; }
.col-codes { width: 210px; }
.col-flags { width: 82px; }
.col-quality { width: 122px; }
.col-actions { width: 92px; text-align: right !important; }
.tv2-tbl tbody td {
  padding: 11px 10px; border-bottom: 1px solid var(--border);
  vertical-align: middle; color: var(--ink-800);
}
.tv2-tbl tbody tr:last-child td { border-bottom: none; }
.tv2-tbl tbody tr { cursor: pointer; transition: background .12s; }
.tv2-tbl tbody tr:hover td { background: var(--surface-alt); }
.tv2-tbl tbody tr.checked td { background: rgba(42, 93, 170, 0.045); }
.tv2-tbl tbody tr.selected td { background: rgba(234, 84, 4, 0.06); box-shadow: inset 2px 0 0 var(--orange-500); }
.tv2-tbl tbody tr.blocked-row td { background: rgba(220, 38, 38, 0.04); }
.empty-cell { text-align: center; color: var(--ink-500); padding: 30px !important; }

.ck {
  width: 14px; height: 14px; border: 1.5px solid var(--border-strong); border-radius: 3px;
  display: inline-grid; place-items: center; background: var(--surface); cursor: pointer;
  color: transparent; font-size: 10px; line-height: 1;
}
.ck.on { background: var(--orange-500); border-color: var(--orange-500); color: #fff; }
.ck.partial { background: var(--orange-500); border-color: var(--orange-500); color: #fff; }
.ck.partial::after { content: ""; width: 8px; height: 1.5px; background: #fff; }
.no { font-family: var(--font-mono); color: var(--ink-400); font-size: 11.5px; }

.type-chip {
  display: inline-flex; align-items: center; gap: 5px; padding: 3px 8px; border-radius: 5px;
  font-size: 11.5px; font-weight: 500; background: var(--bg-elev);
  color: var(--ink-700); border: 1px solid var(--border); white-space: nowrap; line-height: 1.5;
}
.type-chip .dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.type-chip.violet { background: var(--violet-bg); color: var(--violet); border-color: rgba(106,63,172,0.18); }
.type-chip.blue { background: var(--blue-bg); color: var(--blue); border-color: rgba(42,93,170,0.18); }
.type-chip.red { background: var(--red-bg); color: var(--red); border-color: rgba(180,50,51,0.18); }
.type-chip.orange { background: var(--orange-50); color: var(--orange-600); border-color: rgba(234,84,4,0.18); }
.type-chip.amber { background: var(--amber-bg); color: var(--amber); border-color: rgba(177,116,0,0.18); }
.type-chip.green { background: var(--green-bg); color: var(--green); border-color: rgba(31,122,87,0.18); }
.type-chip.slate { background: var(--bg-elev); color: var(--ink-700); border-color: var(--border-strong); }

.summary-cell { min-width: 0; }
.summary-cell .s1 {
  color: var(--ink-900); font-weight: 500; line-height: 1.45;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.summary-cell .s2 {
  display: block; font-size: 11px; color: var(--ink-500); font-weight: 400; margin-top: 3px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono);
}
.sys-tag {
  display: inline-block; padding: 2px 7px; border-radius: 4px;
  background: var(--ink-100); color: var(--ink-700); font-size: 11.5px; white-space: nowrap;
}
.role-chip {
  display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px 2px 6px;
  border-radius: 999px; background: var(--surface); border: 1px solid var(--border);
  font-size: 11.5px; color: var(--ink-800); white-space: nowrap; line-height: 1.5;
}
.role-chip .swatch { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-500); }
.role-chip.violet .swatch { background: var(--violet); }
.role-chip.orange .swatch { background: var(--orange-500); }
.role-chip.blue .swatch { background: var(--blue); }
.role-chip.red .swatch { background: var(--red); }
.role-chip.green .swatch { background: var(--green); }
.role-chip.amber .swatch { background: var(--amber); }
.role-chip.slate .swatch { background: var(--ink-500); }

.code-list { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; font-family: var(--font-mono); font-size: 11px; }
.code-list code, .assets-grp code {
  background: var(--bg-elev); padding: 1.5px 5px; border-radius: 3px;
  color: var(--ink-700); white-space: nowrap; font-family: var(--font-mono); font-size: 11px;
}
.code-list .more { color: var(--ink-400); font-size: 11px; padding: 1.5px 5px; }
.flag-icons { display: inline-flex; gap: 4px; }
.fi {
  width: 22px; height: 22px; border-radius: 5px; background: var(--bg-elev);
  color: var(--ink-400); display: inline-grid; place-items: center; position: relative;
}
.fi.on { background: var(--ink-100); color: var(--ink-800); }
.fi.danger { background: #FCE3E3; color: #DC2626; }
.fi.danger.on { background: #DC2626; color: #fff; }

.qbar { display: flex; align-items: center; gap: 7px; position: relative; min-width: 106px; }
.qbar .v { font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--ink-900); min-width: 38px; text-align: right; }
.qbar .b { flex: 1; height: 4px; border-radius: 2px; background: var(--ink-100); overflow: hidden; min-width: 36px; }
.qbar .b > span { display: block; height: 100%; background: var(--green); border-radius: 2px; }
.qbar.amber .b > span { background: var(--amber); }
.qbar.red .b > span { background: var(--red); }
.qbar.pending .b > span { background: var(--ink-300); }
.flag-ct { font-size: 10px; color: var(--red); font-family: var(--font-mono); padding: 1px 5px; border-radius: 3px; background: var(--red-bg); }
.flag-ct.amber { color: var(--amber); background: var(--amber-bg); }
.actions { text-align: right; }
.ib {
  width: 24px; height: 24px; border-radius: 5px; background: transparent; border: none;
  color: var(--ink-500); display: inline-grid; place-items: center; cursor: pointer;
}
.ib:hover { background: var(--bg-elev); color: var(--ink-900); }
.ib.done { color: var(--green); }

.ticket-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(31, 24, 19, 0.42);
  display: grid;
  place-items: center;
  padding: 32px;
}
.ticket-detail-modal {
  width: min(1080px, 92vw);
  max-height: min(820px, 88vh);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 70px rgba(31, 24, 19, 0.28);
}
.dr-head {
  padding: 16px 18px 14px; border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #FFFCF8, var(--surface));
}
.dr-head .row1 { display: flex; align-items: center; gap: 6px; }
.modal-spacer { flex: 1; }
.dr-head .close {
  width: 26px; height: 26px; background: transparent;
  border: none; border-radius: 6px; color: var(--ink-500); cursor: pointer;
  display: inline-grid; place-items: center;
}
.dr-head h2 { margin: 10px 0 6px; font-size: 15.5px; color: var(--ink-900); font-weight: 700; line-height: 1.4; }
.dr-head .summary { font-size: 12.5px; color: var(--ink-600); line-height: 1.6; }
.dr-head .meta { font-family: var(--font-mono); font-size: 11px; color: var(--ink-400); margin-top: 8px; }
.dr-body { flex: 1; overflow-y: auto; }
.dr-section { padding: 14px 18px; border-bottom: 1px solid var(--border); }
.dr-section:last-child { border-bottom: none; }
.dr-section h4 {
  margin: 0 0 10px; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.8px;
  color: var(--ink-500); font-weight: 600; display: flex; align-items: center; gap: 6px;
}
.ico-h {
  width: 16px; height: 16px; display: inline-grid; place-items: center;
  border-radius: 4px; background: var(--bg-elev); color: var(--ink-700);
}
.ico-h.green { background: var(--green-bg); color: var(--green); }
.ico-h.violet { background: var(--violet-bg); color: var(--violet); }
.ico-h.orange { background: var(--orange-50); color: var(--orange-600); }
.ico-h.amber { background: var(--amber-bg); color: var(--amber); }
.ico-h.blue { background: var(--blue-bg); color: var(--blue); }
.dr-section h4 .ct { margin-left: auto; font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-400); text-transform: none; letter-spacing: 0; }
.dr-assign { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
.dr-assign .item { display: flex; flex-direction: column; gap: 4px; }
.dr-assign .item.full { grid-column: span 2; }
.dr-assign .k, .assets-grp .k { font-size: 11.5px; color: var(--ink-700); letter-spacing: 0; font-weight: 700; }
.assets-grp { display: grid; grid-template-columns: 80px 1fr; gap: 8px 12px; font-size: 12px; align-items: baseline; }
.assets-grp .v { display: flex; flex-wrap: wrap; gap: 4px; }
.detail-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid var(--border);
  border-radius: 7px;
  overflow: hidden;
  font-size: 12px;
  background: var(--surface);
}
.detail-table th,
.detail-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  line-height: 1.55;
}
.detail-table tr:last-child th,
.detail-table tr:last-child td { border-bottom: none; }
.detail-table th {
  width: 112px;
  color: var(--ink-500);
  background: var(--surface-alt);
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}
.detail-table thead th {
  font-size: 10.5px;
  color: var(--ink-500);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.detail-table td { color: var(--ink-800); }
.detail-table code {
  display: inline-block;
  background: var(--bg-elev);
  padding: 1.5px 5px;
  border-radius: 3px;
  color: var(--ink-700);
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 11px;
  margin: 0 4px 4px 0;
}
.asset-table th:nth-child(1),
.asset-table td:nth-child(1) { width: 94px; }
.asset-table th:nth-child(2),
.asset-table td:nth-child(2) { width: 210px; }
.asset-table th:nth-child(4),
.asset-table td:nth-child(4) { width: 98px; }
.evidence-table th:first-child,
.evidence-table td:first-child { width: 220px; }
.history-table th:nth-child(1),
.history-table td:nth-child(1) { width: 230px; }
.history-table th:nth-child(2),
.history-table td:nth-child(2) { width: 210px; }
.history-table th:nth-child(4),
.history-table td:nth-child(4) { width: 68px; text-align: right; }
.note-row td { background: var(--surface-alt); }
.history-title { color: var(--ink-900); font-weight: 600; }
.history-meta { color: var(--ink-400); font-family: var(--font-mono); font-size: 10.5px; margin-top: 3px; }
.asset-note {
  display: inline-flex; align-items: center;
  padding: 1.5px 6px; border-radius: 4px;
  background: var(--bg-elev); color: var(--ink-500);
  font-size: 11px;
}
.more-chip {
  display: inline-flex; align-items: center;
  padding: 1.5px 6px; border-radius: 4px;
  background: var(--orange-50); color: var(--orange-600);
  font-family: var(--font-mono); font-size: 11px;
}
.dr-list { display: flex; flex-direction: column; gap: 8px; }
.dr-list .item { display: grid; grid-template-columns: 20px 1fr; gap: 9px; font-size: 12.5px; color: var(--ink-800); line-height: 1.6; }
.dr-list .n {
  font-family: var(--font-mono); font-size: 10.5px; background: var(--bg-elev);
  color: var(--ink-600); width: 18px; height: 18px; border-radius: 4px;
  display: inline-grid; place-items: center; margin-top: 1px; font-weight: 600;
}
.dr-list.must .n { background: var(--green-bg); color: var(--green); }
.dr-list.confirm .n { background: var(--violet-bg); color: var(--violet); }
.dr-blockers {
  background: #FFF1F1; border: 1px solid #FBD5D5; border-left: 3px solid #DC2626;
  padding: 11px 13px; border-radius: 6px; font-size: 12.5px; color: #7F1D1D; line-height: 1.6;
}
.dr-blockers .head {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600;
  color: #DC2626; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
}
.plain-list { font-size: 12.5px; color: var(--ink-800); line-height: 1.7; }
.pending-text { margin: 0; color: var(--ink-500); font-size: 12.5px; }
.dr-evidence {
  background: var(--surface-alt); border-left: 2px solid var(--orange-300);
  border-radius: 0 6px 6px 0; padding: 10px 12px;
  font-size: 12px; color: var(--ink-700); line-height: 1.6; margin-bottom: 8px;
}
.dr-evidence .src { font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-400); margin-bottom: 4px; }
.dr-history { display: flex; flex-direction: column; gap: 8px; }
.h-card {
  display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; align-items: center;
  padding: 10px 12px; background: var(--surface-alt); border: 1px solid var(--border); border-radius: 6px;
}
.h-card .t { font-size: 12.5px; color: var(--ink-900); font-weight: 500; line-height: 1.4; }
.h-card .m { grid-column: 1 / span 2; font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-400); margin-top: 2px; }
.h-card .match { font-family: var(--font-mono); font-size: 11px; color: var(--orange-600); font-weight: 700; padding: 2px 6px; background: var(--orange-50); border-radius: 4px; }
.quality-pill {
  display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 4px;
  font-size: 11.5px; font-weight: 700; font-family: var(--font-mono);
  background: var(--green-bg); color: var(--green);
}
.quality-pill.amber { background: var(--amber-bg); color: var(--amber); }
.quality-pill.red { background: var(--red-bg); color: var(--red); }
.quality-pill.pending { background: var(--bg-elev); color: var(--ink-500); }
.quality-pill .lbl { font-weight: 500; opacity: 0.75; }
.ticket-content {
  white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 12.5px;
  line-height: 1.7; margin: 0; background: var(--surface-alt); padding: 12px; border-radius: 6px;
}
.dr-foot {
  padding: 12px 18px; border-top: 1px solid var(--border);
  display: flex; gap: 8px; background: var(--surface-alt);
}
.dr-foot .btn { flex: 1; justify-content: center; }

.skbar {
  display: inline-block; height: 10px; border-radius: 3px;
  background: linear-gradient(90deg, var(--ink-100), var(--surface-alt), var(--ink-100));
  background-size: 200% 100%; animation: sk 1.4s linear infinite;
}
.skbar.title { width: 320px; height: 16px; }
.skbar.box { width: 14px; height: 14px; }
.skbar.short { width: 42px; }
.skbar.mid { width: 72px; }
.skbar.long { width: 220px; }
.skbar.sub { display: block; margin-top: 5px; }
.ai-bar {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--orange-600);
}
@keyframes sk {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

@media (max-width: 1180px) {
  .ticket-modal-backdrop { padding: 18px; }
}
@media (max-width: 860px) {
  .tv2-hero .hero-row1, .tv2-page-head { flex-direction: column; align-items: stretch; }
  .ticket-grid { grid-template-columns: 1fr; }
  .doc-head { flex-direction: column; }
  .doc-actions { width: 100%; justify-content: flex-end; }
  .plan-grid { grid-template-columns: 1fr; }
  .ai-plan-summary { grid-template-columns: 1fr; }
  .tv2-tbl-wrap { overflow-x: auto; }
  .tv2-tbl { min-width: 760px; }
  .ticket-detail-modal { width: 96vw; max-height: 92vh; }
  .dr-head .row1 { flex-wrap: wrap; }
}
</style>
