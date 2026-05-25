<template>
  <div>
    <div class="h-eyebrow">第 1 步</div>
    <h1 class="h-title">上传监管发文</h1>
    <p class="h-sub">支持 PDF、Word、Excel、TXT 等格式。上传后系统会自动解析并生成文档画像，识别 1104 报表变更信号。</p>

    <div class="upload-grid mt-24">
      <!-- 左栏：拖拽区 + 样本 -->
      <div>
        <!-- 拖拽上传区 -->
        <label
          :class="['dropzone', { over: dragOver }]"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="onDrop"
        >
          <input
            ref="fileInput"
            type="file"
            style="display:none"
            accept=".txt,.md,.csv,.json,.pdf,.doc,.docx,.xlsx"
            @change="onFileChange"
          />

          <!-- 上传中 -->
          <template v-if="uploading">
            <div class="glyph">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>
            </div>
            <h3>解析中 · {{ uploadingName }}</h3>
            <p>正在调用大模型提取结构、识别报表变更信号…</p>
            <div class="upload-progress">
              <div :style="{ width: uploadProgress + '%' }"></div>
            </div>
          </template>

          <!-- 默认状态 -->
          <template v-else>
            <div class="glyph">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </div>
            <h3>将监管发文拖至此处</h3>
            <p>
              或者
              <span style="color:var(--orange-600);text-decoration:underline;cursor:pointer;font-weight:500;">选择本地文件</span>
              上传
            </p>
            <div class="upload-chips">
              <span class="chip">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                正式通知
              </span>
              <span class="chip">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
                表样 Excel
              </span>
              <span class="chip">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                填报说明
              </span>
              <span class="chip">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                会议纪要
              </span>
            </div>
            <div class="meta">
              <span>PDF / DOCX / XLSX / TXT</span>
              <span>单次 ≤ 50 MB</span>
              <span>支持批量上传</span>
            </div>
          </template>
        </label>

        <!-- 三文件可选上传：报表表样 + 填报说明 + 修订对照表 -->
        <div class="card mt-16">
          <div class="card-head">
            <div>
              <h3 style="font-size:14px;">指标变更扫描（三文件可选上传）</h3>
              <div class="sub">三个文件均为可选，上传什么分析什么。修订对照表优先级最高。</div>
            </div>
          </div>

          <!-- 报表代码输入 -->
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
            <span style="font-size:12px;color:var(--ink-500);white-space:nowrap;">报表代码</span>
            <input
              v-model="tripletObjectCode"
              type="text"
              placeholder="G31"
              style="flex:1;border:1px solid var(--border);border-radius:6px;padding:5px 10px;font-size:13px;font-family:var(--font-mono);"
            />
          </div>

          <div class="triplet-upload">
            <button class="pair-file" type="button" @click="templateInput?.click()">
              <span class="pair-label">① 报表表样</span>
              <span class="pair-name" :style="templateFile ? 'color:var(--green-700)' : ''">
                {{ templateFile?.name || "可选：Excel 表样" }}
              </span>
              <span class="pair-meta">.xls / .xlsx → Excel 结构差异检测</span>
            </button>
            <button class="pair-file" type="button" @click="instructionInput?.click()">
              <span class="pair-label">② 填报说明</span>
              <span class="pair-name" :style="instructionFile ? 'color:var(--green-700)' : ''">
                {{ instructionFile?.name || "可选：Word 填报说明" }}
              </span>
              <span class="pair-meta">.doc / .docx / .pdf → 批注 + 修订提取</span>
            </button>
            <button class="pair-file triplet-third" type="button" @click="revisionTableInput?.click()">
              <span class="pair-label" style="color:var(--orange-600);">③ 修订对照表</span>
              <span class="pair-name" :style="revisionTableFile ? 'color:var(--green-700)' : ''">
                {{ revisionTableFile?.name || "可选：修订对照表 Excel" }}
              </span>
              <span class="pair-meta">.xls / .xlsx → 精确指标变更打标（最高优先级）</span>
            </button>
          </div>

          <input ref="templateInput" type="file" style="display:none" accept=".xls,.xlsx" @change="onTemplateFileChange" />
          <input ref="instructionInput" type="file" style="display:none" accept=".doc,.docx,.pdf,.txt,.md" @change="onInstructionFileChange" />
          <input ref="revisionTableInput" type="file" style="display:none" accept=".xls,.xlsx" @change="onRevisionTableFileChange" />

          <!-- 已选文件徽章 -->
          <div v-if="templateFile || instructionFile || revisionTableFile" class="selected-files">
            <span v-if="templateFile" class="file-badge green">✓ {{ templateFile.name }}</span>
            <span v-if="instructionFile" class="file-badge green">✓ {{ instructionFile.name }}</span>
            <span v-if="revisionTableFile" class="file-badge orange">✓ {{ revisionTableFile.name }}</span>
            <button class="clear-link" @click="clearTripletFiles">清除</button>
          </div>

          <div class="row" style="gap:8px;margin-top:12px;">
            <button
              class="btn primary"
              style="flex:1;justify-content:center;"
              :disabled="busy || (!templateFile && !instructionFile && !revisionTableFile) || uploading"
              @click="startTripletUpload"
            >
              {{ uploading ? "扫描中…" : "上传并扫描指标变更" }}
            </button>
            <button
              class="btn secondary"
              style="white-space:nowrap;"
              :disabled="uploading"
              @click="loadSampleFunnel"
              title="无后端时用样例数据预览三路漏斗（全 3 路）"
            >
              示例·三路
            </button>
            <button
              class="btn secondary"
              style="white-space:nowrap;"
              :disabled="uploading"
              @click="loadSampleFunnelSingleLane"
              title="模拟只上传一个文件的情况（仅填报说明一路）"
            >
              示例·单路
            </button>
          </div>

          <!-- 扫描结果 -->
          <div v-if="tripletResult" class="scan-result-box mt-12">
            <div class="scan-summary">{{ tripletResult.scan_summary || "扫描完成" }}</div>
            <div class="scan-badges">
              <span v-if="tripletResult.revision_entry_count" class="sbadge blue">
                修订对照表 {{ tripletResult.revision_entry_count }} 条
              </span>
              <span v-if="tripletResult.excel_diff_count" class="sbadge yellow">
                Excel 差异 {{ tripletResult.excel_diff_count }} 处
              </span>
              <span v-if="tripletResult.scan_results.length" class="sbadge green">
                已更新 {{ tripletResult.scan_results.length }} 个指标
              </span>
              <span v-if="tripletResult.revision_candidates?.length" class="sbadge blue">
                候选 {{ tripletResult.revision_candidates.length }} 条
              </span>
              <span v-if="unmatchedRevisionCandidates.length" class="sbadge yellow">
                未落格 {{ unmatchedRevisionCandidates.length }} 条
              </span>
            </div>
            <div v-if="tripletResult.error_messages.length" class="scan-errors">
              <div v-for="msg in tripletResult.error_messages" :key="msg" class="scan-error">⚠ {{ msg }}</div>
            </div>
            <details v-if="unmatchedRevisionCandidates.length" class="scan-detail">
              <summary>查看未落格候选（新增/修改/删除待确认）</summary>
              <table class="mini-tbl">
                <thead>
                  <tr><th>分区</th><th>行</th><th>列</th><th>类型</th><th>状态</th><th>依据</th></tr>
                </thead>
                <tbody>
                  <tr v-for="c in unmatchedRevisionCandidates.slice(0, 12)" :key="`${c.section}-${c.row_label}-${c.column_label}`">
                    <td class="mono">{{ c.section }}</td>
                    <td>{{ c.row_label }}</td>
                    <td>{{ c.column_label }}</td>
                    <td><span :class="['stag', statusTagColor(c.change_type)]">{{ c.change_type }}</span></td>
                    <td class="mono">{{ c.match_status }}</td>
                    <td>{{ c.change_desc || c.reason }}</td>
                  </tr>
                </tbody>
              </table>
            </details>
          </div>

          <!-- v2 字段维度修订条目（新版修订对照表展示） -->
          <div
            v-if="tripletResult && fieldLevelRevisions.length"
            class="field-rev-box mt-16"
          >
            <div class="field-rev-head">
              <span class="field-rev-title">修订对照表字段级条目（{{ fieldLevelRevisions.length }} 条）</span>
              <span class="field-rev-sub">来自上传文件原始内容 · 一行 = 一个业务字段</span>
            </div>
            <table class="field-rev-table">
              <thead>
                <tr>
                  <th style="width: 90px">变更类型</th>
                  <th>业务字段</th>
                  <th>变更维度</th>
                  <th>一句话摘要</th>
                  <th style="width: 110px">影响 cell</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in fieldLevelRevisions" :key="c.revision_id || c.field_code">
                  <td>
                    <span :class="['ftype-tag', changeTypeClass(c.change_type)]">{{ c.change_type }}</span>
                  </td>
                  <td>
                    <div class="frev-field-name">{{ c.field_name || c.field_code }}</div>
                    <div class="frev-field-code mono">{{ c.field_code }}</div>
                  </td>
                  <td>
                    <span v-for="d in (c.change_dimensions || [])" :key="d" class="dim-chip">{{ d }}</span>
                  </td>
                  <td class="frev-summary">{{ c.change_summary || c.change_desc || '—' }}</td>
                  <td>
                    <span v-if="(c.matched_item_codes || []).length" class="cell-badge ok">
                      {{ (c.matched_item_codes || []).length }} 个命中
                    </span>
                    <span v-else class="cell-badge none">无 cell 映射</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 三路漏斗融合可视化 -->
          <TripletFunnel
            v-if="tripletResult && (tripletResult.revision_lane.length || tripletResult.excel_lane.length || tripletResult.instruction_lane.length)"
            class="mt-16"
            :scan-results="tripletResult.scan_results"
            :revision-lane="tripletResult.revision_lane"
            :excel-lane="tripletResult.excel_lane"
            :instruction-lane="tripletResult.instruction_lane"
            :scan-summary="tripletResult.scan_summary"
          />
        </div>

        <!-- 已上传发文 -->
        <div class="sec-h mt-24">
          <h2>已上传发文</h2>
          <span class="line"></span>
          <span class="count">{{ documents.length }} 份</span>
        </div>
        <div class="card" style="padding:0;overflow:hidden;">
          <table class="tbl">
            <thead>
              <tr><th>发文标题</th><th>文件名</th><th>上传时间</th><th>状态</th><th></th></tr>
            </thead>
            <tbody>
              <tr
                v-for="doc in documents"
                :key="doc.id"
                :class="{ selected: selectedDocId === doc.id }"
                style="cursor:pointer;"
                @click="selectedDocId = doc.id"
              >
                <td style="font-weight:500;">{{ doc.title || doc.filename }}</td>
                <td class="mono">{{ doc.filename }}</td>
                <td class="mono" style="font-size:12px;">{{ doc.created_at?.slice(0,10) }}</td>
                <td>
                  <span :class="['tag', statusColor(doc.status)]">
                    <span class="dot"></span>{{ statusLabel(doc.status) }}
                  </span>
                </td>
                <td style="white-space:nowrap;">
                  <button
                    class="btn primary sm"
                    :disabled="busy"
                    @click.stop="$emit('create-task', doc.id)"
                  >
                    创建任务
                  </button>
                  <button
                    class="btn-link-danger"
                    :disabled="busy || deletingDocId === doc.id"
                    style="margin-left:8px;"
                    @click.stop="onDeleteDocument(doc)"
                  >
                    {{ deletingDocId === doc.id ? '删除中…' : '删除' }}
                  </button>
                </td>
              </tr>
              <tr v-if="!documents.length">
                <td colspan="5" style="text-align:center;color:var(--ink-400);padding:32px;">暂无发文，请先上传</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 右栏：提示 + 已选发文操作 -->
      <div class="upload-tips">
        <div class="card">
          <h4>关于文档画像</h4>
          <div class="tip-list">
            <div class="tip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <div><b>① 自动结构化：</b>抽取标题、文号、发文机关、生效日期、附件结构。</div>
            </div>
            <div class="tip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              <div><b>② 报表候选：</b>识别 1104 涉及的 G/S 编号及优先级。</div>
            </div>
            <div class="tip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <div><b>③ 变更类型：</b>区分新增、停报、口径调整、频度调整等变更。</div>
            </div>
            <div class="tip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
              <div><b>④ 待确认问题：</b>AI 生成需向业务/科技/监管确认的清单，不替代人工决策。</div>
            </div>
          </div>
        </div>

        <!-- 已选发文操作 -->
        <div v-if="selectedDoc" class="card mt-16">
          <div class="card-head">
            <div>
              <h3 style="font-size:13px;">{{ selectedDoc.title || selectedDoc.filename }}</h3>
              <div class="sub">{{ selectedDoc.filename }} · {{ selectedDoc.char_count }} 字符</div>
            </div>
          </div>
          <div class="kv-list" style="margin-bottom:14px;">
            <div class="kv-row"><span class="k">解析状态</span><span class="v">{{ statusLabel(selectedDoc.status) }}</span></div>
            <div class="kv-row"><span class="k">解析方式</span><span class="v">{{ selectedDoc.parser || "-" }}</span></div>
            <div class="kv-row"><span class="k">段落数</span><span class="v">{{ selectedDoc.paragraph_count }}</span></div>
            <div class="kv-row"><span class="k">表格数</span><span class="v">{{ selectedDoc.table_count }}</span></div>
          </div>
          <button
            class="btn primary"
            style="width:100%;justify-content:center;"
            :disabled="busy"
            @click="$emit('create-task', selectedDoc.id)"
          >
            {{ busy ? "处理中…" : "创建任务 → 进入加工流程" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { RegDocument, DocumentStatus, TripletUploadResponse } from "@/types/api";
import { apiClient } from "@/api/client";
import TripletFunnel from "@/components/TripletFunnel.vue";

const props = defineProps<{
  documents: RegDocument[];
  busy: boolean;
}>();

const emit = defineEmits<{
  upload: [file: File];
  "upload-pair": [templateFile: File, instructionFile: File];
  "create-task": [documentId: number];
  "triplet-done": [response: TripletUploadResponse];
  "document-deleted": [documentId: number];
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const templateInput = ref<HTMLInputElement | null>(null);
const instructionInput = ref<HTMLInputElement | null>(null);
const revisionTableInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const uploadingName = ref("");
const templateFile = ref<File | null>(null);
const instructionFile = ref<File | null>(null);
const revisionTableFile = ref<File | null>(null);
const tripletObjectCode = ref("G31");
const tripletResult = ref<TripletUploadResponse | null>(null);
const selectedDocId = ref<number | null>(props.documents[0]?.id ?? null);
const unmatchedRevisionCandidates = computed(() =>
  tripletResult.value?.revision_candidates?.filter((c) => c.match_status.startsWith("UNMATCHED_")) ?? []
);

// v2 字段维度视图：展示原始 Excel 一行一个 entry。
// 包含已匹配 + 未匹配（NEW/DELETE 等无 cell 的字段也要展示）。
const fieldLevelRevisions = computed(() => {
  const list = tripletResult.value?.revision_candidates ?? [];
  // 只有 v2 文件才有 field_code；老文件 (v1) 没 field_code，跳过
  return list.filter((c) => !!c.field_code);
});

function changeTypeClass(t: string): string {
  const upper = (t || "").toUpperCase();
  if (upper === "NEW") return "ftype-new";
  if (upper === "DELETE" || upper === "DELETED") return "ftype-delete";
  if (upper === "MODIFY" || upper === "MODIFIED") return "ftype-modify";
  return "ftype-other";
}

const deletingDocId = ref<number | null>(null);

async function onDeleteDocument(doc: RegDocument) {
  const ok = window.confirm(
    `确定删除发文「${doc.title || doc.filename}」吗？\n\n` +
    `将级联清理：文档画像、条款、任务、变更候选、影响项、工单草稿，及物理文件。\n` +
    `此操作不可撤销。`
  );
  if (!ok) return;
  deletingDocId.value = doc.id;
  try {
    await apiClient.deleteDocument(doc.id);
    emit("document-deleted", doc.id);
  } catch (err) {
    window.alert(`删除失败：${err}`);
  } finally {
    deletingDocId.value = null;
  }
}

const selectedDoc = computed(() =>
  props.documents.find((d) => d.id === selectedDocId.value) ?? props.documents[0] ?? null
);

watch(
  () => props.documents[0]?.id,
  (id) => {
    if (id) selectedDocId.value = id;
  }
);

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) startUpload(file);
  (e.target as HTMLInputElement).value = "";
}

function onTemplateFileChange(e: Event) {
  templateFile.value = (e.target as HTMLInputElement).files?.[0] ?? null;
  (e.target as HTMLInputElement).value = "";
}

function onInstructionFileChange(e: Event) {
  instructionFile.value = (e.target as HTMLInputElement).files?.[0] ?? null;
  (e.target as HTMLInputElement).value = "";
}

function onRevisionTableFileChange(e: Event) {
  revisionTableFile.value = (e.target as HTMLInputElement).files?.[0] ?? null;
  (e.target as HTMLInputElement).value = "";
}

function clearTripletFiles() {
  templateFile.value = null;
  instructionFile.value = null;
  revisionTableFile.value = null;
  tripletResult.value = null;
}

function onDrop(e: DragEvent) {
  dragOver.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) startUpload(file);
}

function startUpload(file: File) {
  uploadingName.value = file.name;
  uploading.value = true;
  uploadProgress.value = 0;

  const iv = setInterval(() => {
    uploadProgress.value = Math.min(uploadProgress.value + 8 + Math.random() * 6, 90);
  }, 220);

  emit("upload", file);

  setTimeout(() => {
    clearInterval(iv);
    uploadProgress.value = 100;
    setTimeout(() => {
      uploading.value = false;
      uploadProgress.value = 0;
    }, 600);
  }, 3000);
}

async function startTripletUpload() {
  if (!templateFile.value && !instructionFile.value && !revisionTableFile.value) return;

  const names = [templateFile.value?.name, instructionFile.value?.name, revisionTableFile.value?.name]
    .filter(Boolean)
    .join(" + ");
  uploadingName.value = names;
  uploading.value = true;
  uploadProgress.value = 0;
  tripletResult.value = null;

  const iv = setInterval(() => {
    uploadProgress.value = Math.min(uploadProgress.value + 5 + Math.random() * 4, 88);
  }, 250);

  try {
    const result = await apiClient.uploadReportingTriplet(
      tripletObjectCode.value || "G31",
      templateFile.value,
      instructionFile.value,
      revisionTableFile.value,
    );
    tripletResult.value = result;
    emit("triplet-done", result);
  } catch (err) {
    tripletResult.value = {
      document: {} as RegDocument,
      template_parsed: false,
      instruction_parsed: false,
      revision_table_parsed: false,
      revision_entry_count: 0,
      excel_diff_count: 0,
      scan_results: [],
      scan_summary: "",
      excel_diff: [],
      revision_entries: [],
      revision_lane: [],
      excel_lane: [],
      instruction_lane: [],
      revision_candidates: [],
      error_messages: [String(err)],
    };
  } finally {
    clearInterval(iv);
    uploadProgress.value = 100;
    setTimeout(() => {
      uploading.value = false;
      uploadProgress.value = 0;
    }, 600);
  }
}

function loadSampleFunnelSingleLane() {
  const lane = (item_code: string, row: string, col: string, change: string, conf: number, evi: string, won: boolean) => ({
    item_code, row_label: row, column_label: col, change_type: change, confidence: conf, evidence: evi, won,
  });
  tripletResult.value = {
    document: {} as RegDocument,
    template_parsed: false,
    instruction_parsed: true,
    revision_table_parsed: false,
    revision_entry_count: 0,
    excel_diff_count: 0,
    scan_summary: "扫描命中 2 个指标格：修改 2（仅填报说明扫描结果）",
    excel_diff: [],
    revision_entries: [],
    error_messages: [],
    scan_results: [
      { item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", row_label: "金融机构同业融入", column_label: "余额", old_status: "", new_status: "MODIFIED", source: "INSTRUCTION", confidence: 0.75, evidence: "填报说明：'同业融入余额'统计口径调整为实际未到期敞口", overridden_sources: [] },
      { item_code: "G24.MAIN.LOCAL_GOV_REPORTING", row_label: "地方法人机构", column_label: "报送频度", old_status: "", new_status: "MODIFIED", source: "INSTRUCTION", confidence: 0.55, evidence: "填报说明：地方法人机构按月报送", overridden_sources: [] },
    ],
    revision_lane: [],
    excel_lane: [],
    revision_candidates: [],
    instruction_lane: [
      lane("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "金融机构同业融入", "余额", "MODIFIED", 0.75, "填报说明：'同业融入余额'统计口径调整为实际未到期敞口", true),
      lane("G24.MAIN.LOCAL_GOV_REPORTING", "地方法人机构", "报送频度", "MODIFIED", 0.55, "填报说明：地方法人机构按月报送", true),
    ],
  };
}

function loadSampleFunnel() {
  const lane = (item_code: string, row: string, col: string, change: string, conf: number, evi: string, won: boolean) => ({
    item_code, row_label: row, column_label: col, change_type: change, confidence: conf, evidence: evi, won,
  });
  tripletResult.value = {
    document: {} as RegDocument,
    template_parsed: true,
    instruction_parsed: true,
    revision_table_parsed: true,
    revision_entry_count: 4,
    excel_diff_count: 3,
    scan_summary: "扫描命中 6 个指标格：新增 1 · 修改 4 · 删除 1（修订表 4 / Excel 2 / 填报说明 0 胜出）",
    excel_diff: [],
    revision_entries: [],
    error_messages: [],
    scan_results: [
      { item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", row_label: "金融机构同业融入", column_label: "余额", old_status: "", new_status: "MODIFIED", source: "REVISION_TABLE", confidence: 0.95, evidence: "修订对照表：口径由账面余额改为未到期敞口余额", overridden_sources: ["EXCEL_DIFF", "INSTRUCTION"] },
      { item_code: "G24.MAIN.COUNTRY_CODE", row_label: "金融机构同业融入", column_label: "国别代码", old_status: "", new_status: "NEW", source: "REVISION_TABLE", confidence: 0.95, evidence: "修订对照表：新增 C08 列国别代码", overridden_sources: ["EXCEL_DIFF"] },
      { item_code: "G24.MAIN.GSIBS_HAIRCUT", row_label: "G-SIBs 折扣率", column_label: "百分比", old_status: "", new_status: "NEW", source: "REVISION_TABLE", confidence: 0.95, evidence: "修订对照表：R10 行新增 G-SIBs 附加要求", overridden_sources: [] },
      { item_code: "G24.MAIN.LOCAL_GOV_REPORTING", row_label: "地方法人机构", column_label: "报送频度", old_status: "", new_status: "MODIFIED", source: "REVISION_TABLE", confidence: 0.95, evidence: "修订对照表：频度由季报调整为月报", overridden_sources: ["INSTRUCTION"] },
      { item_code: "G24.MAIN.LEGACY_FOREIGN_INST", row_label: "境外机构投资者", column_label: "标识", old_status: "", new_status: "DELETED", source: "EXCEL_DIFF", confidence: 0.80, evidence: "Excel 差异：旧表 R05 列在新表样中已移除", overridden_sources: [] },
      { item_code: "G24.MAIN.SETTLEMENT_DATE", row_label: "结算日", column_label: "日期", old_status: "", new_status: "MODIFIED", source: "EXCEL_DIFF", confidence: 0.80, evidence: "Excel 差异：列名 settle_dt → settlement_date", overridden_sources: ["INSTRUCTION"] },
    ],
    revision_lane: [
      lane("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "金融机构同业融入", "余额", "MODIFIED", 0.95, "修订对照表：口径由账面余额改为未到期敞口余额", true),
      lane("G24.MAIN.COUNTRY_CODE", "金融机构同业融入", "国别代码", "NEW", 0.95, "修订对照表：新增 C08 列国别代码", true),
      lane("G24.MAIN.GSIBS_HAIRCUT", "G-SIBs 折扣率", "百分比", "NEW", 0.95, "修订对照表：R10 行新增 G-SIBs 附加要求", true),
      lane("G24.MAIN.LOCAL_GOV_REPORTING", "地方法人机构", "报送频度", "MODIFIED", 0.95, "修订对照表：频度由季报调整为月报", true),
    ],
    revision_candidates: [
      { table_code: "G24", section: "MAIN", row_label: "金融机构同业融入", column_label: "余额", change_type: "MODIFIED", change_desc: "口径由账面余额改为未到期敞口余额", match_status: "MATCHED_EXISTING", matched_item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", confidence: 0.95, evidence: "修订对照表：口径由账面余额改为未到期敞口余额", reason: "已匹配系统指标" },
      { table_code: "G24", section: "MAIN", row_label: "金融机构同业融入", column_label: "国别代码", change_type: "NEW", change_desc: "新增 C08 列国别代码", match_status: "MATCHED_EXISTING", matched_item_code: "G24.MAIN.COUNTRY_CODE", confidence: 0.95, evidence: "修订对照表：新增 C08 列国别代码", reason: "已匹配系统指标" },
      { table_code: "G24", section: "MAIN", row_label: "集中度补充", column_label: "穿透层级", change_type: "NEW", change_desc: "新增穿透层级字段", match_status: "UNMATCHED_NEW", matched_item_code: "", confidence: 0.70, evidence: "修订对照表：新增穿透层级字段", reason: "未匹配系统已有指标，需落格确认" },
    ],
    excel_lane: [
      lane("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "金融机构同业融入", "余额", "MODIFIED", 0.80, "Excel 差异：列标签从'账面余额'改为'未到期敞口余额'", false),
      lane("G24.MAIN.COUNTRY_CODE", "金融机构同业融入", "国别代码", "NEW", 0.80, "Excel 差异：新表样新增 C08 列", false),
      lane("G24.MAIN.LEGACY_FOREIGN_INST", "境外机构投资者", "标识", "DELETED", 0.80, "Excel 差异：旧表 R05 列在新表样中已移除", true),
      lane("G24.MAIN.SETTLEMENT_DATE", "结算日", "日期", "MODIFIED", 0.80, "Excel 差异：列名 settle_dt → settlement_date", true),
    ],
    instruction_lane: [
      lane("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "金融机构同业融入", "余额", "MODIFIED", 0.75, "填报说明：'同业融入余额'统计口径调整为实际未到期敞口", false),
      lane("G24.MAIN.LOCAL_GOV_REPORTING", "地方法人机构", "报送频度", "MODIFIED", 0.55, "填报说明：地方法人机构按月报送", false),
      lane("G24.MAIN.SETTLEMENT_DATE", "结算日", "日期", "MODIFIED", 0.55, "填报说明：结算日字段命名统一", false),
    ],
  };
}

const statusLabel = (s: DocumentStatus): string =>
  ({ UPLOADED: "已上传", PARSED: "解析完成", FAILED: "解析失败" } as Record<string, string>)[s] ?? s;
const statusColor = (s: DocumentStatus): string =>
  ({ UPLOADED: "blue", PARSED: "green", FAILED: "red" } as Record<string, string>)[s] ?? "outline";
const statusTagColor = (s: string): string =>
  ({ NEW: "green", MODIFIED: "yellow", DELETED: "red", UNCHANGED: "outline" } as Record<string, string>)[s] ?? "outline";
</script>

<style scoped>
.spin {
  animation: spin 1s linear infinite;
}
.triplet-upload {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.triplet-third {
  grid-column: 1 / -1;
}
.selected-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  align-items: center;
}
.file-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-badge.green {
  background: var(--green-50, #f0fdf4);
  color: var(--green-700, #15803d);
  border: 1px solid var(--green-200, #bbf7d0);
}
.file-badge.orange {
  background: var(--orange-50, #fff7ed);
  color: var(--orange-700, #c2410c);
  border: 1px solid var(--orange-200, #fed7aa);
}
.clear-link {
  background: none;
  border: none;
  color: var(--ink-400);
  font-size: 11px;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}
.scan-result-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
}
.scan-summary {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-800);
  margin-bottom: 8px;
}
.scan-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.sbadge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}
.sbadge.blue { background: #eff6ff; color: #1d4ed8; }
.sbadge.yellow { background: #fefce8; color: #a16207; }
.sbadge.green { background: #f0fdf4; color: #15803d; }
.scan-errors { margin-bottom: 6px; }
.scan-error {
  font-size: 12px;
  color: #dc2626;
  padding: 2px 0;
}
.scan-detail {
  margin-top: 8px;
}
.scan-detail summary {
  font-size: 12px;
  color: var(--ink-500);
  cursor: pointer;
  user-select: none;
}
.mini-tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-top: 6px;
}
.mini-tbl th {
  text-align: left;
  padding: 4px 8px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  color: var(--ink-500);
  font-weight: 600;
}
.mini-tbl td {
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--ink-700);
}
.stag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}
.stag.green { background: #dcfce7; color: #15803d; }
.stag.yellow { background: #fef9c3; color: #a16207; }
.stag.red { background: #fee2e2; color: #dc2626; }
.stag.outline { background: #f3f4f6; color: #6b7280; }
.pair-upload {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.pair-file {
  text-align: left;
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: border-color .15s, background .15s;
}
.pair-file:hover {
  border-color: var(--orange-300);
  background: var(--orange-50);
}
.pair-label {
  color: var(--orange-600);
  font-size: 11px;
  font-weight: 700;
}
.pair-name {
  color: var(--ink-900);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  word-break: break-all;
}
.pair-meta {
  color: var(--ink-400);
  font-size: 11px;
  font-family: var(--font-mono);
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* ─── v2 字段维度修订条目视图 ─────────────────────────────────── */
.field-rev-box {
  border: 1px solid #fde8d6;
  border-radius: 12px;
  background: linear-gradient(180deg, #fff8f1 0%, #ffffff 60%);
  padding: 14px 16px;
}
.field-rev-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 10px;
}
.field-rev-title {
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
}
.field-rev-sub {
  font-size: 12px;
  color: #9ca3af;
}
.field-rev-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.field-rev-table thead th {
  text-align: left;
  padding: 8px 10px;
  color: #6b7280;
  font-weight: 500;
  border-bottom: 1px solid #f1d6b8;
  background: #fef3e6;
}
.field-rev-table tbody td {
  padding: 12px 10px;
  border-bottom: 1px solid #f5f5f5;
  vertical-align: top;
  line-height: 1.5;
}
.field-rev-table tbody tr:hover {
  background: #fffaf4;
}
.frev-field-name {
  font-weight: 500;
  color: #1f2937;
}
.frev-field-code {
  color: #9ca3af;
  font-size: 12px;
  margin-top: 2px;
}
.frev-summary {
  color: #374151;
  max-width: 420px;
}
.ftype-tag {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.ftype-new    { background: #dcfce7; color: #15803d; }
.ftype-modify { background: #fef3c7; color: #b45309; }
.ftype-delete { background: #fee2e2; color: #b91c1c; }
.ftype-other  { background: #e5e7eb; color: #4b5563; }
.dim-chip {
  display: inline-block;
  padding: 2px 8px;
  margin: 1px 4px 1px 0;
  border-radius: 10px;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 11px;
}
.cell-badge {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}
.cell-badge.ok   { background: #dbeafe; color: #1e40af; }
.cell-badge.none { background: #f3f4f6; color: #9ca3af; }

/* 删除链接按钮 */
.btn-link-danger {
  background: transparent;
  border: none;
  color: #dc2626;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 6px;
}
.btn-link-danger:hover:not(:disabled) {
  color: #991b1b;
  text-decoration: underline;
}
.btn-link-danger:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}
</style>
