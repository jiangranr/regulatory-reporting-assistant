<template>
  <section class="impact-review" aria-label="影响范围业务复核">
    <div class="ir-head">
      <div>
        <div class="ir-breadcrumb">工单 / {{ taskNo }} / 影响范围 · 业务确认</div>
        <div class="ir-stage">
          <span class="stage-no">{{ currentStage }}</span>
          <span>{{ stageTitle }}</span>
          <span class="stage-muted">第 {{ currentStage }} 步 / 共 5 步</span>
        </div>
        <h3>{{ stageHeading }}</h3>
        <p>{{ stageDescription }}</p>
      </div>
      <div class="ir-status">
        <span class="status-chip">{{ statusLabel }}</span>
        <span class="legend-title">图例</span>
        <span class="legend-chip ai">AI 建议</span>
        <span class="legend-chip muted">AI 未选</span>
        <span class="legend-chip biz">业务新增</span>
      </div>
    </div>

    <div class="ir-stepper" aria-label="影响范围确认流程">
      <span class="step done">1 AI 影响分析</span>
      <button
        type="button"
        :class="['step', currentStage === 2 ? 'active' : '', currentStage > 2 ? 'done' : '']"
        data-test="review-stage-2"
        @click="emit('stage-change', 2)"
      >
        2 业务勾选 · 补充
      </button>
      <button
        type="button"
        :class="['step', currentStage === 3 ? 'active' : '']"
        data-test="review-stage-3"
        @click="emit('stage-change', 3)"
      >
        3 拆分子单 · 派发
      </button>
      <span class="step">4 下游处理</span>
      <span class="step">5 汇总验收</span>
    </div>

    <div v-if="errorMessage" class="ir-banner error">{{ errorMessage }}</div>
    <div v-if="loading && !response" class="ir-loading">影响范围加载中...</div>

    <template v-else-if="review && currentStage === 2">
      <div class="ir-summary">
        <div>
          <span class="label">将拆分为</span>
          <strong>{{ localStats.total_systems }}</strong>
          <span>个系统子单</span>
        </div>
        <div>
          <span class="label">选中字段</span>
          <strong>{{ localStats.selected_fields }}</strong>
          <span>/ {{ totalFields }} 个</span>
        </div>
        <div>
          <span class="label">业务新增</span>
          <strong>{{ localStats.business_added_fields }}</strong>
          <span>个字段</span>
        </div>
        <div>
          <span class="label">取消/排除</span>
          <strong>{{ localStats.business_removed_fields }}</strong>
          <span>个字段</span>
        </div>
      </div>

      <div class="business-tree">
        <details v-for="item in review.items" :key="item.reporting_item_code" class="item-node" open>
          <summary>
            <span>
              <strong>{{ item.reporting_item_code }}</strong>
              {{ item.reporting_item_name }}
            </span>
            <span class="confidence-chip">覆盖率 {{ coverageText(item) }}</span>
            <span class="item-kpi">
              <strong>{{ selectedFieldCount(item) }}</strong>
              / {{ totalFieldCount(item) }} 字段
            </span>
          </summary>

          <details
            v-for="system in item.systems"
            :key="item.reporting_item_code + system.responsible_system"
            class="system-node"
            open
          >
            <summary>
              <span>
                <span class="system-icon">{{ systemInitial(system.responsible_system_zh || system.responsible_system) }}</span>
                <strong>{{ system.responsible_system_zh }}</strong>
                <code>{{ system.responsible_system }}</code>
              </span>
              <span class="system-kpi">选中 {{ selectedSystemFieldCount(system) }}/{{ system.fields.length }}</span>
            </summary>

            <div class="field-list">
              <label
                v-for="field in system.fields"
                :key="field.field_code"
                :class="['field-row', field.removed || !field.selected ? 'cancelled' : '']"
              >
                <input
                  :data-test="`field-checkbox-${field.field_code}`"
                  type="checkbox"
                  :disabled="field.is_required"
                  v-model="field.selected"
                />
                <code>{{ field.field_code }}</code>
                <span>{{ field.field_name || "名称待补充" }}</span>
                <em>{{ field.lineage_role }}</em>
                <b v-if="field.is_required" class="badge required">必选</b>
                <b v-else-if="field.source === 'BUSINESS'" class="badge business">业务新增</b>
                <b v-else-if="field.selected && !field.removed" class="badge ai">AI 建议</b>
                <b v-else class="badge muted">AI 未选</b>
              </label>
            </div>

            <div class="add-field">
              <input
                :data-test="`field-code-${system.responsible_system}`"
                v-model="draftFields[system.responsible_system].code"
                placeholder="字段技术编码"
              />
              <input
                :data-test="`field-name-${system.responsible_system}`"
                v-model="draftFields[system.responsible_system].name"
                placeholder="展示名（可选）"
              />
              <button
                :data-test="`add-field-${system.responsible_system}`"
                type="button"
                @click="addField(system)"
              >
                <Plus :size="13" />添加字段
              </button>
            </div>
          </details>

          <label class="note-box">
            <span>业务备注</span>
            <textarea
              :data-test="`note-${item.reporting_item_code}`"
              v-model="item.business_note"
              maxlength="500"
              placeholder="按报送项补充业务上下文，确认后会合并到相关系统子单。"
            />
          </label>
        </details>

        <div class="ir-actions">
          <div class="split-note">
            将拆分为 <strong>{{ localStats.total_systems }}</strong> 张子单
            <span>{{ totalFields }} 字段 · {{ localStats.business_added_fields }} 条补充</span>
          </div>
          <button type="button" :disabled="mutating" @click="resetReview">
            <RefreshCcw :size="13" />重置为 AI 建议
          </button>
          <button data-test="save-impact-review" type="button" :disabled="mutating" @click="saveReview">
            <Save :size="13" />
            {{ mutating ? "保存中..." : "暂存草稿" }}
          </button>
          <button data-test="confirm-impact-review" type="button" class="primary" :disabled="mutating" @click="confirmReview">
            <Send :size="13" />{{ mutating ? "生成中..." : "确认生成子单" }}
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Plus, RefreshCcw, Save, Send } from "lucide-vue-next";

import type {
  ImpactReviewContent,
  ImpactReviewItem,
  ImpactReviewResponse,
  ImpactReviewStats,
  ImpactReviewSystem,
} from "@/types/api";

const props = defineProps<{ taskId: number; initial?: ImpactReviewResponse | null; activeStage?: 2 | 3 }>();
const emit = defineEmits<{ confirmed: []; "stage-change": [stage: 2 | 3] }>();

const response = ref<ImpactReviewResponse | null>(props.initial ?? null);
const review = ref<ImpactReviewContent | null>(clone(props.initial?.review ?? null));
const loading = ref(false);
const mutating = ref(false);
const errorMessage = ref("");
const draftFields = reactive<Record<string, { code: string; name: string }>>({});

const statusLabel = computed(() => {
  if (!response.value) return "未加载";
  return ({ EDITING: "编辑中", SAVED: "已暂存", CONFIRMED: "已确认" } as Record<string, string>)[response.value.status] ?? response.value.status;
});

const currentStage = computed<2 | 3>(() => props.activeStage ?? 2);
const stageTitle = computed(() => currentStage.value === 3 ? "子单拆分与派发" : "业务确认阶段");
const stageHeading = computed(() => currentStage.value === 3 ? "拆分子单 · 派发" : "影响范围 · 业务可勾选确认");
const stageDescription = computed(() =>
  currentStage.value === 3
    ? "按业务确认后的影响范围拆分系统子单，在下方审核子单摘要、责任系统、处理动作和依赖关系。"
    : "AI 已基于发文与血缘图识别受影响报送项，业务可勾选、取消或补充字段，确认后按系统拆分子单。",
);

const localStats = computed<ImpactReviewStats>(() => computeStats(review.value));
const totalFields = computed(() => (review.value?.items ?? []).reduce((sum, item) => sum + totalFieldCount(item), 0));
const taskNo = computed(() => `TKM-${String(props.taskId).padStart(4, "0")}`);

watch(
  () => props.taskId,
  () => {
    response.value = props.initial ?? null;
    review.value = clone(props.initial?.review ?? null);
    if (!props.initial) void fetchReview();
  },
  { immediate: true },
);

watch(review, (next) => initDraftFields(next), { deep: true, immediate: true });

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const result = await fetch(path, init);
  if (!result.ok) throw new Error((await result.text()) || `Request failed: ${result.status}`);
  return result.json() as Promise<T>;
}

async function fetchReview(): Promise<void> {
  loading.value = true;
  errorMessage.value = "";
  try {
    const next = await requestJson<ImpactReviewResponse>(`/api/tasks/${props.taskId}/impact-review`);
    response.value = next;
    review.value = clone(next.review);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "影响范围复核加载失败";
  } finally {
    loading.value = false;
  }
}

async function saveReview(): Promise<void> {
  if (!review.value) return;
  mutating.value = true;
  errorMessage.value = "";
  try {
    await requestJson<{ ok: true; updated_at: string }>(`/api/tasks/${props.taskId}/impact-review`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review: review.value }),
    });
    if (response.value) response.value.status = "SAVED";
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "暂存失败";
  } finally {
    mutating.value = false;
  }
}

async function resetReview(): Promise<void> {
  mutating.value = true;
  errorMessage.value = "";
  try {
    const next = await requestJson<ImpactReviewResponse>(`/api/tasks/${props.taskId}/impact-review/reset`, { method: "POST" });
    response.value = next;
    review.value = clone(next.review);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "恢复 AI 推荐失败";
  } finally {
    mutating.value = false;
  }
}

async function confirmReview(): Promise<void> {
  if (!review.value) return;
  mutating.value = true;
  errorMessage.value = "";
  try {
    await requestJson(`/api/tasks/${props.taskId}/impact-review/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review: review.value }),
    });
    if (response.value) response.value.status = "CONFIRMED";
    emit("confirmed");
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "确认生成失败";
  } finally {
    mutating.value = false;
  }
}

function addField(system: ImpactReviewSystem): void {
  const draft = draftFields[system.responsible_system];
  const code = draft?.code.trim();
  if (!code) return;
  system.fields.push({
    field_code: code,
    field_name: draft.name.trim(),
    lineage_role: system.responsible_system === "SOURCE_SYSTEM" ? "SOURCE_FIELD" : "DERIVED_FIELD",
    source: "BUSINESS",
    selected: true,
    edited: false,
    removed: false,
    is_required: false,
  });
  draft.code = "";
  draft.name = "";
}

function selectedFieldCount(item: ImpactReviewItem): number {
  return item.systems.reduce((sum, system) => sum + selectedSystemFieldCount(system), 0);
}

function totalFieldCount(item: ImpactReviewItem): number {
  return item.systems.reduce((sum, system) => sum + system.fields.length, 0);
}

function selectedSystemFieldCount(system: ImpactReviewSystem): number {
  return system.fields.filter((field) => field.selected && !field.removed).length;
}

function coverageText(item: ImpactReviewItem): string {
  const total = totalFieldCount(item);
  if (!total) return "0%";
  return `${Math.round((selectedFieldCount(item) / total) * 100)}%`;
}

function systemInitial(value: string): string {
  const trimmed = value.trim();
  const chinese = trimmed.match(/[\u4e00-\u9fa5]/)?.[0];
  return chinese || trimmed.slice(0, 1) || "系";
}

function initDraftFields(content: ImpactReviewContent | null): void {
  for (const item of content?.items ?? []) {
    for (const system of item.systems) {
      if (!draftFields[system.responsible_system]) {
        draftFields[system.responsible_system] = { code: "", name: "" };
      }
    }
  }
}

function computeStats(content: ImpactReviewContent | null): ImpactReviewStats {
  const items = content?.items ?? [];
  const systems = items.flatMap((item) => item.systems);
  const fields = systems.flatMap((system) => system.fields);
  return {
    total_items: items.length,
    total_systems: new Set(systems.map((system) => system.responsible_system)).size,
    selected_fields: fields.filter((field) => field.selected && !field.removed).length,
    business_added_fields: fields.filter((field) => field.source === "BUSINESS").length,
    business_removed_fields: fields.filter((field) => field.removed || !field.selected).length,
  };
}

function clone<T>(value: T): T {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}
</script>

<style scoped>
.impact-review {
  background:
    linear-gradient(180deg, rgba(255, 246, 239, 0.58), rgba(255, 255, 255, 0) 180px),
    var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 12px;
  overflow: hidden;
  padding: 18px 18px 0;
  box-shadow: var(--sh-1);
}

.ir-head,
.ir-status,
.ir-actions,
.add-field {
  align-items: center;
  display: flex;
  gap: 8px;
}

.ir-head {
  align-items: flex-start;
  justify-content: space-between;
  padding: 2px 2px 0;
}

.ir-breadcrumb,
.ir-stage,
.ir-status,
.field-row em {
  color: var(--ink-500);
  font-size: 11px;
}

.ir-breadcrumb {
  font-family: var(--font-mono);
  margin-bottom: 7px;
}

.ir-stage {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.stage-no {
  background: var(--orange-500);
  border-radius: 999px;
  color: white;
  display: inline-grid;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
  height: 20px;
  place-items: center;
  width: 20px;
}

.stage-muted {
  color: var(--ink-400);
}

.ir-head h3 {
  color: var(--ink-900);
  font-size: 22px;
  line-height: 1.28;
  margin: 0;
}

.ir-head p {
  color: var(--ink-600);
  font-size: 13px;
  line-height: 1.7;
  margin: 8px 0 0;
  max-width: 780px;
}

.ir-status {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--border);
  border-radius: 11px;
  box-shadow: var(--sh-1);
  flex-wrap: wrap;
  justify-content: flex-end;
  padding: 8px;
}

.legend-title {
  border-right: 1px solid var(--border);
  color: var(--ink-700);
  font-weight: 700;
  margin-right: 2px;
  padding-right: 8px;
}

.status-chip {
  background: var(--orange-50);
  border: 1px solid rgba(234, 84, 4, 0.2);
  border-radius: 999px;
  color: var(--orange-600);
  font-weight: 800;
  padding: 2px 8px;
}

.legend-chip,
.badge {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 7px;
}

.legend-chip.ai,
.badge.ai {
  background: var(--blue-bg);
  border-color: rgba(42, 93, 170, 0.2);
  color: var(--blue);
}

.legend-chip.biz,
.badge.business {
  background: var(--violet-bg);
  border-color: rgba(106, 63, 172, 0.2);
  color: var(--violet);
}

.legend-chip.muted,
.badge.muted {
  color: var(--ink-500);
}

.ir-stepper {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 2px;
}

.step {
  align-items: center;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--ink-500);
  display: inline-flex;
  font-family: inherit;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  min-height: 30px;
  padding: 0 12px;
}

button.step {
  cursor: pointer;
}

button.step:hover {
  border-color: var(--border-strong);
  color: var(--ink-800);
}

.step.done {
  background: var(--green-bg);
  border-color: rgba(31, 122, 87, 0.2);
  color: var(--green);
}

.step.active {
  background: var(--orange-500);
  border-color: var(--orange-500);
  box-shadow: 0 8px 18px rgba(234, 84, 4, 0.16);
  color: white;
}

.ir-summary {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.ir-summary > div {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--border);
  border-radius: 10px;
  min-width: 0;
  padding: 11px 12px;
}

.ir-summary .label {
  color: var(--ink-500);
  display: block;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 3px;
}

.ir-summary strong {
  color: var(--orange-600);
  font-family: var(--font-mono);
  font-size: 20px;
  line-height: 1;
}

.ir-summary span:not(.label) {
  color: var(--ink-500);
  font-size: 12px;
  margin-left: 4px;
}

.ir-actions button,
.add-field button {
  align-items: center;
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--ink-700);
  cursor: pointer;
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  gap: 5px;
  justify-content: center;
  min-height: 30px;
  padding: 0 10px;
}

.ir-actions button.primary {
  background: var(--orange-600);
  border-color: var(--orange-600);
  color: white;
}

.ir-banner.error {
  background: var(--red-bg);
  border: 1px solid rgba(180, 50, 51, 0.24);
  border-radius: 7px;
  color: var(--red);
  font-size: 12px;
  padding: 8px 10px;
}

.ir-loading {
  color: var(--ink-500);
  font-size: 12px;
}

.item-node,
.system-node {
  border: 1px solid var(--border-strong);
  border-radius: 11px;
  margin-bottom: 10px;
  overflow: hidden;
}

.item-node > summary,
.system-node > summary {
  align-items: center;
  background: var(--surface);
  cursor: pointer;
  display: grid;
  font-size: 12px;
  gap: 8px;
  grid-template-columns: minmax(0, 1fr) auto auto;
  padding: 11px 12px;
}

.item-node > summary {
  background: linear-gradient(180deg, #fff, var(--surface-alt));
  font-size: 14px;
}

.item-node > summary strong {
  display: block;
  font-family: var(--font-mono);
  font-size: 12px;
  margin-bottom: 3px;
}

.item-kpi,
.system-kpi,
.confidence-chip {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--ink-600);
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 8px;
  white-space: nowrap;
}

.confidence-chip {
  background: var(--green-bg);
  border-color: rgba(31, 122, 87, 0.2);
  color: var(--green);
}

.item-kpi strong {
  color: var(--orange-600);
}

.system-node {
  margin: 10px;
  border-color: var(--border);
}

.system-node > summary {
  background: var(--bg-elev);
}

.system-node > summary > span:first-child {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.system-node code {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 1px 5px;
}

.system-icon {
  background: var(--orange-50);
  border: 1px solid rgba(234, 84, 4, 0.15);
  border-radius: 6px;
  color: var(--orange-600);
  display: inline-grid;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 800;
  height: 24px;
  place-items: center;
  width: 24px;
}

.field-list {
  display: grid;
  gap: 7px;
  padding: 10px;
}

.field-row {
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 8px;
  grid-template-columns: 18px minmax(180px, 1fr) minmax(120px, 0.8fr) minmax(90px, 0.4fr) auto;
  font-size: 12px;
  min-height: 38px;
  padding: 7px 9px;
}

.field-row:hover {
  border-color: var(--border-strong);
}

.field-row.cancelled {
  background: var(--surface-alt);
  color: var(--ink-400);
}

.field-row.cancelled code,
.field-row.cancelled span:not(.badge),
.field-row.cancelled em {
  text-decoration: line-through;
}

.field-row input {
  accent-color: var(--orange-500);
}

.badge {
  font-size: 11px;
  font-style: normal;
  font-weight: 700;
  justify-self: start;
}

.badge.required { color: var(--red); }

.add-field {
  border-top: 1px dashed var(--border);
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 0.7fr) auto;
  padding: 10px;
}

.add-field input,
.note-box textarea {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--ink-800);
  font-size: 12px;
  padding: 7px 8px;
}

.note-box {
  display: grid;
  gap: 6px;
  padding: 0 10px 10px;
}

.note-box span {
  color: var(--ink-600);
  font-size: 12px;
  font-weight: 700;
}

.note-box textarea {
  min-height: 72px;
  resize: vertical;
}

.ir-actions {
  background: rgba(255, 255, 255, 0.94);
  border-top: 1px solid var(--border);
  bottom: 0;
  margin: 4px -18px 0;
  padding: 12px 18px;
  position: sticky;
  z-index: 3;
}

.split-note {
  color: var(--ink-500);
  flex: 1;
  font-size: 12px;
  min-width: 220px;
}

.split-note strong {
  color: var(--orange-600);
  font-family: var(--font-mono);
  font-size: 16px;
}

.split-note span {
  border-left: 1px solid var(--border);
  margin-left: 10px;
  padding-left: 10px;
}

@media (max-width: 760px) {
  .ir-head,
  .ir-actions,
  .add-field {
    align-items: stretch;
    flex-direction: column;
  }

  .impact-review {
    padding: 14px 14px 0;
  }

  .ir-head h3 {
    font-size: 19px;
  }

  .ir-status {
    justify-content: flex-start;
    width: 100%;
  }

  .ir-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .item-node > summary,
  .system-node > summary {
    align-items: start;
    grid-template-columns: 1fr;
  }

  .add-field {
    display: flex;
  }

  .field-row {
    grid-template-columns: 18px 1fr;
  }

  .ir-actions {
    margin-left: -14px;
    margin-right: -14px;
  }
}
</style>
