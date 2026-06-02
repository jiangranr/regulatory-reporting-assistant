<template>
  <div>
    <div class="h-eyebrow">数据资产 · 下游数据团队</div>
    <h1 class="h-title">我承载了哪些监管义务</h1>
    <p class="h-sub">从源系统的字段出发，反查它被哪些报送字段、哪些监管指标所依赖。改一个源字段前，先看清下游的监管影响。</p>

    <div class="da-layout mt-24">
      <!-- 左栏：源系统浏览树 -->
      <aside class="da-browser">
        <div class="da-browser-head">
          <div class="da-bh-title">数据资产</div>
          <div class="da-bh-sub">按源系统浏览 · 反查监管依赖</div>
          <div class="da-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;flex-shrink:0;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input v-model="searchQ" placeholder="搜索源字段 / 表名" />
          </div>
          <div class="da-bh-stat">
            <span><b>{{ totalFields }}</b> 源字段</span>
            <span class="mono" style="color:var(--orange-600);">{{ totalDeps }} 监管依赖</span>
          </div>
        </div>

        <div class="da-tree">
          <template v-if="loading">
            <div style="padding:24px;text-align:center;color:var(--ink-400);font-size:13px;">加载中…</div>
          </template>
          <template v-else-if="!systems.length">
            <div style="padding:24px;text-align:center;color:var(--ink-400);font-size:13px;">暂无数据，请先执行 bootstrap</div>
          </template>
          <template v-else>
            <div v-for="sys in systems" :key="sys.code" class="da-sys">
              <button class="da-sys-row" @click="toggleSys(sys.code)">
                <span :class="['chev', { open: openSys.has(sys.code) }]">▾</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;flex-shrink:0;"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
                <span class="nm">{{ sys.name }}</span>
                <span class="dep-pill">{{ sys.totalDeps }}</span>
              </button>

              <template v-if="openSys.has(sys.code)">
                <div v-for="tbl in sys.tables" :key="tbl.name" class="da-table">
                  <button class="da-table-row" @click="toggleTbl(tbl.id)">
                    <span :class="['chev', { open: openTbl.has(tbl.id) }]">▾</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;flex-shrink:0;"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/></svg>
                    <span class="nm mono">{{ tbl.name }}</span>
                  </button>

                  <div v-if="openTbl.has(tbl.id)" class="da-fields">
                    <button
                      v-for="f in filteredFields(tbl.fields)"
                      :key="f.field_code"
                      :class="['da-field-row', { active: activeCode === f.field_code, 'no-dep': !f.regulatory_dependency_count }]"
                      @click="selectField(f.field_code)"
                    >
                      <span class="fcol mono">{{ f.field_code.split('.')[1] || f.field_code }}</span>
                      <span class="fname">{{ f.field_name }}</span>
                      <span v-if="f.regulatory_dependency_count" class="dep-badge">{{ f.regulatory_dependency_count }}</span>
                      <span v-else class="dep-badge zero">–</span>
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </div>
      </aside>

      <!-- 右栏：字段详情 -->
      <div class="da-main" v-if="activeDetail">
        <!-- 头部信息区 -->
        <div class="da-fieldhead">
          <div class="da-fh-path">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
            <span>{{ activeDetail.system_name }}</span>
            <span class="sep">/</span>
            <span class="mono">{{ activeDetail.field_code.split('.')[0] }}</span>
          </div>

          <div class="da-fh-top">
            <div class="da-fh-titles">
              <div class="da-fh-code mono">{{ activeDetail.field_code }}</div>
              <h1 class="da-fh-name">{{ activeDetail.field_name }}</h1>
            </div>
            <div class="da-fh-tags">
              <span v-if="activeDetail.dependency_count > 0" class="dep-headline">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>
                被 <b>{{ activeDetail.dependency_count }}</b> 项监管指标依赖
              </span>
              <span v-else class="dep-headline none">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><polyline points="20 6 9 17 4 12"/></svg>
                暂无监管依赖
              </span>
            </div>
          </div>

          <div class="da-fh-meta">
            <div class="m-cell">
              <span class="k">owner</span>
              <span class="v owner">
                <span class="ava">{{ (activeDetail.owner_team || '?').slice(0, 1) }}</span>
                {{ activeDetail.owner_team || '未指定' }}
              </span>
            </div>
            <div class="m-cell">
              <span class="k">来源系统</span>
              <span class="v">{{ activeDetail.system_name }}</span>
            </div>
            <div class="m-cell">
              <span class="k">字段代码</span>
              <span class="v mono">{{ activeDetail.field_code }}</span>
            </div>
          </div>
        </div>

        <!-- 反向血缘图 -->
        <div v-if="activeDetail.dependency_count > 0" class="card">
          <div class="sec-h">
            <h2>监管依赖血缘</h2>
            <span class="line" />
            <span class="count">反向 · 从源字段看监管义务</span>
          </div>
          <ReverseLineageGraph
            :field-code="activeDetail.field_code"
            :field-name="activeDetail.field_name"
            :dependencies="activeDetail.regulatory_dependencies"
            :highlight="highlightId"
            @hover="highlightId = $event"
          />
        </div>

        <!-- 依赖指标列表 -->
        <div v-if="activeDetail.dependency_count > 0" class="card">
          <div class="sec-h">
            <h2>依赖这个字段的监管指标</h2>
            <span class="line" />
            <span class="count">{{ activeDetail.dependency_count }} 个</span>
          </div>
          <div class="da-dep-list">
            <div
              v-for="(dep, i) in activeDetail.regulatory_dependencies"
              :key="dep.reporting_item_code"
              :class="['da-dep-row', { hl: highlightId === 'i' + i }]"
              @mouseenter="highlightId = 'i' + i"
              @mouseleave="highlightId = null"
            >
              <div class="dep-top">
                <span class="ind-code mono">{{ dep.reporting_item_code }}</span>
                <span :class="['tag', statusTone(dep.mapping_status)]">
                  <span class="dot" />{{ statusLabel(dep.mapping_status) }}
                </span>
                <span class="dep-role-tag">{{ roleLabel(dep.lineage_role) }}</span>
                <button class="btn ghost sm dep-trace">查看血缘 →</button>
              </div>
              <div class="ind-name">{{ dep.reporting_item_code }}</div>
              <div class="ind-sub">{{ dep.reporting_object_code }} · {{ dep.lineage_role }}</div>
              <div class="dep-via">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;flex-shrink:0;color:var(--ink-400);"><polyline points="9 10 4 15 9 20"/><path d="M20 4v7a4 4 0 0 1-4 4H4"/></svg>
                <span class="via-label">{{ dep.lineage_role === 'REPORT_FIELD' ? '报送字段' : dep.lineage_role === 'SOURCE_FIELD' ? '来源字段' : dep.lineage_role === 'FILTER_FIELD' ? '过滤条件' : '维度字段' }}</span>
                <span class="via-sub mono">{{ activeDetail.field_code }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 无依赖空态 -->
        <div v-else class="da-empty">
          <div class="glyph">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:24px;height:24px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          </div>
          <h3>该源字段当前不承载任何监管报送义务</h3>
          <p>没有报送字段引用 <span class="mono">{{ activeDetail.field_code }}</span>。变更该字段不会直接影响 1104 监管报表，可按普通数据资产维护。</p>
        </div>
      </div>

      <!-- 未选中时的提示 -->
      <div v-else class="da-main">
        <div class="card" style="padding:64px 32px;text-align:center;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px;height:40px;margin:0 auto 12px;display:block;opacity:.35;"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
          <p style="color:var(--ink-400);font-size:13px;margin:0;">从左侧选择一个源字段，查看它承载的监管依赖</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { apiClient } from "@/api/client";
import type { SourceField, SourceFieldDependencies } from "@/types/api";
import ReverseLineageGraph from "@/components/ReverseLineageGraph.vue";

// ── 状态 ──────────────────────────────────────────────────────────

const loading = ref(true);
const allFields = ref<SourceField[]>([]);
const activeCode = ref<string | null>(null);
const activeDetail = ref<SourceFieldDependencies | null>(null);
const detailLoading = ref(false);
const searchQ = ref("");
const openSys = ref<Set<string>>(new Set());
const openTbl = ref<Set<string>>(new Set());
const highlightId = ref<string | null>(null);

// ── 数据加载 ───────────────────────────────────────────────────────

onMounted(async () => {
  try {
    allFields.value = await apiClient.listSourceFields();
    // 默认展开所有系统和表
    allFields.value.forEach((f) => {
      const sysCode = f.system_code;
      const tblId = f.field_code.split(".")[0];
      openSys.value.add(sysCode);
      openTbl.value.add(`${sysCode}.${tblId}`);
    });
    // 默认选中第一个有依赖的字段
    const first = allFields.value.find((f) => f.regulatory_dependency_count > 0);
    if (first) selectField(first.field_code);
  } finally {
    loading.value = false;
  }
});

async function selectField(code: string) {
  if (activeCode.value === code) return;
  activeCode.value = code;
  highlightId.value = null;
  detailLoading.value = true;
  try {
    activeDetail.value = await apiClient.getSourceFieldDependencies(code);
  } finally {
    detailLoading.value = false;
  }
}

// ── 树形结构构建 ─────────────────────────────────────────────────

interface TableNode { id: string; name: string; fields: SourceField[] }
interface SystemNode { code: string; name: string; tables: TableNode[]; totalDeps: number }

const systems = computed<SystemNode[]>(() => {
  const bySystem = new Map<string, Map<string, SourceField[]>>();
  const sysNames = new Map<string, string>();

  for (const f of allFields.value) {
    const sysCode = f.system_code || "UNKNOWN";
    const tblName = f.field_code.split(".")[0] || f.field_code;
    sysNames.set(sysCode, f.system_name || sysCode);
    if (!bySystem.has(sysCode)) bySystem.set(sysCode, new Map());
    const tblMap = bySystem.get(sysCode)!;
    if (!tblMap.has(tblName)) tblMap.set(tblName, []);
    tblMap.get(tblName)!.push(f);
  }

  return Array.from(bySystem.entries()).map(([sysCode, tblMap]) => ({
    code: sysCode,
    name: sysNames.get(sysCode) || sysCode,
    tables: Array.from(tblMap.entries()).map(([tblName, fields]) => ({
      id: `${sysCode}.${tblName}`,
      name: tblName,
      fields,
    })),
    totalDeps: Array.from(tblMap.values()).flat().reduce((s, f) => s + f.regulatory_dependency_count, 0),
  }));
});

const totalFields = computed(() => allFields.value.length);
const totalDeps = computed(() => allFields.value.reduce((s, f) => s + f.regulatory_dependency_count, 0));

function filteredFields(fields: SourceField[]): SourceField[] {
  if (!searchQ.value) return fields;
  const q = searchQ.value.toLowerCase();
  return fields.filter(
    (f) =>
      f.field_code.toLowerCase().includes(q) ||
      f.field_name.includes(searchQ.value),
  );
}

// ── 树展开 ───────────────────────────────────────────────────────

function toggleSys(code: string) {
  const next = new Set(openSys.value);
  if (next.has(code)) next.delete(code);
  else next.add(code);
  openSys.value = next;
}

function toggleTbl(id: string) {
  const next = new Set(openTbl.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  openTbl.value = next;
}

// ── 标签工具 ─────────────────────────────────────────────────────

const STATUS_TONE: Record<string, string> = {
  CONFIRMED: "green", SEED_CONFIRMED: "blue", DRAFT: "amber", PENDING: "amber", MISSING: "red",
};
const STATUS_LABEL: Record<string, string> = {
  CONFIRMED: "已确认", SEED_CONFIRMED: "种子确认", DRAFT: "草稿映射", PENDING: "待审核", MISSING: "未映射",
};
const ROLE_LABEL: Record<string, string> = {
  REPORT_FIELD: "报送字段", SOURCE_FIELD: "来源字段", FILTER_FIELD: "过滤条件", DIMENSION_FIELD: "维度字段",
};

const statusTone = (s: string) => STATUS_TONE[s] ?? "outline";
const statusLabel = (s: string) => STATUS_LABEL[s] ?? s;
const roleLabel = (r: string) => ROLE_LABEL[r] ?? r;
</script>

<style scoped>
/* ── 两栏布局 ────────────────────────────────────────────────── */
.da-layout {
  display: grid;
  grid-template-columns: 264px 1fr;
  gap: 20px;
  align-items: start;
}

/* ── 左栏：浏览树 ──────────────────────────────────────────── */
.da-browser {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg, 12px);
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.da-browser-head {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #FFFCF8, var(--surface));
}
.da-bh-title { font-size: 15px; font-weight: 700; color: var(--ink-900); letter-spacing: -0.2px; }
.da-bh-sub { font-size: 11.5px; color: var(--ink-500); margin-top: 2px; }

.da-search {
  display: flex; align-items: center; gap: 7px;
  margin-top: 12px;
  background: var(--bg-elev, #faf6f1);
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 7px 10px;
  color: var(--ink-400);
}
.da-search:focus-within { border-color: var(--orange-300, #fdba74); background: var(--surface); }
.da-search input {
  border: none; background: transparent; outline: none;
  font-size: 12.5px; color: var(--ink-900); width: 100%;
}
.da-search input::placeholder { color: var(--ink-400); }

.da-bh-stat {
  display: flex; justify-content: space-between;
  margin-top: 11px;
  font-size: 11.5px; color: var(--ink-500);
}
.da-bh-stat b { color: var(--ink-900); font-family: var(--font-mono, monospace); }

.da-tree {
  padding: 8px 8px 14px;
  overflow-y: auto;
  flex: 1;
}
.da-tree::-webkit-scrollbar { width: 6px; }
.da-tree::-webkit-scrollbar-thumb { background: var(--ink-200); border-radius: 3px; }

.da-sys { margin-bottom: 2px; }
.da-sys-row {
  display: flex; align-items: center; gap: 8px;
  width: 100%; padding: 8px 8px;
  border: none; background: transparent; border-radius: 7px;
  color: var(--ink-800); font-size: 13px; font-weight: 600;
  text-align: left; cursor: pointer;
}
.da-sys-row:hover { background: var(--bg-elev, #faf6f1); }
.da-sys-row .nm { flex: 1; min-width: 0; }
.da-sys-row .dep-pill {
  font-family: var(--font-mono, monospace); font-size: 10.5px; font-weight: 600;
  color: var(--orange-700, #c2410c);
  background: var(--orange-50, #fff7ed);
  border: 1px solid rgba(234,84,4,0.16);
  padding: 1px 7px; border-radius: 999px;
}

.chev {
  display: inline-block; width: 12px;
  color: var(--ink-300); font-size: 10px;
  transition: transform .15s;
  transform: rotate(-90deg);
}
.chev.open { transform: rotate(0deg); }

.da-table {
  margin: 1px 0 1px 10px;
  padding-left: 8px;
  border-left: 1px dashed var(--border);
}
.da-table-row {
  display: flex; align-items: center; gap: 7px;
  width: 100%; padding: 6px 7px;
  border: none; background: transparent; border-radius: 6px;
  color: var(--ink-700); font-size: 12px; text-align: left; cursor: pointer;
}
.da-table-row:hover { background: var(--bg-elev, #faf6f1); }
.da-table-row .nm { font-weight: 600; color: var(--ink-800); }

.da-fields {
  margin: 2px 0 4px 4px;
  padding-left: 10px;
  border-left: 1px dashed var(--border);
  display: flex; flex-direction: column; gap: 1px;
}
.da-field-row {
  display: flex; align-items: center; gap: 8px;
  width: 100%; padding: 7px 8px;
  border: none; background: transparent; border-radius: 7px;
  text-align: left; cursor: pointer; position: relative;
}
.da-field-row:hover { background: var(--bg-elev, #faf6f1); }
.da-field-row .fcol { font-size: 12px; color: var(--ink-800); font-weight: 600; white-space: nowrap; max-width: 90px; overflow: hidden; text-overflow: ellipsis; }
.da-field-row .fname { font-size: 11px; color: var(--ink-400); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.da-field-row.active {
  background: var(--orange-50, #fff7ed);
  box-shadow: inset 2px 0 0 var(--orange-500, #f97316);
}
.da-field-row.active .fcol { color: var(--orange-700, #c2410c); }
.da-field-row.active .fname { color: var(--orange-600, #ea580c); }
.da-field-row.no-dep .fcol { color: var(--ink-500); font-weight: 500; }

.dep-badge {
  flex-shrink: 0; min-width: 18px; height: 18px;
  display: inline-grid; place-items: center; padding: 0 5px;
  font-family: var(--font-mono, monospace); font-size: 10.5px; font-weight: 700;
  color: #fff; background: var(--orange-500, #f97316);
  border-radius: 999px;
  box-shadow: 0 1px 2px rgba(234,84,4,0.3);
}
.dep-badge.zero {
  color: var(--ink-300); background: transparent; box-shadow: none; font-weight: 500;
}

/* ── 右栏 ──────────────────────────────────────────────────── */
.da-main { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

/* 头部信息区 */
.da-fieldhead {
  background:
    radial-gradient(ellipse 600px 160px at 12% 0%, rgba(234,84,4,0.06), transparent 70%),
    linear-gradient(180deg, #FFFBF6 0%, var(--surface) 100%);
  border: 1px solid var(--border);
  border-radius: var(--r-xl, 16px);
  padding: 20px 24px;
}
.da-fh-path {
  display: flex; align-items: center; gap: 7px;
  font-size: 12px; color: var(--ink-500);
}
.da-fh-path .sep { color: var(--ink-300); }
.da-fh-path .mono { font-family: var(--font-mono, monospace); color: var(--ink-700); font-weight: 500; }

.da-fh-top {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-top: 12px;
}
.da-fh-code {
  font-family: var(--font-mono, monospace);
  font-size: 13px; font-weight: 600;
  color: var(--orange-600, #ea580c); letter-spacing: 0.2px;
}
.da-fh-name {
  margin: 5px 0 0;
  font-size: 22px; font-weight: 700;
  color: var(--ink-900); letter-spacing: -0.4px; line-height: 1.25;
}
.da-fh-tags { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }

.dep-headline {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--orange-700, #c2410c); font-weight: 600;
  background: var(--orange-50, #fff7ed);
  border: 1px solid rgba(234,84,4,0.18);
  padding: 6px 12px; border-radius: 999px;
  white-space: nowrap;
}
.dep-headline b { font-family: var(--font-mono, monospace); font-size: 15px; }
.dep-headline.none { color: #15803d; background: rgba(22,163,74,0.06); border-color: rgba(31,122,87,0.2); }

.da-fh-meta {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 14px 24px; margin-top: 18px;
  padding-top: 16px; border-top: 1px dashed var(--border);
}
.m-cell { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.m-cell .k {
  font-size: 10.5px; color: var(--ink-500);
  text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;
}
.m-cell .v { font-size: 13px; color: var(--ink-900); font-weight: 500; }
.m-cell .v.mono { font-family: var(--font-mono, monospace); font-size: 12px; }
.m-cell .v.owner { display: inline-flex; align-items: center; gap: 7px; }
.m-cell .v.owner .ava {
  width: 20px; height: 20px; border-radius: 50%;
  background: linear-gradient(135deg, #FFCFA3, var(--orange-500, #f97316));
  color: #1A1410; display: inline-grid; place-items: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
}

/* sec-h（与其他页面一致） */
.sec-h {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px;
}
.sec-h h2 { margin: 0; font-size: 14px; font-weight: 700; color: var(--ink-900); white-space: nowrap; }
.sec-h .line { flex: 1; height: 1px; background: var(--border); }
.sec-h .count { font-size: 12px; color: var(--ink-500); white-space: nowrap; font-family: var(--font-mono, monospace); }

/* 依赖指标列表 */
.da-dep-list { display: flex; flex-direction: column; gap: 8px; }
.da-dep-row {
  display: flex; flex-direction: column; gap: 6px;
  padding: 13px 15px;
  background: var(--surface-alt, #faf6f1);
  border: 1px solid var(--border);
  border-radius: 10px;
  border-left: 3px solid var(--border, #e8dfd2);
  transition: border-color .12s, background .12s, box-shadow .12s;
  cursor: default;
}
.da-dep-row:hover, .da-dep-row.hl {
  border-color: var(--orange-300, #fdba74);
  border-left-color: var(--orange-500, #f97316);
  background: #FFFAF4;
  box-shadow: 0 0 0 3px rgba(234,84,4,0.06);
}
.dep-top { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.dep-top .ind-code {
  font-family: var(--font-mono, monospace); font-size: 11.5px; font-weight: 600;
  color: var(--orange-600, #ea580c); letter-spacing: 0.3px;
}
.dep-top .dep-trace { margin-left: auto; color: var(--ink-500); }
.dep-top .dep-trace:hover { color: var(--orange-600, #ea580c); }

.dep-role-tag {
  font-size: 10.5px; color: var(--ink-500);
  background: var(--bg-elev, #faf6f1);
  border: 1px solid var(--border); border-radius: 6px;
  padding: 1px 7px;
}

.da-dep-row .ind-name {
  font-size: 14px; color: var(--ink-900); font-weight: 600; line-height: 1.4;
}
.da-dep-row .ind-sub { font-size: 11.5px; color: var(--ink-500); }

.dep-via {
  display: flex; align-items: center; gap: 8px;
  margin-top: 2px; padding-top: 8px;
  border-top: 1px dashed var(--border);
  color: var(--ink-400); min-width: 0; flex-wrap: wrap;
}
.dep-via .via-label { font-size: 12.5px; color: var(--ink-800); font-weight: 500; }
.dep-via .via-sub {
  font-size: 11px; color: var(--ink-500); font-family: var(--font-mono, monospace);
  background: var(--bg-elev, #faf6f1); padding: 1px 6px; border-radius: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
}

/* 空态 */
.da-empty {
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--r-lg, 12px);
  padding: 48px 32px; text-align: center;
}
.da-empty .glyph {
  width: 52px; height: 52px; margin: 0 auto 14px;
  border-radius: 14px;
  background: rgba(22,163,74,0.08); color: #15803d;
  display: grid; place-items: center;
}
.da-empty h3 { margin: 0 0 8px; font-size: 16px; color: var(--ink-900); font-weight: 600; }
.da-empty p { margin: 0 auto; font-size: 13px; color: var(--ink-500); line-height: 1.6; max-width: 460px; }
.da-empty p .mono {
  font-family: var(--font-mono, monospace); color: var(--ink-700);
  background: var(--bg-elev, #faf6f1); padding: 1px 5px; border-radius: 3px;
}
</style>
