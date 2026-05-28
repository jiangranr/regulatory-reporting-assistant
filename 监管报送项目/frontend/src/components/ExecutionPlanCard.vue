<template>
  <section class="execution-plan-card" aria-label="AI 工单执行规划">
    <div class="ep-head">
      <div>
        <div class="ep-eyebrow">AI 工单执行规划</div>
        <h2>执行规划</h2>
      </div>
      <div v-if="plan" class="ep-meta">
        <span class="confidence">{{ confidenceText }}</span>
        <span class="generator">{{ plan.generated_by }}</span>
        <span v-if="plan.needs_human_review && response?.status !== 'DEGRADED'" class="review-badge">
          待人工复核
        </span>
      </div>
    </div>

    <div v-if="errorMessage" class="ep-banner error" role="alert">
      <span>{{ errorMessage }}</span>
      <button data-test="execution-plan-error-dismiss" type="button" class="icon-btn" aria-label="关闭错误提示" @click="errorMessage = ''">
        ×
      </button>
    </div>

    <div v-if="isFetching && !response" class="ep-skeleton" aria-label="执行规划加载中">
      <span class="sk-line wide"></span>
      <span class="sk-line"></span>
      <span class="sk-line short"></span>
    </div>

    <template v-else>
      <div v-if="response?.status === 'DEGRADED'" class="ep-banner amber">
        <span>{{ response.warning || "规划生成降级，已返回骨架规划，请人工补充" }}</span>
        <span class="review-badge">待人工复核</span>
      </div>
      <div v-if="response?.status === 'STALE'" class="ep-banner blue">
        工单已更新，规划可能过时，建议重新生成
      </div>
      <div v-if="isMutating" class="ep-skeleton" aria-label="执行规划更新中">
        <span class="sk-line wide"></span>
        <span class="sk-line"></span>
        <span class="sk-line short"></span>
      </div>

      <div v-if="!plan" class="ep-empty">
        <div>
          <h3>尚未生成执行规划</h3>
          <p>基于母子工单生成跨团队执行阶段、关键风险和协同建议。</p>
        </div>
        <button
          data-test="execution-plan-generate"
          type="button"
          class="primary-btn"
          :disabled="isMutating"
          @click="generatePlan"
        >
          <span v-if="isMutating" class="spinner"></span>
          {{ isMutating ? "生成中..." : "AI 生成规划" }}
        </button>
      </div>

      <div v-else class="ep-content">
        <section class="summary-box">
          <div class="duration">
            <span>预计周期</span>
            <strong>{{ plan.estimated_duration || "待补充" }}</strong>
          </div>
          <p>{{ plan.executive_summary || "暂无执行摘要" }}</p>
        </section>

        <section class="ep-section">
          <div class="section-title">
            <h3>执行阶段</h3>
            <span>{{ plan.execution_phases.length }} 阶段</span>
          </div>
          <details
            v-for="phase in plan.execution_phases"
            :key="phase.phase_name"
            data-test="execution-phase"
            class="phase"
            open
          >
            <summary>
              <span>{{ phase.phase_name }}</span>
              <span>{{ phase.tasks.length }} 项任务</span>
            </summary>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>团队</th>
                    <th>动作</th>
                    <th>工单</th>
                    <th>阻塞</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="task in phase.tasks" :key="`${phase.phase_name}-${task.ticket_id}-${task.action}`">
                    <td>
                      <span class="team-name">{{ task.team_zh }}</span>
                      <span class="team-code">{{ task.team }}</span>
                    </td>
                    <td>{{ task.action }}</td>
                    <td>
                      <a :href="`#ticket-${task.ticket_id}`">#{{ task.ticket_id }}</a>
                    </td>
                    <td>
                      <span v-if="task.is_blocker" class="blocker" :title="task.blocker_reason || undefined">阻塞</span>
                      <span v-else class="muted">否</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </section>

        <section class="ep-section">
          <div class="section-title">
            <h3>关键风险</h3>
            <span>{{ plan.critical_risks.length }} 项</span>
          </div>
          <div class="risk-list">
            <article
              v-for="risk in plan.critical_risks"
              :key="`${risk.severity}-${risk.description}`"
              data-test="critical-risk"
              class="risk-card"
            >
              <div class="risk-top">
                <span :class="['risk-badge', risk.severity.toLowerCase()]">{{ risk.severity }}</span>
                <a v-if="risk.ticket_id_ref" :href="`#ticket-${risk.ticket_id_ref}`">关联工单 #{{ risk.ticket_id_ref }}</a>
              </div>
              <p>{{ risk.description }}</p>
              <div class="mitigation">缓释措施：{{ risk.mitigation }}</div>
            </article>
          </div>
        </section>

        <section class="ep-section">
          <div class="section-title">
            <h3>团队协同</h3>
          </div>
          <p class="coordination">{{ plan.team_coordination || "暂无协同说明" }}</p>
        </section>

        <div class="ep-actions">
          <button
            data-test="execution-plan-regenerate"
            type="button"
            class="link-btn"
            :disabled="isMutating"
            @click="generatePlan"
          >
            <span v-if="isMutating" class="spinner"></span>
            {{ isMutating ? "生成中..." : "重新生成" }}
          </button>
          <div class="feedback">
            <button
              data-test="feedback-up"
              type="button"
              :disabled="feedbackSent || feedbackBusy"
              :class="{ sent: feedbackSent }"
              aria-label="执行规划有帮助"
              @click="sendFeedback('up')"
            >
              👍
            </button>
            <button
              data-test="feedback-down"
              type="button"
              :disabled="feedbackSent || feedbackBusy"
              :class="{ sent: feedbackSent }"
              aria-label="执行规划需改进"
              @click="sendFeedback('down')"
            >
              👎
            </button>
            <span v-if="feedbackSent" class="feedback-done">已反馈</span>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import type { ExecutionPlanResponse } from "@/types/api";

const props = defineProps<{ taskId: number; initial?: ExecutionPlanResponse | null }>();

const response = ref<ExecutionPlanResponse | null>(props.initial ?? null);
const isFetching = ref(false);
const isMutating = ref(false);
const feedbackBusy = ref(false);
const feedbackSent = ref(false);
const errorMessage = ref("");
let fetchSeq = 0;

const plan = computed(() => response.value?.plan ?? null);
const confidenceText = computed(() => {
  const confidence = plan.value?.confidence;
  return typeof confidence === "number" ? `${Math.round(confidence * 100)}%` : "置信度待补充";
});

onMounted(() => {
  if (!props.initial) void fetchPlan();
});

watch(
  () => props.taskId,
  () => {
    response.value = props.initial ?? null;
    feedbackSent.value = false;
    errorMessage.value = "";
    if (!props.initial) void fetchPlan();
  },
);

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const result = await fetch(path, init);
  if (!result.ok) {
    const message = await result.text();
    throw new Error(message || `Request failed: ${result.status}`);
  }
  return result.json() as Promise<T>;
}

function setError(err: unknown): void {
  errorMessage.value = err instanceof Error ? err.message : "执行规划接口调用失败";
}

async function fetchPlan(): Promise<void> {
  const seq = ++fetchSeq;
  isFetching.value = true;
  errorMessage.value = "";
  try {
    const next = await requestJson<ExecutionPlanResponse>(`/api/tasks/${props.taskId}/execution-plan`);
    if (seq === fetchSeq) response.value = next;
  } catch (err) {
    if (seq === fetchSeq) setError(err);
  } finally {
    if (seq === fetchSeq) isFetching.value = false;
  }
}

async function generatePlan(): Promise<void> {
  if (isMutating.value) return;
  isMutating.value = true;
  errorMessage.value = "";
  try {
    response.value = await requestJson<ExecutionPlanResponse>(`/api/tasks/${props.taskId}/execution-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    feedbackSent.value = false;
  } catch (err) {
    setError(err);
  } finally {
    isMutating.value = false;
  }
}

async function sendFeedback(thumbs: "up" | "down"): Promise<void> {
  if (feedbackBusy.value || feedbackSent.value) return;
  feedbackBusy.value = true;
  errorMessage.value = "";
  try {
    await requestJson<{ ok: true }>(`/api/tasks/${props.taskId}/execution-plan/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thumbs }),
    });
    feedbackSent.value = true;
  } catch (err) {
    setError(err);
  } finally {
    feedbackBusy.value = false;
  }
}
</script>

<style scoped>
.execution-plan-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-1);
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
}

.ep-head {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.ep-eyebrow {
  color: var(--ink-500);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.ep-head h2 {
  color: var(--ink-900);
  font-size: 15px;
  margin: 2px 0 0;
}

.ep-meta {
  align-items: flex-end;
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex-shrink: 0;
}

.confidence {
  color: var(--green);
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 700;
}

.generator {
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11px;
}

.ep-banner {
  align-items: center;
  border-radius: 7px;
  display: flex;
  font-size: 12px;
  gap: 8px;
  justify-content: space-between;
  line-height: 1.5;
  padding: 8px 10px;
}

.ep-banner.error {
  background: var(--red-bg);
  border: 1px solid rgba(180, 50, 51, 0.22);
  color: var(--red);
}

.ep-banner.amber {
  background: var(--amber-bg);
  border: 1px solid rgba(177, 116, 0, 0.22);
  color: var(--amber);
}

.ep-banner.blue {
  background: var(--blue-bg);
  border: 1px solid rgba(42, 93, 170, 0.22);
  color: var(--blue);
}

.review-badge {
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid currentColor;
  border-radius: 999px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
}

.icon-btn {
  background: transparent;
  border: 0;
  color: inherit;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.ep-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0 2px;
}

.sk-line {
  background: var(--bg-elev);
  border-radius: 4px;
  display: block;
  height: 12px;
  width: 72%;
}

.sk-line.wide { width: 92%; }
.sk-line.short { width: 42%; }

.ep-empty {
  align-items: center;
  background: var(--surface-alt);
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 14px;
}

.ep-empty h3 {
  color: var(--ink-900);
  font-size: 14px;
  margin: 0 0 4px;
}

.ep-empty p {
  color: var(--ink-600);
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
}

.primary-btn,
.link-btn,
.feedback button {
  align-items: center;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  gap: 6px;
  justify-content: center;
  min-height: 30px;
}

.primary-btn {
  background: var(--orange-600);
  border: 1px solid var(--orange-600);
  color: white;
  flex-shrink: 0;
  padding: 0 12px;
}

.primary-btn:disabled,
.link-btn:disabled,
.feedback button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.spinner {
  animation: ep-spin 0.8s linear infinite;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  height: 12px;
  width: 12px;
}

@keyframes ep-spin {
  to { transform: rotate(360deg); }
}

.ep-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-box {
  align-items: stretch;
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  grid-template-columns: minmax(130px, 180px) 1fr;
  overflow: hidden;
}

.duration {
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 3px;
  justify-content: center;
  padding: 10px 12px;
}

.duration span {
  color: var(--ink-500);
  font-size: 11px;
}

.duration strong {
  color: var(--ink-900);
  font-size: 16px;
}

.summary-box p {
  color: var(--ink-700);
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  padding: 10px 12px;
}

.ep-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.section-title h3 {
  color: var(--ink-900);
  font-size: 13px;
  margin: 0;
}

.section-title span {
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11px;
}

.phase {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.phase summary {
  align-items: center;
  background: var(--bg-elev);
  color: var(--ink-800);
  cursor: pointer;
  display: flex;
  font-size: 12.5px;
  font-weight: 700;
  justify-content: space-between;
  list-style: none;
  padding: 8px 10px;
}

.phase summary::-webkit-details-marker { display: none; }
.phase summary span:last-child {
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
}

.table-wrap {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  min-width: 620px;
  width: 100%;
}

th,
td {
  border-top: 1px solid var(--border);
  color: var(--ink-700);
  font-size: 12px;
  line-height: 1.45;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

th {
  color: var(--ink-500);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

td a,
.risk-top a {
  color: var(--blue);
  font-family: var(--font-mono);
  text-decoration: none;
}

.team-name {
  color: var(--ink-900);
  display: block;
  font-weight: 700;
}

.team-code {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--ink-500);
  display: inline-flex;
  font-family: var(--font-mono);
  font-size: 10.5px;
  margin-top: 3px;
  padding: 1px 5px;
}

.blocker {
  background: var(--red-bg);
  border: 1px solid rgba(180, 50, 51, 0.24);
  border-radius: 999px;
  color: var(--red);
  display: inline-flex;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
}

.muted {
  color: var(--ink-400);
}

.risk-list {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
}

.risk-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
}

.risk-top {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.risk-badge {
  border-radius: 999px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  padding: 2px 7px;
}

.risk-badge.high {
  background: var(--red-bg);
  color: var(--red);
}

.risk-badge.medium {
  background: var(--amber-bg);
  color: var(--amber);
}

.risk-badge.low {
  background: var(--bg-elev);
  color: var(--ink-500);
}

.risk-card p {
  color: var(--ink-800);
  font-size: 12.5px;
  line-height: 1.55;
  margin: 8px 0 6px;
}

.mitigation {
  color: var(--ink-600);
  font-size: 12px;
  line-height: 1.5;
}

.coordination {
  color: var(--ink-700);
  font-size: 12.5px;
  line-height: 1.65;
  margin: 0;
  white-space: pre-wrap;
}

.ep-actions {
  align-items: center;
  border-top: 1px dashed var(--border);
  display: flex;
  gap: 10px;
  justify-content: space-between;
  padding-top: 12px;
}

.link-btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--ink-700);
  padding: 0 10px;
}

.feedback {
  align-items: center;
  display: flex;
  gap: 6px;
}

.feedback button {
  background: var(--surface-alt);
  border: 1px solid var(--border);
  color: var(--ink-700);
  height: 30px;
  min-width: 34px;
  padding: 0 8px;
}

.feedback button.sent {
  background: var(--bg-elev);
  color: var(--ink-400);
}

.feedback-done {
  color: var(--ink-500);
  font-size: 12px;
}

@media (max-width: 720px) {
  .ep-head,
  .ep-empty,
  .ep-actions,
  .risk-top {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-box {
    grid-template-columns: 1fr;
  }

  .duration {
    border-bottom: 1px solid var(--border);
    border-right: 0;
  }
}
</style>
