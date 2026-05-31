<template>
  <div :class="['app', { 'sidebar-collapsed': sidebarCollapsed }]">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">报</div>
        <div class="brand-text">
          <div class="brand-title">监管报送治理</div>
          <div class="brand-sub">一表通 · 1104 · 资金同业</div>
        </div>
        <button
          class="sidebar-toggle"
          type="button"
          :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="toggleSidebar"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="6" x2="20" y2="6"/>
            <line x1="4" y1="12" x2="20" y2="12"/>
            <line x1="4" y1="18" x2="20" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="nav-section">主流程</div>
      <nav class="nav">
        <button
          v-for="step in mainSteps"
          :key="step.id"
          :class="['nav-item', { active: step.id === activePage, complete: completedSteps.includes(step.id) && step.id !== activePage }]"
          type="button"
          @click="$emit('navigate', step.id)"
        >
          <span class="step-num">{{ step.num }}</span>
          <span class="nav-label">{{ step.label }}</span>
        </button>
      </nav>

      <div class="nav-section">知识与设置</div>
      <nav class="nav">
        <button
          v-for="item in secondaryItems"
          :key="item.id"
          :class="['nav-item', { active: item.id === activePage }]"
          type="button"
          @click="$emit('navigate', item.id)"
        >
          <span class="step-num" style="font-size:9px;">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-foot">
        <div class="avatar">江</div>
        <div class="sidebar-foot-info">
          <div class="sidebar-foot-name">江秋萍</div>
          <div>数据治理团队</div>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <main class="main">
      <div class="topbar">
        <div class="crumb">
          <span v-for="(crumb, i) in crumbs" :key="i">
            <span v-if="i > 0" class="sep">/</span>
            <b v-if="i === crumbs.length - 1">{{ crumb }}</b>
            <span v-else>{{ crumb }}</span>
          </span>
        </div>
        <div class="topbar-actions">
          <div class="search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <span>搜索发文、报表、指标、工单</span>
            <span class="search-kbd">⌘K</span>
          </div>
          <button class="btn secondary" @click="$emit('navigate', 'upload')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            新建任务
          </button>
        </div>
      </div>

      <div class="page-body">
        <div v-if="errorMessage" class="error-banner">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {{ errorMessage }}
        </div>
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

export type PageId =
  | "dashboard"
  | "upload"
  | "portrait"
  | "lineage"
  | "impact"
  | "ticket"
  | "catalog"
  | "library"
  | "concepts"
  | "indicator-qa";

const props = defineProps<{
  activePage: PageId;
  errorMessage?: string;
}>();

defineEmits<{
  navigate: [page: PageId];
}>();

const SIDEBAR_COLLAPSED_KEY = "reg-reporting-sidebar-collapsed";
const sidebarCollapsed = ref(readSidebarCollapsed());

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

watch(sidebarCollapsed, (value) => {
  writeSidebarCollapsed(value);
});

function readSidebarCollapsed(): boolean {
  try {
    return typeof window !== "undefined" && window.localStorage?.getItem?.(SIDEBAR_COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
}

function writeSidebarCollapsed(value: boolean) {
  try {
    window.localStorage?.setItem?.(SIDEBAR_COLLAPSED_KEY, String(value));
  } catch {
    // Storage may be unavailable in tests or privacy-restricted browser contexts.
  }
}

const mainSteps = [
  { id: "dashboard" as PageId, num: "·", label: "工作台" },
  { id: "upload"    as PageId, num: "1", label: "上传发文" },
  { id: "portrait"  as PageId, num: "2", label: "文档画像" },
  { id: "lineage"   as PageId, num: "3", label: "字段定位" },
  { id: "impact"    as PageId, num: "4", label: "影响分析" },
  { id: "ticket"    as PageId, num: "5", label: "工单草稿" },
];

const secondaryItems = [
  { id: "indicator-qa" as PageId, icon: "✦", label: "指标问答" },
  { id: "catalog" as PageId, icon: "⬆", label: "报表目录" },
  { id: "library" as PageId, icon: "◈", label: "规则与口径" },
  { id: "concepts" as PageId, icon: "❋", label: "监管概念库" },
];

// Mark steps before the active one as complete (only in main flow)
const stepOrder = ["upload", "portrait", "lineage", "impact", "ticket"];
const completedSteps = computed<PageId[]>(() => {
  const idx = stepOrder.indexOf(props.activePage);
  if (idx <= 0) return [];
  return stepOrder.slice(0, idx) as PageId[];
});

const crumbMap: Record<PageId, string[]> = {
  dashboard:      ["监管报送治理", "工作台"],
  upload:         ["监管报送治理", "1104 · 资金同业", "上传发文"],
  portrait:       ["监管报送治理", "1104 · 资金同业", "文档画像"],
  lineage:        ["监管报送治理", "1104 · 资金同业", "字段定位"],
  impact:         ["监管报送治理", "1104 · 资金同业", "影响分析"],
  ticket:         ["监管报送治理", "1104 · 资金同业", "工单草稿"],
  catalog:        ["监管报送治理", "报表目录"],
  library:        ["监管报送治理", "规则与口径"],
  concepts:       ["监管报送治理", "监管概念库"],
  "indicator-qa": ["监管报送治理", "指标问答"],
};

const crumbs = computed(() => crumbMap[props.activePage] ?? ["监管报送治理"]);
</script>
