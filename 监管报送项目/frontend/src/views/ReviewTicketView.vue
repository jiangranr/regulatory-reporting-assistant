<template>
  <div>
    <div class="row between">
      <div>
        <div class="h-eyebrow">第 5 步 · 终</div>
        <h1 class="h-title">工单草稿</h1>
        <p class="h-sub">按影响类型分层生成草稿。AI 给出建议正文与可审查 SQL，最终由人工确认后流转。</p>
      </div>
      <div class="row">
        <button class="btn secondary" @click="$emit('back')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          影响分析
        </button>
        <button
          class="btn secondary"
          v-if="tickets.length"
          :disabled="busy"
          @click="onRegenerate"
          title="基于最新影响分析重新生成工单，旧的草稿将被覆盖"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          {{ busy ? "生成中…" : "重新生成" }}
        </button>
        <button class="btn secondary" v-if="tickets.length">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          导出全部
        </button>
        <button class="btn primary" @click="$emit('finish')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          提交流转
        </button>
      </div>
    </div>

    <div class="ticket-grid mt-24">
      <!-- 左：工单列表 -->
      <div>
        <div class="sec-h" style="margin-bottom:10px;">
          <h2>分层工单</h2>
          <span class="line"></span>
          <span class="count">{{ tickets.length }} 个草稿</span>
        </div>

        <!-- 无工单时的生成提示 -->
        <div v-if="!tickets.length" class="card" style="text-align:center;padding:32px;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px;height:40px;margin:0 auto 12px;display:block;opacity:.3;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          <p style="color:var(--ink-400);margin-bottom:16px;">尚未生成工单草稿</p>
          <button class="btn primary" :disabled="busy" @click="$emit('generate')">
            {{ busy ? "生成中…" : "AI 生成工单草稿" }}
          </button>
        </div>

        <div v-else class="ticket-list">
          <!-- 母单 -->
          <div
            v-for="parent in parentTickets"
            :key="'p-' + (parent.id ?? parent.title)"
            class="ticket-group"
          >
            <div
              :class="['ticket-item parent', { active: activeTicketId === parent.id }]"
              @click="activeTicketId = parent.id"
            >
              <div class="tk-head">
                <span class="tag violet">母单</span>
                <span :class="['tag', severityTone(parent.severity_level)]">{{ parent.severity_level || 'L?' }}</span>
                <span class="tag outline">{{ changeTypeLabel(parent.change_ticket_type) }}</span>
              </div>
              <div class="title">{{ parent.title }}</div>
              <div class="desc">Owner：{{ roleLabel(parent.owner_role) }} · 评分 {{ parent.severity_score }}</div>
            </div>

            <!-- 该母单下的子单（缩进） -->
            <div
              v-for="child in childrenOf(parent.id)"
              :key="'c-' + (child.id ?? child.title)"
              :class="['ticket-item child', { active: activeTicketId === child.id }]"
              @click="activeTicketId = child.id"
            >
              <div class="tk-head">
                <span class="tag blue">子单</span>
                <span class="tag outline">{{ actionTypeLabel(child.action_ticket_type) }}</span>
                <span v-if="child.depends_on_lineage" class="tag amber">血缘</span>
                <span v-if="child.business_signoff_required" class="tag green">业务签</span>
              </div>
              <div class="title">{{ child.title }}</div>
              <div class="desc">A：{{ roleLabel(child.owner_role) }} · R：{{ roleLabel(child.executor_role) }}</div>
            </div>
          </div>

          <!-- 兼容旧数据：没有 parent 标识的工单当作独立单展示 -->
          <div
            v-for="tk in orphanTickets"
            :key="'o-' + (tk.id ?? tk.title)"
            :class="['ticket-item', { active: activeTicketId === tk.id }]"
            @click="activeTicketId = tk.id"
          >
            <div class="tk-head">
              <span class="tag violet">草稿</span>
            </div>
            <div class="title">{{ tk.title }}</div>
            <div class="desc">{{ tk.content?.slice(0, 80) }}…</div>
          </div>

          <!-- 默认工单（来自变更信号，无后端工单时才显示，此处保留兼容） -->
          <div
            v-for="(tk, i) in defaultTickets"
            :key="'default-' + i"
            :class="['ticket-item', { active: activeTicketId === 'default-' + i }]"
            @click="activeTicketId = 'default-' + i"
          >
            <div class="tk-head">
              <span :class="['tag', tk.typeTone]">{{ tk.type }}</span>
              <span class="tag outline mono">{{ tk.priority }}</span>
            </div>
            <div class="title">{{ tk.title }}</div>
            <div class="desc">{{ tk.desc }}</div>
          </div>
        </div>
      </div>

      <!-- 右：工单详情 -->
      <div>
        <div class="ticket-doc" v-if="activeTicket">
          <div class="doc-head">
            <div>
              <div class="row" style="gap:6px;flex-wrap:wrap;">
                <span :class="['tag', activeTicket.ticket_role === 'PARENT' ? 'violet' : 'blue']">
                  {{ activeTicket.ticket_role === 'PARENT' ? '母单' : '子单' }}
                </span>
                <span v-if="activeTicket.severity_level" :class="['tag', severityTone(activeTicket.severity_level)]">
                  {{ activeTicket.severity_level }}
                </span>
                <span v-if="activeTicket.change_ticket_type" class="tag outline">
                  {{ changeTypeLabel(activeTicket.change_ticket_type) }}
                </span>
                <span v-if="activeTicket.action_ticket_type" class="tag outline">
                  {{ actionTypeLabel(activeTicket.action_ticket_type) }}
                </span>
                <span v-if="activeTicket.depends_on_lineage" class="tag amber">依赖血缘</span>
                <span v-if="activeTicket.business_signoff_required" class="tag green">需业务签字</span>
                <span v-if="activeTicket.closure_review_required" class="tag orange">关闭前合规复核</span>
              </div>
              <h2 style="margin-top:8px;">{{ activeTicket.title }}</h2>
              <div class="doc-meta">
                TK-{{ activeTicket.id ?? "NEW" }} ·
                A：{{ roleLabel(activeTicket.owner_role) }}
                <template v-if="activeTicket.executor_role"> · R：{{ roleLabel(activeTicket.executor_role) }}</template>
                <template v-if="activeTicket.severity_forced_reason"> · 强制规则：{{ activeTicket.severity_forced_reason }}</template>
              </div>
            </div>
            <div class="row">
              <button class="btn secondary sm">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                编辑
              </button>
            </div>
          </div>

          <div class="doc-body">
            <div class="doc-section">
              <h4>工单正文</h4>
              <pre class="ticket-content">{{ activeTicket.content || defaultTicketContent }}</pre>
            </div>

            <div class="doc-section">
              <h4>影响范围</h4>
              <div class="row" style="flex-wrap:wrap;gap:6px;">
                <span v-for="tag in impactTags" :key="tag" class="tag outline mono">{{ tag }}</span>
              </div>
            </div>

            <div class="doc-section">
              <h4>建议处理动作</h4>
              <p>
                1. 根据变更信号重新核对相关报表填报规则，确认受影响的指标范围。<br/>
                2. 更新报送字段映射关系，确保源系统字段与报送字段一致。<br/>
                3. 与业务部门确认口径调整边界，形成正式的口径确认函。<br/>
                4. 更新 ETL 加工逻辑，并同步校验规则。
              </p>
            </div>

            <div class="doc-section">
              <h4>可审查 SQL · 参考草稿</h4>
              <pre class="sql-block"><span class="cmt">-- 变更后口径验证查询（仅供参考）</span>
<span class="kw">SELECT</span>  report_code,
        indicator_code,
        <span class="fn">SUM</span>(amount) <span class="kw">AS</span> total_amount,
        <span class="fn">COUNT</span>(<span class="kw">DISTINCT</span> counterparty_id) <span class="kw">AS</span> cp_count
<span class="kw">FROM</span>   rpt_1104.base_data
<span class="kw">WHERE</span>  report_date = <span class="str">'${biz_date}'</span>
  <span class="kw">AND</span>  report_code <span class="kw">IN</span> (<span class="str">'G24'</span>, <span class="str">'G21'</span>, <span class="str">'G25'</span>)
<span class="kw">GROUP BY</span> report_code, indicator_code
<span class="kw">ORDER BY</span> report_code, indicator_code;</pre>
              <div class="checks-row" style="margin-top:10px;">
                <span class="check-pill ok">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                  只读查询
                </span>
                <span class="check-pill ok">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                  白名单字段
                </span>
                <span class="check-pill warn">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  涉及报送数据 · 默认脱敏
                </span>
              </div>
            </div>

            <div class="doc-section">
              <h4>验收标准</h4>
              <p>
                1) 报表数据在规定时限内完成生成与校验；
                2) 变更后指标与历史口径差异满足允许范围；
                3) 业务部门完成签字确认；
                4) 校验规则覆盖新口径边界。
              </p>
            </div>
          </div>
        </div>

        <div class="card" v-else style="text-align:center;padding:48px 0;color:var(--ink-400);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px;height:40px;margin:0 auto 12px;display:block;opacity:.4;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          从左侧选择工单查看详情
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { TaskWorkflow, TicketDraft } from "@/types/api";

const props = defineProps<{
  workflow: TaskWorkflow | null;
  busy: boolean;
}>();

const emit = defineEmits<{ back: []; finish: []; generate: [] }>();

function onRegenerate(): void {
  if (props.busy) return;
  const ok = window.confirm(
    "确定基于最新影响分析重新生成工单吗？\n\n当前任务下的所有母单和子单草稿（含人工修改）将被覆盖删除。"
  );
  if (ok) emit("generate");
}

const tickets = computed(() => props.workflow?.ticket_drafts ?? []);

const parentTickets = computed(() =>
  tickets.value.filter((t) => t.ticket_role === "PARENT"),
);

function childrenOf(parentId: number | null): TicketDraft[] {
  if (parentId === null || parentId === undefined) return [];
  return tickets.value.filter(
    (t) => t.ticket_role === "CHILD" && t.parent_ticket_id === parentId,
  );
}

const orphanTickets = computed(() =>
  // 既不是 PARENT 也不是已知 CHILD（兼容老数据：ticket_role 缺省/为空）
  tickets.value.filter(
    (t) => t.ticket_role !== "PARENT" && t.ticket_role !== "CHILD",
  ),
);

// Default tickets derived from change signals (when no real tickets exist)
const defaultTickets = computed(() => {
  if (tickets.value.length) return [];
  const signals = props.workflow?.document_profile?.change_signals ?? [];
  return signals.slice(0, 5).map((s, i) => ({
    type: typeFromChangeType(s.change_type),
    typeTone: toneFromChangeType(s.change_type),
    priority: i === 0 ? "P0" : i < 3 ? "P1" : "P2",
    title: `${s.table_code} ${s.indicator_hint || s.section_hint} ${typeFromChangeType(s.change_type)}处理`,
    desc: s.evidence_text?.slice(0, 80) || "需确认变更口径并更新相关字段映射。",
  }));
});

const activeTicketId = ref<number | string | null>(null);

const activeTicket = computed((): TicketDraft | null => {
  if (activeTicketId.value === null) return tickets.value[0] ?? null;
  if (typeof activeTicketId.value === "string" && activeTicketId.value.startsWith("default-")) return null;
  return tickets.value.find((t) => t.id === activeTicketId.value) ?? tickets.value[0] ?? null;
});

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

function changeTypeLabel(t: string): string {
  return CHANGE_TYPE_LABELS[t] || t || "—";
}
function actionTypeLabel(t: string): string {
  return ACTION_TYPE_LABELS[t] || t || "—";
}
function roleLabel(r: string): string {
  return ROLE_LABELS[r] || r || "—";
}
function severityTone(level: string): string {
  return ({ L1: "green", L2: "blue", L3: "amber", L4: "red" } as Record<string, string>)[level] || "outline";
}

const impactTags = computed(() => {
  const signals = props.workflow?.document_profile?.change_signals ?? [];
  const codes = signals.map((s) => s.table_code);
  return [...new Set(codes), "rpt_1104", "ETL_调度", "校验规则"].slice(0, 6);
});

const defaultTicketContent = computed(() => {
  const doc = props.workflow?.document;
  return doc
    ? `监管发文《${doc.title || doc.filename}》要求对 1104 非现场监管报表相关指标进行调整。本工单针对报送口径、字段映射及加工逻辑进行改造。`
    : "请根据变更信号内容填写工单背景。";
});

function typeFromChangeType(t: string): string {
  return ({ ADD: "新增字段", MODIFY: "字段改造", DELETE: "停报处理", SCOPE_ADJUST: "口径确认", INSTRUCTION_ADJUST: "说明更新", UNCLEAR: "人工复核" } as Record<string, string>)[t] ?? "处理工单";
}
function toneFromChangeType(t: string): string {
  return ({ ADD: "green", MODIFY: "amber", DELETE: "red", SCOPE_ADJUST: "violet", INSTRUCTION_ADJUST: "blue", UNCLEAR: "outline" } as Record<string, string>)[t] ?? "outline";
}
</script>

<style scoped>
.ticket-group {
  margin-bottom: 8px;
}
.ticket-item.parent {
  border-left: 3px solid var(--violet-500, #7c3aed);
}
.ticket-item.child {
  margin-left: 18px;
  border-left: 2px solid var(--blue-400, #60a5fa);
  background: var(--surface-100, #f8fafc);
}
.ticket-item.child .title {
  font-size: 0.92em;
}
.tag.blue {
  background: rgba(59, 130, 246, 0.12);
  color: #1d4ed8;
}
.tag.red {
  background: rgba(220, 38, 38, 0.12);
  color: #b91c1c;
}
.ticket-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  background: var(--surface-100, #f8fafc);
  padding: 12px;
  border-radius: 6px;
}
</style>
