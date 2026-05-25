<template>
  <div>
    <div class="h-eyebrow">报表目录维护</div>
    <h1 class="h-title">批量导入报表目录</h1>
    <p class="h-sub">上传监管局下发的报表目录 zip 包（含 Excel 表样和填报说明），系统自动解析入库全部指标结构。</p>

    <!-- 上传区 -->
    <div class="card mt-16">
      <div class="sec-h">
        <h2>上传 zip 包</h2>
        <span class="line"></span>
        <span v-if="selectedFile" class="count">{{ selectedFile.name }}</span>
      </div>

      <!-- 拖拽上传区域 -->
      <div
        class="upload-zone"
        :class="{ dragging: isDragging, 'has-file': !!selectedFile }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
        @click="fileInput?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".zip"
          style="display:none"
          @change="handleFileChange"
        />
        <template v-if="selectedFile">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:32px;height:32px;color:var(--green);margin-bottom:8px;">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <div style="font-weight:600;color:var(--ink-900);">{{ selectedFile.name }}</div>
          <div style="font-size:12px;color:var(--ink-400);margin-top:4px;">{{ formatBytes(selectedFile.size) }} · 点击重新选择</div>
        </template>
        <template v-else>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:36px;height:36px;color:var(--ink-300);margin-bottom:12px;">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <div style="font-weight:600;color:var(--ink-700);">点击选择或拖拽 zip 文件</div>
          <div style="font-size:12px;color:var(--ink-400);margin-top:6px;">
            支持监管局下发的附件目录格式（含"新增报表"/"修订报表"子文件夹）
          </div>
        </template>
      </div>

      <!-- 来源文件 + 报表过滤 + 上传按钮 -->
      <div style="display:flex;gap:12px;align-items:flex-end;margin-top:16px;">
        <div style="flex:1;">
          <label style="font-size:12px;color:var(--ink-600);display:block;margin-bottom:6px;">来源文件编号（选填）</label>
          <input
            v-model="sourceRef"
            class="text-input"
            placeholder="如：金发〔2024〕39号"
            style="width:100%;box-sizing:border-box;"
          />
        </div>
        <div style="flex:1;">
          <label style="font-size:12px;color:var(--ink-600);display:block;margin-bottom:6px;">
            只处理报表代码
            <span style="color:var(--ink-400);font-weight:400;">（留空=全部；多个用逗号分隔）</span>
          </label>
          <input
            v-model="objectCodesInput"
            class="text-input"
            placeholder="如：G31 或 G31,G32"
            style="width:100%;box-sizing:border-box;font-family:monospace;"
          />
        </div>
        <button
          class="btn primary"
          :disabled="!selectedFile || uploading"
          style="white-space:nowrap;padding:9px 20px;"
          @click="doUpload"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          {{ uploading ? '上传中…' : '开始上传解析' }}
        </button>
      </div>

      <!-- 上传错误提示 -->
      <div v-if="uploadError" style="margin-top:12px;padding:10px 14px;background:var(--red-bg);border-radius:6px;color:var(--red);font-size:13px;">
        {{ uploadError }}
      </div>
    </div>

    <!-- 当前批次进度（轮询中或刚完成） -->
    <div v-if="activeBatch" class="card mt-16">
      <div class="sec-h">
        <h2>解析进度</h2>
        <span class="line"></span>
        <span :class="['tag', batchStatusClass(activeBatch.status)]">{{ batchStatusLabel(activeBatch.status) }}</span>
        <span class="count" style="margin-left:4px;">{{ activeBatch.done_count }}/{{ activeBatch.total_count }} 完成
          <template v-if="activeBatch.fail_count"> · {{ activeBatch.fail_count }} 失败</template>
        </span>
      </div>

      <!-- 批次元信息 -->
      <div style="display:flex;gap:24px;padding:12px 0 16px;border-bottom:1px solid var(--border);margin-bottom:12px;flex-wrap:wrap;">
        <div>
          <div style="font-size:11px;color:var(--ink-400);margin-bottom:2px;">版本</div>
          <div style="font-weight:600;font-family:var(--font-mono);font-size:13px;">{{ activeBatch.version_label || '—' }}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--ink-400);margin-bottom:2px;">来源文件</div>
          <div style="font-size:13px;">{{ activeBatch.source_document_ref || activeBatch.source_zip_filename || '—' }}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--ink-400);margin-bottom:2px;">共</div>
          <div style="font-size:13px;font-weight:600;">{{ activeBatch.total_count }} 张报表</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--ink-400);margin-bottom:2px;">批次号</div>
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--ink-500);">{{ activeBatch.batch_code }}</div>
        </div>
      </div>

      <!-- 报表解析列表 -->
      <table class="tbl">
        <thead>
          <tr>
            <th>报表代码</th>
            <th>变更类型</th>
            <th>状态</th>
            <th>指标项数</th>
            <th>变更摘要</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in activeBatch.items" :key="item.id">
            <td class="mono" style="font-weight:600;">{{ item.object_code }}</td>
            <td>
              <span :class="['tag', item.change_type === 'NEW' ? 'green' : item.change_type === 'MODIFIED' ? 'amber' : 'outline']">
                {{ changeTypeLabel(item.change_type) }}
              </span>
            </td>
            <td>
              <span :class="['tag', itemStatusClass(item.parse_status)]">
                {{ itemStatusLabel(item.parse_status) }}
              </span>
            </td>
            <td style="font-family:var(--font-mono);font-size:13px;">
              {{ item.parse_status === 'DONE' ? item.items_count : '—' }}
            </td>
            <td style="font-size:12px;color:var(--ink-600);max-width:320px;">
              <span v-if="item.parse_status === 'FAILED'" style="color:var(--red);" :title="item.parse_error">
                解析失败：{{ item.parse_error.slice(0, 60) }}…
              </span>
              <span v-else-if="item.change_summary">{{ item.change_summary.slice(0, 80) }}<span v-if="item.change_summary.length > 80">…</span></span>
              <span v-else style="color:var(--ink-300);">—</span>
            </td>
          </tr>
          <tr v-if="!activeBatch.items?.length">
            <td colspan="5" style="text-align:center;color:var(--ink-400);padding:24px;">正在扫描文件…</td>
          </tr>
        </tbody>
      </table>

      <!-- 轮询指示 -->
      <div v-if="isPolling" style="display:flex;align-items:center;gap:8px;margin-top:12px;color:var(--ink-400);font-size:12px;">
        <span class="spinner"></span>
        解析进行中，每 2 秒自动刷新…
      </div>
    </div>

    <!-- 历史批次 -->
    <div class="card mt-16">
      <div class="sec-h">
        <h2>历史批次</h2>
        <span class="line"></span>
        <span class="count">共 {{ batches.length }} 次</span>
      </div>
      <table class="tbl">
        <thead>
          <tr>
            <th>批次号</th>
            <th>版本</th>
            <th>来源文件</th>
            <th>状态</th>
            <th>完成/总数</th>
            <th>失败</th>
            <th>导入时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="b in batches"
            :key="b.id"
            style="cursor:pointer;"
            :class="{ selected: activeBatch?.id === b.id }"
            @click="loadBatch(b.id)"
          >
            <td class="mono" style="font-size:11px;color:var(--ink-500);">{{ b.batch_code }}</td>
            <td class="mono" style="font-weight:600;">{{ b.version_label || '—' }}</td>
            <td style="font-size:12px;color:var(--ink-600);">{{ b.source_document_ref || b.source_zip_filename || '—' }}</td>
            <td><span :class="['tag', batchStatusClass(b.status)]">{{ batchStatusLabel(b.status) }}</span></td>
            <td style="font-family:var(--font-mono);font-size:12px;">{{ b.done_count }} / {{ b.total_count }}</td>
            <td style="font-family:var(--font-mono);font-size:12px;">
              <span v-if="b.fail_count" style="color:var(--red);">{{ b.fail_count }}</span>
              <span v-else style="color:var(--ink-300);">0</span>
            </td>
            <td style="font-size:12px;color:var(--ink-500);">{{ formatDate(b.created_at) }}</td>
          </tr>
          <tr v-if="!batches.length">
            <td colspan="7" style="text-align:center;color:var(--ink-400);padding:24px;">暂无历史批次，请上传 zip 包开始导入</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { apiClient } from "@/api/client";
import type { CatalogBatch } from "@/types/api";

// ── 状态 ──────────────────────────────────────────────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const isDragging = ref(false);
const sourceRef = ref("");
const objectCodesInput = ref("");
const uploading = ref(false);
const uploadError = ref("");

const batches = ref<CatalogBatch[]>([]);
const activeBatch = ref<CatalogBatch | null>(null);
const isPolling = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// ── 文件选择 ──────────────────────────────────────────────────────────────────
function handleDrop(e: DragEvent) {
  isDragging.value = false;
  const file = e.dataTransfer?.files[0];
  if (file && file.name.endsWith(".zip")) {
    selectedFile.value = file;
    uploadError.value = "";
  } else {
    uploadError.value = "请上传 .zip 格式文件";
  }
}

function handleFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) {
    selectedFile.value = file;
    uploadError.value = "";
  }
}

// ── 上传 ──────────────────────────────────────────────────────────────────────
async function doUpload() {
  if (!selectedFile.value || uploading.value) return;
  uploading.value = true;
  uploadError.value = "";
  try {
    const batch = await apiClient.uploadCatalogZip(
      selectedFile.value,
      sourceRef.value || undefined,
      objectCodesInput.value.trim() || undefined,
    );
    selectedFile.value = null;
    sourceRef.value = "";
    objectCodesInput.value = "";
    // 立即加入激活批次，开始轮询
    activeBatch.value = batch;
    await refreshBatches();
    if (batch.status === "PROCESSING" || batch.status === "PENDING") {
      startPolling(batch.id);
    }
  } catch (err) {
    uploadError.value = err instanceof Error ? err.message : "上传失败，请检查后端服务";
  } finally {
    uploading.value = false;
  }
}

// ── 轮询 ──────────────────────────────────────────────────────────────────────
function startPolling(batchId: number) {
  stopPolling();
  isPolling.value = true;
  pollTimer = setInterval(async () => {
    try {
      const updated = await apiClient.getCatalogBatch(batchId);
      activeBatch.value = updated;
      if (updated.status === "DONE" || updated.status === "PARTIAL_FAIL") {
        stopPolling();
        await refreshBatches();
      }
    } catch {
      stopPolling();
    }
  }, 2000);
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  isPolling.value = false;
}

// ── 加载历史批次 ──────────────────────────────────────────────────────────────
async function refreshBatches() {
  try {
    batches.value = await apiClient.listCatalogBatches();
  } catch {
    // 忽略
  }
}

async function loadBatch(batchId: number) {
  try {
    activeBatch.value = await apiClient.getCatalogBatch(batchId);
    stopPolling();
  } catch {
    // 忽略
  }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────────
function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function batchStatusClass(s: string) {
  if (s === "DONE") return "green";
  if (s === "PARTIAL_FAIL") return "amber";
  if (s === "PROCESSING") return "blue";
  return "outline";
}

function batchStatusLabel(s: string) {
  const m: Record<string, string> = { DONE: "完成", PARTIAL_FAIL: "部分失败", PROCESSING: "解析中", PENDING: "待处理" };
  return m[s] ?? s;
}

function itemStatusClass(s: string) {
  if (s === "DONE") return "green";
  if (s === "FAILED") return "red";
  if (s === "PARSING") return "blue";
  return "outline";
}

function itemStatusLabel(s: string) {
  const m: Record<string, string> = { DONE: "完成", FAILED: "失败", PARSING: "解析中", PENDING: "待解析" };
  return m[s] ?? s;
}

function changeTypeLabel(t: string) {
  const m: Record<string, string> = { NEW: "新增", MODIFIED: "修订", INSTRUCTION_ONLY: "说明调整" };
  return m[t] ?? t;
}

// ── 生命周期 ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  await refreshBatches();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.upload-zone {
  border: 2px dashed var(--border-strong);
  border-radius: 10px;
  padding: 40px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: var(--surface-alt);
  text-align: center;
  min-height: 120px;
}
.upload-zone:hover,
.upload-zone.dragging {
  border-color: var(--orange-400);
  background: var(--orange-50);
}
.upload-zone.has-file {
  border-color: var(--green);
  background: var(--green-bg);
}

.text-input {
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
  color: var(--ink-900);
  background: var(--bg-elev);
  outline: none;
  transition: border-color 0.15s;
}
.text-input:focus {
  border-color: var(--orange-400);
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--border-strong);
  border-top-color: var(--orange-500);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
