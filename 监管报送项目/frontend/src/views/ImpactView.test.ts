import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import ImpactView from "./ImpactView.vue";
import type { TaskWorkflow } from "@/types/api";

vi.mock("@/api/client", () => ({
  apiClient: {
    listRuleCards: vi.fn(async () => []),
    matchConcepts: vi.fn(async () => []),
  },
}));

const workflow: TaskWorkflow = {
  task: {
    id: 1,
    document_id: 1,
    title: "G24 口径调整",
    status: "IMPACT_ANALYZED",
    risk_level: "HIGH",
    created_at: "2026-05-27T00:00:00Z",
    updated_at: "2026-05-27T00:00:00Z",
  },
  document: {
    id: 1,
    filename: "notice.txt",
    content_type: "text/plain",
    storage_path: "/tmp/notice.txt",
    title: "G24 填报说明调整",
    text_excerpt: "G24 同业融入口径调整",
    parsed_text: "G24 同业融入口径调整",
    status: "PARSED",
    parse_status: "PARSED",
    parser: "text",
    char_count: 12,
    paragraph_count: 1,
    table_count: 0,
    parse_quality: "GOOD",
    parse_error_message: "",
    created_at: "2026-05-27T00:00:00Z",
  },
  document_profile: null,
  steps: [],
  clauses: [],
  semantic_items: [],
  field_mappings: [
    {
      object_code: "G24",
      item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
      regulatory_term: "最大百家同业融入",
      field_code: "rpt_g24.interbank_borrowing_bal_top100",
      field_name: "G24 同业融入余额",
      column_name: "interbank_borrowing_bal_top100",
      table_name: "rpt_g24",
      system_name: "1104 报送集市",
      system_code: "RPT_1104",
      lineage_role: "REPORT_FIELD",
      mapping_status: "CONFIRMED",
    },
    {
      object_code: "G24",
      item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
      regulatory_term: "最大百家同业融入",
      field_code: "interbank_deal.balance",
      field_name: "同业交易余额",
      column_name: "balance",
      table_name: "interbank_deal",
      system_name: "同业业务系统",
      system_code: "INTERBANK_CORE",
      lineage_role: "SOURCE_FIELD",
      mapping_status: "CONFIRMED",
    },
    {
      object_code: "G24",
      item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
      regulatory_term: "最大百家同业融入",
      field_code: "counterparty.institution_type",
      field_name: "交易对手机构类型",
      column_name: "institution_type",
      table_name: "counterparty",
      system_name: "交易对手主数据",
      system_code: "COUNTERPARTY_MDM",
      lineage_role: "FILTER_FIELD",
      mapping_status: "PENDING",
    },
  ],
  reporting_candidates: [],
  lineage_candidates: [],
  impact_items: [
    {
      reporting_item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
      impact_type: "INDICATOR_SCOPE",
      impacted_reporting_field: "rpt_g24.interbank_borrowing_bal_top100",
      impacted_source_fields: [
        "rpt_g24.interbank_borrowing_bal_top100",
        "interbank_deal.balance",
        "counterparty.institution_type",
      ],
      impacted_lineage_roles: ["REPORT_FIELD", "SOURCE_FIELD", "FILTER_FIELD"],
      impact_reason: "同业融入余额口径调整",
      recommended_action: "确认口径并调整加工逻辑",
      confidence_level: "HIGH",
      risk_level: "HIGH",
    },
  ],
  rule_cards: [],
  ticket_drafts: [],
};

describe("ImpactView", () => {
  it("shows concrete systems and fields in the impact radius hover panel", () => {
    const wrapper = mount(ImpactView, {
      props: {
        workflow,
        busy: false,
      },
    });

    const trigger = wrapper.find("[data-test='impact-radius-trigger']");
    const panel = wrapper.find("[data-test='impact-radius-panel']");

    expect(trigger.exists()).toBe(true);
    expect(trigger.attributes("tabindex")).toBe("0");
    expect(trigger.attributes("aria-label")).toContain("查看影响半径明细");
    expect(panel.exists()).toBe(true);
    expect(panel.text()).toContain("系统与字段范围");
    expect(panel.text()).toContain("1104 报送集市");
    expect(panel.text()).toContain("同业业务系统");
    expect(panel.text()).toContain("交易对手主数据");
    expect(panel.text()).toContain("rpt_g24.interbank_borrowing_bal_top100");
    expect(panel.text()).toContain("interbank_deal.balance");
    expect(panel.text()).toContain("counterparty.institution_type");
  });
});
