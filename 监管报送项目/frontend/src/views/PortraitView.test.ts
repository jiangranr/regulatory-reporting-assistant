import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import PortraitView from "./PortraitView.vue";
import type { DocumentTaskProfile, RegDocument } from "@/types/api";

const { getDocumentRawText, reviewDocumentSignal } = vi.hoisted(() => ({
  getDocumentRawText: vi.fn(async () => ({
    document_id: 7,
    title: "监管发文",
    filename: "notice.txt",
    source: "revision_table",
    text: "修订对照表解析明细\n底层资产合计 × E_穿透层级\n251版新增穿透层级",
  })),
  reviewDocumentSignal: vi.fn(async () => ({
    signal: {
      table_code: "G31",
      section_hint: "PART_I",
      indicator_hint: "绿色债券投资余额删除",
      change_type: "DELETE",
      evidence_text: "本期删除绿色债券投资余额字段。",
      confidence: 0.3,
      evidence_verified: false,
      source_type: "LLM",
      grounding_status: "UNVERIFIED",
      grounding_coverage: 0.25,
      human_review_status: "ACCEPTED",
    },
    metrics: {
      total_signals: 3,
      ai_signals: 2,
      rule_based_signals: 1,
      verified_signals: 1,
      partial_signals: 0,
      unverified_signals: 1,
      isolated_signals: 0,
      grounding_rate: 0.5,
      suspected_hallucination_rate: 0.5,
      isolation_rate: 0.5,
      pending_review_signals: 0,
      accepted_signals: 1,
      rejected_signals: 0,
      corrected_signals: 0,
      human_acceptance_rate: 1,
    },
  })),
}));

vi.mock("@/api/client", () => ({
  apiClient: {
    getDocumentRawText,
    reviewDocumentSignal,
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

  it("treats inserted financial-institution qualifier as scope adjustment", () => {
    const profileWithInsertedQualifier: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          business_signal_id: "G01::11.a.1",
          item_codes: ["11.a.1"],
          table_code: "G01",
          section_hint: "填报说明定义",
          indicator_hint: "11.a.1通过第三方互联网平台吸收的个人定期存款",
          change_type: "ADD",
          evidence_text: [
            "[新增 | 陈施霖 | 2024-12-23] 金融机构",
            "[11.a.1 通过第三方互联网平台吸收的个人定期存款]指项目 11.a 中，金融机构吸收的个人定期存款。",
          ].join("；"),
          change_summary: "口径调整：11.a.1 统计主体明确为金融机构，影响个人定期存款填报口径。",
          changed_dimension: "统计主体",
          changed_to: "金融机构",
          confidence: 0.86,
          evidence_verified: true,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithInsertedQualifier,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    expect(wrapper.find("tbody").text()).toContain("口径调整");
    expect(wrapper.find("tbody").text()).toContain("统计主体明确为金融机构");
    expect(wrapper.find("tbody").text()).toContain("金融机构");
  });

  it("shows full evidence text without ellipsis in the signal table", () => {
    const longEvidence = [
      "3．填报机构：第IV部分：政策性银行（含开发银行）、大型商业银行（含邮储银行）、",
      "政策性银行、国家开发银行、国有商业银行、股份制商业银行、城市商业银行、",
      "民营银行、农村商业银行、外资法人银行以及其他纳入本表统计范围的金融机构。",
    ].join("");
    const profileWithLongEvidence: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G01",
          section_hint: "填报说明",
          indicator_hint: "填报机构范围",
          change_type: "SCOPE_ADJUST",
          evidence_text: longEvidence,
          confidence: 0.86,
          evidence_verified: true,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithLongEvidence,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const evidence = wrapper.find(".evidence-cell .evidence-plain");

    expect(evidence.text()).toContain("民营银行");
    expect(evidence.text()).toContain("其他纳入本表统计范围的金融机构");
    expect(evidence.text()).not.toContain("...");
    expect(evidence.attributes("title")).toContain("其他纳入本表统计范围的金融机构");
    expect(evidence.attributes("title")).not.toContain("...");
  });

  it("merges duplicate LLM and rule signals into one business change with source details", async () => {
    const profileWithDuplicateSignals: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          business_signal_id: "G01_IV::11.a.1",
          item_codes: ["11.a.1"],
          table_code: "G01_IV",
          section_hint: "填报说明定义",
          indicator_hint: "11.a.1通过第三方互联网平台吸收的个人定期存款",
          change_type: "SCOPE_ADJUST",
          evidence_text: [
            "[新增 | 陈施霖 | 2024-12-23] 金融机构",
            "[11.a.1 通过第三方互联网平台吸收的个人定期存款]指项目 11.a 中，金融机构吸收的个人定期存款。",
          ].join("；"),
          change_summary: "口径调整：11.a.1 统计主体明确为金融机构，影响个人定期存款填报口径。",
          confidence: 0.86,
          evidence_verified: true,
          source_type: "RULE_BASED",
          grounding_status: "RULE_BASED",
          grounding_coverage: 1,
          candidate_sources: [
            {
              table_code: "G01_IV",
              section_hint: "第 IV 部分",
              indicator_hint: "11.a.1通过第三方互联网平台吸收的个人定期存款",
              change_type: "ADD",
              evidence_text: "金融机构 [11.a.1 通过第三方互联网平台吸收的个人定期存款]指项目 11.a 中，金融机构吸收的个人定期存款。",
              confidence: 0.31,
              evidence_verified: false,
              source_type: "LLM",
              grounding_status: "UNVERIFIED",
              grounding_coverage: 0.31,
            },
            {
              table_code: "G01_IV",
              section_hint: "填报说明定义",
              indicator_hint: "11.a.1通过第三方互联网平台吸收的个人定期存款",
              change_type: "SCOPE_ADJUST",
              evidence_text: "[新增 | 陈施霖 | 2024-12-23] 金融机构",
              confidence: 0.86,
              evidence_verified: true,
              source_type: "RULE_BASED",
              grounding_status: "RULE_BASED",
              grounding_coverage: 1,
            },
          ],
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithDuplicateSignals,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const rows = wrapper.findAll("tbody tr");
    expect(rows).toHaveLength(1);
    expect(wrapper.text()).toContain("业务变更信号：1 个");
    expect(rows[0].text()).toContain("统计主体明确为金融机构");
    expect(rows[0].text()).not.toContain("LLM 草稿");

    await rows[0].find("button").trigger("click");

    const detail = wrapper.get(".signal-detail-panel");
    expect(detail.text()).toContain("来源明细");
    expect(detail.text()).toContain("LLM 草稿");
    expect(detail.text()).toContain("规则结果");
    expect(detail.text()).toContain("原文依据");
  });

  it("shows tracked additions and deletions in signal details", async () => {
    const profileWithTrackedDefinitionChange: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          business_signal_id: "G01_IV::11.1",
          item_codes: ["11.1"],
          table_code: "G01_IV",
          section_hint: "第 IV 部分",
          indicator_hint: "11.1通过互联网吸收的个人定期存款",
          change_type: "SCOPE_ADJUST",
          evidence_text: [
            "[新增 | 陈施霖 | 2024-12-23] 金融机构",
            "[新增 | 陈施霖 | 2024-12-23] 互联网",
            "[删除 | 陈施霖 | 2024-12-23] 银行",
            "[删除 | 陈施霖 | 2024-12-23] 开卡",
            "[删除 | 陈施霖 | 2024-12-23] 远程",
            "[11.1 通过互联网吸收的个人定期存款]指项目 11 中，金融机构个人客户在不通过银行网点、柜面、开卡机等实体渠道，而直接通过手机银行、网上银行、第三方互联网平台等互联网渠道开立 II 类账户后吸收的定期存款。",
          ].join("；"),
          change_summary: "11.1 定义由银行远程开卡场景调整为金融机构互联网吸储。",
          confidence: 0.86,
          evidence_verified: true,
          source_type: "RULE_BASED",
          grounding_status: "RULE_BASED",
          grounding_coverage: 1,
          revision_spans: [
            { type: "TEXT", text: "[11.1 通过", author: "", date: "", action: "" },
            { type: "INSERT", text: "互联网", author: "陈施霖", date: "2024-12-23T08:55:00Z", action: "新增" },
            { type: "TEXT", text: "吸收的个人定期存款]指项目 11 中，", author: "", date: "", action: "" },
            { type: "INSERT", text: "金融机构", author: "陈施霖", date: "2024-12-23T08:55:00Z", action: "新增" },
            { type: "TEXT", text: "个人客户在不通过", author: "", date: "", action: "" },
            { type: "DELETE", text: "银行", author: "陈施霖", date: "2024-12-23T08:55:00Z", action: "删除" },
            { type: "TEXT", text: "网点、柜面、", author: "", date: "", action: "" },
            { type: "DELETE", text: "开卡", author: "陈施霖", date: "2024-12-23T08:55:00Z", action: "删除" },
            { type: "TEXT", text: "机等实体渠道，而直接通过手机银行、网上银行、第三方互联网平台等互联网渠道为客户", author: "", date: "", action: "" },
            { type: "DELETE", text: "远程", author: "陈施霖", date: "2024-12-23T08:55:00Z", action: "删除" },
            { type: "TEXT", text: "开立 II 类账户后吸收的定期存款。", author: "", date: "", action: "" },
          ],
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithTrackedDefinitionChange,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    await wrapper.get(".detail-btn").trigger("click");

    const detail = wrapper.get(".signal-detail-panel");
    expect(detail.text()).not.toContain("Word 修订动作");
    expect(detail.find(".source-evidence .source-revision-add").exists()).toBe(true);
    expect(detail.findAll(".source-evidence .source-revision-add").map((item) => item.text())).toEqual([
      "互联网",
      "金融机构",
    ]);
    expect(detail.findAll(".source-evidence .source-revision-delete").map((item) => item.text())).toEqual([
      "银行",
      "开卡",
      "远程",
    ]);
    expect(detail.findAll(".source-evidence .source-revision-delete")[0].attributes("title")).toContain("删除 · 陈施霖 · 2024-12-23");
  });

  it("does not expose internal revision span JSON in detail evidence", async () => {
    const profileWithJsonEvidence: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G01_IV",
          section_hint: "第 IV 部分",
          indicator_hint: "11.a.2通过第三方互联网平台吸收的个人活期存款",
          change_type: "ADD",
          evidence_text: [
            '{"type": "TEXT", "text": "[11.a.2 通过第三方互联网平台", "author": "", "date": "", "action": ""}',
            '{"type": "INSERT", "text": "吸收的个人活期存款", "author": "周世杰", "date": "2024-11-21T09:00:00Z", "action": "新增"}',
            '{"type": "TEXT", "text": "]指项目 11.a 中，", "author": "", "date": "", "action": ""}',
            '{"type": "INSERT", "text": "金融机构", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "新增"}',
            '{"type": "TEXT", "text": "吸收的个人活期存款。", "author": "", "date": "", "action": ""}',
            '{"type": "DELETE", "text": "银行", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "删除"}',
          ].join("\n"),
          confidence: 0.98,
          evidence_verified: true,
          source_type: "LLM",
          grounding_status: "VERIFIED",
          grounding_coverage: 1,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithJsonEvidence,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    await wrapper.get(".detail-btn").trigger("click");

    const detail = wrapper.get(".signal-detail-panel");
    expect(detail.text()).not.toContain('{"type"');
    expect(detail.findAll(".source-evidence .source-revision-add").map((item) => item.text())).toEqual([
      "吸收的个人活期存款",
      "金融机构",
    ]);
    expect(detail.findAll(".source-evidence .source-revision-delete").map((item) => item.text())).toEqual([
      "银行",
    ]);
    expect(detail.findAll(".source-evidence .source-revision-delete")[0].attributes("title")).toContain("删除 · 陈施霖 · 2024-12-23");
  });

  it("deduplicates G01 LLM drafts and rule definition signals by item code", () => {
    const profileWithG01BusinessSignals: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          business_signal_id: "G01_IV::11.a.1",
          item_codes: ["11.a.1"],
          table_code: "G01_IV",
          section_hint: "填报说明定义",
          indicator_hint: "11.a.1通过第三方互联网平台吸收的个人定期存款",
          change_type: "SCOPE_ADJUST",
          evidence_text: "[11.a.1 通过第三方互联网平台吸收的个人定期存款]指项目 11.a 中，金融机构吸收的个人定期存款。",
          change_summary: "口径调整：11.a.1 统计主体明确为金融机构，影响个人定期存款填报口径。",
          confidence: 0.86,
          evidence_verified: true,
          source_type: "RULE_BASED",
          grounding_status: "RULE_BASED",
          grounding_coverage: 1,
        },
        {
          business_signal_id: "G01_IV::11.a.2",
          item_codes: ["11.a.2"],
          table_code: "G01_IV",
          section_hint: "填报说明定义",
          indicator_hint: "11.a.2通过第三方互联网平台吸收的个人活期存款",
          change_type: "SCOPE_ADJUST",
          evidence_text: "[11.a.2 通过第三方互联网平台吸收的个人活期存款]指项目 11.a 中，金融机构吸收的个人活期存款。",
          change_summary: "口径调整：11.a.2 统计主体明确为金融机构，影响个人活期存款填报口径。",
          confidence: 0.86,
          evidence_verified: true,
          source_type: "RULE_BASED",
          grounding_status: "RULE_BASED",
          grounding_coverage: 1,
          candidate_sources: [
            {
              table_code: "G01_IV",
              section_hint: "第 IV 部分",
              indicator_hint: "11.a.2 通过第三方互联网平台吸收的个人活期存款（B列 其中：储蓄存款）",
              change_type: "ADD",
              evidence_text: "11.a.2 通过第三方互联网平台吸收的个人活期存款，定义中出现金融机构。",
              confidence: 0.3,
              evidence_verified: false,
              source_type: "LLM",
              grounding_status: "UNVERIFIED",
              grounding_coverage: 0.2,
            },
            {
              table_code: "G01_IV",
              section_hint: "第 IV 部分",
              indicator_hint: "11.a.1/11.a.2 附注解释",
              change_type: "SCOPE_ADJUST",
              evidence_text: "11.a.1/11.a.2 附注解释的定义或计算公式发生调整。",
              confidence: 0.3,
              evidence_verified: false,
              source_type: "LLM",
              grounding_status: "UNVERIFIED",
              grounding_coverage: 0.04,
            },
          ],
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithG01BusinessSignals,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const rows = wrapper.findAll("tbody tr");
    const tableText = wrapper.find("tbody").text();

    expect(rows).toHaveLength(2);
    expect(tableText).toContain("11.a.1通过第三方互联网平台吸收的个人定期存款");
    expect(tableText).toContain("11.a.2通过第三方互联网平台吸收的个人活期存款");
    expect(tableText).not.toContain("11.a.1/11.a.2 附注解释");
    expect(tableText).not.toContain("定义或计算公式发生调整");
    expect(tableText).toContain("统计主体明确为金融机构");
  });

  it("uses backend-provided business summaries without front-end semantic rewriting", () => {
    const profileWithBackendSummaries: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "第二部分：一般说明",
          indicator_hint: "填报机构范围",
          change_type: "SCOPE_ADJUST",
          evidence_text: "[新增 | 陈施霖 | 2024-12-16] 直销银行、；3．填报机构：第IV部分：政策性银行、直销银行。",
          change_summary: "口径调整：填报机构范围补充直销银行，需按更新后的机构范围填报。",
          confidence: 0.86,
          evidence_verified: true,
        },
        {
          table_code: "G31",
          section_hint: "第 I 部分：底层资产投资情况",
          indicator_hint: "D列/ E列列位说明（因新增C列发生顺延）",
          change_type: "SCOPE_ADJUST",
          evidence_text: "[新增 | 陈施霖 | 2024-12-16] C.；D列/E列列位说明因新增C列发生顺延。",
          change_summary: "口径调整：因新增C列，D/E列列位说明发生顺延或调整。",
          confidence: 0.72,
          evidence_verified: true,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithBackendSummaries,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const tableText = wrapper.find("tbody").text();

    expect(tableText).toContain("填报机构范围补充");
    expect(tableText).toContain("直销银行");
    expect(tableText).toContain("因新增C列");
    expect(tableText).not.toContain("限定");
  });

  it("uses cleaned evidence text for verified evidence hover titles", () => {
    const rawEvidence = [
      "[删除 | 陈施霖 | 2024-12-03] 投资",
      "[新增 | 陈施霖 | 2024-11-22] [C.",
      "[新增 | 陈施霖 | 2024-11-22] 修正久期",
      "[新增 | 陈施霖 | 2024-12-20] MD=-(dP/P)/dy=D/(1+y/k)",
    ].join("；");
    const profileWithTrackedEvidence: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "C列 修正久期",
          change_type: "ADD",
          evidence_text: rawEvidence,
          confidence: 0.97,
          evidence_verified: true,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithTrackedEvidence,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const evidence = wrapper.get(".evidence-plain");
    expect(evidence.attributes("title")).toBe(evidence.text());
    expect(evidence.attributes("title")).not.toContain("[新增");
    expect(evidence.attributes("title")).not.toContain("[删除");
    expect(evidence.attributes("title")).not.toContain("投资");
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

  it("shows measurable grounding metrics and graded signal states", () => {
    const profileWithTrustSignals: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "绿色债券投资余额",
          change_type: "ADD",
          evidence_text: "本期新增绿色债券投资余额字段。",
          confidence: 0.9,
          evidence_verified: true,
          source_type: "LLM",
          grounding_status: "VERIFIED",
          grounding_coverage: 1,
        },
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "绿色债券投资余额删除",
          change_type: "DELETE",
          evidence_text: "本期删除绿色债券投资余额字段。",
          confidence: 0.3,
          evidence_verified: false,
          source_type: "LLM",
          grounding_status: "UNVERIFIED",
          grounding_coverage: 0.25,
        },
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "新增 C 列",
          change_type: "ADD",
          evidence_text: "Excel 差异：新增 C 列",
          confidence: 0.8,
          evidence_verified: true,
          source_type: "EXCEL_DIFF",
          grounding_status: "RULE_BASED",
          grounding_coverage: 1,
        },
      ],
    };

    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithTrustSignals,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    expect(wrapper.text()).toContain("AI 可信度检查");
    expect(wrapper.text()).toContain("原文锚定率");
    expect(wrapper.text()).toContain("50%");
    expect(wrapper.text()).toContain("已隔离");
    expect(wrapper.text()).toContain("1 条");
    expect(wrapper.text()).toContain("原文已锚定");
    expect(wrapper.text()).toContain("未验证·已隔离");
    expect(wrapper.find("tbody").text()).not.toContain("物理 Diff");
  });

  it("keeps unverified AI evidence visible in signal details for human review", async () => {
    const profileWithUnverifiedSignal: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "绿色债券投资余额删除",
          change_type: "DELETE",
          evidence_text: "本期删除绿色债券投资余额字段。",
          confidence: 0.3,
          evidence_verified: false,
          source_type: "LLM",
          grounding_status: "UNVERIFIED",
          grounding_coverage: 0.25,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithUnverifiedSignal,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    await wrapper.get(".detail-btn").trigger("click");

    const detail = wrapper.get(".signal-detail-panel");
    expect(detail.text()).toContain("未验证");
    expect(detail.text()).toContain("本期删除绿色债券投资余额字段。");
  });

  it("does not show a synthetic zero coverage for legacy verified signals", () => {
    const legacyProfile: DocumentTaskProfile = {
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
          grounding_coverage: 0,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: legacyProfile,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    expect(wrapper.find("tbody").text()).toContain("原文已锚定");
    expect(wrapper.find(".coverage-text").exists()).toBe(false);
  });

  it("allows a reviewer to accept an isolated signal", async () => {
    const profileWithIsolatedSignal: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "绿色债券投资余额删除",
          change_type: "DELETE",
          evidence_text: "本期删除绿色债券投资余额字段。",
          confidence: 0.3,
          evidence_verified: false,
          source_type: "LLM",
          grounding_status: "UNVERIFIED",
          grounding_coverage: 0.25,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithIsolatedSignal,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const accept = wrapper.findAll("button").find((button) => button.text() === "采纳");
    await accept!.trigger("click");
    await flushPromises();

    expect(reviewDocumentSignal).toHaveBeenCalledWith(document.id, 0, "ACCEPTED", "demo_user");
    expect(wrapper.text()).toContain("已人工采纳");
  });

  it("shows an error when reviewing an isolated signal fails", async () => {
    reviewDocumentSignal.mockRejectedValueOnce(new Error("backend unavailable"));
    const profileWithIsolatedSignal: DocumentTaskProfile = {
      ...profile,
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "绿色债券投资余额删除",
          change_type: "DELETE",
          evidence_text: "本期删除绿色债券投资余额字段。",
          confidence: 0.3,
          evidence_verified: false,
          source_type: "LLM",
          grounding_status: "UNVERIFIED",
          grounding_coverage: 0.25,
        },
      ],
    };
    const wrapper = mount(PortraitView, {
      props: {
        documents: [document],
        selectedDocumentId: document.id,
        selectedProfile: profileWithIsolatedSignal,
        instructionAnalysis: null,
        analysisBusy: false,
        workflow: null,
        busy: false,
        profileBusy: false,
        profileScanMessage: "",
      },
    });

    const reject = wrapper.findAll("button").find((button) => button.text() === "退回");
    await reject!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("复核操作失败，请稍后重试。");
  });
});
