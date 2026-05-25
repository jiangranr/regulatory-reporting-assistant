<template>
  <div>
    <div class="row between">
      <div>
        <div class="h-eyebrow">知识库</div>
        <h1 class="h-title">G31 填报规则卡片</h1>
        <p class="h-sub">
          从 1104 G31 填报说明抽出的规则资产。一期以 G31 为样板,数据模型通用,二期扩展到 EAST / 一表通。
        </p>
      </div>
      <div class="row" style="gap:8px;">
        <button class="btn primary" @click="openExtractDialog" :disabled="extracting">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          {{ extracting ? "抽取中…" : "从填报说明抽取" }}
        </button>
      </div>
    </div>

    <!-- Tab 切换:已生效 / 候选池 -->
    <div class="card mt-16" style="padding:0;">
      <div class="tab-bar">
        <button
          :class="['tab-btn', activeTab === 'active' ? 'active' : '']"
          @click="switchTab('active')"
        >
          已生效卡片
          <span class="tab-count">{{ activeCount }}</span>
        </button>
        <button
          :class="['tab-btn', activeTab === 'draft' ? 'active' : '']"
          @click="switchTab('draft')"
        >
          候选池 (待复核)
          <span :class="['tab-count', draftCount > 0 ? 'pulse' : '']">{{ draftCount }}</span>
        </button>
      </div>

      <!-- 过滤区 -->
      <div style="padding:14px 18px;border-top:1px solid var(--line-100);display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:12px;color:var(--ink-600);">报表：</span>
        <select v-model="filterObjectCode" @change="reload">
          <option value="">全部</option>
          <option value="G31">G31</option>
          <option value="G24">G24</option>
          <option value="G21">G21</option>
        </select>
        <span style="font-size:12px;color:var(--ink-600);margin-left:16px;">级别：</span>
        <select v-model="filterLevel" @change="reload">
          <option value="">全部</option>
          <option value="L1">L1 文本卡</option>
          <option value="L2">L2 结构卡</option>
          <option value="L3">L3 可执行卡</option>
        </select>
        <span style="font-size:11px;color:var(--ink-400);margin-left:auto;">
          共 {{ cards.length }} 张
        </span>
      </div>
    </div>

    <!-- 抽取结果提示 -->
    <div class="card mt-12" v-if="lastExtraction" :style="{ borderLeft: '3px solid ' + (lastExtraction.error_message ? 'var(--amber-600)' : '#22c55e') }">
      <div style="font-size:13px;color:var(--ink-700);">
        <strong>{{ lastExtraction.error_message ? "抽取部分成功" : "抽取完成" }}</strong>
        · 报表对象:{{ lastExtraction.inferred_object_code || "未识别" }}
        · 新增卡片 {{ lastExtraction.rule_cards_created }} 张（跳过 {{ lastExtraction.rule_cards_skipped }} 张）
        · 新增概念 {{ lastExtraction.concepts_created }} 个（跳过 {{ lastExtraction.concepts_skipped }} 个）
        · 关联 {{ lastExtraction.card_concept_links_created }} 条
        · {{ lastExtraction.llm_used ? "LLM" : "Mock" }}模式
      </div>
      <div v-if="lastExtraction.error_message" style="font-size:11px;color:var(--amber-700);margin-top:4px;">
        {{ lastExtraction.error_message }}
      </div>
      <div style="font-size:11px;color:var(--ink-500);margin-top:6px;">
        请切换到"候选池"Tab 进行人工复核。
      </div>
    </div>

    <div class="card mt-16" v-if="!cards.length && !extracting">
      <div style="text-align:center;padding:48px 0;">
        <p style="color:var(--ink-400);">
          {{ activeTab === 'draft' ? '候选池暂无待复核的卡片，请先点击右上角"从填报说明抽取"' : '暂无生效卡片，请先在候选池采纳几张' }}
        </p>
      </div>
    </div>

    <div v-else>
      <div class="sec-h mt-16" v-if="cards.length">
        <h2>{{ activeTab === 'draft' ? '候选规则卡片' : '已生效规则卡片' }}</h2>
        <span class="line"></span>
        <span class="count">{{ cards.length }} 张</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(380px, 1fr));gap:16px;">
        <div
          v-for="card in cards"
          :key="card.card_code"
          class="card"
          :style="activeTab === 'draft' ? { borderLeft: '3px solid #6366f1' } : {}"
        >
          <div class="row between" style="margin-bottom:10px;">
            <div class="row" style="gap:6px;">
              <span :class="['tag', levelColor(card.card_level)]">
                <span class="dot"></span>{{ card.card_level }}
              </span>
              <span :class="['tag', confidenceColor(card.confidence_level)]">
                {{ confidenceLabel(card.confidence_level) }}
              </span>
            </div>
            <span :class="['tag', statusColor(card.review_status)]" style="font-size:10px;">
              {{ statusLabel(card.review_status) }}
            </span>
          </div>
          <h3 style="font-size:14px;margin-bottom:6px;line-height:1.4;">
            {{ card.card_title }}
          </h3>
          <p style="font-size:12px;color:var(--ink-700);margin-bottom:12px;line-height:1.6;">
            {{ card.card_text }}
          </p>

          <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px;" v-if="card.related_concept_codes.length">
            <span
              v-for="code in card.related_concept_codes"
              :key="code"
              class="tag outline"
              style="font-size:10px;font-family:monospace;"
              :title="conceptName(code)"
            >{{ conceptName(code) }}</span>
          </div>

          <div style="border-top:1px solid var(--line-100);padding-top:8px;margin-top:8px;">
            <div style="font-size:11px;color:var(--ink-500);margin-bottom:6px;">
              来源：{{ card.source_location || '—' }}
            </div>
            <div class="row between" style="align-items:center;">
              <span :class="['tag', card.evidence_verified ? 'green' : 'amber']" style="font-size:10px;">
                {{ card.evidence_verified ? '✓ 原文已锚定' : '⚠ 未核对原文' }}
              </span>
              <span style="font-size:10px;color:var(--ink-400);font-family:monospace;">
                {{ card.card_code }}
              </span>
            </div>
          </div>

          <!-- 候选池才显示采纳/退回 -->
          <div v-if="activeTab === 'draft'" style="margin-top:10px;padding-top:10px;border-top:1px dashed var(--line-100);display:flex;gap:6px;">
            <button class="btn primary sm" style="flex:1;" :disabled="reviewingId === card.id" @click="review(card, 'ACCEPT')">
              ✓ 采纳
            </button>
            <button class="btn secondary sm" style="flex:1;" :disabled="reviewingId === card.id" @click="review(card, 'REJECT')">
              ✗ 退回
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 抽取弹框 -->
    <div v-if="dialogOpen" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog">
        <div class="dialog-h">
          <h3>从填报说明抽取规则卡片</h3>
          <button class="btn ghost sm" @click="closeDialog">✕</button>
        </div>
        <div class="dialog-body">
          <p style="font-size:12px;color:var(--ink-600);margin-bottom:12px;">
            选择一份已上传的填报说明 (.doc/.docx),系统会同步抽取候选卡片 + 候选概念,落入候选池等你复核。
          </p>
          <p style="font-size:11px;color:var(--ink-500);margin-bottom:14px;">
            当前 LLM 配置:<code>{{ mockMode ? 'MOCK 模式(基于段落规则信号词)' : 'LLM 模式' }}</code>
          </p>
          <div v-if="!docs.length" style="text-align:center;padding:24px 0;color:var(--ink-400);">
            未找到已上传文档,请先去"上传发文"上传填报说明。
          </div>
          <div v-else style="display:flex;flex-direction:column;gap:6px;max-height:380px;overflow-y:auto;">
            <label
              v-for="d in docs"
              :key="d.id"
              class="doc-row"
              :class="{ selected: selectedDocId === d.id }"
            >
              <input type="radio" :value="d.id" v-model="selectedDocId" />
              <div style="flex:1;">
                <div style="font-weight:500;font-size:13px;">{{ d.filename }}</div>
                <div style="font-size:11px;color:var(--ink-500);">
                  {{ d.title || '—' }} · {{ d.parse_quality }} · {{ d.char_count }} 字
                </div>
              </div>
            </label>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn secondary" @click="closeDialog">取消</button>
          <button class="btn primary" :disabled="!selectedDocId || extracting" @click="confirmExtract">
            {{ extracting ? '抽取中…' : '开始抽取' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { apiClient } from "@/api/client";
import type { Concept, ExtractionResult, RegDocument, RuleCard } from "@/types/api";

const props = defineProps<{
  ruleCards: RuleCard[];
  busy: boolean;
}>();

const cards = ref<RuleCard[]>([]);
const concepts = ref<Concept[]>([]);
const docs = ref<RegDocument[]>([]);
const activeTab = ref<"active" | "draft">("active");
const activeCount = ref(0);
const draftCount = ref(0);
const filterObjectCode = ref<string>("");
const filterLevel = ref<string>("");
const dialogOpen = ref(false);
const selectedDocId = ref<number | null>(null);
const extracting = ref(false);
const lastExtraction = ref<ExtractionResult | null>(null);
const reviewingId = ref<number | null>(null);
const mockMode = ref(true); // P0 阶段默认 mock,以后可由后端 /health 接口告知

const switchTab = (tab: "active" | "draft") => {
  activeTab.value = tab;
  reload();
};

const reload = async (): Promise<void> => {
  try {
    cards.value = await apiClient.listRuleCards({
      reporting_object_code: filterObjectCode.value || undefined,
      card_level: filterLevel.value || undefined,
      status: activeTab.value === "draft" ? "DRAFT" : "ACTIVE",
    });
    refreshCounts();
  } catch {
    cards.value = props.ruleCards ?? [];
  }
};

const refreshCounts = async (): Promise<void> => {
  try {
    const [actives, drafts] = await Promise.all([
      apiClient.listRuleCards({ status: "ACTIVE" }),
      apiClient.listRuleCards({ status: "DRAFT" }),
    ]);
    activeCount.value = actives.length;
    draftCount.value = drafts.length;
  } catch {
    /* ignore */
  }
};

const loadConcepts = async (): Promise<void> => {
  try {
    concepts.value = await apiClient.listConcepts({ status: "ACTIVE" });
    const drafts = await apiClient.listConcepts({ status: "DRAFT" });
    concepts.value = [...concepts.value, ...drafts];
  } catch {
    concepts.value = [];
  }
};

const loadDocs = async (): Promise<void> => {
  try {
    docs.value = await apiClient.listDocuments();
  } catch {
    docs.value = [];
  }
};

const conceptName = (code: string): string => {
  const found = concepts.value.find((c) => c.concept_code === code);
  return found?.canonical_name ?? code;
};

const openExtractDialog = async (): Promise<void> => {
  await loadDocs();
  selectedDocId.value = docs.value[0]?.id ?? null;
  dialogOpen.value = true;
};

const closeDialog = (): void => {
  dialogOpen.value = false;
};

const confirmExtract = async (): Promise<void> => {
  if (!selectedDocId.value) return;
  extracting.value = true;
  try {
    lastExtraction.value = await apiClient.triggerManualExtraction(selectedDocId.value);
    dialogOpen.value = false;
    // 抽取后自动切到候选池
    activeTab.value = "draft";
    await Promise.all([reload(), loadConcepts()]);
  } catch (err) {
    lastExtraction.value = {
      document_id: selectedDocId.value,
      inferred_object_code: "",
      rule_cards_created: 0,
      concepts_created: 0,
      aliases_created: 0,
      card_concept_links_created: 0,
      rule_cards_skipped: 0,
      concepts_skipped: 0,
      llm_used: false,
      error_message: err instanceof Error ? err.message : "抽取失败",
    };
  } finally {
    extracting.value = false;
  }
};

const review = async (card: RuleCard, action: "ACCEPT" | "REJECT"): Promise<void> => {
  if (!card.id) return;
  reviewingId.value = card.id;
  try {
    await apiClient.reviewRuleCard(card.id, action);
    // 从当前列表移除,刷新数量
    cards.value = cards.value.filter((c) => c.id !== card.id);
    refreshCounts();
  } catch {
    /* keep card in list on failure */
  } finally {
    reviewingId.value = null;
  }
};

const levelColor = (level: string): string =>
  ({ L1: "green", L2: "amber", L3: "blue" } as Record<string, string>)[level] ?? "outline";

const confidenceLabel = (level: string): string =>
  ({ HIGH: "高置信", MEDIUM: "中等置信", LOW: "低置信" } as Record<string, string>)[level] ?? level;

const confidenceColor = (level: string): string =>
  ({ HIGH: "green", MEDIUM: "amber", LOW: "outline" } as Record<string, string>)[level] ?? "outline";

const statusLabel = (status: string): string =>
  ({
    PENDING: "待复核",
    CONFIRMED: "已确认",
    AUTO_APPROVED: "自动通过",
    REJECTED: "已退回",
    DEPRECATED: "已废弃",
  } as Record<string, string>)[status] ?? status;

const statusColor = (status: string): string =>
  ({
    PENDING: "amber",
    CONFIRMED: "green",
    AUTO_APPROVED: "blue",
    REJECTED: "outline",
    DEPRECATED: "outline",
  } as Record<string, string>)[status] ?? "outline";

watch(() => props.ruleCards, (next) => {
  if (next?.length && !cards.value.length) cards.value = next;
});

onMounted(async () => {
  await Promise.all([reload(), loadConcepts()]);
});
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 8px 8px 0;
}
.tab-btn {
  position: relative;
  padding: 10px 18px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: 13px;
  color: var(--ink-500);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.15s;
}
.tab-btn:hover {
  color: var(--ink-800);
}
.tab-btn.active {
  color: var(--ink-900);
  border-bottom-color: rgba(99, 102, 241, 1);
  font-weight: 500;
}
.tab-count {
  font-size: 11px;
  background: var(--ink-100);
  color: var(--ink-600);
  padding: 1px 7px;
  border-radius: 999px;
  font-family: monospace;
}
.tab-btn.active .tab-count {
  background: rgba(99, 102, 241, 0.15);
  color: rgba(67, 56, 202, 1);
}
.tab-count.pulse {
  background: rgba(239, 68, 68, 0.15);
  color: rgba(185, 28, 28, 1);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.dialog {
  background: white;
  border-radius: 10px;
  width: 560px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.dialog-h {
  padding: 16px 20px;
  border-bottom: 1px solid var(--line-100);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dialog-h h3 {
  font-size: 15px;
  margin: 0;
}
.dialog-body {
  padding: 18px 20px;
  overflow-y: auto;
  flex: 1;
}
.dialog-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--line-100);
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.doc-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--line-100);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.1s;
  align-items: flex-start;
}
.doc-row:hover {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.03);
}
.doc-row.selected {
  border-color: rgba(99, 102, 241, 1);
  background: rgba(99, 102, 241, 0.06);
}
</style>
