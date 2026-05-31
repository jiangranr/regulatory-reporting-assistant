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
  business_note: "",
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

function childTicket(id: number, ticket: Partial<TicketDraft>): TicketDraft {
  return {
    ...baseTicket,
    ...ticket,
    id,
    parent_ticket_id: 1,
    ticket_role: "CHILD",
    action_ticket_type: ticket.action_ticket_type ?? "DATA_MAPPING",
  };
}

async function openFirstChildDetail(wrapper: ReturnType<typeof mount>): Promise<void> {
  const auditTab = wrapper.findAll("button").find((button) => button.text().includes("工单审核"));
  if (!auditTab) throw new Error("工单审核 tab not found");
  await auditTab.trigger("click");
  const stage3 = wrapper.find("[data-test='impact-review-stage3-stub']");
  if (stage3.exists()) await stage3.trigger("click");
  await wrapper.get(".ticket-item").trigger("click");
}

const globalStubs = {
  ExecutionPlanCard: { template: "<div data-test=\"execution-plan-card-stub\" />" },
  ImpactScopeReview: {
    props: ["activeStage"],
    emits: ["stage-change", "confirmed"],
    template: `
      <div data-test="impact-scope-review-stub">
        <button data-test="impact-review-stage2-stub" @click="$emit('stage-change', 2)">2 业务勾选 · 补充</button>
        <button data-test="impact-review-stage3-stub" @click="$emit('stage-change', 3)">3 拆分子单 · 派发</button>
      </div>
    `,
  },
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
    expect(wrapper.find("[data-test='impact-scope-review-stub']").exists()).toBe(false);

    const auditTab = wrapper.findAll("button").find((button) => button.text().includes("工单审核"));
    if (!auditTab) throw new Error("工单审核 tab not found");
    await auditTab.trigger("click");

    expect(wrapper.find("[data-test='execution-plan-card-stub']").exists()).toBe(false);
    expect(wrapper.find("[data-test='impact-scope-review-stub']").exists()).toBe(true);
    expect(wrapper.find(".audit-stage-hint").exists()).toBe(true);
    expect(wrapper.find(".ticket-grid").exists()).toBe(false);
    expect(wrapper.find(".ticket-list-table").exists()).toBe(false);

    await wrapper.get("[data-test='impact-review-stage3-stub']").trigger("click");

    expect(wrapper.find(".audit-stage-hint").exists()).toBe(false);
    expect(wrapper.find(".ticket-grid").exists()).toBe(true);
    expect(wrapper.find(".ticket-doc").exists()).toBe(true);
  });

  it("groups the left ticket list by action type and supports folding a type group", async () => {
    const workflow = workflowWithTicket({
      action_ticket_type: "SOURCE_SYSTEM_CHANGE",
      summary: "交易对手与授信系统需处理 1 个报送项、2 个字段。",
    });
    workflow.ticket_drafts.push(
      childTicket(3, {
        action_ticket_type: "SOURCE_SYSTEM_CHANGE",
        summary: "投资交易 ODS 需处理 2 个报送项、5 个字段。",
      }),
      childTicket(4, {
        action_ticket_type: "SOURCE_SYSTEM_CHANGE",
        summary: "核心源系统需补充采集字段。",
      }),
      childTicket(5, {
        action_ticket_type: "REPORT_PROCESSING",
        summary: "报送加工链路需调整调度。",
      }),
    );
    const wrapper = mount(ReviewTicketView, {
      props: { busy: false, workflow },
      global: { stubs: globalStubs },
    });

    const auditTab = wrapper.findAll("button").find((button) => button.text().includes("工单审核"));
    if (!auditTab) throw new Error("工单审核 tab not found");
    await auditTab.trigger("click");
    await wrapper.get("[data-test='impact-review-stage3-stub']").trigger("click");

    const groups = wrapper.findAll(".ticket-type-group");
    expect(groups).toHaveLength(2);
    expect(groups[0].text()).toContain("源系统改造");
    expect(groups[0].text()).toContain("3 个子单");
    expect(groups[1].text()).toContain("报送加工");
    expect(groups[1].text()).toContain("1 个子单");

    await groups[0].get("[data-test='ticket-type-group-toggle']").trigger("click");
    expect(groups[0].get(".ticket-group-body").attributes("style")).toContain("display: none");
  });

  it("renders structured ticket fields in the document-style ticket view and hides the fixed SQL draft block", async () => {
    const wrapper = mount(ReviewTicketView, {
      props: {
        busy: false,
        workflow: workflowWithTicket({
          summary: "确认 G31 优先股口径调整影响范围",
          responsible_system: "REG_REPORTING_SYSTEM",
          affected_assets: JSON.stringify({
            REPORTING_ITEM_CODES: ["G31.PART_I"],
            SOURCE_FIELDS: [{ code: "rpt_g31_position", name: "G31 持仓源表" }],
            LINEAGE_ROLES: ["SOURCE_FIELD"],
          }),
          must_do: JSON.stringify(["更新报送字段映射", "补充口径校验规则"]),
          quality_score: 92,
        }),
      },
      global: { stubs: globalStubs },
    });

    await openFirstChildDetail(wrapper);

    expect(wrapper.find(".ticket-doc").exists()).toBe(true);
    expect(wrapper.text()).toContain("监管报送系统");
    expect(wrapper.text()).toContain("确认 G31 优先股口径调整影响范围");
    expect(wrapper.text()).toContain("rpt_g31_position");
    expect(wrapper.text()).toContain("G31 持仓源表");
    expect(wrapper.text()).toContain("质量 92");
    expect(wrapper.text()).toContain("92");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("建议处理动作");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("待确认问题");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("验收标准");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("关联与依赖");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("更新报送字段映射");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("G31.PART_I");
    expect(wrapper.find(".ticket-doc").text()).not.toContain("SOURCE_FIELD");
    expect(wrapper.text()).not.toContain("可审查 SQL · 参考草稿");

    await wrapper.get(".lineage-btn").trigger("click");
    const modal = wrapper.get(".lineage-modal");
    expect(modal.text()).toContain("G31.PART_I");
    expect(modal.text()).toContain("SOURCE_FIELD");
  });

  it("renders only related regulatory evidence as bullet summaries in the background section", async () => {
    const workflow = workflowWithTicket({
      summary: "交易对手与授信系统需处理 1 个报送项、2 个字段。",
      related_impact_codes: JSON.stringify(["G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE"]),
      affected_assets: JSON.stringify({
        reporting_items: [
          { code: "G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE", name: "因持有非底层资产而间接持有期末余额" },
        ],
        source_fields: [{ code: "crms_counterparty.counterparty_id", name: "交易对手编号", role: "SOURCE_FIELD" }],
        lineage_roles: ["SOURCE_FIELD"],
      }),
      content: "## 责任分配\n\n- 出口责任 (A)：REPORTING_MGMT\n\n## 影响范围\n\n- 不应出现在背景区",
    });
    workflow.document_profile!.change_signals = [
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "因持有非底层资产而间接持有_期末余额",
        change_type: "ADD",
        evidence_text: "- [新增 | 陈施霖 | 2024-12-20] G31.PART_I.1_0.D 因持有非底层资产而间接持有：期末余额",
        confidence: 0.92,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE",
      },
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "D列/ E列列序调整（因持有非底层资产而间接持有、穿透后期末余额）",
        change_type: "MODIFY",
        evidence_text: "D列/ E列列序调整：新增 DECD",
        confidence: 0.73,
        evidence_verified: true,
        matched_item_code: "",
        match_status: "FUZZY_LANE",
        composite_match: {
          reporting_item_codes: ["G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE"],
        } as any,
      },
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "修正久期",
        change_type: "MODIFY",
        evidence_text: "C列修正久期发生 INDICATOR_ADD，需要复核报送字段、源字段和加工逻辑。",
        confidence: 0.88,
        evidence_verified: true,
      },
    ];
    const wrapper = mount(ReviewTicketView, {
      props: { busy: false, workflow },
      global: { stubs: globalStubs },
    });

    await openFirstChildDetail(wrapper);

    const backgroundSection = wrapper.findAll(".doc-section").find((section) => section.text().includes("背景与变更来源"));
    if (!backgroundSection) throw new Error("background section not found");

    const evidenceCards = backgroundSection.findAll(".reg-evidence-card");
    expect(evidenceCards).toHaveLength(1);
    expect(backgroundSection.text()).toContain("监管原文摘要");
    expect(evidenceCards[0].text()).toContain("G31.PART_I.1_0.D 因持有非底层资产而间接持有：期末余额");
    expect(backgroundSection.text()).not.toContain("D列/ E列列序调整");
    expect(backgroundSection.text()).not.toContain("C列修正久期发生 INDICATOR_ADD");
    expect(backgroundSection.text()).not.toContain("## 责任分配");
    expect(backgroundSection.text()).not.toContain("不应出现在背景区");
  });

  it("merges overlapping regulatory evidence and highlights only revision operations", async () => {
    const workflow = workflowWithTicket({
      summary: "G31 修正久期和填报机构范围调整处理",
      related_impact_codes: JSON.stringify(["G31.PART_I.1_0.C_修正久期"]),
      affected_assets: JSON.stringify({
        reporting_items: [{ code: "G31.PART_I.1_0.C_修正久期", name: "修正久期" }],
      }),
    });
    workflow.document_profile!.change_signals = [
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "C列 修正久期",
        change_type: "ADD",
        evidence_text:
          "[新增 | 陈施霖 | 2024-11-22] 修正久期；C. 修正久期MD=-(dP/P)/dy=D/(1+y/k)，其中MD为修正久期。",
        confidence: 0.92,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.1_0.C_修正久期",
      },
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "C列 修正久期 / 填报机构范围",
        change_type: "SCOPE_ADJUST",
        evidence_text:
          "[删除 | 陈施霖 | 2024-12-03] 投资 填报机构：政策性银行、企业集团财务公司、信托公司、金融租赁公司。C. 修正久期MD=-(dP/P)/dy=D/(1+y/k)，其中MD为修正久期。",
        confidence: 0.88,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.1_0.C_修正久期",
      },
    ];
    const wrapper = mount(ReviewTicketView, {
      props: { busy: false, workflow },
      global: { stubs: globalStubs },
    });

    await openFirstChildDetail(wrapper);

    const backgroundSection = wrapper.findAll(".doc-section").find((section) => section.text().includes("背景与变更来源"));
    if (!backgroundSection) throw new Error("background section not found");

    const evidenceCards = backgroundSection.findAll(".reg-evidence-card");
    expect(evidenceCards).toHaveLength(1);
    expect(evidenceCards[0].text()).toContain("填报机构：政策性银行、企业集团财务公司、信托投资公司、金融租赁公司");
    expect(evidenceCards[0].find(".reg-revision-add").text()).toContain("修正久期");
    expect(evidenceCards[0].find(".reg-revision-delete").text()).toBe("投资");
    expect(evidenceCards[0].find(".reg-revision-delete").attributes("title")).toContain("删除 · 陈施霖 · 2024-12-03");
    expect(evidenceCards[0].find(".reg-evidence-highlight").exists()).toBe(false);
  });

  it("uses the institution paragraph when a deletion revision belongs to that context", async () => {
    const workflow = workflowWithTicket({
      summary: "D列期末余额处理",
      related_impact_codes: JSON.stringify(["G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE"]),
      affected_assets: JSON.stringify({
        reporting_items: [
          { code: "G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE", name: "因持有非底层资产而间接持有期末余额" },
        ],
      }),
    });
    workflow.document_profile!.change_signals = [
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "D列期末余额",
        change_type: "SCOPE_ADJUST",
        evidence_text:
          "[新增 | 陈施霖 | 2024-12-20] 为修正久期、；[删除 | 陈施霖 | 2024-12-03] 投资；[C. 修正久期] ：衡量单笔债券投资组合估值对到期收益率变化的敏感度指标。",
        confidence: 0.78,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE",
      },
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "C列修正久期",
        change_type: "ADD",
        evidence_text:
          "[删除 | 陈施霖 | 2024-12-03] 投资；[新增 | 陈施霖 | 2024-11-22] [C.\n[新增 | 陈施霖 | 2024-11-22] 修正久期\n[新增 | 陈施霖 | 2024-11-22] ]\n[新增 | 陈施霖 | 2024-11-22] ：；[新增 | 陈施霖 | 2024-12-20] 衡量单笔债券投资组合估值对到期收益率变化的敏感度指标，计算公式为\n[新增 | 陈施霖 | 2024-12-20] MD=-(dP/P)/dy=D/(1+y/k)\n[新增 | 陈施霖 | 2024-12-20] ，其中\n[新增 | 陈施霖 | 2024-12-20] MD\n[新增 | 陈施霖 | 2024-12-20] 为修正久期、\n[新增 | 陈施霖 | 2024-12-20] dP\n[新增 | 陈施霖 | 2024-12-20] 为债券估值变化，\n[新增 | 陈施霖 | 2024-12-20] dy\n[新增 | 陈施霖 | 2024-12-20] 为到期收益率变化。",
        confidence: 0.92,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.1_0.D_INDIRECT_HOLDING_BALANCE",
      },
      {
        table_code: "G31",
        section_hint: "第二部分：一般说明",
        indicator_hint: "填报机构范围",
        change_type: "SCOPE_ADJUST",
        evidence_text:
          "[新增 | 陈施霖 | 2024-12-16] 直销银行、；[删除 | 陈施霖 | 2024-12-03] 投资；填报机构：政策性银行、企业集团财务公司、信托投资公司、金融租赁公司、消费金融公司。",
        confidence: 0.86,
        evidence_verified: true,
        matched_item_code: "",
      },
    ];
    const wrapper = mount(ReviewTicketView, {
      props: { busy: false, workflow },
      global: { stubs: globalStubs },
    });

    await openFirstChildDetail(wrapper);

    const backgroundSection = wrapper.findAll(".doc-section").find((section) => section.text().includes("背景与变更来源"));
    if (!backgroundSection) throw new Error("background section not found");

    expect(backgroundSection.text()).toContain("填报机构：政策性银行、企业集团财务公司、信托投资公司、金融租赁公司、消费金融公司");
    expect(backgroundSection.findAll(".reg-revision-delete")).toHaveLength(1);
    expect(backgroundSection.find(".reg-revision-delete").text()).toBe("投资");
    expect(backgroundSection.text()).not.toContain("投资；[C. 修正久期]");
    expect(backgroundSection.text()).not.toContain("投资 [C. 修正久期]");
    expect(backgroundSection.text()).not.toMatch(/投资\s*\[C\.\s*修正久期/);
    expect(backgroundSection.text()).not.toContain("dy dP");
    expect(backgroundSection.text()).not.toContain("为修正久期、 [C. 修正久期]");
    expect(backgroundSection.text()).not.toContain("为修正久期、 投资 [C. 修正久期]");
    expect(backgroundSection.text()).not.toMatch(/为修正久期、\s*\[C\.\s*修正久期/);
  });

  it("falls back to cleaned content for old tickets without structured evidence", async () => {
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

    expect(wrapper.text()).toContain("老工单正文");
    expect(wrapper.text()).toContain("请按原 Markdown 方式展示。");
    expect(wrapper.text()).not.toContain("## 老工单正文");
  });
});
