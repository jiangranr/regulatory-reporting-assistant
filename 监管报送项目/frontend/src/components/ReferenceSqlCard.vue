<template>
  <section class="sql-card" aria-label="参考 SQL">
    <!-- 不可生成态 -->
    <div v-if="data?.status === 'NOT_APPLICABLE'" class="sql-not-applicable">
      <span class="na-icon">⊘</span>
      <div>
        <div class="na-title">不适用：无需生成参考 SQL</div>
        <div class="na-reason">{{ data.not_applicable_reason || "该子单类型不需要参考 SQL。" }}</div>
      </div>
    </div>

    <template v-else>
      <!-- 安全警示横幅（READY / DEGRADED / EDITED 时恒显） -->
      <div v-if="showSafetyBanner" class="sql-banner safety">
        ⚠️ AI 参考 SQL，必须人工审核后才能用于生产
      </div>

      <!-- 降级横幅 -->
      <div v-if="data?.status === 'DEGRADED'" class="sql-banner danger">
        AI 生成参考 SQL 已降级，请人工审核（语法错误或 LLM 失败）
      </div>

      <!-- STALE 横幅 -->
      <div v-if="data?.status === 'STALE'" class="sql-banner info">
        影响范围已更新，建议重新生成参考 SQL
      </div>

      <!-- 头部：标题 + 操作 -->
      <div class="sql-head">
        <div class="sql-title-row">
          <span class="sql-label">
            {{ data?.ability === 'VALIDATION_ONLY' ? '对账校验 SQL' : '参考 SQL' }}
          </span>
          <span v-if="data?.ability === 'VALIDATION_ONLY'" class="sql-validation-note">
            本 SQL 用于核对两侧口径一致性（差异比对），非取数逻辑
          </span>
          <span v-if="data?.status === 'EDITED_BY_USER'" class="sql-tag edited">已人工编辑</span>
          <span v-if="data?.confidence" class="sql-confidence">
            置信度 {{ Math.round(data.confidence * 100) }}%
          </span>
          <span v-if="data?.sql_dialect && data.status !== 'NOT_GENERATED'" class="sql-dialect">
            {{ data.sql_dialect }}
          </span>
        </div>

        <div v-if="data && data.status !== 'NOT_GENERATED'" class="sql-actions">
          <button
            class="sql-btn ghost"
            :disabled="generating || editing"
            title="重新生成"
            @click="onRegenerate"
          >
            ♻ 重新生成
          </button>
          <button
            v-if="!editing"
            class="sql-btn ghost"
            :disabled="!data.reference_sql"
            title="复制 SQL"
            @click="onCopy"
          >
            {{ copied ? '已复制 ✓' : '📋 复制' }}
          </button>
          <button
            v-if="!editing"
            class="sql-btn ghost"
            :disabled="generating"
            title="编辑"
            @click="editing = true"
          >
            ✏ 编辑
          </button>
          <template v-if="editing">
            <button class="sql-btn ghost" @click="cancelEdit">取消</button>
            <button class="sql-btn primary" :disabled="saving" @click="onSave">
              {{ saving ? '保存中...' : '💾 保存' }}
            </button>
          </template>
          <button
            v-if="!editing"
            class="sql-btn ghost icon-btn"
            :class="{ active: thumbed === 'up' }"
            title="好评"
            @click="onFeedback('up')"
          >👍</button>
          <button
            v-if="!editing"
            class="sql-btn ghost icon-btn"
            :class="{ active: thumbed === 'down' }"
            title="差评"
            @click="onFeedback('down')"
          >👎</button>
        </div>
      </div>

      <!-- 未生成态 -->
      <div v-if="!data || data.status === 'NOT_GENERATED'" class="sql-empty">
        <div class="sql-empty-text">AI 尚未生成参考 SQL</div>
        <button class="sql-btn primary" :disabled="generating" @click="onGenerate">
          <span v-if="generating">生成中...</span>
          <span v-else>🤖 AI 生成</span>
        </button>
      </div>

      <!-- 生成中 skeleton -->
      <div v-else-if="generating" class="sql-skeleton" aria-busy="true">
        <div class="sk-line long"></div>
        <div class="sk-line mid"></div>
        <div class="sk-line long"></div>
        <div class="sk-line short"></div>
        <div class="sk-line mid"></div>
      </div>

      <!-- SQL 查看态 -->
      <template v-else-if="!editing && data.reference_sql">
        <pre class="sql-pre" data-test="sql-display">{{ data.reference_sql }}</pre>
      </template>

      <!-- SQL 编辑态 -->
      <template v-else-if="editing">
        <textarea
          v-model="editBuffer"
          class="sql-textarea"
          spellcheck="false"
          data-test="sql-editor"
          rows="12"
        />
      </template>

      <!-- warnings -->
      <div v-if="data?.warnings?.length" class="sql-warnings">
        <div
          v-for="(w, i) in data.warnings"
          :key="i"
          :class="['sql-warn', w.severity.toLowerCase()]"
          :data-test="`sql-warning-${w.severity.toLowerCase()}`"
        >
          <span class="warn-sev">{{ w.severity }}</span>
          <span class="warn-msg">
            {{ w.message }}
            <code v-if="w.field_code" class="warn-field">{{ w.field_code }}</code>
          </span>
        </div>
      </div>

      <!-- explanation/assumptions（折叠） -->
      <details v-if="data?.explanation || data?.assumptions?.length" class="sql-details">
        <summary>AI 分析说明</summary>
        <p v-if="data.explanation" class="sql-explanation">{{ data.explanation }}</p>
        <ul v-if="data.assumptions?.length" class="sql-assumptions">
          <li v-for="(a, i) in data.assumptions" :key="i">{{ a }}</li>
        </ul>
      </details>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="sql-banner danger" data-test="sql-error">{{ errorMsg }}</div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import type { ReferenceSqlResponse } from "@/types/api";

const props = defineProps<{
  ticketId: number;
  initial?: ReferenceSqlResponse | null;
}>();

const data = ref<ReferenceSqlResponse | null>(props.initial ?? null);
const generating = ref(false);
const editing = ref(false);
const saving = ref(false);
const copied = ref(false);
const thumbed = ref<"up" | "down" | null>(null);
const editBuffer = ref("");
const errorMsg = ref("");

const showSafetyBanner = computed(() =>
  data.value !== null &&
  ["READY", "DEGRADED", "EDITED_BY_USER", "STALE"].includes(data.value.status),
);

const baseUrl = computed(() => `/api/tickets/${props.ticketId}/reference-sql`);

async function fetchCurrent(): Promise<void> {
  try {
    const res = await fetch(baseUrl.value);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data.value = await res.json();
  } catch (e) {
    errorMsg.value = `加载参考 SQL 失败：${(e as Error).message}`;
  }
}

async function onGenerate(): Promise<void> {
  errorMsg.value = "";
  generating.value = true;
  try {
    const res = await fetch(`${baseUrl.value}/generate`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data.value = await res.json();
  } catch (e) {
    errorMsg.value = `生成失败：${(e as Error).message}`;
  } finally {
    generating.value = false;
  }
}

function onRegenerate(): void {
  const ok = window.confirm("确定重新生成参考 SQL 吗？\n\n会覆盖当前 SQL（含人工编辑）。");
  if (ok) onGenerate();
}

async function onSave(): Promise<void> {
  errorMsg.value = "";
  saving.value = true;
  try {
    const res = await fetch(baseUrl.value, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reference_sql: editBuffer.value, comment: "" }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data.value = await res.json();
    editing.value = false;
  } catch (e) {
    errorMsg.value = `保存失败：${(e as Error).message}`;
  } finally {
    saving.value = false;
  }
}

function cancelEdit(): void {
  editing.value = false;
  editBuffer.value = data.value?.reference_sql ?? "";
}

async function onCopy(): Promise<void> {
  if (!data.value?.reference_sql) return;
  await navigator.clipboard.writeText(data.value.reference_sql);
  copied.value = true;
  setTimeout(() => { copied.value = false; }, 1800);
}

async function onFeedback(thumbs: "up" | "down"): Promise<void> {
  try {
    await fetch(`${baseUrl.value}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thumbs, comment: "" }),
    });
    thumbed.value = thumbs;
  } catch {
    // 反馈失败静默
  }
}

onMounted(() => {
  if (!props.initial) fetchCurrent();
  editBuffer.value = props.initial?.reference_sql ?? "";
});
</script>

<style scoped>
.sql-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sql-banner {
  padding: 8px 14px;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.5;
}
.sql-banner.safety {
  background: rgba(177, 116, 0, 0.08);
  color: var(--amber);
  border-bottom: 1px solid rgba(177, 116, 0, 0.18);
}
.sql-banner.danger {
  background: var(--red-bg);
  color: var(--red);
  border-bottom: 1px solid rgba(180, 50, 51, 0.18);
}
.sql-banner.info {
  background: var(--blue-bg, #EFF6FF);
  color: var(--blue);
  border-bottom: 1px solid rgba(42, 93, 170, 0.18);
}

.sql-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.sql-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.sql-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-900);
}
.sql-validation-note {
  font-size: 11.5px;
  color: var(--ink-500);
}
.sql-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.sql-tag.edited {
  background: var(--blue-bg, #EFF6FF);
  color: var(--blue);
  border: 1px solid rgba(42, 93, 170, 0.2);
}
.sql-confidence, .sql-dialect {
  font-size: 11.5px;
  color: var(--ink-500);
  font-family: var(--font-mono);
}

.sql-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.sql-btn {
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.12s, border-color 0.12s;
}
.sql-btn.ghost {
  background: transparent;
  color: var(--ink-700);
  border-color: var(--border);
}
.sql-btn.ghost:hover:not(:disabled) {
  background: var(--surface-alt);
  border-color: var(--border-strong);
}
.sql-btn.ghost.active {
  background: var(--surface-alt);
  border-color: var(--border-strong);
}
.sql-btn.primary {
  background: var(--orange-500, #EA5404);
  color: #fff;
  border-color: transparent;
}
.sql-btn.primary:hover:not(:disabled) {
  opacity: 0.88;
}
.sql-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.sql-btn.icon-btn {
  padding: 4px 7px;
}

.sql-empty {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 22px 14px;
}
.sql-empty-text {
  color: var(--ink-500);
  font-size: 13px;
}

.sql-pre {
  margin: 0;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-900);
  background: #FAFAF8;
  white-space: pre;
  overflow-x: auto;
  border-bottom: 1px solid var(--border);
}

.sql-textarea {
  width: 100%;
  padding: 14px 16px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-900);
  background: #FAFAF8;
  border: none;
  border-bottom: 1px solid var(--border);
  resize: vertical;
  outline: none;
  box-sizing: border-box;
}
.sql-textarea:focus {
  background: #FFF;
  box-shadow: inset 0 0 0 2px rgba(234, 84, 4, 0.3);
}

.sql-skeleton {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sk-line {
  height: 13px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--border) 25%, var(--surface-alt) 50%, var(--border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
.sk-line.long { width: 85%; }
.sk-line.mid { width: 65%; }
.sk-line.short { width: 40%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.sql-warnings {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}
.sql-warn {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  line-height: 1.55;
}
.sql-warn.error { color: var(--red); }
.sql-warn.warning { color: var(--amber); }
.sql-warn.info { color: var(--ink-500); }
.warn-sev {
  font-weight: 700;
  font-size: 10px;
  font-family: var(--font-mono);
  white-space: nowrap;
  padding: 1px 4px;
  border-radius: 3px;
  background: currentColor;
  color: #fff;
  opacity: 0.85;
}
.warn-msg { flex: 1; }
.warn-field {
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0 4px;
  font-size: 11px;
  color: inherit;
  margin-left: 4px;
}

.sql-details {
  padding: 10px 14px;
  font-size: 12.5px;
  color: var(--ink-700);
  border-bottom: 1px solid var(--border);
}
.sql-details summary {
  cursor: pointer;
  color: var(--ink-500);
  font-weight: 600;
  font-size: 12px;
  user-select: none;
}
.sql-explanation {
  margin: 8px 0 4px;
  line-height: 1.7;
}
.sql-assumptions {
  margin: 4px 0 0 16px;
  padding: 0;
  line-height: 1.7;
}

.sql-not-applicable {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 18px 16px;
  background: var(--bg-elev);
  color: var(--ink-500);
}
.na-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 1px;
}
.na-title {
  font-weight: 700;
  font-size: 13px;
  color: var(--ink-600);
  margin-bottom: 4px;
}
.na-reason {
  font-size: 12.5px;
  line-height: 1.65;
}
</style>
