import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ReviewTicketView from "./ReviewTicketView.vue";
import type { TaskWorkflow, TicketDraft } from "@/types/api";

const baseTicket: TicketDraft = {
  id: 1,
  task_id: 1,
  title: "G31 口径调整处理",
  content: "旧版 Markdown 正文",
  parent_ticket_id: null,
  ticket_role: "PARENT",
  change_ticket_type: "REPORT_REVISION",
  action_ticket_type: "",
  severity_level: "L3",
  severity_score: 78,
  severity_signals: "",
  severity_forced_reason: "",
  severity_overridden_by: "",
  owner_role: "REPORTING_MGMT",
  executor_role: "",
  depends_on_lineage: false,
  business_signoff_required: false,
  closure_review_required: false,
  related_impact_codes: "",
  summary: "",
  responsible_system: "",
  affected_systems: "",
  affected_assets: "",
  must_do: "",
  must_confirm: "",
  output_artifacts: "",
  acceptance_criteria_structured: "",
  blockers: "",
  evidence_refs: "",
  historical_cases: "",
  quality_score: 0,
  quality_flags: "",
  status: "DRAFT",
  created_at: null,
};

function workflowWithTicket(ticket: Partial<TicketDraft>): TaskWorkflow {
  const parentTicket = { ...baseTicket };
  const childTicket: TicketDraft = {
    ...baseTicket,
    ...ticket,
    id: 2,
    parent_ticket_id: parentTicket.id,
    ticket_role: "CHILD",
    action_ticket_type: ticket.action_ticket_type ?? "DATA_MAPPING",
  };

  return {
    task: {
      id: 1,
      document_id: 1,
      title: "G31 指标变更扫描",
      status: "TICKET_GENERATED",
      risk_level: "MEDIUM",
      created_at: "2026-05-25T00:00:00Z",
      updated_at: "2026-05-25T00:00:00Z",
    },
    document: {
      id: 1,
      filename: "G31.xlsx",
      content_type: "application/vnd.reg-reporting.triplet",
      storage_path: "/tmp/G31.xlsx",
      title: "G31 指标变更扫描",
      text_excerpt: "",
      parsed_text: "",
      status: "PARSED",
      parse_status: "PARSED",
      parser: "triplet",
      char_count: 1,
      paragraph_count: 1,
      table_count: 1,
      parse_quality: "GOOD",
      parse_error_message: "",
      created_at: "2026-05-25T00:00:00Z",
    },
    document_profile: {
      id: 1,
      document_id: 1,
      document_type: "",
      affected_table_codes: ["G31"],
      change_signals: [],
      in_scope_tables: ["G31"],
      out_of_scope_tables: [],
      suggested_route: "FULL_ANALYSIS",
      should_create_task: true,
      confidence_score: 0.8,
      reason: "",
      evidence_text: "",
      llm_model: "fake-model",
      review_status: "PENDING",
      raw_response: "",
      created_at: "2026-05-25T00:00:00Z",
    },
    steps: [],
    clauses: [],
    semantic_items: [],
    field_mappings: [],
    reporting_candidates: [],
    lineage_candidates: [],
    impact_items: [],
    rule_cards: [],
    ticket_drafts: [parentTicket, childTicket],
  };
}

async function openFirstChildDetail(wrapper: ReturnType<typeof mount>): Promise<void> {
  const auditTab = wrapper.findAll("button").find((button) => button.text().includes("工单审核"));
  if (!auditTab) throw new Error("工单审核 tab not found");
  await auditTab.trigger("click");
  await wrapper.get("tbody tr").trigger("click");
}

const globalStubs = {
  ExecutionPlanCard: { template: "<div data-test=\"execution-plan-card-stub\" />" },
};

describe("ReviewTicketView", () => {
  it("shows the execution plan card only inside the execution-plan sub tab", async () => {
    const wrapper = mount(ReviewTicketView, {
      props: {
        busy: false,
        workflow: workflowWithTicket({
          summary: "确认 G31 优先股口径调整影响范围",
        }),
      },
      global: { stubs: globalStubs },
    });

    expect(wrapper.find(".ai-plan [data-test='execution-plan-card-stub']").exists()).toBe(true);

    const auditTab = wrapper.findAll("button").find((button) => button.text().includes("工单审核"));
    if (!auditTab) throw new Error("工单审核 tab not found");
    await auditTab.trigger("click");

    expect(wrapper.find("[data-test='execution-plan-card-stub']").exists()).toBe(false);
  });

  it("renders structured ticket fields and hides the fixed SQL draft block", async () => {
    const wrapper = mount(ReviewTicketView, {
      props: {
        busy: false,
        workflow: workflowWithTicket({
          summary: "确认 G31 优先股口径调整影响范围",
          responsible_system: "REG_REPORTING_SYSTEM",
          affected_assets: JSON.stringify(["G31.PART_I", "rpt_g31_position"]),
          must_do: JSON.stringify(["更新报送字段映射", "补充口径校验规则"]),
          quality_score: 92,
        }),
      },
      global: { stubs: globalStubs },
    });

    await openFirstChildDetail(wrapper);

    expect(wrapper.text()).toContain("监管报送系统");
    expect(wrapper.text()).toContain("确认 G31 优先股口径调整影响范围");
    expect(wrapper.text()).toContain("更新报送字段映射");
    expect(wrapper.text()).toContain("质量评分");
    expect(wrapper.text()).toContain("92");
    expect(wrapper.text()).not.toContain("可审查 SQL · 参考草稿");
  });

  it("falls back to content markdown for old tickets without structured fields", async () => {
    const wrapper = mount(ReviewTicketView, {
      props: {
        busy: false,
        workflow: workflowWithTicket({
          content: "## 老工单正文\n请按原 Markdown 方式展示。",
          summary: "",
          responsible_system: "",
          must_do: "",
        }),
      },
      global: { stubs: globalStubs },
    });

    await openFirstChildDetail(wrapper);

    expect(wrapper.text()).toContain("## 老工单正文");
    expect(wrapper.text()).toContain("请按原 Markdown 方式展示。");
  });
});
