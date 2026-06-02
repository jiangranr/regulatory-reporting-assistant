<template>
  <div class="qa-shell">
    <header class="qa-topbar">
      <button class="qa-brand" type="button" @click="$emit('navigate', 'dashboard')">
        <span class="qa-brand-mark">报</span>
        <span>监管报送治理</span>
        <ChevronRight :size="14" />
        <b>指标问答</b>
      </button>
      <div class="qa-topbar-actions">
        <div class="qa-global-search">
          <Search :size="14" />
          <span>搜索发文、报表、指标、工单</span>
          <span class="qa-key">⌘K</span>
        </div>
        <button class="qa-icon-btn" type="button" title="数据引导" @click="showBootstrap = !showBootstrap">
          <Database :size="16" />
        </button>
        <button class="qa-icon-btn" type="button" title="通知">
          <Bell :size="16" />
        </button>
        <button class="qa-icon-btn" type="button" title="帮助">
          <CircleHelp :size="16" />
        </button>
      </div>
    </header>

    <div v-if="showBootstrap" class="qa-bootstrap">
      <span>首次使用排查模式前，需要将种子血缘写入数据库。</span>
      <button class="qa-bootstrap-btn" type="button" :disabled="bootstrapping" @click="runBootstrap">
        {{ bootstrapping ? "引导中…" : "一键引导（幂等）" }}
      </button>
      <span v-if="bootstrapResult" class="qa-bootstrap-result">
        基础血缘 {{ bootstrapResult.basic_lineage ?? 0 }} 条 · G31 详细血缘 {{ bootstrapResult.g31_lineage ?? 0 }} 条
      </span>
      <span v-if="bootstrapError" class="qa-bootstrap-error">{{ bootstrapError }}</span>
    </div>

    <div class="qa-body">
      <aside class="qa-rail" data-testid="qa-session-rail">
        <div class="qa-rail-head">
          <div class="qa-rail-eyebrow">指标问答</div>
          <button class="qa-new-chat" data-testid="qa-new-chat" type="button" @click="startNewChat">
            <Plus :size="15" />
            新建对话
          </button>
        </div>
        <label class="qa-rail-search">
          <Search :size="14" />
          <input v-model="sessionKeyword" placeholder="搜索历史对话…" />
        </label>
        <div class="qa-session-list">
          <div v-for="group in filteredSessions" :key="group.label">
            <div class="qa-session-group">{{ group.label }}</div>
            <button
              v-for="session in group.items"
              :key="session.id"
              :class="['qa-session', { active: activeSessionId === session.id }]"
              type="button"
              @click="selectSession(session.id)"
            >
              <span class="qa-session-row">
                <span class="qa-session-title">{{ session.title }}</span>
                <span :class="['qa-session-mode', session.mode]">{{ sessionModeLabel(session.mode) }}</span>
              </span>
              <span class="qa-session-meta">{{ session.code }} · {{ session.time }}</span>
            </button>
          </div>
        </div>
      </aside>

      <main class="qa-conversation-column">
        <section class="qa-context-bar" data-testid="qa-context-bar">
          <span :class="['qa-context-mode', currentContext.mode]">{{ contextModeLabel(currentContext.mode) }}</span>
          <div class="qa-context-lock">
            <LockKeyhole :size="13" />
            <b>{{ currentContext.item_name }}</b>
            <span>{{ currentContext.location }}</span>
            <code>{{ currentContext.item_code }}</code>
          </div>
          <span class="qa-context-hint">对话已锁定该指标上下文</span>
          <div class="qa-context-switch-wrap">
            <button class="qa-context-switch" data-testid="qa-context-switch" type="button" @click="contextMenuOpen = !contextMenuOpen">
              <Repeat2 :size="13" />
              切换上下文
              <ChevronDown :size="13" />
            </button>
            <div v-if="contextMenuOpen" class="qa-context-menu">
              <button
                v-for="item in contextOptions"
                :key="item.item_code"
                :class="{ active: item.item_code === currentContext.item_code }"
                type="button"
                @click="switchContext(item)"
              >
                <b>{{ item.item_name }}</b>
                <span>{{ item.location }}</span>
                <code>{{ item.item_code }}</code>
              </button>
            </div>
          </div>
        </section>

        <section ref="scrollArea" class="qa-scroll" data-testid="qa-conversation">
          <div v-if="messages.length === 0" class="qa-empty">
            <div class="qa-empty-mark"><Sparkles :size="24" /></div>
            <h1>问我任何报送指标的问题</h1>
            <p>解释指标口径 · 排查数值异常 · 追溯血缘来源。对话会保留上下文，可连续追问。</p>
            <div class="qa-empty-grid">
              <button v-for="example in EXAMPLES" :key="example.text" type="button" @click="sendPreset(example)">
                <span :class="['qa-empty-icon', example.mode]">
                  <BookOpen v-if="example.mode === 'explanation'" :size="15" />
                  <Activity v-else :size="15" />
                </span>
                <span>
                  <b>{{ example.text }}</b>
                  <small>{{ example.mode === "explanation" ? "解释口径" : "排查异常" }}</small>
                </span>
              </button>
            </div>
          </div>

          <div v-else class="qa-thread">
            <div class="qa-day-divider">2026-05-31</div>
            <article v-for="message in messages" :key="message.id" :class="['qa-message', message.role]">
              <div class="qa-avatar">{{ message.role === "user" ? "江" : "报" }}</div>
              <div class="qa-message-stack">
                <div class="qa-message-meta">
                  <b>{{ message.role === "user" ? "江秋坪" : "报送指标助手" }}</b>
                  <span>{{ message.time }}</span>
                </div>
                <div v-if="message.role === 'user'" class="qa-user-bubble">
                  <span v-if="message.quote" class="qa-quote-ref">{{ message.quote }}</span>
                  {{ message.text }}
                </div>
                <div v-else class="qa-agent-bubble">
                  <div v-if="message.loading && !message.response?.plain_explanation" class="qa-thinking">
                    正在检索口径与血缘
                    <span><i></i><i></i><i></i></span>
                  </div>
                  <template v-else-if="message.response">
                    <p v-if="message.response.plain_explanation" class="qa-answer">{{ message.response.plain_explanation }}</p>
                    <div v-if="message.response.error" class="qa-answer-error">{{ message.response.error }}</div>

                    <div v-if="message.response.key_points.length" class="qa-keypoints">
                      <b>口径要点</b>
                      <ul>
                        <li v-for="point in message.response.key_points" :key="point">{{ point }}</li>
                      </ul>
                    </div>

                    <div class="qa-evidence-list">
                      <section v-if="message.response.instruction_excerpts.length" :class="['qa-evidence', { open: isEvidenceOpen(message.id, 'instruction') }]">
                        <button type="button" @click="toggleEvidence(message.id, 'instruction')">
                          <span class="qa-evidence-icon doc"><FileText :size="13" /></span>
                          <b>填报说明原文</b>
                          <small>{{ message.response.instruction_excerpts.length }} 处命中</small>
                          <ChevronDown :size="15" />
                        </button>
                        <div v-if="isEvidenceOpen(message.id, 'instruction')" class="qa-evidence-body">
                          <div v-for="excerpt in message.response.instruction_excerpts" :key="excerpt.text" class="qa-excerpt">
                            <span># {{ excerpt.match_type === "exact" ? "精确命中" : "关键词" }}</span>
                            <b>{{ excerpt.item_name || excerpt.source_label }}</b>
                            <p>{{ excerpt.text }}</p>
                          </div>
                        </div>
                      </section>

                      <section v-if="message.response.hypotheses.length" :class="['qa-evidence', { open: isEvidenceOpen(message.id, 'hypotheses') }]">
                        <button type="button" @click="toggleEvidence(message.id, 'hypotheses')">
                          <span class="qa-evidence-icon data"><TrendingUp :size="13" /></span>
                          <b>异常排查假说</b>
                          <small>{{ message.response.hypotheses.length }} 项</small>
                          <ChevronDown :size="15" />
                        </button>
                        <div v-if="isEvidenceOpen(message.id, 'hypotheses')" class="qa-evidence-body qa-hypothesis-list">
                          <div v-for="hypothesis in message.response.hypotheses" :key="hypothesis.label" :class="['qa-hypothesis', hypothesis.status]">
                            <b>{{ hypothesisIcon(hypothesis.status) }} {{ hypothesis.label }}</b>
                            <p>{{ hypothesis.evidence }}</p>
                            <small v-if="hypothesis.action">建议操作：{{ hypothesis.action }}</small>
                          </div>
                        </div>
                      </section>

                      <section v-if="message.response.lineage_fields.length" :class="['qa-evidence', { open: isEvidenceOpen(message.id, 'lineage') }]">
                        <button type="button" @click="toggleEvidence(message.id, 'lineage')">
                          <span class="qa-evidence-icon lineage"><GitFork :size="13" /></span>
                          <b>血缘来源</b>
                          <small>{{ message.response.lineage_fields.length }} 节点</small>
                          <ChevronDown :size="15" />
                        </button>
                        <div v-if="isEvidenceOpen(message.id, 'lineage')" class="qa-evidence-body">
                          <div class="qa-lineage-chain">
                            <div v-for="field in message.response.lineage_fields" :key="field.field_code">
                              <small>{{ field.lineage_role }}</small>
                              <b>{{ field.field_name }}</b>
                              <code>{{ field.system_name }} · {{ field.table_name }}.{{ field.field_code }}</code>
                            </div>
                          </div>
                        </div>
                      </section>

                      <section v-if="message.response.related_tickets.length" :class="['qa-evidence', { open: isEvidenceOpen(message.id, 'tickets') }]">
                        <button type="button" @click="toggleEvidence(message.id, 'tickets')">
                          <span class="qa-evidence-icon ticket"><ClipboardList :size="13" /></span>
                          <b>相关历史工单</b>
                          <small>{{ message.response.related_tickets.length }}</small>
                          <ChevronDown :size="15" />
                        </button>
                        <div v-if="isEvidenceOpen(message.id, 'tickets')" class="qa-evidence-body qa-ticket-list">
                          <div v-for="ticket in message.response.related_tickets" :key="ticket.ticket_id">
                            <b>{{ ticket.title }}</b>
                            <code>#{{ ticket.ticket_id }}</code>
                            <span>{{ ticket.status }}</span>
                          </div>
                        </div>
                      </section>
                    </div>

                    <div v-if="!message.loading" class="qa-message-actions">
                      <button type="button" @click="copyAnswer(message)">
                        <Check v-if="copiedMessageId === message.id" :size="14" />
                        <Copy v-else :size="14" />
                        {{ copiedMessageId === message.id ? "已复制" : "复制" }}
                      </button>
                      <button type="button" @click="quoteAnswer(message)">
                        <Reply :size="14" />
                        引用追问
                      </button>
                      <span></span>
                      <button :class="{ active: feedback[message.id] === 'good' }" type="button" @click="toggleFeedback(message.id, 'good')">
                        <ThumbsUp :size="14" />
                        有用
                      </button>
                      <button :class="{ active: feedback[message.id] === 'bad' }" type="button" @click="toggleFeedback(message.id, 'bad')">
                        <ThumbsDown :size="14" />
                        无用
                      </button>
                    </div>

                    <div v-if="!message.loading" class="qa-followups">
                      <b>建议追问</b>
                      <button v-for="followup in suggestedFollowups(message.response)" :key="followup" type="button" @click="sendQuestion(followup)">
                        <CornerDownRight :size="13" />
                        {{ followup }}
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </article>
          </div>
        </section>

        <footer class="qa-input-dock" data-testid="qa-composer">
          <div class="qa-composer">
            <div v-if="quotedText" class="qa-quoted">
              <span></span>
              <p>引用 · {{ truncate(quotedText, 90) }}</p>
              <button type="button" @click="quotedText = ''"><X :size="14" /></button>
            </div>
            <textarea
              ref="composerInput"
              v-model="composerText"
              data-testid="qa-composer-input"
              rows="1"
              placeholder="继续追问，或换一个指标问题…（对话会保留上下文）"
              @input="resizeComposer"
              @keydown="handleComposerKeydown"
            />
            <div class="qa-composer-footer">
              <button type="button"><Paperclip :size="14" />关联报表</button>
              <button type="button" @click="contextMenuOpen = true"><Hash :size="14" />指定指标</button>
              <span></span>
              <small><b>Enter</b> 发送 · <b>Shift+Enter</b> 换行</small>
              <button class="qa-send" data-testid="qa-send" type="button" :disabled="!composerText.trim() || sending" @click="sendQuestion()">
                <ArrowUp :size="15" />
                {{ sending ? "分析中" : "发送" }}
              </button>
            </div>
          </div>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import {
  Activity,
  ArrowUp,
  Bell,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Copy,
  CornerDownRight,
  Database,
  FileText,
  GitFork,
  Hash,
  LockKeyhole,
  Paperclip,
  Plus,
  Repeat2,
  Reply,
  Search,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
  X,
} from "lucide-vue-next";

import { apiClient } from "@/api/client";
import type { HypothesisStatus, QAQueryableItem, QAResponse } from "@/types/api";

defineEmits<{ navigate: [page: "dashboard"] }>();

type ContextMode = "explanation" | "anomaly";
type MessageRole = "user" | "agent";
type FeedbackValue = "good" | "bad";

interface IndicatorContext extends QAQueryableItem {
  location: string;
  mode: ContextMode;
}

interface ChatMessage {
  id: string;
  role: MessageRole;
  time: string;
  text?: string;
  quote?: string;
  loading?: boolean;
  response?: QAResponse;
}

interface SessionItem {
  id: string;
  title: string;
  mode: "explanation" | "anomaly" | "lineage";
  code: string;
  time: string;
}

const FALLBACK_CONTEXTS: IndicatorContext[] = [
  { item_name: "修正久期", item_code: "G31.PART_I.1_0.C_修正久期", location: "1 行 · C 列", mode: "explanation" },
  { item_name: "债券投资余额", item_code: "G31.PART_I.BOND_INVESTMENT_BALANCE", location: "3 行 · C 列", mode: "explanation" },
  { item_name: "最大百家同业融入余额", item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", location: "5 行 · B 列", mode: "anomaly" },
  { item_name: "流动性缺口", item_code: "G33.PART_I.7_0.D", location: "7 行 · D 列", mode: "explanation" },
];

const EXAMPLES = [
  { text: "G31 修正久期怎么计算？", itemCode: "G31.PART_I.1_0.C_修正久期", mode: "explanation" as const },
  { text: "G31 债券投资余额口径是什么？", itemCode: "G31.PART_I.BOND_INVESTMENT_BALANCE", mode: "explanation" as const },
  { text: "修正久期这期取值异常，从 3.2 变成 5.8", itemCode: "G31.PART_I.1_0.C_修正久期", mode: "anomaly" as const },
  { text: "G24 最大百家同业融入余额取值异常", itemCode: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", mode: "anomaly" as const },
];

const SESSION_GROUPS: Array<{ label: string; items: SessionItem[] }> = [];

const queryableItems = ref<QAQueryableItem[]>([]);
const currentContext = ref<IndicatorContext>({ ...FALLBACK_CONTEXTS[0] });
const contextMenuOpen = ref(false);
const sessionKeyword = ref("");
const activeSessionId = ref("");
const messages = ref<ChatMessage[]>(createSeedMessages());
const composerText = ref("");
const quotedText = ref("");
const sending = ref(false);
const scrollArea = ref<HTMLElement | null>(null);
const composerInput = ref<HTMLTextAreaElement | null>(null);
const evidenceOpen = ref(new Set(["a1-instruction", "a2-hypotheses"]));
const copiedMessageId = ref("");
const feedback = ref<Record<string, FeedbackValue | undefined>>({});
const showBootstrap = ref(false);
const bootstrapping = ref(false);
const bootstrapResult = ref<Record<string, unknown> | null>(null);
const bootstrapError = ref("");
let messageSequence = 100;

const contextOptions = computed<IndicatorContext[]>(() => {
  const resolved = queryableItems.value.map((item, index) => ({
    ...item,
    location: inferLocation(item.item_code, index),
    mode: inferMode(item.item_name),
  }));
  const merged = [...FALLBACK_CONTEXTS, ...resolved];
  return merged.filter((item, index) => merged.findIndex((candidate) => candidate.item_code === item.item_code) === index);
});

const filteredSessions = computed(() => {
  const keyword = sessionKeyword.value.trim().toLowerCase();
  if (!keyword) return SESSION_GROUPS;
  return SESSION_GROUPS
    .map((group) => ({ ...group, items: group.items.filter((item) => `${item.title} ${item.code}`.toLowerCase().includes(keyword)) }))
    .filter((group) => group.items.length);
});

onMounted(async () => {
  try {
    queryableItems.value = await apiClient.listQueryableItems();
  } catch {
    queryableItems.value = [];
  }
  await scrollToBottom();
});

function startNewChat() {
  activeSessionId.value = "";
  messages.value = [];
  quotedText.value = "";
  composerText.value = "";
}

function selectSession(sessionId: string) {
  activeSessionId.value = sessionId;
}

function switchContext(context: IndicatorContext) {
  currentContext.value = { ...context };
  contextMenuOpen.value = false;
}

function sendPreset(example: (typeof EXAMPLES)[number]) {
  const context = contextOptions.value.find((item) => item.item_code === example.itemCode);
  if (context) switchContext({ ...context, mode: example.mode });
  void sendQuestion(example.text);
}

async function sendQuestion(preset?: string) {
  const text = (preset ?? composerText.value).trim();
  if (!text || sending.value) return;

  const quote = quotedText.value;
  composerText.value = "";
  quotedText.value = "";
  sending.value = true;

  const userMessage: ChatMessage = { id: nextId("u"), role: "user", time: currentTime(), text, quote };
  const agentMessage: ChatMessage = { id: nextId("a"), role: "agent", time: currentTime(), loading: true, response: blankResponse() };
  messages.value.push(userMessage, agentMessage);
  await scrollToBottom();

  const params = new URLSearchParams({ question: text });
  if (currentContext.value.item_code) params.set("item_code", currentContext.value.item_code);

  try {
    const response = await fetch(`/api/indicator-qa/ask/stream?${params}`, { method: "POST" });
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
    await consumeStream(response, agentMessage);
  } catch (error: unknown) {
    agentMessage.response = { ...blankResponse(), error: error instanceof Error ? error.message : "请求失败，请检查后端服务是否正常" };
  } finally {
    agentMessage.loading = false;
    sending.value = false;
    await scrollToBottom();
  }
}

async function consumeStream(response: Response, message: ChatMessage) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) consumeLine(line, message);
    await scrollToBottom();
  }
  if (buffer) consumeLine(buffer, message);
}

function consumeLine(line: string, message: ChatMessage) {
  if (!line.startsWith("data: ")) return;
  try {
    const event = JSON.parse(line.slice(6));
    const response = message.response ?? blankResponse();
    if (event.type === "meta") {
      response.mode = event.mode ?? "explanation";
      response.item_code = event.item_code ?? "";
      response.item_name = event.item_name ?? "";
      response.instruction_excerpts = event.instruction_excerpts ?? [];
      response.related_tickets = event.related_tickets ?? [];
    } else if (event.type === "token") {
      response.plain_explanation += event.text ?? "";
    } else if (event.type === "keypoints") {
      response.key_points = event.data ?? [];
    } else if (event.type === "hypotheses") {
      response.hypotheses = event.data ?? [];
    } else if (event.type === "lineage") {
      response.lineage_fields = event.data ?? [];
    } else if (event.type === "error") {
      response.error = event.message ?? "未知错误";
    }
    message.response = response;
  } catch {
    // Ignore malformed SSE lines without interrupting an otherwise usable answer.
  }
}

function createSeedMessages(): ChatMessage[] {
  return [
    { id: "u1", role: "user", time: "11:42", text: "G31 修正久期怎么计算？" },
    { id: "a1", role: "agent", time: "11:42", response: seedExplanation() },
    { id: "u2", role: "user", time: "11:44", text: "那这期从 3.2 变成 5.8，正常吗？" },
    { id: "a2", role: "agent", time: "11:44", response: seedAnomaly() },
  ];
}

function seedExplanation(): QAResponse {
  return {
    ...blankResponse(),
    item_code: FALLBACK_CONTEXTS[0].item_code,
    item_name: "修正久期",
    plain_explanation: "G31 的修正久期按填报说明计算：MD = −(dP/P)/dy = D/(1+y/k)。其中 D 是麦考利久期，P 是债券估值（价格），dP 是价格变动，y 是到期收益率，dy 是到期收益率变动，k 是每年复利频率。\n\n单券直接套用公式；若填报的是债券投资组合，通常按各债券期末估值占比，对单券修正久期加权，得到组合修正久期。",
    instruction_excerpts: [{
      text: "[C.修正久期]：衡量单笔债券或债券投资组合估值（价格）对到期收益率变化的敏感度指标，计算公式为 MD=−(dP/P)/dy=D/(1+y/k)。",
      source_label: "G31 填报说明",
      item_name: "修正久期",
      match_type: "exact",
    }],
    related_tickets: [
      { ticket_id: 20240911, title: "G31 修正久期口径与估值系统不一致", status: "已解决" },
      { ticket_id: 20250203, title: "组合久期加权未剔除到期券", status: "已解决" },
    ],
  };
}

function seedAnomaly(): QAResponse {
  return {
    ...blankResponse(),
    mode: "anomaly",
    item_code: FALLBACK_CONTEXTS[0].item_code,
    item_name: "修正久期",
    plain_explanation: "本期修正久期从上期 3.2 跳到 5.8，环比 +81%，确实超出常规波动区间。结合血缘与持仓，建议先核对持仓结构变化，再回溯中间层加工逻辑。",
    hypotheses: [
      { label: "久期结构变化", status: "checked", evidence: "若本期新增长久期利率债或赎回短久期券，组合加权久期会被显著抬升。", action: "先核对本期新增持仓明细。" },
      { label: "取数口径错位", status: "uncertain", evidence: "中间层可能误用了麦考利久期 D，而非修正久期 MD。", action: "回溯 dm_g31_risk.modified_duration 加工逻辑。" },
    ],
    lineage_fields: [
      { field_name: "麦考利久期", field_code: "macaulay_duration", table_name: "bond_valuation", system_name: "估值系统 FVS", lineage_role: "SOURCE_FIELD" },
      { field_name: "修正久期加工", field_code: "modified_duration", table_name: "dm_g31_risk", system_name: "风险加工层", lineage_role: "PROCESS_FIELD" },
      { field_name: "G31 修正久期", field_code: "modified_duration", table_name: "rpt_g31_part_i", system_name: "监管报送", lineage_role: "REPORT_FIELD" },
    ],
    related_tickets: [{ ticket_id: 20240911, title: "G31 修正久期口径与估值系统不一致（误用麦考利久期）", status: "已解决" }],
  };
}

function blankResponse(): QAResponse {
  return {
    mode: "explanation",
    item_code: "",
    item_name: "",
    instruction_excerpts: [],
    plain_explanation: "",
    key_points: [],
    hypotheses: [],
    lineage_fields: [],
    related_tickets: [],
    error: "",
  };
}

function suggestedFollowups(response: QAResponse): string[] {
  if (response.mode === "anomaly") return ["帮我生成一张排查工单", "查看本期新增持仓明细", "中间层加工 SQL 是什么？"];
  return ["组合修正久期怎么加权？", "D（麦考利久期）从哪个系统取数？", "这个口径和 G33 的久期一致吗？"];
}

function toggleEvidence(messageId: string, type: string) {
  const key = `${messageId}-${type}`;
  const next = new Set(evidenceOpen.value);
  next.has(key) ? next.delete(key) : next.add(key);
  evidenceOpen.value = next;
}

function isEvidenceOpen(messageId: string, type: string) {
  return evidenceOpen.value.has(`${messageId}-${type}`);
}

async function copyAnswer(message: ChatMessage) {
  const text = message.response?.plain_explanation ?? "";
  try {
    await navigator.clipboard?.writeText(text);
  } catch {
    // Clipboard may be unavailable in restricted browser contexts.
  }
  copiedMessageId.value = message.id;
  window.setTimeout(() => {
    if (copiedMessageId.value === message.id) copiedMessageId.value = "";
  }, 1600);
}

function quoteAnswer(message: ChatMessage) {
  quotedText.value = message.response?.plain_explanation ?? "";
  composerInput.value?.focus();
}

function toggleFeedback(messageId: string, value: FeedbackValue) {
  feedback.value[messageId] = feedback.value[messageId] === value ? undefined : value;
}

function handleComposerKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void sendQuestion();
  }
}

function resizeComposer() {
  const input = composerInput.value;
  if (!input) return;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

async function scrollToBottom() {
  await nextTick();
  if (scrollArea.value) scrollArea.value.scrollTop = scrollArea.value.scrollHeight;
}

async function runBootstrap() {
  bootstrapping.value = true;
  bootstrapResult.value = null;
  bootstrapError.value = "";
  try {
    bootstrapResult.value = await apiClient.bootstrapAll();
    queryableItems.value = await apiClient.listQueryableItems();
  } catch (error: unknown) {
    bootstrapError.value = error instanceof Error ? error.message : "引导失败";
  } finally {
    bootstrapping.value = false;
  }
}

function inferLocation(itemCode: string, index: number) {
  const match = itemCode.match(/\.(\d+)_\d+\.([A-Z])/);
  return match ? `${match[1]} 行 · ${match[2]} 列` : `${index + 1} 行`;
}

function inferMode(itemName: string): ContextMode {
  return itemName.includes("异常") ? "anomaly" : "explanation";
}

function contextModeLabel(mode: ContextMode) {
  return mode === "anomaly" ? "排查模式" : "解释模式";
}

function sessionModeLabel(mode: SessionItem["mode"]) {
  if (mode === "anomaly") return "排查";
  if (mode === "lineage") return "血缘";
  return "解释";
}

function hypothesisIcon(status: HypothesisStatus) {
  if (status === "checked") return "✓";
  if (status === "uncertain") return "!";
  return "×";
}

function nextId(prefix: string) {
  messageSequence += 1;
  return `${prefix}${messageSequence}`;
}

function currentTime() {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());
}

function truncate(value: string, length: number) {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}
</script>

<style src="./indicator-qa.css" scoped></style>
