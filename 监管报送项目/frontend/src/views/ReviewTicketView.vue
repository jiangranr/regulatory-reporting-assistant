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
          <span class="badge">接口待完善</span>
          <span v-if="stats.blocked" class="badge danger">{{ stats.blocked }} 阻塞</span>
        </button>
        <button :class="['sub-tab', activeTab === 'audit' ? 'active' : '']" @click="activeTab = 'audit'">
          <ClipboardList :size="12" />工单审核
          <span class="badge">{{ childRows.length }} 子单</span>
          <span v-if="stats.pendingConfirm" class="badge danger">{{ stats.pendingConfirm }} 待确认</span>
        </button>
      </nav>

      <section v-if="activeTab === 'plan'" class="ai-plan as-page">
        <div class="ai-plan-head">
          <div class="ai-plan-title">
            <span class="ai-plan-icon"><Target :size="14" /></span>
            <h3>执行规划</h3>
            <span class="ai-plan-meta">详细排期、依赖拓扑、SLA 为接口待完善</span>
          </div>
          <span class="pending-chip">/api/ticket-plans 待完善</span>
        </div>
        <div class="ai-plan-body">
          <div class="ai-plan-summary">
            <span class="label-col"><FileText :size="12" />后端摘要</span>
            <span>
              当前任务已返回 <b>{{ tickets.length }}</b> 个草稿，其中母单
              <b>{{ parentTickets.length }}</b> 个、子单 <b>{{ childRows.length }}</b> 个。
              可确认字段包括责任角色、责任系统、影响范围、必须动作、待确认问题、证据链和质量评分。
            </span>
          </div>
          <div class="plan-grid">
            <div class="plan-card critical">
              <h4><CalendarRange :size="12" />建议执行顺序</h4>
              <div v-if="childRows.length" class="plan-list">
                <div v-for="row in childRows" :key="'plan-' + row.idKey" class="plan-item">
                  <span class="ck-box"></span>
                  <span class="team">{{ row.ownerLabel }}</span>
                  <span class="label">{{ row.summary }}</span>
                </div>
              </div>
              <p v-else>子单拆分接口待完善。</p>
            </div>
            <div class="plan-card">
              <h4><TriangleAlert :size="12" />关键风险</h4>
              <div v-if="blockedRows.length" class="risk-list">
                <div v-for="row in blockedRows" :key="'risk-' + row.idKey" class="risk high">
                  <span class="lev">高</span>
                  <span>{{ row.blockers[0] }}</span>
                </div>
              </div>
              <p v-else>风险分级、阻塞影响范围接口待完善。</p>
            </div>
          </div>
          <div class="ai-plan-foot">
            <Sparkles :size="12" />
            <span>本区域不使用原型 mock 数据；现阶段仅基于后端工单字段做事实汇总。</span>
          </div>
        </div>
      </section>

      <section v-else class="audit-panel">
        <div v-if="checked.size" class="tv2-bulk">
          <CheckSquare :size="14" />
          已选 <b>{{ checked.size }}</b> / {{ childRows.length }}
          <span class="spacer"></span>
          <button class="btn ghost sm" title="重新指派接口待完善"><UserPlus :size="12" />重新指派</button>
          <button class="btn ghost sm" title="状态更新接口待完善"><Check :size="12" />批量标记完成</button>
          <button class="btn ghost sm" title="导出选中接口待完善"><Download :size="12" />导出选中</button>
          <button class="btn primary sm" title="批量流转接口待完善"><Send :size="12" />批量流转</button>
        </div>
        <div v-else class="tv2-filterbar">
          <button
            v-for="item in filterItems"
            :key="item.key"
            :class="['tv2-filter-chip', filter === item.key ? 'active' : '', item.danger ? 'danger' : '']"
            @click="filter = item.key"
          >
            {{ item.label }} <span class="ct">{{ item.count }}</span>
          </button>
          <span class="grow"></span>
          <span class="pending-chip">编辑、流转、导出接口待完善</span>
        </div>

        <div class="tv2-tbl-wrap ticket-list-table">
            <table class="tv2-tbl">
              <thead>
                <tr>
                  <th class="col-check">
                    <span :class="['ck', allChecked]" @click="toggleAll">{{ allChecked === 'on' ? "✓" : "" }}</span>
                  </th>
                  <th class="col-num">#</th>
                  <th class="col-type">子单类型</th>
                  <th class="sortable" @click="toggleSort('summary')">
                    摘要 <span v-if="sort.key === 'summary'" class="sort-i">{{ sort.dir === 'asc' ? "▲" : "▼" }}</span>
                  </th>
                  <th class="col-sys">责任系统</th>
                  <th class="col-ar">A · 出口</th>
                  <th class="col-ar">R · 执行</th>
                  <th class="col-codes">关联报送项</th>
                  <th class="col-flags">标记</th>
                  <th class="col-quality sortable" @click="toggleSort('quality')">
                    质量 <span v-if="sort.key === 'quality'" class="sort-i">{{ sort.dir === 'asc' ? "▲" : "▼" }}</span>
                  </th>
                  <th class="col-actions">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!childRows.length">
                  <td colspan="10" class="empty-cell">子单拆分接口待完善：当前仅返回母单或旧版草稿。</td>
                </tr>
                <tr
                  v-for="row in filteredRows"
                  :key="row.idKey"
                  :class="[
                    selectedRow?.idKey === row.idKey ? 'selected' : '',
                    checked.has(row.idKey) ? 'checked' : '',
                    row.blockers.length ? 'blocked-row' : '',
                  ]"
                  @click="openId = row.idKey"
                >
                  <td class="col-check" @click.stop="toggleCheck(row.idKey)">
                    <span :class="['ck', checked.has(row.idKey) ? 'on' : '']">{{ checked.has(row.idKey) ? "✓" : "" }}</span>
                  </td>
                  <td class="no">{{ String(row.index + 1).padStart(2, "0") }}</td>
                  <td><TypeChip :label="row.typeLabel" :tone="row.typeTone" /></td>
                  <td>
                    <div class="summary-cell">
                      <div class="s1" :title="row.summary">{{ row.summary }}</div>
                      <span class="s2">{{ row.caption }}</span>
                    </div>
                  </td>
                  <td><span class="sys-tag">{{ row.systemLabel }}</span></td>
                  <td><RoleChip :label="row.ownerLabel" :tone="roleTone(row.ticket.owner_role)" /></td>
                  <td><RoleChip :label="row.executorLabel" :tone="roleTone(row.ticket.executor_role)" /></td>
                  <td>
                    <div class="code-list">
                      <code v-for="code in row.codes.slice(0, 2)" :key="code">{{ code }}</code>
                      <span v-if="!row.codes.length" class="pending-chip inline">接口待完善</span>
                      <span v-if="row.codes.length > 2" class="more">+{{ row.codes.length - 2 }}</span>
                    </div>
                  </td>
                  <td>
                    <span class="flag-icons">
                      <span :class="['fi', row.ticket.depends_on_lineage ? 'on' : '']" title="血缘依赖"><GitFork :size="11" /></span>
                      <span :class="['fi', row.ticket.business_signoff_required ? 'on' : '']" title="业务签字"><Signature :size="11" /></span>
                      <span :class="['fi danger', row.blockers.length ? 'on' : '']" title="阻塞点"><OctagonAlert :size="11" /></span>
                    </span>
                  </td>
                  <td class="col-quality"><QualityBar :score="row.qualityScore" :flags="row.qualityFlags" /></td>
                  <td class="actions" @click.stop>
                    <button class="ib" title="查看" @click="openId = row.idKey"><Eye :size="13" /></button>
                    <button class="ib" title="编辑接口待完善"><Pencil :size="13" /></button>
                    <button class="ib done" title="状态接口待完善"><Check :size="13" /></button>
                  </td>
                </tr>
              </tbody>
            </table>
        </div>

        <div v-if="selectedRow" class="ticket-modal-backdrop" @click.self="closeDetail">
          <article class="ticket-detail-modal">
            <div class="dr-head">
              <div class="row1">
                <TypeChip :label="selectedRow.typeLabel" :tone="selectedRow.typeTone" />
                <span :class="['quality-pill', qualityTone(selectedRow.qualityScore)]">
                  <span class="lbl">质量</span>{{ selectedRow.qualityScore || "待完善" }}
                </span>
                <span v-if="selectedRow.blockers.length" class="quality-pill red">
                  <OctagonAlert :size="11" />阻塞
                </span>
                <span class="modal-spacer"></span>
                <button class="btn secondary sm" :disabled="!previousRow" @click="openPrevious">上一条</button>
                <button class="btn secondary sm" :disabled="!nextRow" @click="openNext">下一条</button>
                <button class="close" @click="closeDetail"><X :size="15" /></button>
              </div>
              <h2>{{ selectedRow.caption }}</h2>
              <div class="summary">{{ selectedRow.summary }}</div>
              <div class="meta">TK-{{ selectedRow.ticket.id ?? "接口待完善" }} · 系统 {{ selectedRow.systemLabel }}</div>
            </div>

            <div class="dr-body">
              <DrawerSection title="责任分配">
                <template #icon><Users :size="10" /></template>
                <table class="detail-table ticket-detail-table">
                  <tbody>
                    <tr>
                      <th>A · 出口责任</th>
                      <td><RoleChip :label="selectedRow.ownerLabel" :tone="roleTone(selectedRow.ticket.owner_role)" /></td>
                      <th>R · 执行人</th>
                      <td><RoleChip :label="selectedRow.executorLabel" :tone="roleTone(selectedRow.ticket.executor_role)" /></td>
                    </tr>
                    <tr>
                      <th>责任系统</th>
                      <td colspan="3"><span class="sys-tag">{{ selectedRow.systemLabel }}</span></td>
                    </tr>
                  </tbody>
                </table>
              </DrawerSection>

              <DrawerSection title="影响范围" tone="blue">
                <template #icon><Boxes :size="10" /></template>
                <table v-if="selectedRow.assetEntries.length" class="detail-table asset-table">
                  <thead>
                    <tr>
                      <th>资产类型</th>
                      <th>中文名称</th>
                      <th>技术编码</th>
                      <th>血缘角色</th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="entry in selectedRow.assetEntries" :key="entry.key">
                      <tr v-for="value in entry.values" :key="entry.key + value.code + value.name">
                        <td>{{ entry.key }}</td>
                        <td>{{ value.name || "名称待补充" }}</td>
                        <td><code>{{ value.code }}</code></td>
                        <td>{{ value.role || "-" }}</td>
                      </tr>
                      <tr v-if="entry.hiddenCount" :key="entry.key + '-more'">
                        <td>{{ entry.key }}</td>
                        <td colspan="3"><span class="more-chip">+{{ entry.hiddenCount }} 个更多</span></td>
                      </tr>
                      <tr v-if="entry.note" :key="entry.key + '-note'" class="note-row">
                        <td>{{ entry.key }}</td>
                        <td colspan="3"><span class="asset-note">{{ entry.note }}</span></td>
                      </tr>
                    </template>
                  </tbody>
                </table>
                <p v-else class="pending-text">影响范围接口待完善。</p>
              </DrawerSection>

              <DrawerSection v-if="selectedRow.mustDo.length" title="必须动作" tone="green" :count="selectedRow.mustDo.length">
                <template #icon><Check :size="10" /></template>
                <table class="detail-table action-table">
                  <tbody>
                    <tr v-for="(item, i) in selectedRow.mustDo" :key="item">
                      <th>{{ i + 1 }}</th>
                      <td>{{ item }}</td>
                    </tr>
                  </tbody>
                </table>
              </DrawerSection>
              <DrawerSection v-else title="必须动作" tone="green">
                <template #icon><Check :size="10" /></template>
                <p class="pending-text">must_do 接口待完善。</p>
              </DrawerSection>

              <DrawerSection v-if="selectedRow.mustConfirm.length" title="待确认问题" tone="violet" :count="selectedRow.mustConfirm.length">
                <template #icon><CircleHelp :size="10" /></template>
                <table class="detail-table action-table">
                  <tbody>
                    <tr v-for="item in selectedRow.mustConfirm" :key="item">
                      <th>待确认</th>
                      <td>{{ item }}</td>
                    </tr>
                  </tbody>
                </table>
              </DrawerSection>

              <div v-if="selectedRow.blockers.length" class="dr-section">
                <div class="dr-blockers">
                  <div class="head"><OctagonAlert :size="11" />阻塞点 · {{ selectedRow.blockers.length }} 项</div>
                  <ul><li v-for="item in selectedRow.blockers" :key="item">{{ item }}</li></ul>
                </div>
              </div>

              <DrawerSection title="产出资产" tone="orange">
                <template #icon><Package :size="10" /></template>
                <table v-if="selectedRow.outputs.length" class="detail-table action-table">
                  <tbody>
                    <tr v-for="item in selectedRow.outputs" :key="item">
                      <th>产出</th>
                      <td>{{ item }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-else class="pending-text">output_artifacts 接口待完善。</p>
              </DrawerSection>

              <DrawerSection title="验收标准" tone="amber">
                <template #icon><Target :size="10" /></template>
                <table v-if="selectedRow.acceptance.length" class="detail-table action-table">
                  <tbody>
                    <tr v-for="item in selectedRow.acceptance" :key="item">
                      <th>验收</th>
                      <td>{{ item }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-else class="pending-text">acceptance_criteria_structured 接口待完善。</p>
              </DrawerSection>

              <DrawerSection title="证据链" :count="selectedRow.evidence.length">
                <template #icon><Quote :size="10" /></template>
                <table v-if="selectedRow.evidence.length" class="detail-table evidence-table">
                  <thead>
                    <tr>
                      <th>来源</th>
                      <th>证据文本</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in selectedRow.evidence" :key="item.src + item.text">
                      <td>{{ item.src || "来源待补充" }}</td>
                      <td>{{ item.text || "证据文本待补充" }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-else class="pending-text">evidence_refs 接口待完善。</p>
              </DrawerSection>

              <DrawerSection title="历史相似决策" :count="selectedRow.history.length">
                <template #icon><History :size="10" /></template>
                <table v-if="selectedRow.history.length" class="detail-table history-table">
                  <thead>
                    <tr>
                      <th>历史工单</th>
                      <th>匹配项</th>
                      <th>复用依据</th>
                      <th>分值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in selectedRow.history" :key="item.id + item.title">
                      <td>
                        <div class="history-title">{{ item.title || "标题待补充" }}</div>
                        <div class="history-meta">{{ item.id || "ID 待补充" }} · {{ item.date || "日期待补充" }}</div>
                      </td>
                      <td><code v-for="code in item.matchedCodes" :key="code">{{ code }}</code><span v-if="!item.matchedCodes.length">-</span></td>
                      <td>{{ item.rationale || "-" }}</td>
                      <td><span class="match">{{ item.match || "?" }}%</span></td>
                    </tr>
                  </tbody>
                </table>
                <p v-else class="pending-text">historical_cases 接口待完善。</p>
              </DrawerSection>

              <DrawerSection title="后端正文回退">
                <template #icon><FileText :size="10" /></template>
                <pre class="ticket-content">{{ selectedRow.ticket.content || "content 接口待完善" }}</pre>
              </DrawerSection>
            </div>

            <div class="dr-foot">
              <button class="btn secondary"><Check :size="12" />标记完成</button>
              <button class="btn secondary"><Pencil :size="12" />编辑</button>
              <button class="btn primary"><Download :size="12" />导出</button>
            </div>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref, watch } from "vue";
import type { PropType } from "vue";
import {
  ArrowLeft,
  Boxes,
  CalendarRange,
  Check,
  CheckSquare,
  CircleHelp,
  ClipboardList,
  Download,
  Eye,
  FileText,
  GitFork,
  History,
  OctagonAlert,
  Package,
  Pencil,
  Quote,
  RefreshCcw,
  Send,
  Signature,
  Sparkles,
  Target,
  TriangleAlert,
  UserPlus,
  Users,
  X,
} from "lucide-vue-next";
import type { TaskWorkflow, TicketDraft } from "@/types/api";

const props = defineProps<{
  workflow: TaskWorkflow | null;
  busy: boolean;
}>();

const emit = defineEmits<{ back: []; finish: []; generate: [] }>();

type FilterKey = "all" | "blocked" | "signoff" | "lowQuality" | "pendingConfirm";
type SortKey = "quality" | "summary";

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
  qualityScore: number;
  qualityFlags: string[];
}

const activeTab = ref<"plan" | "audit">("plan");
const openId = ref<string | null>(null);
const checked = ref<Set<string>>(new Set());
const filter = ref<FilterKey>("all");
const sort = ref<{ key: SortKey; dir: "asc" | "desc" }>({ key: "quality", dir: "asc" });

const tickets = computed(() => props.workflow?.ticket_drafts ?? []);
const parentTickets = computed(() => tickets.value.filter((ticket) => ticket.ticket_role === "PARENT"));
const parentTicket = computed(() => parentTickets.value[0] ?? null);
const childTickets = computed(() => tickets.value.filter((ticket) => ticket.ticket_role === "CHILD"));

const childRows = computed<TicketRow[]>(() =>
  childTickets.value.map((ticket, index) => normalizeTicket(ticket, index)),
);

const filteredRows = computed(() => {
  let rows = [...childRows.value];
  if (filter.value === "blocked") rows = rows.filter((row) => row.blockers.length > 0);
  if (filter.value === "signoff") rows = rows.filter((row) => row.ticket.business_signoff_required);
  if (filter.value === "lowQuality") rows = rows.filter((row) => row.qualityScore > 0 && row.qualityScore < 80);
  if (filter.value === "pendingConfirm") rows = rows.filter((row) => row.mustConfirm.length > 0);

  const dir = sort.value.dir === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    if (sort.value.key === "summary") return a.summary.localeCompare(b.summary, "zh-Hans-CN") * dir;
    const aq = a.qualityScore || 999;
    const bq = b.qualityScore || 999;
    return (aq - bq) * dir;
  });
  return rows;
});

const selectedRow = computed(() => childRows.value.find((row) => row.idKey === openId.value) ?? null);
const blockedRows = computed(() => childRows.value.filter((row) => row.blockers.length > 0));
const selectedRowIndex = computed(() =>
  selectedRow.value ? childRows.value.findIndex((row) => row.idKey === selectedRow.value?.idKey) : -1,
);
const previousRow = computed(() =>
  selectedRowIndex.value > 0 ? childRows.value[selectedRowIndex.value - 1] : null,
);
const nextRow = computed(() =>
  selectedRowIndex.value >= 0 && selectedRowIndex.value < childRows.value.length - 1
    ? childRows.value[selectedRowIndex.value + 1]
    : null,
);

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

const filterItems = computed<Array<{ key: FilterKey; label: string; count: number; danger?: boolean }>>(() => [
  { key: "all", label: "全部", count: childRows.value.length },
  { key: "blocked", label: "仅阻塞", count: blockedRows.value.length, danger: true },
  { key: "signoff", label: "待业务签字", count: childRows.value.filter((row) => row.ticket.business_signoff_required).length },
  { key: "lowQuality", label: "质量 < 80", count: childRows.value.filter((row) => row.qualityScore > 0 && row.qualityScore < 80).length },
  { key: "pendingConfirm", label: "有待确认", count: childRows.value.filter((row) => row.mustConfirm.length > 0).length },
]);

const allChecked = computed(() => {
  if (!childRows.value.length || !checked.value.size) return "";
  return checked.value.size === childRows.value.length ? "on" : "partial";
});

const parentTitle = computed(() => parentTicket.value?.title || `${props.workflow?.document?.title || "母单标题"}接口待完善`);
const parentTicketNo = computed(() => (parentTicket.value?.id ? `TKM-${parentTicket.value.id}` : "母单编号接口待完善"));
const documentRef = computed(() => {
  const doc = props.workflow?.document;
  if (!doc) return "发文接口待完善";
  return `DOC-${doc.id} · ${doc.title || doc.filename || "标题接口待完善"}`;
});
const parentChangeType = computed(() => parentTicket.value?.change_ticket_type ?? "");
const severitySignals = computed(() => textArray(parentTicket.value?.severity_signals));
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

function toggleCheck(id: string): void {
  const next = new Set(checked.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  checked.value = next;
}

function toggleAll(): void {
  checked.value = checked.value.size === childRows.value.length
    ? new Set()
    : new Set(childRows.value.map((row) => row.idKey));
}

function toggleSort(key: SortKey): void {
  sort.value = {
    key,
    dir: sort.value.key === key && sort.value.dir === "asc" ? "desc" : "asc",
  };
}

function closeDetail(): void {
  openId.value = null;
}

function openPrevious(): void {
  if (previousRow.value) openId.value = previousRow.value.idKey;
}

function openNext(): void {
  if (nextRow.value) openId.value = nextRow.value.idKey;
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
      const visibleLimit = normalizedKey === "SOURCE_FIELDS" ? 4 : values.length;
      return {
        key: assetLabel(normalizedKey),
        values: values.slice(0, visibleLimit),
        hiddenCount: Math.max(values.length - visibleLimit, 0),
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

function roleTone(value: string): string {
  return ({
    BUSINESS: "violet",
    REPORTING_MGMT: "orange",
    DATA_GOVERNANCE: "blue",
    SOURCE_SYSTEM: "red",
    DATA_DEV: "green",
    DATA_QUALITY: "amber",
    QA: "slate",
    COMPLIANCE: "slate",
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
    checked.value = new Set([...checked.value].filter((id) => rows.some((row) => row.idKey === id)));
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

const RoleChip = defineComponent({
  props: {
    label: { type: String, required: true },
    tone: { type: String, default: "slate" },
  },
  setup(props) {
    return () => h("span", { class: ["role-chip", props.tone] }, [
      h("span", { class: "swatch" }),
      props.label,
    ]);
  },
});

const QualityBar = defineComponent({
  props: {
    score: { type: Number, required: true },
    flags: { type: Array as PropType<string[]>, default: () => [] },
  },
  setup(props) {
    return () => {
      const tone = qualityTone(props.score);
      return h("span", { class: ["qbar", tone] }, [
        h("span", { class: "v" }, props.score ? String(props.score) : "待完善"),
        h("span", { class: "b" }, [h("span", { style: { width: `${props.score || 0}%` } })]),
        props.flags.length ? h("span", { class: ["flag-ct", props.score >= 70 ? "amber" : ""] }, `!${props.flags.length}`) : null,
      ]);
    };
  },
});

const DrawerSection = defineComponent({
  props: {
    title: { type: String, required: true },
    tone: { type: String, default: "" },
    count: { type: Number, default: null },
  },
  setup(props, { slots }) {
    return () => h("div", { class: "dr-section" }, [
      h("h4", [
        h("span", { class: ["ico-h", props.tone] }, slots.icon?.()),
        props.title,
        props.count !== null ? h("span", { class: "ct" }, `${props.count} 条`) : null,
      ]),
      slots.default?.(),
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
  .plan-grid { grid-template-columns: 1fr; }
  .ai-plan-summary { grid-template-columns: 1fr; }
  .tv2-tbl-wrap { overflow-x: auto; }
  .tv2-tbl { min-width: 760px; }
  .ticket-detail-modal { width: 96vw; max-height: 92vh; }
  .dr-head .row1 { flex-wrap: wrap; }
}
</style>
