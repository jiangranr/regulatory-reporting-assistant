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
      :workflow="taskWorkflow"
      :focus-item-code="focusedLineageItemCode"
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
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

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
import type {
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
// 影响分析「查看血缘」跳转携带的指标 item_code；LineageView 据此聚焦节点
const focusedLineageItemCode = ref<string | null>(null);
function onViewLineage(itemCode: string): void {
  focusedLineageItemCode.value = itemCode;
  activePage.value = "lineage";
}
const selectedPortraitDocument = computed(() =>
  documents.value.find((doc) => doc.id === selectedPortraitDocumentId.value) ?? null
);

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
  });
}

async function uploadReportingPair(templateFile: File, instructionFile: File): Promise<void> {
  await withBusy(async () => {
    const doc = await apiClient.uploadReportingPair(templateFile, instructionFile);
    documents.value = [doc, ...documents.value.filter((d) => d.id !== doc.id)];
    selectedPortraitDocumentId.value = doc.id;
    selectedPortraitProfile.value = null;
  });
}

function handleDocumentDeleted(documentId: number): void {
  documents.value = documents.value.filter((d) => d.id !== documentId);
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
    selectedPortraitProfile.value = await apiClient.profileDocument(doc.id);
    activePage.value = "portrait";
  });
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
      taskWorkflow.value = await apiClient.getTaskWorkflow(relatedTask.id);
      selectedPortraitProfile.value = taskWorkflow.value.document_profile ?? profile;
      profileScanMessage.value = formatProfileScanMessage(selectedPortraitProfile.value);
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
    await apiClient.analyzeImpact(taskWorkflow.value!.task.id);
    taskWorkflow.value = await apiClient.getTaskWorkflow(taskWorkflow.value!.task.id);
  });
}

async function generateTicket(): Promise<void> {
  if (!taskWorkflow.value) return;
  await withBusy(async () => {
    await apiClient.generateTicket(taskWorkflow.value!.task.id);
    taskWorkflow.value = await apiClient.getTaskWorkflow(taskWorkflow.value!.task.id);
  });
}
</script>
