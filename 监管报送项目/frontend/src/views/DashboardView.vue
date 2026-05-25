<template>
  <div>
    <div class="h-eyebrow">工作台</div>
    <h1 class="h-title">监管报送变更影响分析与工单助手</h1>
    <p class="h-sub">围绕 监管发文 → 报表字段定位 → 影响分析 → 工单草稿 的全流程治理。当前域：一表通 1104 资金同业（G21 / G24 / G25）。</p>

    <!-- 统计卡片 -->
    <div class="dash-stats mt-24">
      <div class="dash-stat hot">
        <div class="lbl">待处理发文</div>
        <div class="val">{{ pendingCount }}</div>
        <div class="delta">较昨日 +1 · 1 项高影响</div>
      </div>
      <div class="dash-stat">
        <div class="lbl">影响分析中</div>
        <div class="val">{{ analyzingCount }}</div>
        <div class="delta">G24 / G21 / G25 共 5 项</div>
      </div>
      <div class="dash-stat">
        <div class="lbl">待复核工单</div>
        <div class="val">{{ ticketCount }}</div>
        <div class="delta">业务 4 / 开发 5 / 治理 3</div>
      </div>
      <div class="dash-stat">
        <div class="lbl">本月已归档</div>
        <div class="val">18</div>
        <div class="delta">22 条经验沉淀</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:20px;">
      <!-- 任务列表 -->
      <div class="card">
        <div class="card-head">
          <div>
            <h3>正在进行的发文任务</h3>
            <div class="sub">按风险等级和处理截止排序</div>
          </div>
          <button class="btn secondary sm" @click="$emit('navigate', 'upload')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            新建
          </button>
        </div>
        <table class="tbl">
          <thead>
            <tr><th>发文</th><th>当前阶段</th><th>风险</th><th>截止</th></tr>
          </thead>
          <tbody>
            <tr
              v-for="task in displayTasks"
              :key="task.id"
              style="cursor:pointer"
              @click="$emit('navigate', 'portrait')"
            >
              <td>
                <div style="font-weight:600;color:var(--ink-900);">{{ task.title }}</div>
                <div class="mono" style="color:var(--ink-400);margin-top:2px;font-size:11px;">TASK-{{ task.id }}</div>
              </td>
              <td>
                <span :class="['tag', stageColor(task.status)]">{{ stageLabel(task.status) }}</span>
              </td>
              <td>
                <span :class="['tag', riskColor(task.risk_level)]">
                  <span class="dot"></span>{{ riskLabel(task.risk_level) }}
                </span>
              </td>
              <td class="mono" style="font-size:12px;">{{ task.updated_at?.slice(5,10) ?? "--" }}</td>
            </tr>
            <tr v-if="!displayTasks.length">
              <td colspan="4" style="text-align:center;color:var(--ink-400);padding:24px;">暂无进行中的任务</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- AI 推荐 -->
      <div class="card">
        <div class="card-head">
          <div>
            <h3>新增发文 · AI 推荐处理</h3>
            <div class="sub">基于历史经验和报送日历</div>
          </div>
        </div>
        <div class="tip-list">
          <div class="tip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;width:14px;height:14px;margin-top:2px;color:var(--orange-500);"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            <div>
              <b>建议优先：</b>2025 年度非现场监管报表填报通知。AI 识别命中 G24 / G21 / G25，包含口径调整与频度调整。
            </div>
          </div>
          <div class="tip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;width:14px;height:14px;margin-top:2px;color:var(--orange-500);"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <div>
              <b>历史经验复用：</b>2024 年同期处理流程可复用，预计减少 60% 人工沟通。
            </div>
          </div>
          <div class="tip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;width:14px;height:14px;margin-top:2px;color:var(--orange-500);"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <div>
              <b>风险提示：</b>G24 上报时限缩短 7 天，需确认 ETL 调度是否满足 T+5 要求。
            </div>
          </div>
        </div>
        <button class="btn primary mt-16" style="width:100%;justify-content:center;" @click="$emit('navigate', 'upload')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          上传新发文，开始处理
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { PageId } from "@/components/AppShell.vue";
import type { RegDocument, RegTask, TaskStatus, RiskLevel } from "@/types/api";

const props = defineProps<{
  tasks: RegTask[];
  documents: RegDocument[];
}>();

defineEmits<{ navigate: [page: PageId] }>();

const displayTasks = computed(() => props.tasks.slice(0, 5));
const pendingCount = computed(() => props.tasks.filter((t) => t.status === "CREATED").length || props.tasks.length);
const analyzingCount = computed(() => props.tasks.filter((t) => t.status === "IMPACT_ANALYZED").length);
const ticketCount = computed(() => props.tasks.filter((t) => t.status === "TICKET_GENERATED").length);

const stageLabel = (s: TaskStatus): string =>
  ({ CREATED: "待画像", RULE_EXTRACTED: "规则提取", IMPACT_ANALYZED: "影响分析", TICKET_GENERATED: "工单生成" } as Record<string,string>)[s] ?? s;
const stageColor = (s: TaskStatus): string =>
  ({ CREATED: "orange", RULE_EXTRACTED: "blue", IMPACT_ANALYZED: "violet", TICKET_GENERATED: "green" } as Record<string,string>)[s] ?? "outline";
const riskLabel = (r: RiskLevel): string => ({ LOW: "低", MEDIUM: "中", HIGH: "高" } as Record<string,string>)[r] ?? r;
const riskColor = (r: RiskLevel): string => ({ LOW: "green", MEDIUM: "amber", HIGH: "red" } as Record<string,string>)[r] ?? "outline";
</script>
