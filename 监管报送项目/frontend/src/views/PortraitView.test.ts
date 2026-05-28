import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import PortraitView from "./PortraitView.vue";
import type { DocumentTaskProfile, RegDocument } from "@/types/api";

const { getDocumentRawText } = vi.hoisted(() => ({
  getDocumentRawText: vi.fn(async () => ({
    document_id: 7,
    title: "监管发文",
    filename: "notice.txt",
    source: "revision_table",
    text: "修订对照表解析明细\n底层资产合计 × E_穿透层级\n251版新增穿透层级",
  })),
}));

vi.mock("@/api/client", () => ({
  apiClient: {
    getDocumentRawText,
  },
}));

const document: RegDocument = {
  id: 7,
  filename: "notice.txt",
  content_type: "text/plain",
  storage_path: "/tmp/notice.txt",
  title: "监管发文",
  text_excerpt: "G31 指标口径调整",
  parsed_text: "G31 指标口径调整",
  status: "PARSED",
  parse_status: "PARSED",
  parser: "text",
  char_count: 12,
  paragraph_count: 1,
  table_count: 0,
  parse_quality: "GOOD",
  parse_error_message: "",
  created_at: "2026-05-21T00:00:00Z",
};

const profile: DocumentTaskProfile = {
  id: 11,
  document_id: 7,
  document_type: "",
  affected_table_codes: ["G31"],
  change_signals: [],
  in_scope_tables: ["G31"],
  out_of_scope_tables: [],
  suggested_route: "FULL_ANALYSIS",
  should_create_task: true,
  confidence_score: 0.9,
  reason: "已生成画像",
  evidence_text: "",
  llm_model: "fake-model",
  review_status: "PENDING",
  raw_response: "",
  created_at: "2026-05-21T00:00:00Z",
};

describe("PortraitView", () => {
  it("shows business signal count separately from impacted reporting item count", () => {
    const profileWithSignals: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "修正久期",
          change_type: "MODIFY",
          evidence_text: "修正久期定义调整",
          confidence: 0.9,
          evidence_verified: true,
        },
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "填报机构范围",
          change_type: "SCOPE_ADJUST",
          evidence_text: "填报机构范围调整",
          confidence: 0.88,
          evidence_verified: true,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithSignals,
        impactItemCount: 15,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    expect(wrapper.text()).toContain("业务变更信号：2 个");
    expect(wrapper.text()).toContain("影响指标格：15 个");
  });

  it("shows revision-tracked inserted formula evidence as scope adjustment", () => {
    const profileWithInsertedInstruction: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "C.修正久期填报定义/公式",
          change_type: "INSTRUCTION_ADJUST",
          evidence_text: "- [新增 | 陈施霖 | 2024-12-20] MD=-(dP/P)/dy=D/(1+y/k)",
          confidence: 0.95,
          evidence_verified: true,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithInsertedInstruction,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    expect(wrapper.find("tbody").text()).toContain("口径调整");
    expect(wrapper.find("tbody").text()).not.toContain("说明调整");
  });

  it("keeps rescan clickable while non-profile background work is busy", async () => {
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profile,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: true,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const rescan = wrapper.findAll("button").find((button) => button.text().includes("重新扫描"));
    expect(rescan?.attributes("disabled")).toBeUndefined();

    await rescan!.trigger("click");

    expect(wrapper.emitted("profile-document")).toEqual([[document.id]]);
  });

  it("disables rescan only while the profile scan itself is running", () => {
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profile,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: true,
        profileScanMessage: "",
      },
    });

    const scanButton = wrapper.findAll("button").find((button) => button.text().includes("扫描中"));

    expect(scanButton?.attributes("disabled")).toBeDefined();
  });

  it("opens a raw text dialog from the parsed document text", async () => {
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profile,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const rawTextButton = wrapper.findAll("button").find((button) => button.text().includes("查看原文"));
    await rawTextButton!.trigger("click");
    await flushPromises();

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("解析文本");
    expect(getDocumentRawText).toHaveBeenCalledWith(document.id);
    expect(wrapper.text()).toContain("修订对照表解析明细");
    expect(wrapper.text()).toContain("底层资产合计 × E_穿透层级");

    await wrapper.find('[aria-label="关闭原文弹窗"]').trigger("click");

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
  });
});
