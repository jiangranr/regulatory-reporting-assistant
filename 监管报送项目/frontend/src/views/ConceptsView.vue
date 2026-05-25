<template>
  <div>
    <div class="row between">
      <div>
        <div class="h-eyebrow">知识库</div>
        <h1 class="h-title">监管概念库</h1>
        <p class="h-sub">
          1104 监管报送中的核心术语/口径词。概念变化会自动辐射到所有相关报送项,是影响分析的"放大器"。
        </p>
      </div>
    </div>

    <!-- Tab -->
    <div class="card mt-16" style="padding:0;">
      <div class="tab-bar">
        <button :class="['tab-btn', activeTab === 'active' ? 'active' : '']" @click="switchTab('active')">
          已生效概念 <span class="tab-count">{{ activeCount }}</span>
        </button>
        <button :class="['tab-btn', activeTab === 'draft' ? 'active' : '']" @click="switchTab('draft')">
          候选池 (待复核) <span :class="['tab-count', draftCount > 0 ? 'pulse' : '']">{{ draftCount }}</span>
        </button>
      </div>

      <div style="padding:14px 18px;border-top:1px solid var(--line-100);display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:12px;color:var(--ink-600);">类型：</span>
        <select v-model="filterType" @change="reload">
          <option value="">全部</option>
          <option value="METRIC">METRIC 指标</option>
          <option value="SCOPE">SCOPE 范围</option>
          <option value="CLASSIFICATION">CLASSIFICATION 分类</option>
          <option value="CALCULATION">CALCULATION 计算</option>
          <option value="DIMENSION">DIMENSION 维度</option>
          <option value="ENTITY">ENTITY 实体</option>
        </select>
        <span style="font-size:12px;color:var(--ink-600);margin-left:16px;">关键词：</span>
        <input
          type="text"
          v-model="filterKeyword"
          placeholder="搜索概念名 / 定义"
          @keydown.enter="reload"
          style="padding:6px 10px;font-size:13px;border:1px solid var(--line-200);border-radius:4px;min-width:220px;"
        />
        <button class="btn ghost sm" @click="reload">搜索</button>
        <span style="font-size:11px;color:var(--ink-400);margin-left:auto;">共 {{ concepts.length }} 个</span>
      </div>
    </div>

    <div class="card mt-16" v-if="!concepts.length">
      <div style="text-align:center;padding:40px 0;color:var(--ink-400);">
        {{ activeTab === 'draft' ? '候选池暂无待复核的概念。从"规则与口径"页面抽取填报说明时会产生候选概念。' : '暂无生效概念。' }}
      </div>
    </div>

    <div v-else>
      <div class="sec-h mt-16">
        <h2>{{ activeTab === 'draft' ? '候选概念' : '已生效概念' }}</h2>
        <span class="line"></span>
        <span class="count">{{ concepts.length }} 个</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(340px, 1fr));gap:14px;">
        <div
          v-for="concept in concepts"
          :key="concept.concept_code"
          class="card"
          :style="activeTab === 'draft' ? { borderLeft: '3px solid #6366f1' } : {}"
        >
          <div class="row between" style="margin-bottom:8px;">
            <span :class="['tag', typeColor(concept.concept_type)]">{{ concept.concept_type }}</span>
            <span v-if="concept.is_locked" class="tag amber" style="font-size:10px;">🔒 已锁定</span>
          </div>
          <h3 style="font-size:15px;margin-bottom:4px;">{{ concept.canonical_name }}</h3>
          <p style="font-size:12px;color:var(--ink-700);line-height:1.5;margin-bottom:10px;min-height:36px;">
            {{ concept.short_definition || '（暂无定义,请补充）' }}
          </p>

          <div v-if="concept.aliases.length > 1" style="margin-bottom:10px;">
            <div style="font-size:10px;color:var(--ink-400);margin-bottom:3px;">别名 / 同义:</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;">
              <span
                v-for="alias in concept.aliases.filter(a => a !== concept.canonical_name).slice(0, 5)"
                :key="alias"
                class="tag outline"
                style="font-size:10px;"
              >{{ alias }}</span>
            </div>
          </div>

          <div v-if="concept.related_reporting_item_codes.length" style="margin-bottom:10px;">
            <div style="font-size:10px;color:var(--ink-400);margin-bottom:3px;">辐射到报送项 ({{ concept.related_reporting_item_codes.length }}):</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;">
              <span
                v-for="code in concept.related_reporting_item_codes.slice(0, 4)"
                :key="code"
                class="tag outline"
                style="font-size:10px;font-family:monospace;"
              >{{ code.split('.')[0] }}</span>
            </div>
          </div>

          <div style="border-top:1px solid var(--line-100);padding-top:6px;margin-top:6px;font-size:10px;color:var(--ink-400);font-family:monospace;">
            {{ concept.concept_code }} · {{ concept.reporting_system_scope || '通用' }}
          </div>

          <!-- 候选池采纳/退回 -->
          <div v-if="activeTab === 'draft'" style="margin-top:10px;padding-top:10px;border-top:1px dashed var(--line-100);display:flex;gap:6px;">
            <button class="btn primary sm" style="flex:1;" :disabled="reviewingId === concept.id" @click="review(concept, 'ACCEPT')">
              ✓ 采纳
            </button>
            <button class="btn secondary sm" style="flex:1;" :disabled="reviewingId === concept.id" @click="review(concept, 'REJECT')">
              ✗ 退回
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiClient } from "@/api/client";
import type { Concept } from "@/types/api";

const concepts = ref<Concept[]>([]);
const activeTab = ref<"active" | "draft">("active");
const activeCount = ref(0);
const draftCount = ref(0);
const filterType = ref<string>("");
const filterKeyword = ref<string>("");
const reviewingId = ref<number | null>(null);

const switchTab = (tab: "active" | "draft") => {
  activeTab.value = tab;
  reload();
};

const reload = async (): Promise<void> => {
  try {
    concepts.value = await apiClient.listConcepts({
      concept_type: filterType.value || undefined,
      keyword: filterKeyword.value || undefined,
      status: activeTab.value === "draft" ? "DRAFT" : "ACTIVE",
    });
    refreshCounts();
  } catch {
    concepts.value = [];
  }
};

const refreshCounts = async (): Promise<void> => {
  try {
    const [actives, drafts] = await Promise.all([
      apiClient.listConcepts({ status: "ACTIVE" }),
      apiClient.listConcepts({ status: "DRAFT" }),
    ]);
    activeCount.value = actives.length;
    draftCount.value = drafts.length;
  } catch {
    /* ignore */
  }
};

const review = async (concept: Concept, action: "ACCEPT" | "REJECT"): Promise<void> => {
  if (!concept.id) return;
  reviewingId.value = concept.id;
  try {
    await apiClient.reviewConcept(concept.id, action);
    concepts.value = concepts.value.filter((c) => c.id !== concept.id);
    refreshCounts();
  } catch {
    /* ignore */
  } finally {
    reviewingId.value = null;
  }
};

const typeColor = (t: string): string =>
  ({
    METRIC: "blue",
    SCOPE: "amber",
    CLASSIFICATION: "green",
    CALCULATION: "outline",
    DIMENSION: "outline",
    ENTITY: "outline",
  } as Record<string, string>)[t] ?? "outline";

onMounted(reload);
</script>

<style scoped>
.tab-bar { display: flex; gap: 4px; padding: 8px 8px 0; }
.tab-btn {
  position: relative; padding: 10px 18px; background: transparent; border: none;
  border-bottom: 2px solid transparent; font-size: 13px; color: var(--ink-500);
  cursor: pointer; display: inline-flex; align-items: center; gap: 8px;
  transition: all 0.15s;
}
.tab-btn:hover { color: var(--ink-800); }
.tab-btn.active { color: var(--ink-900); border-bottom-color: rgba(99, 102, 241, 1); font-weight: 500; }
.tab-count {
  font-size: 11px; background: var(--ink-100); color: var(--ink-600);
  padding: 1px 7px; border-radius: 999px; font-family: monospace;
}
.tab-btn.active .tab-count { background: rgba(99, 102, 241, 0.15); color: rgba(67, 56, 202, 1); }
.tab-count.pulse {
  background: rgba(239, 68, 68, 0.15); color: rgba(185, 28, 28, 1);
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
</style>
