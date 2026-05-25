<template>
  <div>
    <!-- Hero -->
    <div class="portrait-hero">
      <div class="ai-bar">
        <span class="sparkle">✦</span> AI 文档画像 · 大模型生成
      </div>
      <div class="doc-picker" v-if="documents.length">
        <label for="portrait-document-select">画像文章</label>
        <select
          id="portrait-document-select"
          :value="selectedDocumentId ?? ''"
          :disabled="busy"
          @change="$emit('select-document', Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="item in documents" :key="item.id" :value="item.id">
            {{ item.title }} · {{ item.filename }}
          </option>
        </select>
      </div>
      <h1>{{ doc?.title || "监管发文文档画像" }}</h1>
      <div class="meta-row" v-if="doc">
        <span><span class="muted">文件名：</span><b>{{ doc.filename }}</b></span>
        <span><span class="muted">字符数：</span><b>{{ doc.char_count?.toLocaleString() }}</b></span>
        <span><span class="muted">段落数：</span><b>{{ doc.paragraph_count }}</b></span>
        <span><span class="muted">表格数：</span><b>{{ doc.table_count }}</b></span>
        <span><span class="muted">解析质量：</span><b>{{ doc.parse_quality || "-" }}</b></span>
        <span v-if="profile?.llm_model">
          <span class="muted">分析模型：</span>
          <span class="tag outline mono" style="margin-left:4px;">{{ profile.llm_model }}</span>
        </span>
      </div>
      <div class="hero-actions">
        <button class="btn secondary sm" :disabled="!doc || profileBusy" @click="doc && $emit('profile-document', doc.id)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.6"/></svg>
          {{ profileBusy ? "扫描中…" : (profile ? "重新扫描" : "开始扫描") }}
        </button>
        <span v-if="profileScanMessage" class="scan-feedback">{{ profileScanMessage }}</span>
        <button class="btn secondary sm" :disabled="!doc" @click="openRawTextDialog">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          查看原文
        </button>
      </div>
    </div>

    <div class="portrait-grid">
      <!-- 左主栏 -->
      <div class="portrait-main">

        <!-- AI 摘要 -->
        <div class="ai-card" v-if="doc">
          <div class="card-head">
            <div>
              <div class="ai-bar"><span class="sparkle">✦</span> 文档摘要</div>
              <h3 style="margin-top:8px;">大模型生成的发文摘要与变更结论</h3>
            </div>
            <div class="row">
              <span v-if="profile?.llm_model" class="tag outline mono">{{ profile.llm_model }}</span>
            </div>
          </div>
          <p class="summary">
            <template v-if="profile?.reason">{{ profile.reason }}</template>
            <template v-else>{{ doc.text_excerpt || "暂无摘要，请点击「开始扫描」生成文档画像。" }}</template>
          </p>
        </div>

        <!-- 1104 变更扫描结果 -->
        <div class="card" v-if="profile">
          <div class="sec-h">
            <h2>1104 指标变更扫描</h2>
            <span class="line"></span>
            <span class="count">{{ profile.change_signals.length }} 个变更信号</span>
          </div>

          <!-- 涉及表号 -->
          <div class="row" style="flex-wrap:wrap;gap:8px;margin-bottom:16px;" v-if="profile.affected_table_codes.length">
            <span
              v-for="code in profile.affected_table_codes"
              :key="code"
              :class="['tag', isInScope(code) ? 'orange' : 'outline']"
              style="font-family:var(--font-mono);font-size:12px;"
            >
              {{ code }}
              <span v-if="isInScope(code)" style="font-size:9px;opacity:.7;">本行</span>
            </span>
          </div>

          <!-- 幻觉预警提示 -->
          <div
            v-if="profile.change_signals.some(s => s.evidence_verified === false)"
            style="display:flex;align-items:flex-start;gap:10px;padding:10px 14px;background:#fff8ed;border:1px solid #f6b93b;border-radius:8px;margin-bottom:12px;font-size:13px;"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="#d68910" stroke-width="2" style="width:16px;height:16px;flex-shrink:0;margin-top:1px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <span style="color:#7d5a00;">
              <b>检测到疑似幻觉：</b>标记 <span style="background:#f6b93b33;padding:1px 5px;border-radius:4px;font-family:var(--font-mono);">⚠ 未验证</span> 的原文依据在文档中未找到对应片段，请勿直接采信。可展开「LLM 原始响应」核查完整返回。
            </span>
          </div>

          <!-- 变更信号表 -->
          <table class="tbl" v-if="profile.change_signals.length">
            <thead>
              <tr><th>表号</th><th>分区</th><th>指标提示</th><th>变更类型</th><th>置信度</th><th>原文依据</th></tr>
            </thead>
            <tbody>
              <tr v-for="(sig, i) in profile.change_signals" :key="i" :class="{ 'row-unverified': sig.evidence_verified === false }">
                <td>
                  <span :class="['tag', isInScope(sig.table_code) ? 'orange' : 'outline']" style="font-family:var(--font-mono);font-size:12px;">
                    {{ sig.table_code }}
                  </span>
                </td>
                <td style="color:var(--ink-600);font-size:12px;">{{ sig.section_hint || "-" }}</td>
                <td style="font-weight:500;">{{ sig.indicator_hint || "-" }}</td>
                <td>
                  <span :class="['tag', changeTypeColor(sig.change_type)]">{{ changeTypeLabel(sig.change_type) }}</span>
                </td>
                <td>
                  <span class="confidence">
                    <b class="mono">{{ Math.round(sig.confidence * 100) }}%</b>
                    <span class="bar" style="width:40px;"><span :style="{ width: sig.confidence * 100 + '%' }"></span></span>
                  </span>
                </td>
                <td style="font-size:12px;max-width:220px;">
                  <span v-if="sig.evidence_verified === false" class="evidence-unverified" :title="sig.evidence_text">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#d68910" stroke-width="2" style="width:12px;height:12px;flex-shrink:0;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    ⚠ 未验证
                  </span>
                  <span v-else style="color:var(--ink-600);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block;" :title="sig.evidence_text">
                    {{ sig.evidence_text || "-" }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else style="text-align:center;color:var(--ink-400);padding:24px 0;">
            暂未发现变更信号，点击「开始扫描」进行 AI 分析
          </div>

          <!-- 建议路由 -->
          <div style="margin-top:16px;padding:12px 14px;background:var(--surface-alt);border-radius:10px;display:flex;align-items:center;gap:12px;font-size:13px;">
            <span :class="['tag', routeColor(profile.suggested_route)]">{{ routeLabel(profile.suggested_route) }}</span>
            <span style="color:var(--ink-700);">
              置信度 <b class="mono">{{ Math.round(profile.confidence_score * 100) }}%</b>
              <span v-if="profile.should_create_task" style="color:var(--green);margin-left:8px;">· 建议进入完整流程</span>
            </span>
          </div>

          <!-- LLM 原始响应（可折叠，用于幻觉核查） -->
          <details v-if="profile.raw_response" style="margin-top:12px;">
            <summary style="cursor:pointer;font-size:12px;color:var(--ink-400);user-select:none;padding:4px 0;">
              LLM 原始响应（点击展开，用于核查幻觉）
            </summary>
            <pre style="margin-top:8px;padding:12px;background:var(--surface-alt);border:1px solid var(--border);border-radius:8px;font-size:11px;font-family:var(--font-mono);white-space:pre-wrap;word-break:break-all;color:var(--ink-700);max-height:320px;overflow-y:auto;">{{ profile.raw_response }}</pre>
          </details>
        </div>

        <!-- 无画像时提示 -->
        <div class="card" v-else>
          <div style="text-align:center;padding:40px 0;">
            <div style="width:56px;height:56px;background:var(--orange-50);border-radius:16px;display:grid;place-items:center;margin:0 auto 16px;">
              <svg viewBox="0 0 24 24" fill="none" stroke="var(--orange-500)" stroke-width="2" style="width:26px;height:26px;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <h3 style="color:var(--ink-800);margin-bottom:8px;">尚未生成文档画像</h3>
            <p style="color:var(--ink-500);margin-bottom:20px;">点击「开始扫描」，AI 将识别发文涉及的 1104 报表变更信号</p>
            <button class="btn primary" :disabled="!doc || profileBusy" @click="doc && $emit('profile-document', doc.id)">
              {{ profileBusy ? "扫描中…" : "开始扫描" }}
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧栏 -->
      <div class="portrait-side">

        <!-- 置信度 -->
        <div class="card" v-if="profile">
          <div class="card-head">
            <div>
              <h3>画像置信度</h3>
              <div class="sub">影响 AI 召回质量</div>
            </div>
          </div>
          <div class="gauge">
            <div class="gauge-ring" :style="{ '--p': Math.round(profile.confidence_score * 100) }">
              <b>{{ Math.round(profile.confidence_score * 100) }}</b>
            </div>
            <div style="flex:1;font-size:12px;color:var(--ink-600);line-height:1.6;">
              <div><b style="color:var(--ink-900);">范围内报表</b> · {{ profile.in_scope_tables.join(" / ") || "-" }}</div>
              <div><b style="color:var(--ink-900);">变更信号数</b> · {{ profile.change_signals.length }}</div>
              <div><b style="color:var(--ink-900);">处理建议</b> · {{ routeLabel(profile.suggested_route) }}</div>
            </div>
          </div>
        </div>

        <!-- 文档上下文 -->
        <div class="card" v-if="doc">
          <div class="card-head"><div><h3>文档上下文</h3></div></div>
          <div class="kv-list">
            <div class="kv-row"><span class="k">文件名</span><span class="v mono" style="font-size:11px;">{{ doc.filename }}</span></div>
            <div class="kv-row"><span class="k">解析状态</span>
              <span :class="['tag', doc.status === 'PARSED' ? 'green' : doc.status === 'FAILED' ? 'red' : 'blue']">
                {{ { UPLOADED: "已上传", PARSED: "解析完成", FAILED: "解析失败" }[doc.status] }}
              </span>
            </div>
            <div class="kv-row"><span class="k">字符数</span><span class="v">{{ doc.char_count?.toLocaleString() }}</span></div>
            <div class="kv-row"><span class="k">段落</span><span class="v">{{ doc.paragraph_count }}</span></div>
            <div class="kv-row"><span class="k">表格</span><span class="v">{{ doc.table_count }}</span></div>
            <div class="kv-row" v-if="doc.parse_quality"><span class="k">解析质量</span><span class="v">{{ doc.parse_quality }}</span></div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="row" style="gap:8px;">
          <button class="btn secondary" style="flex:1;justify-content:center;" @click="$emit('back')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            返回
          </button>
          <button class="btn primary lg" style="flex:2;justify-content:center;" @click="$emit('continue')">
            进入字段定位
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 填报说明版本变更分析（仅联合上传文档显示） -->
    <div v-if="isPairDoc" class="instruction-analysis-section">
      <div class="sec-h" style="margin-bottom:16px;">
        <div class="ai-bar"><span class="sparkle">✦</span> 填报说明版本变更分析</div>
        <span class="line"></span>
        <span class="count">对比上一版本</span>
      </div>

      <!-- 还未分析 -->
      <div v-if="!instructionAnalysis && !analysisBusy" class="card ia-empty">
        <div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding:32px 0;">
          <div style="width:48px;height:48px;background:var(--orange-50);border-radius:14px;display:grid;place-items:center;">
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--orange-500)" stroke-width="2" style="width:24px;height:24px;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <div style="text-align:center;">
            <div style="font-weight:600;color:var(--ink-800);margin-bottom:4px;">提取 Word 批注与修订，识别版本变更</div>
            <div style="font-size:13px;color:var(--ink-500);">将分析文档中所有批注（批注栏）和修订追踪（插入/删除），结合 G31 报表范围生成变更摘要。</div>
          </div>
          <button
            class="btn primary"
            :disabled="busy || !doc"
            @click="doc && $emit('analyze-instruction-changes', doc.id)"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            分析填报说明变更
          </button>
        </div>
      </div>

      <!-- 分析中 -->
      <div v-else-if="analysisBusy" class="card ia-empty">
        <div style="display:flex;align-items:center;gap:12px;padding:24px;color:var(--ink-600);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin" style="width:20px;height:20px;flex-shrink:0;"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>
          正在提取批注并调用大模型分析变更…
        </div>
      </div>

      <!-- 分析结果 -->
      <template v-else-if="instructionAnalysis">
        <!-- 统计条 -->
        <div class="ia-stat-row">
          <div class="ia-stat">
            <span class="ia-stat-n">{{ instructionAnalysis.comments_count }}</span>
            <span class="ia-stat-l">条批注</span>
          </div>
          <div class="ia-stat">
            <span class="ia-stat-n">{{ instructionAnalysis.revisions_count }}</span>
            <span class="ia-stat-l">条修订</span>
          </div>
          <div class="ia-stat">
            <span class="ia-stat-n">{{ instructionAnalysis.highlights_count }}</span>
            <span class="ia-stat-l">处高亮</span>
          </div>
          <div class="ia-stat" style="margin-left:auto;">
            <span class="tag outline mono" style="font-size:11px;">{{ instructionAnalysis.llm_model }}</span>
          </div>
        </div>

        <!-- LLM 摘要 -->
        <div class="card ia-summary-card" style="margin-top:12px;">
          <div class="card-head" style="margin-bottom:8px;">
            <div class="ai-bar"><span class="sparkle">✦</span> 整体变更摘要</div>
          </div>
          <p style="color:var(--ink-800);line-height:1.7;margin:0;">{{ instructionAnalysis.summary || "（大模型未生成摘要）" }}</p>
        </div>

        <!-- 关键变更明细 -->
        <div v-if="instructionAnalysis.key_changes.length" class="card" style="margin-top:12px;padding:0;overflow:hidden;">
          <div style="padding:14px 16px 10px;border-bottom:1px solid var(--border);">
            <div class="ai-bar"><span class="sparkle">✦</span> 关键变更明细</div>
          </div>
          <table class="tbl">
            <thead>
              <tr><th>变更类型</th><th>变更内容</th><th>依据（批注/原文）</th></tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in instructionAnalysis.key_changes" :key="i">
                <td><span class="tag blue" style="white-space:nowrap;">{{ c.category }}</span></td>
                <td style="font-weight:500;line-height:1.5;">{{ c.change }}</td>
                <td style="font-size:12px;color:var(--ink-500);max-width:200px;word-break:break-all;">{{ c.evidence || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 注意事项 + 待确认 -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
          <div class="card" v-if="instructionAnalysis.attention_items.length">
            <div style="font-weight:600;font-size:13px;color:var(--orange-700);margin-bottom:10px;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;vertical-align:-2px;margin-right:4px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              注意事项
            </div>
            <ul class="ia-list">
              <li v-for="(item, i) in instructionAnalysis.attention_items" :key="i">{{ item }}</li>
            </ul>
          </div>
          <div class="card" v-if="instructionAnalysis.uncertain_items.length">
            <div style="font-weight:600;font-size:13px;color:var(--ink-600);margin-bottom:10px;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;vertical-align:-2px;margin-right:4px;"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              需人工确认
            </div>
            <ul class="ia-list">
              <li v-for="(item, i) in instructionAnalysis.uncertain_items" :key="i">{{ item }}</li>
            </ul>
          </div>
        </div>

        <!-- 重新分析按钮 -->
        <div style="margin-top:12px;display:flex;justify-content:flex-end;">
          <button
            class="btn secondary sm"
            :disabled="busy"
            @click="doc && $emit('analyze-instruction-changes', doc.id)"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.6"/></svg>
            重新分析
          </button>
        </div>
      </template>
    </div>

    <div v-if="showRawText && doc" class="modal-mask" @click.self="showRawText = false">
      <section class="raw-dialog" role="dialog" aria-modal="true" aria-labelledby="raw-dialog-title">
        <header class="raw-dialog-head">
          <div>
            <div class="ai-bar"><span class="sparkle">✦</span> 解析文本</div>
            <h2 id="raw-dialog-title">{{ doc.title || "文档原文" }}</h2>
          </div>
          <button class="icon-close" aria-label="关闭原文弹窗" @click="showRawText = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        <div class="raw-meta">
          <span>{{ doc.filename }}</span>
          <span>{{ doc.char_count?.toLocaleString() || 0 }} 字符</span>
          <span>{{ doc.paragraph_count || 0 }} 段</span>
          <span>解析质量 {{ doc.parse_quality || "-" }}</span>
        </div>

        <div v-if="rawTextBusy" class="raw-loading">正在加载解析文本…</div>
        <template v-else>
          <div v-if="rawDialogFiles.length > 1" class="raw-tabs" role="tablist">
            <button
              v-for="(file, idx) in rawDialogFiles"
              :key="`${file.filename}-${idx}`"
              :class="['raw-tab', { active: idx === activeFileIndex }]"
              role="tab"
              :aria-selected="idx === activeFileIndex"
              @click="activeFileIndex = idx"
            >
              <span class="raw-tab-role">{{ file.role_label || "文件" }}</span>
              <span class="raw-tab-name">{{ file.filename }}</span>
            </button>
          </div>
          <div v-if="activeFile" class="raw-file-meta">
            <span v-if="activeFile.role_label">{{ activeFile.role_label }}</span>
            <span v-if="activeFile.source">来源 · {{ activeFile.source }}</span>
            <span>{{ activeFile.text.length.toLocaleString() }} 字符</span>
            <span v-if="activeFile.error_message" class="raw-file-error">{{ activeFile.error_message }}</span>
          </div>
          <pre class="raw-text">{{ activeFile?.text || rawDialogText || "暂无解析文本。" }}</pre>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { apiClient } from "@/api/client";
import type {
  RawDocumentFile,
  DocumentTaskProfile,
  InstructionChangeAnalysis,
  RegDocument,
  TaskWorkflow,
  TableChangeType,
} from "@/types/api";

const props = defineProps<{
  documents: RegDocument[];
  selectedDocumentId: number | null;
  selectedProfile: DocumentTaskProfile | null;
  instructionAnalysis: InstructionChangeAnalysis | null;
  analysisBusy: boolean;
  workflow: TaskWorkflow | null;
  busy: boolean;
  profileBusy: boolean;
  profileScanMessage: string;
}>();

defineEmits<{
  "select-document": [documentId: number];
  "profile-document": [documentId: number];
  "analyze-instruction-changes": [documentId: number];
  continue: [];
  back: [];
}>();

const doc = computed(() =>
  props.documents.find((item) => item.id === props.selectedDocumentId) ?? props.workflow?.document ?? null
);
const profile = computed(() => props.selectedProfile ?? props.workflow?.document_profile ?? null);
const showRawText = ref(false);
const rawTextBusy = ref(false);
const rawDialogText = ref("");
const rawDialogFiles = ref<RawDocumentFile[]>([]);
const activeFileIndex = ref(0);
const activeFile = computed<RawDocumentFile | null>(
  () => rawDialogFiles.value[activeFileIndex.value] ?? null
);
const isPairDoc = computed(() =>
  doc.value?.content_type === "application/vnd.reg-reporting.pair"
);

async function openRawTextDialog(): Promise<void> {
  if (!doc.value) return;

  showRawText.value = true;
  rawTextBusy.value = true;
  rawDialogText.value = "";
  rawDialogFiles.value = [];
  activeFileIndex.value = 0;
  try {
    const result = await apiClient.getDocumentRawText(doc.value.id);
    rawDialogText.value = result.text || "暂无解析文本。";
    rawDialogFiles.value = result.files ?? [];
  } catch {
    const fallback = doc.value.parsed_text || doc.value.text_excerpt || "暂无解析文本。";
    rawDialogText.value = fallback;
    rawDialogFiles.value = [
      {
        filename: doc.value.filename || doc.value.title || "文档",
        role: "summary",
        role_label: "解析摘要",
        source: "fallback",
        text: fallback,
      },
    ];
  } finally {
    rawTextBusy.value = false;
  }
}

const IN_SCOPE = new Set(["G21", "G24", "G25", "G27", "G31"]);
function isInScope(code: string) { return IN_SCOPE.has(code); }

const changeTypeLabel = (t: TableChangeType): string =>
  ({ ADD: "新增", MODIFY: "修改", DELETE: "删除", SCOPE_ADJUST: "口径调整", INSTRUCTION_ADJUST: "说明调整", UNCLEAR: "待确认" } as Record<string, string>)[t] ?? t;

const changeTypeColor = (t: TableChangeType): string =>
  ({ ADD: "green", MODIFY: "amber", DELETE: "red", SCOPE_ADJUST: "amber", INSTRUCTION_ADJUST: "blue", UNCLEAR: "outline" } as Record<string, string>)[t] ?? "outline";

const routeLabel = (r: string): string =>
  ({ FULL_ANALYSIS: "完整流程", LIGHTWEIGHT_ARCHIVE: "轻量归档", MANUAL_REVIEW: "人工复核", SKIP: "跳过" } as Record<string, string>)[r] ?? r;

const routeColor = (r: string): string =>
  ({ FULL_ANALYSIS: "orange", LIGHTWEIGHT_ARCHIVE: "blue", MANUAL_REVIEW: "amber", SKIP: "outline" } as Record<string, string>)[r] ?? "outline";
</script>

<style scoped>
.doc-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 760px;
  margin: 12px 0 18px;
}

.doc-picker label {
  flex: 0 0 auto;
  color: var(--ink-500);
  font-size: 13px;
  font-weight: 600;
}

.doc-picker select {
  min-width: 280px;
  max-width: min(640px, 100%);
  height: 36px;
  padding: 0 36px 0 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-800);
  font: inherit;
  font-size: 13px;
}

.scan-feedback {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(42, 157, 143, 0.28);
  border-radius: 8px;
  background: rgba(42, 157, 143, 0.09);
  color: var(--green);
  font-size: 12px;
  font-weight: 600;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.42);
}

.raw-dialog {
  width: min(920px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
}

.raw-dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border);
}

.raw-dialog-head h2 {
  margin: 6px 0 0;
  color: var(--ink-900);
  font-size: 18px;
  line-height: 1.4;
}

.icon-close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
  color: var(--ink-600);
  cursor: pointer;
}

.icon-close:hover {
  color: var(--ink-900);
  background: var(--surface);
}

.icon-close svg {
  width: 16px;
  height: 16px;
}

.raw-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-alt);
}

.raw-meta span {
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink-600);
  font-size: 12px;
}

.raw-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 20px 0;
  background: var(--surface-alt);
  border-bottom: 1px solid var(--border);
}

.raw-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--surface);
  color: var(--ink-600);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}

.raw-tab:hover {
  color: var(--ink-900);
}

.raw-tab.active {
  background: var(--surface);
  color: var(--ink-900);
  border-color: var(--accent, var(--ink-900));
  box-shadow: 0 1px 0 var(--surface);
  font-weight: 500;
}

.raw-tab-role {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface-alt);
  color: var(--ink-700);
  font-size: 11px;
}

.raw-tab.active .raw-tab-role {
  background: var(--accent-soft, rgba(255, 122, 47, 0.15));
  color: var(--accent, var(--ink-900));
}

.raw-tab-name {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.raw-file-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-alt);
  font-size: 12px;
  color: var(--ink-600);
}

.raw-file-meta span {
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.raw-file-meta .raw-file-error {
  border-color: var(--danger, #e3493a);
  color: var(--danger, #e3493a);
}

.raw-text {
  flex: 1;
  min-height: 360px;
  margin: 0;
  padding: 18px 20px;
  overflow: auto;
  color: var(--ink-800);
  background: var(--surface);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.raw-loading {
  min-height: 360px;
  display: grid;
  place-items: center;
  color: var(--ink-500);
  font-size: 13px;
}

@media (max-width: 720px) {
  .doc-picker {
    align-items: stretch;
    flex-direction: column;
  }

  .doc-picker select {
    width: 100%;
    min-width: 0;
  }

  .modal-mask {
    padding: 12px;
  }

  .raw-dialog {
    max-height: calc(100vh - 24px);
  }

  .raw-text {
    min-height: 260px;
  }

  .raw-loading {
    min-height: 260px;
  }
}

.row-unverified td {
  background: #fffbf0;
}

.evidence-unverified {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #d68910;
  font-weight: 600;
  font-size: 11px;
  padding: 2px 6px;
  background: #fff3cd;
  border-radius: 4px;
  border: 1px solid #f6b93b;
}

.instruction-analysis-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
}

.ia-empty {
  border: 1px dashed var(--border);
  background: var(--surface-alt);
}

.ia-stat-row {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 16px;
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 10px;
}

.ia-stat {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.ia-stat-n {
  font-size: 22px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--orange-600);
}

.ia-stat-l {
  font-size: 12px;
  color: var(--ink-500);
}

.ia-summary-card {
  border-left: 3px solid var(--orange-400);
}

.ia-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--ink-700);
  line-height: 1.8;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
