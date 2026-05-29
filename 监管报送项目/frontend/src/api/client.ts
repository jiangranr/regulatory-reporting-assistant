import type {
  CatalogBatch,
  Concept,
  ConceptMatchHit,
  DocumentTaskProfile,
  ExtractionResult,
  ImpactReviewContent,
  ImpactReviewResponse,
  InstructionChangeAnalysis,
  RawDocumentText,
  RegDocument,
  RegTask,
  RuleCard,
  TaskWorkflow,
  TicketPlanResponse,
  ImpactItem,
  TripletUploadResponse,
} from "@/types/api";

export interface ApiClient {
  listDocuments(): Promise<RegDocument[]>;
  uploadDocument(file: File): Promise<RegDocument>;
  deleteDocument(documentId: number): Promise<{ document_id: number; deleted: Record<string, number> }>;
  getDocumentRawText(documentId: number): Promise<RawDocumentText>;
  uploadReportingPair(templateFile: File, instructionFile: File): Promise<RegDocument>;
  uploadReportingTriplet(
    objectCode: string,
    templateFile?: File | null,
    instructionFile?: File | null,
    revisionTableFile?: File | null,
  ): Promise<TripletUploadResponse>;
  listTasks(): Promise<RegTask[]>;
  createTaskFromDocument(documentId: number): Promise<RegTask>;
  getTaskWorkflow(taskId: number): Promise<TaskWorkflow>;
  getImpactReview(taskId: number): Promise<ImpactReviewResponse>;
  saveImpactReview(taskId: number, review: ImpactReviewContent): Promise<{ ok: true; updated_at: string }>;
  confirmImpactReview(taskId: number, review?: ImpactReviewContent): Promise<TicketPlanResponse>;
  resetImpactReview(taskId: number): Promise<ImpactReviewResponse>;
  profileDocument(documentId: number): Promise<DocumentTaskProfile>;
  getDocumentProfile(documentId: number): Promise<DocumentTaskProfile | null>;
  analyzeInstructionChanges(documentId: number, objectCode?: string): Promise<InstructionChangeAnalysis>;
  analyzeImpact(taskId: number): Promise<ImpactItem[]>;
  generateTicket(taskId: number): Promise<TicketPlanResponse>;
  listRuleCards(params?: {
    reporting_object_code?: string;
    reporting_item_code?: string;
    card_level?: string;
    status?: string;
  }): Promise<RuleCard[]>;
  reviewRuleCard(cardId: number, action: "ACCEPT" | "REJECT" | "HOLD", reviewer?: string): Promise<RuleCard>;
  listConcepts(params?: {
    concept_type?: string;
    reporting_system_scope?: string;
    keyword?: string;
    status?: string;
  }): Promise<Concept[]>;
  reviewConcept(conceptId: number, action: "ACCEPT" | "REJECT" | "HOLD", reviewer?: string): Promise<Concept>;
  matchConcepts(text: string, topK?: number): Promise<ConceptMatchHit[]>;
  triggerManualExtraction(documentId: number): Promise<ExtractionResult>;
  uploadCatalogZip(file: File, sourceRef?: string, objectCodes?: string): Promise<CatalogBatch>;
  getCatalogBatch(batchId: number): Promise<CatalogBatch>;
  listCatalogBatches(): Promise<CatalogBatch[]>;
}

export function createApiClient(baseUrl = "/api", fetcher: typeof fetch = fetch): ApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, init);
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  return {
    listDocuments: () => request<RegDocument[]>("/documents"),
    deleteDocument: (documentId) =>
      request<{ document_id: number; deleted: Record<string, number> }>(
        `/documents/${documentId}`,
        { method: "DELETE" },
      ),
    getDocumentRawText: (documentId) =>
      request<RawDocumentText>(`/documents/${documentId}/raw-text`),
    uploadDocument: (file) => {
      const form = new FormData();
      form.append("file", file);
      return request<RegDocument>("/documents/upload", { method: "POST", body: form });
    },
    uploadReportingPair: (templateFile, instructionFile) => {
      const form = new FormData();
      form.append("template_file", templateFile);
      form.append("instruction_file", instructionFile);
      return request<RegDocument>("/documents/upload-reporting-pair", { method: "POST", body: form });
    },
    uploadReportingTriplet: (objectCode, templateFile, instructionFile, revisionTableFile) => {
      const form = new FormData();
      if (templateFile) form.append("template_file", templateFile);
      if (instructionFile) form.append("instruction_file", instructionFile);
      if (revisionTableFile) form.append("revision_table_file", revisionTableFile);
      return request<TripletUploadResponse>(
        `/documents/upload-reporting-triplet?object_code=${encodeURIComponent(objectCode)}`,
        { method: "POST", body: form },
      );
    },
    listTasks: () => request<RegTask[]>("/tasks"),
    createTaskFromDocument: (documentId) =>
      request<RegTask>(`/tasks/from-document/${documentId}`, { method: "POST" }),
    getTaskWorkflow: (taskId) => request<TaskWorkflow>(`/tasks/${taskId}/workflow`),
    getImpactReview: (taskId) => request<ImpactReviewResponse>(`/tasks/${taskId}/impact-review`),
    saveImpactReview: (taskId, review) =>
      request<{ ok: true; updated_at: string }>(`/tasks/${taskId}/impact-review`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review }),
      }),
    confirmImpactReview: (taskId, review) =>
      request<TicketPlanResponse>(`/tasks/${taskId}/impact-review/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(review ? { review } : {}),
      }),
    resetImpactReview: (taskId) =>
      request<ImpactReviewResponse>(`/tasks/${taskId}/impact-review/reset`, { method: "POST" }),
    profileDocument: (documentId) =>
      request<DocumentTaskProfile>(`/documents/${documentId}/profile`, { method: "POST" }),
    getDocumentProfile: (documentId) =>
      request<DocumentTaskProfile | null>(`/documents/${documentId}/profile`),
    analyzeInstructionChanges: (documentId, objectCode = "G31") =>
      request<InstructionChangeAnalysis>(
        `/documents/${documentId}/analyze-instruction-changes?object_code=${objectCode}`,
        { method: "POST" },
      ),
    analyzeImpact: (taskId) =>
      request<{ task_id: number; impacts: ImpactItem[] }>(`/tasks/${taskId}/analyze-impact`, { method: "POST" })
        .then((r) => r.impacts),
    generateTicket: (taskId) =>
      request<TicketPlanResponse>(`/tasks/${taskId}/generate-ticket`, { method: "POST" }),
    listRuleCards: (params) => {
      const query = new URLSearchParams();
      if (params?.reporting_object_code) query.set("reporting_object_code", params.reporting_object_code);
      if (params?.reporting_item_code) query.set("reporting_item_code", params.reporting_item_code);
      if (params?.card_level) query.set("card_level", params.card_level);
      if (params?.status) query.set("status", params.status);
      const qs = query.toString();
      return request<RuleCard[]>(`/rule-cards${qs ? `?${qs}` : ""}`);
    },
    reviewRuleCard: (cardId, action, reviewer = "demo_user") =>
      request<RuleCard>(`/rule-cards/${cardId}/review`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, reviewer }),
      }),
    listConcepts: (params) => {
      const query = new URLSearchParams();
      if (params?.concept_type) query.set("concept_type", params.concept_type);
      if (params?.reporting_system_scope) query.set("reporting_system_scope", params.reporting_system_scope);
      if (params?.keyword) query.set("keyword", params.keyword);
      if (params?.status) query.set("status", params.status);
      const qs = query.toString();
      return request<Concept[]>(`/concepts${qs ? `?${qs}` : ""}`);
    },
    reviewConcept: (conceptId, action, reviewer = "demo_user") =>
      request<Concept>(`/concepts/${conceptId}/review`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, reviewer }),
      }),
    matchConcepts: (text, topK = 20) =>
      request<{ hits: ConceptMatchHit[] }>("/concepts/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, top_k: topK }),
      }).then((r) => r.hits),
    triggerManualExtraction: (documentId) =>
      request<ExtractionResult>("/extraction-jobs/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId }),
      }),
    uploadCatalogZip: (file, sourceRef, objectCodes) => {
      const form = new FormData();
      form.append("file", file);
      if (sourceRef) form.append("source_document_ref", sourceRef);
      if (objectCodes) form.append("object_codes", objectCodes);
      return request<CatalogBatch>("/catalog/upload-zip", { method: "POST", body: form });
    },
    getCatalogBatch: (batchId) => request<CatalogBatch>(`/catalog/batches/${batchId}`),
    listCatalogBatches: () => request<CatalogBatch[]>("/catalog/batches"),
  };
}

export const apiClient = createApiClient();
