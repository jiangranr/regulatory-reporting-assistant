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
            <template v-if="profile">{{ briefProfileConclusion }}</template>
            <template v-else>{{ doc.text_excerpt || "暂无摘要，请点击「开始扫描」生成文档画像。" }}</template>
          </p>
        </div>

        <!-- 1104 变更扫描结果 -->
        <div class="card" v-if="profile">
          <div class="sec-h">
            <h2>1104 指标变更扫描</h2>
            <span class="line"></span>
            <span class="count">业务变更信号：{{ businessSignalCount }} 个</span>
            <span v-if="hasImpactItemCount" class="count">影响指标格：{{ impactItemCount }} 个</span>
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

          <div class="trust-card">
            <div class="trust-head">
              <div>
                <h3>AI 可信度检查</h3>
                <p>规则结果与 AI 草稿分开统计；未验证 AI 信号自动隔离，不进入后续工单。</p>
              </div>
              <span class="tag blue">可审计</span>
            </div>
            <div class="trust-stats">
              <div class="trust-stat">
                <span class="trust-label">原文锚定率</span>
                <b>{{ formatPercent(trustMetrics.grounding_rate) }}</b>
                <span>{{ trustMetrics.verified_signals }} / {{ trustMetrics.ai_signals }} 条 AI 信号</span>
              </div>
              <div class="trust-stat warning">
                <span class="trust-label">疑似幻觉</span>
                <b>{{ trustMetrics.partial_signals + trustMetrics.unverified_signals }} 条</b>
                <span>部分命中或未验证</span>
              </div>
              <div class="trust-stat danger">
                <span class="trust-label">已隔离</span>
                <b>{{ trustMetrics.isolated_signals }} 条</b>
                <span>禁止自动进入工单</span>
              </div>
              <div class="trust-stat">
                <span class="trust-label">待人工复核</span>
                <b>{{ trustMetrics.pending_review_signals }} 条</b>
                <span>可采纳或退回</span>
              </div>
            </div>
            <div class="trust-progress">
              <span :style="{ width: `${Math.round(trustMetrics.grounding_rate * 100)}%` }"></span>
            </div>
          </div>

          <!-- 幻觉预警提示 -->
          <div
            v-if="profile.change_signals.some(s => signalGroundingStatus(s) === 'UNVERIFIED')"
            style="display:flex;align-items:flex-start;gap:10px;padding:10px 14px;background:#fff8ed;border:1px solid #f6b93b;border-radius:8px;margin-bottom:12px;font-size:13px;"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="#d68910" stroke-width="2" style="width:16px;height:16px;flex-shrink:0;margin-top:1px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <span style="color:#7d5a00;">
              <b>检测到疑似幻觉：</b>标记 <span style="background:#f6b93b33;padding:1px 5px;border-radius:4px;font-family:var(--font-mono);">⚠ 未验证</span> 的原文依据在文档中未找到对应片段，请勿直接采信。可展开「LLM 原始响应」核查完整返回。
            </span>
          </div>
          <div v-if="reviewError" class="review-error">{{ reviewError }}</div>

          <!-- 变更信号表 -->
          <div v-if="profile.change_signals.length" class="signal-table-scroll">
          <table class="tbl signal-table">
            <thead>
              <tr><th>表号</th><th>分区</th><th>指标提示</th><th>变更类型</th><th>置信度</th><th>变更摘要</th><th>锚定状态</th><th>人工复核</th><th>详情</th></tr>
            </thead>
            <tbody>
              <tr
                v-for="group in businessSignalGroups"
                :key="group.id"
                :class="{ 'row-unverified': group.groundingStatus === 'UNVERIFIED' }"
              >
                <td>
                  <span :class="['tag', isInScope(group.tableCode) ? 'orange' : 'outline']" style="font-family:var(--font-mono);font-size:12px;">
                    {{ group.tableCode }}
                  </span>
                </td>
                <td style="color:var(--ink-600);font-size:12px;">{{ group.sectionHint || "-" }}</td>
                <td style="font-weight:500;">{{ group.indicatorHint || "-" }}</td>
                <td>
                  <span :class="['tag', changeTypeColor(group.changeType)]">{{ changeTypeLabel(group.changeType) }}</span>
                </td>
                <td>
                  <span class="confidence">
                    <b class="mono">{{ Math.round(group.confidence * 100) }}%</b>
                    <span class="bar" style="width:40px;"><span :style="{ width: group.confidence * 100 + '%' }"></span></span>
                  </span>
                </td>
                <td class="evidence-cell">
                  <span v-if="group.summary" class="evidence-plain" :title="group.summary">{{ group.summary }}</span>
                  <span v-else class="evidence-empty">-</span>
                </td>
                <td>
                  <span :class="['grounding-chip', groundingColorForStatus(group.groundingStatus)]">{{ groundingStatusLabel(group.groundingStatus) }}</span>
                  <span v-if="group.showCoverage" class="coverage-text">
                    {{ formatPercent(group.groundingCoverage) }}
                  </span>
                </td>
                <td>
                  <div v-if="group.primaryReviewableIndex !== null && group.reviewStatus === 'PENDING'" class="review-actions">
                    <button class="review-btn accept" :disabled="reviewingSignalIndex === group.primaryReviewableIndex" @click="reviewSignal(group.primaryReviewableIndex, 'ACCEPTED')">采纳</button>
                    <button class="review-btn reject" :disabled="reviewingSignalIndex === group.primaryReviewableIndex" @click="reviewSignal(group.primaryReviewableIndex, 'REJECTED')">退回</button>
                  </div>
                  <span v-else :class="['review-result', group.reviewStatus.toLowerCase()]">
                    {{ reviewStatusLabel(group.reviewStatus) }}
                  </span>
                </td>
                <td>
                  <button class="detail-btn" type="button" @click="activeGroupId = activeGroupId === group.id ? null : group.id">
                    {{ activeGroupId === group.id ? "收起" : "查看" }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
          <section v-if="activeBusinessSignal" class="signal-detail-panel">
            <div class="detail-head">
              <div>
                <span class="tag outline mono">{{ activeBusinessSignal.tableCode }}</span>
                <span :class="['tag', changeTypeColor(activeBusinessSignal.changeType)]">{{ changeTypeLabel(activeBusinessSignal.changeType) }}</span>
                <h3>{{ activeBusinessSignal.indicatorHint || "未命名变更信号" }}</h3>
              </div>
              <button class="close-detail" type="button" aria-label="关闭详情" @click="activeGroupId = null">×</button>
            </div>
            <div class="detail-summary">
              <div class="detail-label">业务变更摘要</div>
              <p>{{ activeBusinessSignal.summary }}</p>
            </div>
            <div class="detail-grid">
              <div>
                <div class="detail-label">来源明细</div>
                <article
                  v-for="source in activeBusinessSignal.sources"
                  :key="source.originalIndex"
                  class="source-card"
                >
                  <div class="source-card-head">
                    <span :class="['grounding-chip', sourceColor(source.signal)]">{{ sourceLabel(source.signal) }}</span>
                    <span :class="['grounding-chip', groundingColor(source.signal)]">{{ groundingLabel(source.signal) }}</span>
                    <span class="mono">{{ Math.round(source.signal.confidence * 100) }}%</span>
                  </div>
                  <div class="source-meta">
                    {{ source.signal.section_hint || "无分区" }} · {{ changeTypeLabel(effectiveChangeType(source.signal)) }}
                  </div>
                  <div v-if="detailEvidenceText(source.signal)" class="source-evidence">
                    <b>原文依据</b>
                    <span class="source-evidence-row">
                      <template v-for="(segment, segmentIndex) in detailEvidenceSegments(source.signal)" :key="segmentIndex">
                        <ins
                          v-if="segment.action === '新增'"
                          class="source-revision-mark source-revision-add"
                          :title="segment.title"
                        >{{ segment.text }}</ins>
                        <del
                          v-else-if="segment.action === '删除'"
                          class="source-revision-mark source-revision-delete"
                          :title="segment.title"
                        >{{ segment.text }}</del>
                        <mark
                          v-else-if="segment.action"
                          class="source-revision-mark source-revision-modify"
                          :title="segment.title"
                        >{{ segment.text }}</mark>
                        <span v-else>{{ segment.text }}</span>
                      </template>
                    </span>
                  </div>
                </article>
              </div>
              <div>
                <div class="detail-label">归并依据</div>
                <ul class="merge-reasons">
                  <li>主列表展示后端归并后的业务变更信号。</li>
                  <li>候选来源、原位修订片段和原文依据仅在详情中展示。</li>
                  <li>变更摘要来自后端结构化总结；前端不解释修订词含义。</li>
                </ul>
              </div>
            </div>
          </section>
          <div v-if="!profile.change_signals.length" style="text-align:center;color:var(--ink-400);padding:24px 0;">
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
              <div><b style="color:var(--ink-900);">业务变更信号</b> · {{ businessSignalCount }}</div>
              <div v-if="hasImpactItemCount"><b style="color:var(--ink-900);">影响指标格</b> · {{ impactItemCount }}</div>
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
import { formatReadableEvidence, normalizeEvidenceText, shortenText } from "@/utils/evidence";
import type {
  RawDocumentFile,
  DocumentTaskProfile,
  HallucinationMetrics,
  InstructionChangeAnalysis,
  RegDocument,
  RevisionSpan,
  TableChangeSignal,
  TaskWorkflow,
  TableChangeType,
} from "@/types/api";

const props = defineProps<{
  documents: RegDocument[];
  selectedDocumentId: number | null;
  selectedProfile: DocumentTaskProfile | null;
  impactItemCount?: number | null;
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
interface SignalSource {
  signal: TableChangeSignal;
  originalIndex: number;
}

interface BusinessSignalGroup {
  id: string;
  tableCode: string;
  sectionHint: string;
  indicatorHint: string;
  changeType: TableChangeType;
  confidence: number;
  summary: string;
  groundingStatus: string;
  groundingCoverage: number;
  showCoverage: boolean;
  reviewStatus: string;
  primaryReviewableIndex: number | null;
  sources: SignalSource[];
}

const activeGroupId = ref<string | null>(null);
const businessSignalGroups = computed<BusinessSignalGroup[]>(() =>
  buildBusinessSignalGroups(profile.value?.change_signals ?? []),
);
const activeBusinessSignal = computed<BusinessSignalGroup | null>(
  () => businessSignalGroups.value.find((group) => group.id === activeGroupId.value) ?? null,
);
const businessSignalCount = computed(() => businessSignalGroups.value.length);
const localReviewStatuses = ref<Record<number, string>>({});
const reviewingSignalIndex = ref<number | null>(null);
const reviewError = ref("");
const trustMetrics = computed<HallucinationMetrics>(() => {
  const signals = profile.value?.change_signals ?? [];
  const metrics: HallucinationMetrics = {
    total_signals: signals.length,
    ai_signals: 0,
    rule_based_signals: 0,
    verified_signals: 0,
    partial_signals: 0,
    unverified_signals: 0,
    isolated_signals: 0,
    grounding_rate: 0,
    suspected_hallucination_rate: 0,
    isolation_rate: 0,
    pending_review_signals: 0,
    accepted_signals: 0,
    rejected_signals: 0,
    corrected_signals: 0,
    human_acceptance_rate: 0,
  };
  signals.forEach((signal, index) => {
    const grounding = signalGroundingStatus(signal);
    const review = signalReviewStatus(signal, index);
    if (grounding === "RULE_BASED") metrics.rule_based_signals += 1;
    else {
      metrics.ai_signals += 1;
      if (grounding === "VERIFIED") metrics.verified_signals += 1;
      if (grounding === "PARTIAL") metrics.partial_signals += 1;
      if (grounding === "UNVERIFIED") {
        metrics.unverified_signals += 1;
        if (!["ACCEPTED", "CORRECTED"].includes(review)) metrics.isolated_signals += 1;
      }
    }
    if (["PARTIAL", "UNVERIFIED"].includes(grounding) && review === "PENDING") metrics.pending_review_signals += 1;
    if (review === "ACCEPTED") metrics.accepted_signals += 1;
    if (review === "REJECTED") metrics.rejected_signals += 1;
    if (review === "CORRECTED") metrics.corrected_signals += 1;
  });
  if (metrics.ai_signals) {
    metrics.grounding_rate = metrics.verified_signals / metrics.ai_signals;
    metrics.suspected_hallucination_rate = (metrics.partial_signals + metrics.unverified_signals) / metrics.ai_signals;
    metrics.isolation_rate = metrics.isolated_signals / metrics.ai_signals;
  }
  const reviewed = metrics.accepted_signals + metrics.rejected_signals + metrics.corrected_signals;
  if (reviewed) metrics.human_acceptance_rate = (metrics.accepted_signals + metrics.corrected_signals) / reviewed;
  return metrics;
});
const hasImpactItemCount = computed(() => typeof props.impactItemCount === "number");
const briefProfileConclusion = computed(() => buildBriefProfileConclusion(profile.value, doc.value?.text_excerpt ?? ""));
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

function effectiveChangeType(signal: TableChangeSignal): TableChangeType {
  const evidence = signal.evidence_text || "";
  if (/\[\s*(?:新增|删除)\s*\|/.test(evidence)) {
    const body = evidence.replace(/-?\s*\[\s*(?:新增|删除)\s*\|[^\]]+\]\s*/g, "").trim();
    const businessText = `${signal.indicator_hint || ""} ${body}`;
    if (/\[\s*新增\s*\|/.test(evidence) && /新增\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)/.test(body)) return "ADD";
    if (/\[\s*删除\s*\|/.test(evidence) && /(?:删除|停报)\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)/.test(body)) return "DELETE";
    if (/(定义|公式|计算|口径|范围|填报|统计|指项目)/.test(businessText)) return "SCOPE_ADJUST";
  }
  return signal.change_type;
}

const routeLabel = (r: string): string =>
  ({ FULL_ANALYSIS: "完整流程", LIGHTWEIGHT_ARCHIVE: "轻量归档", MANUAL_REVIEW: "人工复核", SKIP: "跳过" } as Record<string, string>)[r] ?? r;

const routeColor = (r: string): string =>
  ({ FULL_ANALYSIS: "orange", LIGHTWEIGHT_ARCHIVE: "blue", MANUAL_REVIEW: "amber", SKIP: "outline" } as Record<string, string>)[r] ?? "outline";

function buildBusinessSignalGroups(signals: TableChangeSignal[]): BusinessSignalGroup[] {
  const groups = new Map<string, SignalSource[]>();
  signals.forEach((signal, originalIndex) => {
    const key = businessSignalKey(signal);
    groups.set(key, [...(groups.get(key) ?? []), { signal, originalIndex }]);
  });
  return Array.from(groups.entries()).map(([id, sources]) => {
    const primary = choosePrimarySignal(sources.map((source) => source.signal));
    const groundingStatus = mergedGroundingStatus(sources.map((source) => source.signal));
    const reviewable = groundingStatus === "RULE_BASED" ? undefined : sources.find((source) => needsHumanReview(source.signal));
    const coverageSignals = sources
      .map((source) => source.signal.grounding_coverage ?? 0)
      .filter((value) => value > 0);
    const reviewStatus = reviewable
      ? signalReviewStatus(reviewable.signal, reviewable.originalIndex)
      : signalReviewStatus(primary);
    const displaySources = expandedSignalSources(sources, primary);
    return {
      id,
      tableCode: primary.table_code,
      sectionHint: primary.section_hint,
      indicatorHint: primary.indicator_hint,
      changeType: mergedChangeType(sources.map((source) => source.signal)),
      confidence: Math.max(...sources.map((source) => source.signal.confidence || 0)),
      summary: changeSummary(primary, sources.map((source) => source.signal)),
      groundingStatus,
      groundingCoverage: coverageSignals.length ? Math.max(...coverageSignals) : 0,
      showCoverage: groundingStatus !== "RULE_BASED" && coverageSignals.length > 0,
      reviewStatus,
      primaryReviewableIndex: reviewable?.originalIndex ?? null,
      sources: displaySources,
    };
  });
}

function businessSignalKey(signal: TableChangeSignal): string {
  if (signal.business_signal_id) return signal.business_signal_id;
  const itemCode = primaryBusinessItemCode(signal);
  if (itemCode) return `${signal.table_code || "UNKNOWN"}::item:${itemCode}`;
  const keyHint = normaliseSignalKey(signal.matched_item_code || signal.indicator_hint || signal.section_hint);
  return `${signal.table_code || "UNKNOWN"}::${keyHint}`;
}

function primaryBusinessItemCode(signal: TableChangeSignal): string {
  return extractBusinessItemCodes(
    [
      signal.matched_item_code,
      signal.indicator_hint,
      signal.evidence_text,
      signal.section_hint,
    ].filter(Boolean).join(" "),
  )[0] || "";
}

function extractBusinessItemCodes(value = ""): string[] {
  const codes: string[] = [];
  const pattern = /(^|[^A-Za-z0-9.])([1-9]\d?(?:\.[0-9A-Za-z]+)+)(?=$|[^A-Za-z0-9.])/g;
  for (const match of value.matchAll(pattern)) {
    const code = (match[2] || "").replace(/．/g, ".").toLowerCase();
    if (code && !codes.includes(code)) codes.push(code);
  }
  return codes.filter((code) => !codes.some((other) => other !== code && other.startsWith(`${code}.`)));
}

function normaliseSignalKey(value = ""): string {
  return value
    .toLowerCase()
    .replace(/^\s*\[[^\]]+\]\s*/, "")
    .replace(/[\s\[\]【】（）()_.．、，,；;:：\-]+/g, "");
}

function choosePrimarySignal(signals: TableChangeSignal[]): TableChangeSignal {
  return [...signals].sort((left, right) => signalPriority(right) - signalPriority(left))[0] ?? signals[0];
}

function signalPriority(signal: TableChangeSignal): number {
  const source = signal.source_type || "LLM";
  const grounding = signalGroundingStatus(signal);
  const sourceScore = source === "RULE_BASED" || source === "REVISION_TABLE" || source === "EXCEL_DIFF" ? 100 : 0;
  const groundingScore = grounding === "RULE_BASED" ? 40 : grounding === "VERIFIED" ? 30 : grounding === "PARTIAL" ? 15 : 0;
  return sourceScore + groundingScore + (signal.confidence || 0);
}

function mergedChangeType(signals: TableChangeSignal[]): TableChangeType {
  const priority: Record<TableChangeType, number> = {
    ADD: 6,
    DELETE: 5,
    MODIFY: 4,
    SCOPE_ADJUST: 3,
    INSTRUCTION_ADJUST: 2,
    UNCLEAR: 1,
  };
  const types = signals.map((signal) => effectiveChangeType(signal));
  return types.sort((left, right) => priority[right] - priority[left])[0] ?? "UNCLEAR";
}

function mergedGroundingStatus(signals: TableChangeSignal[]): string {
  const statuses = signals.map(signalGroundingStatus);
  if (statuses.includes("RULE_BASED")) return "RULE_BASED";
  if (statuses.includes("VERIFIED")) return "VERIFIED";
  if (statuses.includes("PARTIAL")) return "PARTIAL";
  if (statuses.includes("UNVERIFIED")) return "UNVERIFIED";
  return "VERIFIED";
}

function changeSummary(primary: TableChangeSignal, allSignals: TableChangeSignal[]): string {
  const explicit = explicitSignalSummary(primary);
  if (explicit) return explicit;

  const evidence = allSignals.map((signal) => signal.evidence_text || "").join("；");
  const insertedTerms = extractRevisionTerms(evidence, "新增");
  const deletedTerms = extractRevisionTerms(evidence, "删除");
  const indicator = cleanSignalFocus(primary.indicator_hint) || primary.indicator_hint || "该指标";
  if (insertedTerms.length) {
    return `口径调整：${indicator}修订记录新增${formatSummaryTerms(insertedTerms)}，需人工确认具体业务含义。`;
  }
  if (deletedTerms.length) {
    return `口径调整：${indicator}修订记录删除${formatSummaryTerms(deletedTerms)}，需人工确认具体业务含义。`;
  }
  if (primary.change_type === "ADD") return `新增指标：${indicator}。`;
  if (primary.change_type === "DELETE") return `删除指标：${indicator}。`;
  return plainEvidenceText(primary) || `${changeTypeLabel(effectiveChangeType(primary))}：${indicator}。`;
}

function formatSummaryTerms(terms: string[]): string {
  return terms.map((term) => `“${term}”`).join("、");
}

function explicitSignalSummary(signal: TableChangeSignal): string {
  const record = signal as TableChangeSignal & {
    change_summary?: string;
    business_summary?: string;
    llm_summary?: string | { change_summary?: string; display_title?: string; business_meaning?: string };
  };
  if (record.change_summary) return record.change_summary;
  if (record.business_summary) return record.business_summary;
  if (typeof record.llm_summary === "string") return record.llm_summary;
  if (record.llm_summary?.change_summary) return record.llm_summary.change_summary;
  return "";
}

function extractRevisionTerms(evidence: string, operation: "新增" | "删除"): string[] {
  const terms: string[] = [];
  const pattern = new RegExp(`\\[\\s*${operation}\\s*\\|[^\\]]+\\]\\s*([^；\\n]+)`, "g");
  for (const match of evidence.matchAll(pattern)) {
    const term = cleanRevisionTerm(match[1] || "");
    if (term && term.length <= 24 && !terms.includes(term)) terms.push(term);
  }
  return terms;
}

function cleanRevisionTerm(value: string): string {
  const term = normalizeEvidenceText(value).replace(/^[-*]\s*/, "").trim().replace(/[，,。；;、]+$/g, "");
  const column = term.match(/^([A-Z])[.．]?$/);
  if (column) return `${column[1]}列`;
  return term;
}

function expandedSignalSources(sources: SignalSource[], primary: TableChangeSignal): SignalSource[] {
  if (!primary.candidate_sources?.length) return sources;
  return primary.candidate_sources.map((source, index) => ({
    originalIndex: sources[0]?.originalIndex ?? index,
    signal: {
      table_code: String(source.table_code || primary.table_code || ""),
      section_hint: String(source.section_hint || ""),
      indicator_hint: String(source.indicator_hint || primary.indicator_hint || ""),
      change_type: (source.change_type || primary.change_type || "UNCLEAR") as TableChangeType,
      evidence_text: String(source.evidence_text || ""),
      change_summary: String(source.change_summary || ""),
      business_summary: String(source.business_summary || ""),
      confidence: Number(source.confidence ?? primary.confidence ?? 0),
      evidence_verified: source.evidence_verified ?? primary.evidence_verified ?? true,
      source_type: source.source_type || primary.source_type,
      grounding_status: source.grounding_status || primary.grounding_status,
      grounding_coverage: Number(source.grounding_coverage ?? primary.grounding_coverage ?? 0),
      matched_excerpt: String(source.matched_excerpt || ""),
      human_review_status: source.human_review_status || primary.human_review_status,
      matched_item_code: String(source.matched_item_code || ""),
      match_status: String(source.match_status || ""),
      composite_match: source.composite_match,
      revision_spans: Array.isArray(source.revision_spans) && source.revision_spans.length
        ? source.revision_spans
        : primary.revision_spans || [],
    },
  }));
}

function buildBriefProfileConclusion(profile: DocumentTaskProfile | null, fallback: string): string {
  if (!profile) return fallback;
  const tables = profile.in_scope_tables.length ? profile.in_scope_tables : profile.affected_table_codes;
  const tableText = tables.length ? tables.join(" / ") : "当前文档";
  const signals = businessSignalGroups.value;
  if (!signals.length) {
    return shortenText(profile.reason || fallback || "暂未识别到明确变更信号。", 120);
  }

  const focuses = Array.from(
    new Set(
      signals
        .map((signal) => cleanSignalFocus(signal.indicatorHint || signal.sectionHint))
        .filter(Boolean),
    ),
  ).slice(0, 2);
  const route = profile.should_create_task ? "可进入字段定位和影响确认。" : "建议先人工复核后再决定是否建单。";
  return `${tableText} 发现 ${signals.length} 条相关变更，重点是${focuses.join("、") || "报送口径"}，${route}`;
}

function cleanSignalFocus(value = ""): string {
  let text = value
    .replace(/_/g, "")
    .replace(/^\[[^\]]+\]\s*/, "")
    .replace(/\s+/g, " ")
    .trim();
  const columnPair = text.match(/^([A-Z])列\s*\/\s*([A-Z])列\s*(.+)$/);
  if (columnPair) {
    return shortenText(stripFocusDetail(`${columnPair[1]}/${columnPair[2]}列${columnPair[3].trim()}`), 24);
  }
  const bracketed = text.match(/^\[\s*([A-Z])\s+([A-Z][.．]?\s*)?(.+?)\s*\]$/);
  if (bracketed) text = bracketed[3];
  text = text
    .replace(/^\[\s*/, "")
    .replace(/\s*\]$/, "")
    .replace(/^[A-Z]\s+[A-Z][.．]?\s*/, "")
    .replace(/^[A-Z]列\s*/, "")
    .replace(/^\s*[A-Z][.．、]\s*/, "")
    .replace(/^\s*[/、，；:：-]+/, "")
    .trim();
  return shortenText(stripFocusDetail(text), 24);
}

function stripFocusDetail(value: string): string {
  return value
    .replace(/（[^）]*）/g, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/\s*[-－]\s*/g, "")
    .trim();
}

function plainEvidenceText(signal: TableChangeSignal): string {
  const raw = signal.evidence_text ?? "";
  if (!raw) return "";
  const rows = formatReadableEvidence(raw, [], { contextualRevisions: true });
  const joined = rows.map((row) => row.text).filter(Boolean).join("\uff1b");
  const fallback = joined || normalizeEvidenceText(raw);
  if (fallback.replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, "").length > 4) {
    return fallback;
  }
  return cleanSignalFocus(signal.indicator_hint) || signal.indicator_hint || fallback;
}

interface DetailEvidenceSegment {
  text: string;
  action?: string;
  title?: string;
  author?: string;
  date?: string;
}

function detailEvidenceText(signal: TableChangeSignal): string {
  const raw = signal.evidence_text ?? "";
  const jsonSpans = parseRevisionSpansFromEvidence(raw);
  if (jsonSpans.length) return jsonSpans.map((span) => span.text).join("");
  const context = raw.match(/(?:^|；)\s*(\[\s*\d+(?:\.[0-9A-Za-z]+)+\s+[^\]]+\]\s*指[\s\S]*)$/)?.[1];
  return context ? normalizeEvidenceText(context) : plainEvidenceText(signal);
}

function detailEvidenceSegments(signal: TableChangeSignal): DetailEvidenceSegment[] {
  const revisionSpans = normalizedRevisionSpans(signal);
  if (revisionSpans.length) {
    return revisionSpans.map((span) => ({
      text: span.text,
      action: span.action,
      title: revisionSpanTitle(span),
    })).filter((segment) => segment.text);
  }
  return [{ text: detailEvidenceText(signal) }].filter((segment) => segment.text);
}

function revisionActionClass(action: string): string {
  if (action === "新增") return "source-revision-add";
  if (action === "删除") return "source-revision-delete";
  return "source-revision-modify";
}

function normalizedRevisionSpans(signal: TableChangeSignal): DetailEvidenceSegment[] {
  const spans = Array.isArray(signal.revision_spans) && signal.revision_spans.length
    ? signal.revision_spans
    : parseRevisionSpansFromEvidence(signal.evidence_text ?? "");
  return spans
    .map((span) => {
      const type = String(span.type || "TEXT").toUpperCase();
      const action = type === "INSERT" ? "新增" : type === "DELETE" ? "删除" : "";
      return {
        text: String(span.text || ""),
        action,
        author: String(span.author || ""),
        date: String(span.date || ""),
      };
    })
    .filter((span) => span.text);
}

function parseRevisionSpansFromEvidence(evidence: string): RevisionSpan[] {
  if (!evidence.includes('"type"') || !evidence.includes('"text"')) return [];
  const spans: RevisionSpan[] = [];
  for (const line of evidence.split(/\n+|；+/)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) continue;
    try {
      const raw = JSON.parse(trimmed) as Partial<RevisionSpan>;
      const type = String(raw.type || "TEXT").toUpperCase();
      if (!["TEXT", "INSERT", "DELETE"].includes(type)) continue;
      const text = String(raw.text || "");
      if (!text) continue;
      spans.push({
        type: type as RevisionSpan["type"],
        text,
        author: String(raw.author || ""),
        date: String(raw.date || ""),
        action: String(raw.action || ""),
      });
    } catch {
      // Historical bad profiles may contain partial JSON-like snippets; ignore them.
    }
  }
  return spans;
}

function revisionSpanTitle(span: DetailEvidenceSegment): string {
  if (!span.action) return "";
  const date = (span.date || "").slice(0, 10);
  return [span.action, span.author, date, span.text].filter(Boolean).join(" · ");
}

function signalGroundingStatus(signal: TableChangeSignal): string {
  if (signal.grounding_status) return signal.grounding_status;
  if (signal.source_type && signal.source_type !== "LLM") return "RULE_BASED";
  return signal.evidence_verified === false ? "UNVERIFIED" : "VERIFIED";
}

function signalReviewStatus(signal: TableChangeSignal, index?: number): string {
  return (index !== undefined ? localReviewStatuses.value[index] : undefined) || signal.human_review_status || "PENDING";
}

function needsHumanReview(signal: TableChangeSignal): boolean {
  return ["PARTIAL", "UNVERIFIED"].includes(signalGroundingStatus(signal));
}

function sourceLabel(signal: TableChangeSignal): string {
  return ({ LLM: "LLM 草稿", REVISION_TABLE: "修订对照表", EXCEL_DIFF: "物理 Diff", RULE_BASED: "规则结果" } as Record<string, string>)[signal.source_type || "LLM"];
}

function sourceColor(signal: TableChangeSignal): string {
  return signal.source_type && signal.source_type !== "LLM" ? "blue" : "outline";
}

function groundingLabel(signal: TableChangeSignal): string {
  return ({ VERIFIED: "原文已锚定", PARTIAL: "部分命中·待复核", UNVERIFIED: "未验证·已隔离", RULE_BASED: "确定性规则" } as Record<string, string>)[signalGroundingStatus(signal)];
}

function groundingColor(signal: TableChangeSignal): string {
  return ({ VERIFIED: "green", PARTIAL: "amber", UNVERIFIED: "red", RULE_BASED: "blue" } as Record<string, string>)[signalGroundingStatus(signal)];
}

function groundingStatusLabel(status: string): string {
  return ({ VERIFIED: "原文已锚定", PARTIAL: "部分命中·待复核", UNVERIFIED: "未验证·已隔离", RULE_BASED: "确定性规则" } as Record<string, string>)[status] ?? status;
}

function groundingColorForStatus(status: string): string {
  return ({ VERIFIED: "green", PARTIAL: "amber", UNVERIFIED: "red", RULE_BASED: "blue" } as Record<string, string>)[status] ?? "outline";
}

function shouldShowGroundingCoverage(signal: TableChangeSignal): boolean {
  return Boolean(signal.grounding_status && signal.grounding_status !== "RULE_BASED");
}

function reviewStatusLabel(status: string): string {
  return ({ PENDING: "无需复核", ACCEPTED: "已人工采纳", REJECTED: "已人工退回", CORRECTED: "已人工修正" } as Record<string, string>)[status] ?? status;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

async function reviewSignal(index: number, action: "ACCEPTED" | "REJECTED"): Promise<void> {
  if (!doc.value) return;
  reviewingSignalIndex.value = index;
  reviewError.value = "";
  try {
    const result = await apiClient.reviewDocumentSignal(doc.value.id, index, action, "demo_user");
    localReviewStatuses.value[index] = result.signal.human_review_status || action;
  } catch {
    reviewError.value = "复核操作失败，请稍后重试。";
  } finally {
    reviewingSignalIndex.value = null;
  }
}
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

.trust-card {
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid rgba(42, 157, 143, 0.28);
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(42, 157, 143, 0.08), rgba(255, 255, 255, 0.9));
}

.signal-table-scroll {
  overflow-x: auto;
}

.signal-table {
  min-width: 1080px;
}

.trust-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.trust-head h3,
.trust-head p {
  margin: 0;
}

.trust-head p {
  margin-top: 4px;
  color: var(--ink-500);
  font-size: 12px;
}

.trust-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.trust-stat {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.84);
}

.trust-stat b,
.trust-stat span {
  display: block;
}

.trust-stat b {
  margin: 3px 0;
  color: var(--ink-900);
  font-size: 20px;
  font-family: var(--font-mono);
}

.trust-stat span:last-child {
  color: var(--ink-500);
  font-size: 11px;
}

.trust-label {
  color: var(--ink-600);
  font-size: 12px;
  font-weight: 600;
}

.trust-progress {
  height: 4px;
  margin-top: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(42, 157, 143, 0.14);
}

.trust-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--green);
}

.grounding-chip,
.review-result {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.grounding-chip.green { color: #247c70; background: rgba(42, 157, 143, 0.12); }
.grounding-chip.amber { color: #a56500; background: rgba(246, 185, 59, 0.18); }
.grounding-chip.red { color: #b9382d; background: rgba(227, 73, 58, 0.12); }
.grounding-chip.blue { color: #276c9b; background: rgba(52, 152, 219, 0.12); }
.grounding-chip.outline { color: var(--ink-600); border: 1px solid var(--border); }

.coverage-text {
  display: block;
  margin-top: 3px;
  color: var(--ink-400);
  font-family: var(--font-mono);
  font-size: 10px;
}

.review-actions {
  display: flex;
  gap: 4px;
}

.review-btn {
  padding: 3px 7px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  cursor: pointer;
  font-size: 11px;
}

.review-btn.accept { color: var(--green); }
.review-btn.reject { color: var(--red, #b9382d); }
.review-result.accepted { color: var(--green); background: rgba(42, 157, 143, 0.12); }
.review-result.rejected { color: #b9382d; background: rgba(227, 73, 58, 0.12); }
.review-result.corrected { color: #276c9b; background: rgba(52, 152, 219, 0.12); }
.review-result.pending { color: var(--ink-500); background: var(--surface-alt); }

.review-error {
  margin-bottom: 12px;
  padding: 8px 10px;
  border: 1px solid rgba(227, 73, 58, 0.32);
  border-radius: 6px;
  color: #b9382d;
  background: rgba(227, 73, 58, 0.08);
  font-size: 12px;
}

.detail-btn,
.close-detail {
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink-700);
  cursor: pointer;
}

.detail-btn {
  padding: 5px 10px;
  font-size: 12px;
  white-space: nowrap;
}

.close-detail {
  width: 28px;
  height: 28px;
  font-size: 18px;
  line-height: 1;
}

.signal-detail-panel {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-alt);
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.detail-head h3 {
  margin: 8px 0 0;
  color: var(--ink-900);
  font-size: 16px;
}

.detail-summary {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid rgba(234, 84, 4, 0.22);
  border-radius: 8px;
  background: rgba(234, 84, 4, 0.06);
}

.detail-summary p {
  margin: 4px 0 0;
  color: var(--ink-800);
  line-height: 1.7;
}

.detail-label {
  color: var(--ink-500);
  font-size: 12px;
  font-weight: 700;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.6fr);
  gap: 14px;
  margin-top: 14px;
}

.source-card {
  margin-top: 8px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}

.source-card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.source-meta {
  margin-top: 6px;
  color: var(--ink-500);
  font-size: 12px;
}

.source-evidence {
  display: grid;
  gap: 4px;
  margin-top: 8px;
  color: var(--ink-700);
  font-size: 12px;
  line-height: 1.65;
  word-break: break-word;
}

.source-evidence-row {
  white-space: pre-wrap;
}

.source-revision-mark {
  padding: 0 2px;
  border-radius: 3px;
  text-decoration: none;
}

.source-revision-audit {
  display: grid;
  gap: 6px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  color: var(--ink-700);
  font-size: 12px;
}

.source-revision-action {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 2px 6px;
  align-items: start;
}

.source-revision-action small {
  grid-column: 2;
  color: var(--ink-400);
  font-size: 10px;
}

.source-revision-operation {
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
}

.source-revision-text {
  word-break: break-word;
}

.source-revision-add {
  color: #155ebf;
  background: rgba(52, 152, 219, 0.14);
  border-bottom: 1px solid rgba(21, 94, 191, 0.45);
}

.source-revision-delete {
  color: #b9382d;
  background: rgba(227, 73, 58, 0.12);
  text-decoration: line-through;
}

.source-revision-modify {
  color: #a56500;
  background: rgba(246, 185, 59, 0.18);
}

.merge-reasons {
  margin: 8px 0 0;
  padding-left: 18px;
  color: var(--ink-600);
  font-size: 12px;
  line-height: 1.8;
}

@media (max-width: 900px) {
  .trust-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
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

.evidence-unverified-block {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 5px;
}

.evidence-cell {
  font-size: 12px;
  max-width: 280px;
  min-width: 220px;
}

.evidence-plain {
  color: var(--ink-700);
  display: block;
  line-height: 1.55;
  word-break: break-word;
  white-space: normal;
}

.evidence-empty {
  color: var(--ink-400);
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
