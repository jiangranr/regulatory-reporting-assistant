<template>
  <AppShell
    :active-page="activePage"
    :error-message="errorMessage"
    @navigate="activePage = $event"
  >
    <DashboardView
      v-if="activePage === 'dashboard'"
      :tasks="tasks"
      :documents="documents"
      @navigate="activePage = $event"
    />
    <DocumentsView
      v-else-if="activePage === 'upload'"
      :documents="documents"
      :busy="busy"
      @upload="uploadDocument"
      @upload-pair="uploadReportingPair"
      @triplet-done="handleTripletDone"
      @create-task="createTaskFromDocument"
      @document-deleted="handleDocumentDeleted"
    />
    <PortraitView
      v-else-if="activePage === 'portrait'"
      :documents="documents"
      :selected-document-id="selectedPortraitDocumentId"
      :selected-profile="selectedPortraitProfile"
      :impact-item-count="portraitImpactItemCount"
      :instruction-analysis="instructionAnalysis"
      :analysis-busy="analysisBusy"
      :workflow="taskWorkflow"
      :busy="busy"
      :profile-busy="profileBusy"
      :profile-scan-message="profileScanMessage"
      @select-document="selectPortraitDocument"
      @profile-document="profileDocument"
      @analyze-instruction-changes="analyzeInstructionChanges"
      @continue="activePage = 'lineage'"
      @back="activePage = 'upload'"
    />
    <LineageView
      v-else-if="activePage === 'lineage'"
      :key="lineageViewKey"
      :workflow="taskWorkflow"
      :busy="busy"
      :concept-hits="conceptHits"
      :concept-hits-busy="conceptHitsBusy"
      :focus-item-code="focusedLineageItemCode"
      @analyze="analyzeImpact"
      @continue="activePage = 'impact'"
      @back="activePage = 'portrait'"
    />
    <ImpactView
      v-else-if="activePage === 'impact'"
      :workflow="taskWorkflow"
      :busy="busy"
      @analyze="analyzeImpact"
      @view-lineage="onViewLineage"
      @continue="activePage = 'ticket'"
      @back="activePage = 'lineage'"
    />
    <TicketView
      v-else-if="activePage === 'ticket'"
      :workflow="taskWorkflow"
      :busy="busy"
      @generate="generateTicket"
      @impact-review-confirmed="refreshTicketWorkflow"
      @back="activePage = 'impact'"
      @finish="activePage = 'dashboard'"
    />
    <CatalogUploadView
      v-else-if="activePage === 'catalog'"
    />
    <LibraryView
      v-else-if="activePage === 'library'"
      :rule-cards="ruleCards"
      :busy="busy"
    />
    <ConceptsView v-else-if="activePage === 'concepts'" />
    <IndicatorQAView v-else-if="activePage === 'indicator-qa'" />
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { apiClient } from "@/api/client";
import AppShell, { type PageId } from "@/components/AppShell.vue";
import DashboardView from "@/views/DashboardView.vue";
import DocumentsView from "@/views/DocumentsView.vue";
import PortraitView from "@/views/PortraitView.vue";
import LineageView from "@/views/LineageView.vue";
import ImpactView from "@/views/ImpactView.vue";
import TicketView from "@/views/ReviewTicketView.vue";
import CatalogUploadView from "@/views/CatalogUploadView.vue";
import LibraryView from "@/views/LibraryView.vue";
import ConceptsView from "@/views/ConceptsView.vue";
import IndicatorQAView from "@/views/IndicatorQAView.vue";
import type {
  ConceptMatchHit,
  DocumentTaskProfile,
  InstructionChangeAnalysis,
  RegDocument,
  RegTask,
  RuleCard,
  TaskWorkflow,
  TripletUploadResponse,
} from "@/types/api";

const activePage = ref<PageId>(
  (new URLSearchParams(window.location.search).get("page") as PageId) || "dashboard"
);
const documents = ref<RegDocument[]>([]);
const tasks = ref<RegTask[]>([]);
const taskWorkflow = ref<TaskWorkflow | null>(null);
const selectedPortraitDocumentId = ref<number | null>(null);
const selectedPortraitProfile = ref<DocumentTaskProfile | null>(null);
const ruleCards = ref<RuleCard[]>([]);
const busy = ref(false);
const profileBusy = ref(false);
const profileScanMessage = ref("");
const analysisBusy = ref(false);
const instructionAnalysis = ref<InstructionChangeAnalysis | null>(null);
const errorMessage = ref("");
const tripletImpactItemCounts = ref<Record<number, number>>({});
// 当前发文命中的概念集合（驱动 LineageView 顶部横幅 + 右侧"通过哪些概念命中到这里"）
const conceptHits = ref<ConceptMatchHit[]>([]);
const conceptHitsBusy = ref(false);
// 影响分析「查看血缘」跳转携带的指标 item_code；LineageView 据此聚焦节点
const focusedLineageItemCode = ref<string | null>(null);
function onViewLineage(itemCode: string): void {
  focusedLineageItemCode.value = itemCode;
  activePage.value = "lineage";
}
const selectedPortraitDocument = computed(() =>
  documents.value.find((doc) => doc.id === selectedPortraitDocumentId.value) ?? null
);
const portraitImpactItemCount = computed(() => {
  const documentId = selectedPortraitDocumentId.value;
  if (!documentId) return null;
  return tripletImpactItemCounts.value[documentId] ?? null;
});

/**
 * 当前 workflow 对应的文档文本签名，用于触发 conceptHits 重拉。
 * 文档变 → profile.id 变 → 重新调 /concepts/match
 */
const conceptMatchSignature = computed(() => {
  const w = taskWorkflow.value;
  if (!w) return "";
  const docId = w.document?.id ?? 0;
  const profileId = w.document_profile?.id ?? 0;
  return `${docId}:${profileId}`;
});

watch(
  conceptMatchSignature,
  async (sig) => {
    if (!sig) {
      conceptHits.value = [];
      return;
    }
    const w = taskWorkflow.value;
    const text = w?.document?.parsed_text ?? "";
    if (!text.trim()) {
      conceptHits.value = [];
      return;
    }
    conceptHitsBusy.value = true;
    try {
      conceptHits.value = await apiClient.matchConcepts(text, 30);
    } catch {
      // 概念匹配失败不阻断 LineageView 主流程
      conceptHits.value = [];
    } finally {
      conceptHitsBusy.value = false;
    }
  },
  { immediate: true },
);

/**
 * 给 LineageView 用的 :key —— 文档/画像/扫描结果一变就强制重建，
 * 避免本地 activeTable/activeItem 选中状态粘到新 workflow 上。
 * 同步组合 document_id + task_id + profile.id + change_signals 内容签名，
 * 避免信号数量相同但内容已换成新文档时仍复用旧子组件状态。
 */
const lineageViewKey = computed(() => {
  const w = taskWorkflow.value;
  if (!w) return "empty";
  const docId = w.document?.id ?? "none";
  const taskId = w.task?.id ?? "none";
  const profileId = w.document_profile?.id ?? "none";
  const signalSignature = (w.document_profile?.change_signals ?? [])
    .map((signal) => `${signal.matched_item_code ?? ""}:${signal.indicator_hint ?? ""}:${signal.change_type ?? ""}`)
    .join("|");
  return `${docId}:${taskId}:${profileId}:${signalSignature}`;
});

onMounted(async () => {
  await refreshLists();
  if (tasks.value[0]) {
    await refreshTaskWorkflow(tasks.value[0].id, false);
  }
});

async function refreshLists(): Promise<void> {
  try {
    const [docRows, taskRows] = await Promise.all([
      apiClient.listDocuments(),
      apiClient.listTasks(),
    ]);
    if (docRows.length) documents.value = docRows;
    if (taskRows.length) tasks.value = taskRows;
    if (!selectedPortraitDocumentId.value && documents.value[0]) {
      selectedPortraitDocumentId.value = documents.value[0].id;
      selectedPortraitProfile.value = await apiClient.getDocumentProfile(documents.value[0].id);
    }
  } catch {
    // 使用本地样例数据
  }
}

async function refreshTaskWorkflow(taskId: number, showError = true): Promise<void> {
  await withBusy(async () => {
    taskWorkflow.value = await apiClient.getTaskWorkflow(taskId);
  }, showError);
}

async function withBusy(action: () => Promise<void>, showError = true): Promise<void> {
  busy.value = true;
  errorMessage.value = "";
  try {
    await action();
  } catch (err) {
    if (showError) {
      errorMessage.value = err instanceof Error ? err.message : "接口调用失败，请检查后端服务";
    }
  } finally {
    busy.value = false;
  }
}

async function uploadDocument(file: File): Promise<void> {
  await withBusy(async () => {
    const doc = await apiClient.uploadDocument(file);
    documents.value = [doc, ...documents.value.filter((d) => d.id !== doc.id)];
    selectedPortraitDocumentId.value = doc.id;
    selectedPortraitProfile.value = null;
    instructionAnalysis.value = null;
    profileScanMessage.value = "";
    focusedLineageItemCode.value = null;
    setTripletImpactItemCount(doc.id, null);
    syncPortraitWorkflow(doc.id, null);
  });
}

async function uploadReportingPair(templateFile: File, instructionFile: File): Promise<void> {
  await withBusy(async () => {
    const doc = await apiClient.uploadReportingPair(templateFile, instructionFile);
    documents.value = [doc, ...documents.value.filter((d) => d.id !== doc.id)];
    selectedPortraitDocumentId.value = doc.id;
    selectedPortraitProfile.value = null;
    instructionAnalysis.value = null;
    profileScanMessage.value = "";
    focusedLineageItemCode.value = null;
    setTripletImpactItemCount(doc.id, null);
    syncPortraitWorkflow(doc.id, null);
  });
}

function handleDocumentDeleted(documentId: number): void {
  documents.value = documents.value.filter((d) => d.id !== documentId);
  setTripletImpactItemCount(documentId, null);
  if (selectedPortraitDocumentId.value === documentId) {
    selectedPortraitDocumentId.value = documents.value[0]?.id ?? null;
    selectedPortraitProfile.value = null;
  }
}

async function handleTripletDone(result: TripletUploadResponse): Promise<void> {
  await withBusy(async () => {
    const doc = result.document;
    documents.value = [doc, ...documents.value.filter((d) => d.id !== doc.id)];
    selectedPortraitDocumentId.value = doc.id;
    instructionAnalysis.value = null;
    focusedLineageItemCode.value = null;
    setTripletImpactItemCount(doc.id, result.scan_results.length);
    const profile = await apiClient.profileDocument(doc.id);
    selectedPortraitProfile.value = profile;
    syncPortraitWorkflow(doc.id, profile);
    profileScanMessage.value = formatProfileScanMessage(profile);
    activePage.value = "portrait";
  });
}

function setTripletImpactItemCount(documentId: number, count: number | null): void {
  const next = { ...tripletImpactItemCounts.value };
  if (count === null) delete next[documentId];
  else next[documentId] = count;
  tripletImpactItemCounts.value = next;
}

async function createTaskFromDocument(documentId: number): Promise<void> {
  await withBusy(async () => {
    const task = await apiClient.createTaskFromDocument(documentId);
    tasks.value = [task, ...tasks.value.filter((t) => t.id !== task.id)];
    taskWorkflow.value = await apiClient.getTaskWorkflow(task.id);
    selectedPortraitDocumentId.value = documentId;
    selectedPortraitProfile.value = taskWorkflow.value.document_profile;
    activePage.value = "portrait";
  });
}

async function profileDocument(documentId: number): Promise<void> {
  profileBusy.value = true;
  profileScanMessage.value = "";
  errorMessage.value = "";
  try {
    const profile = await apiClient.profileDocument(documentId);
    selectedPortraitProfile.value = profile;
    selectedPortraitDocumentId.value = documentId;

    const relatedTask = tasks.value.find((t) => t.document_id === documentId);
    if (relatedTask) {
      busy.value = true;
      const freshWorkflow = await apiClient.getTaskWorkflow(relatedTask.id);
      // 兜底：后端 workflow 可能仍指向旧 profile 快照，强制覆盖为本轮最新结果，
      // 避免「画像页 17 条 / 字段定位页 3 条」这种不一致。
      freshWorkflow.document_profile = profile;
      taskWorkflow.value = freshWorkflow;
      selectedPortraitProfile.value = profile;
      profileScanMessage.value = formatProfileScanMessage(profile);
      return;
    }

    syncPortraitWorkflow(documentId, profile);
    profileScanMessage.value = formatProfileScanMessage(profile);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "文档画像扫描失败";
  } finally {
    busy.value = false;
    profileBusy.value = false;
  }
}

async function analyzeInstructionChanges(documentId: number): Promise<void> {
  analysisBusy.value = true;
  errorMessage.value = "";
  try {
    instructionAnalysis.value = await apiClient.analyzeInstructionChanges(documentId);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "填报说明变更分析失败";
  } finally {
    analysisBusy.value = false;
  }
}

async function selectPortraitDocument(documentId: number): Promise<void> {
  await withBusy(async () => {
    selectedPortraitDocumentId.value = documentId;
    instructionAnalysis.value = null;
    profileScanMessage.value = "";
    selectedPortraitProfile.value = await apiClient.getDocumentProfile(documentId);
    const relatedTask = tasks.value.find((task) => task.document_id === documentId);
    if (relatedTask) {
      taskWorkflow.value = await apiClient.getTaskWorkflow(relatedTask.id);
      selectedPortraitProfile.value = taskWorkflow.value.document_profile ?? selectedPortraitProfile.value;
      return;
    }
    syncPortraitWorkflow(documentId, selectedPortraitProfile.value);
  });
}

function formatProfileScanMessage(profile: DocumentTaskProfile | null): string {
  if (!profile?.created_at) return "扫描完成，画像已更新";
  return `扫描完成，画像已更新 · ${new Date(profile.created_at).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })}`;
}

function syncPortraitWorkflow(
  documentId: number,
  profile: DocumentTaskProfile | null,
): void {
  const document = documents.value.find((item) => item.id === documentId);
  if (!document) return;

  taskWorkflow.value = {
    task: {
      id: 0,
      document_id: documentId,
      title: `${document.title}规则加工任务`,
      status: "CREATED",
      risk_level: "HIGH",
      created_at: document.created_at,
      updated_at: document.created_at,
    },
    document,
    document_profile: profile,
    steps: [],
    clauses: [],
    semantic_items: [],
    field_mappings: [],
    reporting_candidates: [],
    lineage_candidates: [],
    impact_items: [],
    rule_cards: [],
    ticket_drafts: [],
  };
}

async function analyzeImpact(): Promise<void> {
  if (!taskWorkflow.value) return;
  await withBusy(async () => {
    const taskId = await ensureWorkflowTaskId();
    await apiClient.analyzeImpact(taskId);
    taskWorkflow.value = await apiClient.getTaskWorkflow(taskId);
  });
}

async function ensureWorkflowTaskId(): Promise<number> {
  if (!taskWorkflow.value) {
    throw new Error("尚未选择任务");
  }
  if (taskWorkflow.value.task.id > 0) {
    return taskWorkflow.value.task.id;
  }

  const documentId = taskWorkflow.value.document.id;
  const existingTask = tasks.value.find((task) => task.document_id === documentId);
  if (existingTask) {
    taskWorkflow.value = await apiClient.getTaskWorkflow(existingTask.id);
    return existingTask.id;
  }

  const task = await apiClient.createTaskFromDocument(documentId);
  tasks.value = [task, ...tasks.value.filter((item) => item.id !== task.id)];
  taskWorkflow.value = {
    ...taskWorkflow.value,
    task,
  };
  return task.id;
}

async function generateTicket(): Promise<void> {
  if (!taskWorkflow.value) return;
  await withBusy(async () => {
    await apiClient.generateTicket(taskWorkflow.value!.task.id);
    taskWorkflow.value = await apiClient.getTaskWorkflow(taskWorkflow.value!.task.id);
  });
}

async function refreshTicketWorkflow(): Promise<void> {
  if (!taskWorkflow.value) return;
  await withBusy(async () => {
    taskWorkflow.value = await apiClient.getTaskWorkflow(taskWorkflow.value!.task.id);
  });
}
</script>
