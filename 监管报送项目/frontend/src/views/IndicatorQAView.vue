<template>
  <div>
    <!-- 页眉 -->
    <div class="row between" style="align-items:flex-start;">
      <div>
        <div class="h-eyebrow">监管报送治理</div>
        <h1 class="h-title">指标问答</h1>
        <p class="h-sub">解释指标口径 · 排查数值异常 · 追溯血缘来源</p>
      </div>
      <button class="btn ghost sm" @click="showBootstrap = !showBootstrap" style="margin-top:8px;">
        数据引导
      </button>
    </div>

    <!-- 数据引导面板（折叠） -->
    <div v-if="showBootstrap" class="card mt-12" style="padding:14px 18px;background:var(--surface-50);">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <span style="font-size:13px;color:var(--ink-600);">首次使用需将种子血缘写入数据库，才能启用排查模式。</span>
        <button class="btn primary sm" @click="runBootstrap" :disabled="bootstrapping">
          {{ bootstrapping ? '引导中…' : '一键引导 (幂等)' }}
        </button>
        <span v-if="bootstrapResult" style="font-size:12px;color:var(--ink-500);">
          基础血缘 {{ bootstrapResult.basic_lineage }} 条 · G31 详细血缘 {{ bootstrapResult.g31_lineage }} 条 ✓
        </span>
        <span v-if="bootstrapError" style="font-size:12px;color:var(--red-500);">{{ bootstrapError }}</span>
      </div>
    </div>

    <!-- 示例问题 + 指标选择 -->
    <div class="row mt-16" style="gap:12px;flex-wrap:wrap;align-items:flex-start;">
      <!-- 示例 -->
      <div class="card" style="flex:0 0 auto;padding:14px 18px;min-width:260px;">
        <div style="font-size:12px;color:var(--ink-500);margin-bottom:8px;">示例问题</div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <button
            v-for="ex in EXAMPLES"
            :key="ex.text"
            class="btn ghost sm"
            style="text-align:left;white-space:normal;line-height:1.4;"
            @click="fillExample(ex)"
          >{{ ex.text }}</button>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="card" style="flex:1;min-width:320px;padding:18px;">
        <div style="display:flex;flex-direction:column;gap:12px;">
          <div>
            <label style="font-size:12px;color:var(--ink-500);display:block;margin-bottom:4px;">指标编码（可选，Agent 会自动识别）</label>
            <div style="display:flex;gap:8px;">
              <select v-model="selectedObjectCode" @change="loadItems" style="flex:0 0 auto;font-size:13px;padding:6px 10px;border:1px solid var(--line-200);border-radius:4px;">
                <option value="">全部报表</option>
                <option value="G31">G31</option>
                <option value="G24">G24</option>
                <option value="G21">G21</option>
                <option value="G25">G25</option>
                <option value="G27">G27</option>
              </select>
              <select v-model="selectedItemCode" style="flex:1;font-size:13px;padding:6px 10px;border:1px solid var(--line-200);border-radius:4px;">
                <option value="">不指定</option>
                <option v-for="item in queryableItems" :key="item.item_code" :value="item.item_code">
                  {{ item.item_code }} · {{ item.item_name }}
                </option>
              </select>
            </div>
          </div>

          <div>
            <label style="font-size:12px;color:var(--ink-500);display:block;margin-bottom:4px;">你的问题</label>
            <textarea
              v-model="question"
              placeholder="例：修正久期怎么计算？ / 修正久期这期取值异常，从 3.2 变成 5.8"
              rows="3"
              style="width:100%;box-sizing:border-box;padding:8px 10px;font-size:14px;border:1px solid var(--line-200);border-radius:4px;resize:vertical;font-family:inherit;"
              @keydown.ctrl.enter.prevent="submitQuestion"
              @keydown.meta.enter.prevent="submitQuestion"
            />
          </div>

          <div style="display:flex;align-items:center;gap:10px;">
            <button class="btn primary" @click="submitQuestion" :disabled="!question.trim() || loading">
              {{ loading ? '分析中…' : '发送' }}
            </button>
            <span style="font-size:12px;color:var(--ink-400);">Ctrl+Enter 发送</span>
            <button v-if="response" class="btn ghost sm" @click="clearResponse" style="margin-left:auto;">清空</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="card mt-16" style="padding:14px 18px;border-left:3px solid var(--red-400);">
      <span style="color:var(--red-600);font-size:13px;">{{ errorMsg }}</span>
    </div>

    <!-- 回答区 -->
    <div v-if="response || streaming" class="card mt-16" style="padding:20px 24px;">
      <!-- 标题行 -->
      <div class="row between" style="margin-bottom:16px;align-items:flex-start;">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <span
            :class="['badge', (response?.mode ?? streamMeta.mode) === 'explanation' ? 'badge-blue' : 'badge-orange']"
            style="font-size:11px;"
          >{{ (response?.mode ?? streamMeta.mode) === 'explanation' ? '解释模式' : '排查模式' }}</span>
          <span style="font-size:14px;font-weight:600;">
            {{ response?.item_name || streamMeta.item_name || response?.item_code || streamMeta.item_code }}
          </span>
          <span v-if="response?.item_code || streamMeta.item_code" style="font-size:12px;color:var(--ink-400);">
            {{ response?.item_code || streamMeta.item_code }}
          </span>
          <!-- 流式光标 -->
          <span v-if="streaming" style="display:inline-block;width:8px;height:14px;background:var(--ink-400);animation:blink 1s step-end infinite;border-radius:1px;margin-left:2px;"></span>
        </div>
      </div>

      <!-- ── 解释模式 ── -->
      <template v-if="(response?.mode ?? streamMeta.mode) === 'explanation'">
        <!-- 通俗解释：流式时用 streamText，完成后用 response -->
        <div v-if="streamText || response?.plain_explanation" style="margin-bottom:18px;">
          <div class="section-label">通俗解释</div>
          <div style="font-size:14px;line-height:1.7;color:var(--ink-700);white-space:pre-wrap;">{{
            streaming ? streamText : response?.plain_explanation
          }}<span v-if="streaming && !streamKeypoints.length" class="cursor-blink">▌</span></div>
        </div>

        <!-- 口径要点 -->
        <div v-if="(response?.key_points ?? streamKeypoints).length" style="margin-bottom:18px;">
          <div class="section-label">口径要点</div>
          <ul style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:4px;">
            <li v-for="(pt, i) in (response?.key_points ?? streamKeypoints)" :key="i" style="font-size:13px;color:var(--ink-700);">{{ pt }}</li>
          </ul>
        </div>

        <!-- 填报说明原文 -->
        <div v-if="(response?.instruction_excerpts ?? streamMeta.instruction_excerpts ?? []).length" style="margin-bottom:18px;">
          <div class="section-label">填报说明原文</div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            <div
              v-for="(ex, i) in (response?.instruction_excerpts ?? streamMeta.instruction_excerpts ?? [])"
              :key="i"
              :style="{
                background: ex.match_type === 'exact' ? '#f0fdf4' : 'var(--surface-50)',
                borderLeft: ex.match_type === 'exact' ? '3px solid #4ade80' : '3px solid var(--line-200)',
                padding: '10px 14px',
                borderRadius: '0 4px 4px 0',
              }"
            >
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                <span v-if="ex.match_type === 'exact'" style="font-size:11px;background:#dcfce7;color:#15803d;padding:1px 5px;border-radius:3px;">精确命中</span>
                <span v-else-if="ex.match_type === 'keyword'" style="font-size:11px;background:#eff6ff;color:#1d4ed8;padding:1px 5px;border-radius:3px;">关键词</span>
                <span style="font-size:11px;color:var(--ink-400);">
                  {{ ex.item_name || ex.source_label }}
                </span>
              </div>
              <div style="font-size:13px;color:var(--ink-700);white-space:pre-wrap;line-height:1.6;">{{ ex.text }}</div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── 排查模式 ── -->
      <template v-if="(response?.mode ?? streamMeta.mode) === 'anomaly'">
        <div v-if="(response?.hypotheses ?? streamHypotheses).length" style="margin-bottom:18px;">
          <div class="section-label">假说清单（按优先级）</div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div
              v-for="(h, i) in (response?.hypotheses ?? streamHypotheses)"
              :key="i"
              :class="['hypothesis-card', `hypothesis-${h.status}`]"
            >
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span class="hyp-icon">{{ hypothesisIcon(h.status) }}</span>
                <span style="font-size:14px;font-weight:600;">{{ h.label }}</span>
                <span :class="['badge', hypothesisBadgeClass(h.status)]" style="font-size:11px;">
                  {{ hypothesisStatusLabel(h.status) }}
                </span>
              </div>
              <div style="font-size:13px;color:var(--ink-600);line-height:1.6;white-space:pre-wrap;">{{ h.evidence }}</div>
              <div v-if="h.action" style="margin-top:6px;font-size:12px;color:var(--ink-500);">
                建议操作：{{ h.action }}
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── 通用：血缘字段 ── -->
      <div v-if="(response?.lineage_fields ?? streamLineage).length" style="margin-bottom:18px;">
        <div class="section-label">血缘字段</div>
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="border-bottom:1px solid var(--line-100);">
                <th style="text-align:left;padding:6px 10px;color:var(--ink-500);font-weight:500;">字段</th>
                <th style="text-align:left;padding:6px 10px;color:var(--ink-500);font-weight:500;">表名</th>
                <th style="text-align:left;padding:6px 10px;color:var(--ink-500);font-weight:500;">系统</th>
                <th style="text-align:left;padding:6px 10px;color:var(--ink-500);font-weight:500;">角色</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(f, i) in (response?.lineage_fields ?? streamLineage)" :key="i" style="border-bottom:1px solid var(--line-50);">
                <td style="padding:6px 10px;">
                  <span style="font-weight:500;">{{ f.field_name }}</span>
                  <span style="font-size:11px;color:var(--ink-400);margin-left:6px;">{{ f.field_code }}</span>
                </td>
                <td style="padding:6px 10px;color:var(--ink-500);">{{ f.table_name }}</td>
                <td style="padding:6px 10px;color:var(--ink-500);">{{ f.system_name }}</td>
                <td style="padding:6px 10px;">
                  <span :class="['badge', roleClass(f.lineage_role)]" style="font-size:11px;">{{ f.lineage_role }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── 通用：相关工单 ── -->
      <div v-if="(response?.related_tickets ?? streamMeta.related_tickets ?? []).length">
        <div class="section-label">相关历史工单</div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <div
            v-for="t in (response?.related_tickets ?? streamMeta.related_tickets ?? [])"
            :key="t.ticket_id"
            style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface-50);border-radius:4px;"
          >
            <span style="font-size:12px;color:var(--ink-400);">#{{ t.ticket_id }}</span>
            <span style="font-size:13px;flex:1;">{{ t.title }}</span>
            <span class="badge" style="font-size:11px;">{{ t.status }}</span>
          </div>
        </div>
      </div>

      <!-- 无内容兜底 -->
      <div v-if="response?.error" style="color:var(--red-600);font-size:13px;">{{ response.error }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { apiClient } from "@/api/client";
import type { QAResponse, QAQueryableItem } from "@/types/api";

// ── 示例 ──────────────────────────────────────────────────────────────────────
const EXAMPLES = [
  { text: "G31 修正久期怎么计算？", itemCode: "G31.PART_I.1_0.C_修正久期" },
  { text: "G31 债券投资余额口径是什么？", itemCode: "G31.PART_I.BOND_INVESTMENT_BALANCE" },
  { text: "修正久期这期取值异常，从 3.2 变成 5.8", itemCode: "G31.PART_I.1_0.C_修正久期" },
  { text: "G24 最大百家同业融入余额取值异常", itemCode: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" },
];

// ── 状态 ──────────────────────────────────────────────────────────────────────
const question = ref("");
const selectedObjectCode = ref("");
const selectedItemCode = ref("");
const queryableItems = ref<QAQueryableItem[]>([]);
const loading = ref(false);
const response = ref<QAResponse | null>(null);
const errorMsg = ref("");

// 流式状态
const streaming = ref(false);
const streamText = ref("");
const streamKeypoints = ref<string[]>([]);
const streamHypotheses = ref<Array<{label:string;status:string;evidence:string;action:string}>>([]);
const streamLineage = ref<QAResponse["lineage_fields"]>([]);
const streamMeta = ref<{
  mode: string;
  item_code: string;
  item_name: string;
  instruction_excerpts: QAResponse["instruction_excerpts"];
  related_tickets: QAResponse["related_tickets"];
}>({ mode: "explanation", item_code: "", item_name: "", instruction_excerpts: [], related_tickets: [] });

const showBootstrap = ref(false);
const bootstrapping = ref(false);
const bootstrapResult = ref<Record<string, number> | null>(null);
const bootstrapError = ref("");

// ── 初始化 ────────────────────────────────────────────────────────────────────
onMounted(() => loadItems());

async function loadItems() {
  try {
    queryableItems.value = await apiClient.listQueryableItems(selectedObjectCode.value || undefined);
  } catch {
    // 加载失败不影响主流程
  }
}

// ── 操作 ──────────────────────────────────────────────────────────────────────
function fillExample(ex: { text: string; itemCode?: string }) {
  question.value = ex.text;
  if (ex.itemCode) selectedItemCode.value = ex.itemCode;
}

async function submitQuestion() {
  const q = question.value.trim();
  if (!q || loading.value) return;

  // 重置所有状态
  loading.value = true;
  streaming.value = false;
  errorMsg.value = "";
  response.value = null;
  streamText.value = "";
  streamKeypoints.value = [];
  streamHypotheses.value = [];
  streamLineage.value = [];
  streamMeta.value = { mode: "explanation", item_code: "", item_name: "", instruction_excerpts: [], related_tickets: [] };

  const params = new URLSearchParams({ question: q });
  if (selectedItemCode.value) params.set("item_code", selectedItemCode.value);

  try {
    const res = await fetch(`/api/indicator-qa/ask/stream?${params}`, { method: "POST" });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    loading.value = false;
    streaming.value = true;

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // 按 SSE 行解析（data: {...}\n\n）
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";          // 末尾不完整行留着
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "meta") {
            streamMeta.value = evt;
          } else if (evt.type === "token") {
            streamText.value += evt.text;
          } else if (evt.type === "keypoints") {
            streamKeypoints.value = evt.data ?? [];
          } else if (evt.type === "hypotheses") {
            streamHypotheses.value = evt.data ?? [];
          } else if (evt.type === "lineage") {
            streamLineage.value = evt.data ?? [];
          } else if (evt.type === "done") {
            // 固化到 response，防止 streaming=false 后内容消失
            response.value = {
              mode: streamMeta.value.mode as "explanation" | "anomaly",
              item_code: streamMeta.value.item_code,
              item_name: streamMeta.value.item_name,
              instruction_excerpts: streamMeta.value.instruction_excerpts ?? [],
              plain_explanation: streamText.value,
              key_points: streamKeypoints.value,
              hypotheses: streamHypotheses.value,
              lineage_fields: streamLineage.value ?? [],
              related_tickets: streamMeta.value.related_tickets ?? [],
              error: "",
            };
            streaming.value = false;
          } else if (evt.type === "error") {
            errorMsg.value = evt.message ?? "未知错误";
            streaming.value = false;
          }
        } catch { /* 忽略非法行 */ }
      }
    }
    // reader 自然结束兜底：确保内容已固化
    if (!response.value && (streamText.value || streamMeta.value.item_name)) {
      response.value = {
        mode: streamMeta.value.mode as "explanation" | "anomaly",
        item_code: streamMeta.value.item_code,
        item_name: streamMeta.value.item_name,
        instruction_excerpts: streamMeta.value.instruction_excerpts ?? [],
        plain_explanation: streamText.value,
        key_points: streamKeypoints.value,
        hypotheses: streamHypotheses.value,
        lineage_fields: streamLineage.value ?? [],
        related_tickets: streamMeta.value.related_tickets ?? [],
        error: "",
      };
    }
    streaming.value = false;

  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : "请求失败，请检查后端服务是否正常";
    loading.value = false;
    streaming.value = false;
  }
}

function clearResponse() {
  response.value = null;
  errorMsg.value = "";
  streaming.value = false;
  streamText.value = "";
  streamKeypoints.value = [];
  streamHypotheses.value = [];
  streamLineage.value = [];
  streamMeta.value = { mode: "explanation", item_code: "", item_name: "", instruction_excerpts: [], related_tickets: [] };
}

async function runBootstrap() {
  bootstrapping.value = true;
  bootstrapError.value = "";
  bootstrapResult.value = null;
  try {
    const result = await apiClient.bootstrapAll();
    bootstrapResult.value = result as Record<string, number>;
    await loadItems();
  } catch (e: unknown) {
    bootstrapError.value = e instanceof Error ? e.message : "引导失败";
  } finally {
    bootstrapping.value = false;
  }
}

// ── 展示辅助 ──────────────────────────────────────────────────────────────────
function hypothesisIcon(status: string) {
  if (status === "checked") return "✅";
  if (status === "uncertain") return "⚠️";
  return "❌";
}

function hypothesisBadgeClass(status: string) {
  if (status === "checked") return "badge-green";
  if (status === "uncertain") return "badge-orange";
  return "badge-gray";
}

function hypothesisStatusLabel(status: string) {
  if (status === "checked") return "有数据，必查";
  if (status === "uncertain") return "条件具备才展示";
  return "AI 无法分析";
}

function roleClass(role: string) {
  if (role === "SOURCE_FIELD") return "badge-blue";
  if (role === "FILTER_FIELD") return "badge-orange";
  if (role === "REPORT_FIELD") return "badge-green";
  return "badge-gray";
}
</script>

<style scoped>
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.cursor-blink {
  display: inline-block;
  animation: blink 0.8s step-end infinite;
  color: var(--ink-500);
  font-weight: 300;
  margin-left: 1px;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-400);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.hypothesis-card {
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid var(--line-100);
}

.hypothesis-checked {
  background: #f0fdf4;
  border-color: #86efac;
}

.hypothesis-uncertain {
  background: #fffbeb;
  border-color: #fde68a;
}

.hypothesis-out_of_scope {
  background: var(--surface-50);
  border-color: var(--line-100);
}

.hyp-icon {
  font-size: 16px;
  line-height: 1;
}

.badge-green {
  background: #dcfce7;
  color: #15803d;
}

.badge-orange {
  background: #fff7ed;
  color: #c2410c;
}

.badge-blue {
  background: #eff6ff;
  color: #1d4ed8;
}

.badge-gray {
  background: var(--surface-100);
  color: var(--ink-500);
}
</style>
