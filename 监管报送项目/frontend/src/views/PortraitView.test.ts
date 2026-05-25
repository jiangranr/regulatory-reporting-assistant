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
