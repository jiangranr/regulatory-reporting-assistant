import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import DocumentsView from "@/views/DocumentsView.vue";
import type { DocumentTaskProfile, RegDocument, TaskWorkflow, TripletUploadResponse } from "@/types/api";

const apiMock = vi.hoisted(() => ({
  listDocuments: vi.fn(),
  listTasks: vi.fn(),
  createTaskFromDocument: vi.fn(),
  getTaskWorkflow: vi.fn(),
  getDocumentProfile: vi.fn(),
  profileDocument: vi.fn(),
  analyzeImpact: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiClient: apiMock,
}));

import App from "../App.vue";

describe("App triplet workflow refresh", () => {
  it("keeps triplet scan item count visible on the portrait page after profiling", async () => {
    const document = makeDocument(4, "triplet");
    const profile = makeProfile(4, "修正久期");

    apiMock.listDocuments.mockResolvedValue([]);
    apiMock.listTasks.mockResolvedValue([]);
    apiMock.getDocumentProfile.mockResolvedValue(null);
    apiMock.profileDocument.mockResolvedValue(profile);

    const wrapper = mount(App);
    await flushPromises();

    await clickButton(wrapper, "上传发文");
    wrapper.findComponent(DocumentsView).vm.$emit("triplet-done", makeTripletResponse(document, 15));
    await flushPromises();

    expect(wrapper.text()).toContain("业务变更信号：1 个");
    expect(wrapper.text()).toContain("影响指标格：15 个");
  });

  it("shows the newly parsed document signals in lineage after triplet upload", async () => {
    const oldDocument = makeDocument(1, "old");
    const newDocument = makeDocument(2, "new");
    const oldProfile = makeProfile(1, "旧文档字段 × A·穿透前·期末余额");
    const newProfile = makeProfile(2, "新文档字段 × C·修正久期");

    apiMock.listDocuments.mockResolvedValue([oldDocument]);
    apiMock.listTasks.mockResolvedValue([
      {
        id: 11,
        document_id: oldDocument.id,
        title: "旧文档任务",
        status: "IMPACT_ANALYZED",
        risk_level: "HIGH",
        created_at: oldDocument.created_at,
        updated_at: oldDocument.created_at,
      },
    ]);
    apiMock.getDocumentProfile.mockResolvedValue(oldProfile);
    apiMock.getTaskWorkflow.mockResolvedValue(makeWorkflow(oldDocument, oldProfile));
    apiMock.profileDocument.mockResolvedValue(newProfile);

    const wrapper = mount(App);
    await flushPromises();

    await clickButton(wrapper, "上传发文");
    wrapper.findComponent(DocumentsView).vm.$emit("triplet-done", makeTripletResponse(newDocument));
    await flushPromises();

    await clickButton(wrapper, "字段定位");
    await flushPromises();

    expect(wrapper.text()).toContain("新文档字段 × C·修正久期");
    expect(wrapper.text()).not.toContain("旧文档字段 × A·穿透前·期末余额");
  });

  it("starts impact analysis from lineage for the current parsed document", async () => {
    const document = makeDocument(3, "current");
    const profile = makeProfile(3, "当前文档字段 × C·修正久期");
    const task = {
      id: 33,
      document_id: document.id,
      title: "当前文档任务",
      status: "CREATED",
      risk_level: "HIGH",
      created_at: document.created_at,
      updated_at: document.created_at,
    } as const;

    apiMock.listDocuments.mockResolvedValue([]);
    apiMock.listTasks.mockResolvedValue([]);
    apiMock.getDocumentProfile.mockResolvedValue(null);
    apiMock.profileDocument.mockResolvedValue(profile);
    apiMock.createTaskFromDocument.mockResolvedValue(task);
    apiMock.analyzeImpact.mockResolvedValue([]);
    apiMock.getTaskWorkflow.mockResolvedValue(makeWorkflow(document, profile));

    const wrapper = mount(App);
    await flushPromises();

    await clickButton(wrapper, "上传发文");
    wrapper.findComponent(DocumentsView).vm.$emit("triplet-done", makeTripletResponse(document));
    await flushPromises();

    await clickButton(wrapper, "字段定位");
    await flushPromises();
    await clickButton(wrapper, "开始影响分析");
    await flushPromises();

    expect(apiMock.createTaskFromDocument).toHaveBeenCalledWith(document.id);
    expect(apiMock.analyzeImpact).toHaveBeenCalledWith(task.id);
    expect(apiMock.getTaskWorkflow).toHaveBeenCalledWith(task.id);
  });
});

function makeDocument(id: number, title: string): RegDocument {
  return {
    id,
    filename: `${title}.xlsx`,
    content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    storage_path: `/tmp/${title}.xlsx`,
    title,
    text_excerpt: "",
    parsed_text: "",
    status: "PARSED",
    parse_status: "PARSED",
    parser: "xlsx",
    char_count: 0,
    paragraph_count: 0,
    table_count: 1,
    parse_quality: "HIGH",
    parse_error_message: "",
    created_at: "2026-05-26T00:00:00Z",
  };
}

function makeProfile(documentId: number, indicatorHint: string): DocumentTaskProfile {
  return {
    id: documentId,
    document_id: documentId,
    document_type: "G31修订表",
    affected_table_codes: ["G31"],
    change_signals: [
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: indicatorHint,
        change_type: "MODIFY",
        evidence_text: indicatorHint,
        confidence: 0.9,
        evidence_verified: true,
        matched_item_code: `G31.PART_I.${documentId}_0.C_修正久期`,
      },
    ],
    in_scope_tables: ["G31"],
    out_of_scope_tables: [],
    suggested_route: "FULL_ANALYSIS",
    should_create_task: true,
    confidence_score: 0.9,
    reason: "",
    evidence_text: indicatorHint,
    llm_model: "test",
    review_status: "PENDING",
    raw_response: "",
    created_at: "2026-05-26T00:00:00Z",
  };
}

function makeWorkflow(document: RegDocument, profile: DocumentTaskProfile): TaskWorkflow {
  return {
    task: {
      id: document.id * 10,
      document_id: document.id,
      title: `${document.title}任务`,
      status: "IMPACT_ANALYZED",
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

function makeTripletResponse(document: RegDocument, scanCount = 0): TripletUploadResponse {
  return {
    document,
    template_parsed: true,
    instruction_parsed: true,
    revision_table_parsed: true,
    revision_entry_count: 1,
    excel_diff_count: 1,
    scan_results: Array.from({ length: scanCount }, (_, index) => ({
      item_code: `G31.PART_I.${index}_0.C_修正久期`,
      row_label: "第 I 部分：底层资产投资情况（列项目）",
      column_label: "C.修正久期",
      old_status: "",
      new_status: "MODIFIED",
      source: "INSTRUCTION",
      confidence: 0.8,
      evidence: "填报说明命中",
      overridden_sources: [],
    })),
    scan_summary: "",
    excel_diff: [],
    revision_entries: [],
    revision_lane: [],
    excel_lane: [],
    instruction_lane: [],
    revision_candidates: [],
    error_messages: [],
  };
}

async function clickButton(wrapper: ReturnType<typeof mount>, label: string): Promise<void> {
  const button = wrapper.findAll("button").find((item) => item.text().includes(label));
  expect(button, `button ${label} should exist`).toBeTruthy();
  await button!.trigger("click");
}
