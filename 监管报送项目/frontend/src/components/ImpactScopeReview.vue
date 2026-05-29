<template>
  <section class="impact-review" aria-label="影响范围业务复核">
    <div class="ir-head">
      <div>
        <div class="ir-eyebrow">影响范围复核</div>
        <h3>AI 推荐与业务确认</h3>
      </div>
      <div class="ir-status">
        <span>{{ statusLabel }}</span>
        <span v-if="response">选中 {{ localStats.selected_fields }} 个字段</span>
      </div>
    </div>

    <div class="mode-tabs" role="tablist">
      <button :class="{ active: mode === 'ai' }" type="button" @click="mode = 'ai'">AI 推荐视图</button>
      <button
        data-test="business-review-tab"
        :class="{ active: mode === 'business' }"
        type="button"
        @click="mode = 'business'"
      >
        业务复核视图
      </button>
    </div>

    <div v-if="errorMessage" class="ir-banner error">{{ errorMessage }}</div>
    <div v-if="loading && !response" class="ir-loading">影响范围加载中...</div>

    <template v-else-if="review">
      <div v-if="mode === 'ai'" class="ai-table">
        <div class="ai-summary">
          <span>受影响字段</span>
          <b>{{ localStats.total_items }}</b> 个报送项 · <b>{{ localStats.total_systems }}</b> 个系统
        </div>
        <table>
          <thead>
            <tr>
              <th>报送项</th>
              <th>责任系统</th>
              <th>字段</th>
              <th>角色</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="item in review.items" :key="item.reporting_item_code">
              <tr v-for="field in aiFields(item)" :key="item.reporting_item_code + field.system + field.field.field_code">
                <td><code>{{ item.reporting_item_code }}</code><span>{{ item.reporting_item_name }}</span></td>
                <td>{{ field.system }}</td>
                <td><code>{{ field.field.field_code }}</code></td>
                <td>{{ field.field.lineage_role }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div v-else class="business-tree">
        <details v-for="item in review.items" :key="item.reporting_item_code" class="item-node" open>
          <summary>
            <span>
              <strong>{{ item.reporting_item_code }}</strong>
              {{ item.reporting_item_name }}
            </span>
            <span>{{ selectedFieldCount(item) }}/{{ totalFieldCount(item) }} 字段</span>
          </summary>

          <details
            v-for="system in item.systems"
            :key="item.reporting_item_code + system.responsible_system"
            class="system-node"
            open
          >
            <summary>
              <span>{{ system.responsible_system }} · {{ system.responsible_system_zh }}</span>
              <span>{{ selectedSystemFieldCount(system) }}/{{ system.fields.length }}</span>
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
                <b v-else class="badge ai">AI</b>
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
                添加字段
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
          <button data-test="save-impact-review" type="button" :disabled="mutating" @click="saveReview">
            {{ mutating ? "保存中..." : "暂存草稿" }}
          </button>
          <button type="button" :disabled="mutating" @click="resetReview">恢复 AI 推荐</button>
          <button data-test="confirm-impact-review" type="button" class="primary" :disabled="mutating" @click="confirmReview">
            {{ mutating ? "生成中..." : "确认并生成工单" }}
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import type {
  ImpactReviewContent,
  ImpactReviewField,
  ImpactReviewItem,
  ImpactReviewResponse,
  ImpactReviewStats,
  ImpactReviewSystem,
} from "@/types/api";

const props = defineProps<{ taskId: number; initial?: ImpactReviewResponse | null }>();
const emit = defineEmits<{ confirmed: [] }>();

const response = ref<ImpactReviewResponse | null>(props.initial ?? null);
const review = ref<ImpactReviewContent | null>(clone(props.initial?.review ?? null));
const mode = ref<"ai" | "business">("ai");
const loading = ref(false);
const mutating = ref(false);
const errorMessage = ref("");
const draftFields = reactive<Record<string, { code: string; name: string }>>({});

const statusLabel = computed(() => {
  if (!response.value) return "未加载";
  return ({ EDITING: "编辑中", SAVED: "已暂存", CONFIRMED: "已确认" } as Record<string, string>)[response.value.status] ?? response.value.status;
});

const localStats = computed<ImpactReviewStats>(() => computeStats(review.value));

watch(
  () => props.taskId,
  () => {
    response.value = props.initial ?? null;
    review.value = clone(props.initial?.review ?? null);
    mode.value = "ai";
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

function aiFields(item: ImpactReviewItem): Array<{ system: string; field: ImpactReviewField }> {
  return item.systems.flatMap((system) =>
    system.fields.map((field) => ({ system: system.responsible_system_zh, field })),
  );
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
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
}

.ir-head,
.ir-status,
.mode-tabs,
.ir-actions,
.add-field {
  align-items: center;
  display: flex;
  gap: 8px;
}

.ir-head {
  justify-content: space-between;
}

.ir-eyebrow,
.ir-status,
.ai-summary,
.field-row em {
  color: var(--ink-500);
  font-size: 11px;
}

.ir-head h3 {
  color: var(--ink-900);
  font-size: 15px;
  margin: 2px 0 0;
}

.ir-status {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.ir-status span,
.badge {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 7px;
}

.mode-tabs {
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}

.mode-tabs button,
.ir-actions button,
.add-field button {
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--ink-700);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  min-height: 30px;
  padding: 0 10px;
}

.mode-tabs button.active,
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

.ai-summary {
  margin-bottom: 8px;
}

.ai-summary b {
  color: var(--ink-900);
}

.ai-table table {
  border-collapse: collapse;
  width: 100%;
}

.ai-table th,
.ai-table td {
  border-top: 1px solid var(--border);
  color: var(--ink-700);
  font-size: 12px;
  padding: 8px;
  text-align: left;
}

.ai-table td span {
  color: var(--ink-500);
  display: block;
  margin-top: 2px;
}

.item-node,
.system-node {
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.item-node > summary,
.system-node > summary {
  align-items: center;
  background: var(--bg-elev);
  cursor: pointer;
  display: flex;
  font-size: 12px;
  justify-content: space-between;
  padding: 8px 10px;
}

.system-node {
  margin: 10px;
}

.field-list {
  display: grid;
  gap: 6px;
  padding: 10px;
}

.field-row {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: 18px minmax(180px, 1fr) minmax(120px, 0.8fr) minmax(90px, 0.4fr) auto;
  font-size: 12px;
}

.field-row.cancelled {
  color: var(--ink-400);
  text-decoration: line-through;
}

.badge {
  font-size: 11px;
  font-style: normal;
  font-weight: 700;
  justify-self: start;
}

.badge.required { color: var(--red); }
.badge.business { color: var(--blue); }
.badge.ai { color: var(--violet); }

.add-field {
  border-top: 1px dashed var(--border);
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
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .ir-head,
  .ir-actions,
  .add-field {
    align-items: stretch;
    flex-direction: column;
  }

  .field-row {
    grid-template-columns: 18px 1fr;
  }
}
</style>
