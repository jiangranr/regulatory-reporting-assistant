import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import LineageView from "./LineageView.vue";
import type { TableChangeSignal, TaskWorkflow } from "@/types/api";

function workflowWithSignal(signal: Partial<TableChangeSignal>): TaskWorkflow {
  return {
    task: {
      id: 1,
      document_id: 1,
      title: "G31 指标变更扫描",
      status: "IMPACT_ANALYZED",
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
      change_signals: [
        {
          table_code: "G31",
          section_hint: "PART_I",
          indicator_hint: "优先股投资余额",
          change_type: "DELETE",
          evidence_text: "从 G31 移出：优先股不再计入债券投资余额",
          confidence: 0.55,
          evidence_verified: true,
          matched_item_code: "",
          match_status: "UNMATCHED_DELETED",
          ...signal,
        },
      ],
      in_scope_tables: ["G31"],
      out_of_scope_tables: [],
      suggested_route: "FULL_ANALYSIS",
      should_create_task: true,
      confidence_score: 0.55,
      reason: "",
      evidence_text: "",
      llm_model: "rule-based-triplet-scanner",
      review_status: "PENDING",
      raw_response: "",
      created_at: "2026-05-25T00:00:00Z",
    },
    steps: [],
    clauses: [],
    semantic_items: [],
    field_mappings: [
      {
        object_code: "G31",
        item_code: "G31.PART_I.1_0.A_穿透前_期末余额",
        regulatory_term: "G31穿透前期末余额",
        field_code: "rpt_g31_part_i_pre_balance",
        field_name: "G31穿透前期末余额",
        column_name: "pre_balance",
        table_name: "rpt_g31_part_i",
        system_name: "报送平台",
        system_code: "RPT",
        lineage_role: "REPORT_FIELD",
        mapping_status: "CONFIRMED",
      },
      {
        object_code: "G24",
        item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
        regulatory_term: "G24同业融入余额",
        field_code: "rpt_g24_interbank_balance",
        field_name: "G24同业融入余额",
        column_name: "interbank_balance",
        table_name: "rpt_g24",
        system_name: "报送平台",
        system_code: "RPT",
        lineage_role: "REPORT_FIELD",
        mapping_status: "CONFIRMED",
      },
    ],
    reporting_candidates: [],
    lineage_candidates: [],
    impact_items: [],
    rule_cards: [],
    ticket_drafts: [],
  };
}

describe("LineageView", () => {
  it("renders the report catalog in a sticky sidebar region", () => {
    const wrapper = mount(LineageView, {
      props: { workflow: workflowWithSignal({}) },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.find(".lineage-sidebar").exists()).toBe(true);
    expect(wrapper.find(".lineage-sidebar .tree").text()).toContain("1104 报表目录");
  });

  it("does not show whole-table lineage when a revision signal is explicitly unmatched", () => {
    const wrapper = mount(LineageView, {
      props: { workflow: workflowWithSignal({}) },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.text()).toContain("优先股投资余额");
    expect(wrapper.text()).toContain("暂无字段映射数据");
    expect(wrapper.text()).not.toContain("G31穿透前期末余额");
  });

  it("still shows exact lineage when matched_item_code is present", () => {
    const wrapper = mount(LineageView, {
      props: {
        workflow: workflowWithSignal({
          indicator_hint: "债券投资合计 × A_穿透前_期末余额",
          matched_item_code: "G31.PART_I.1_0.A_穿透前_期末余额",
          match_status: "MATCHED_EXISTING",
        }),
      },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.text()).toContain("G31穿透前期末余额");
  });

  it("groups revision signals by business metric and keeps product details expandable", async () => {
    const workflow = workflowWithSignal({
      indicator_hint: "资产支持证券 × B·投资收入（年初至报告期末数）",
      matched_item_code: "G31.PART_I.13_0.B_投资收入_年初至报告期末数",
    });
    workflow.document_profile!.change_signals.push(
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "其中：1.8.1信贷资产证券化 × B·投资收入（年初至报告期末数）",
        change_type: "DELETE",
        evidence_text: "信贷资产证券化投资收入删除",
        confidence: 0.8,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.14_0.B_投资收入_年初至报告期末数",
      },
      {
        table_code: "G31",
        section_hint: "PART_I",
        indicator_hint: "交易所资产支持证券 × B·投资收入（年初至报告期末数）",
        change_type: "DELETE",
        evidence_text: "交易所资产支持证券投资收入删除",
        confidence: 0.8,
        evidence_verified: true,
        matched_item_code: "G31.PART_I.15_0.B_投资收入_年初至报告期末数",
      },
    );

    const wrapper = mount(LineageView, {
      props: { workflow },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.text()).toContain("G31.1 B·投资收入（年初至报告期末数）");
    expect(wrapper.find(".tree").text()).toContain("+3");
    expect(wrapper.find(".tree").text()).not.toContain("G31.1 资产支持证券 × B·投资收入");

    const metricNode = wrapper
      .findAll(".tree-node")
      .find((node) => node.text().includes("G31.1 B·投资收入（年初至报告期末数）"));
    expect(metricNode).toBeTruthy();
    await metricNode!.trigger("click");

    expect(wrapper.find(".tree").text()).toContain("资产支持证券 × B·投资收入（年初至报告期末数）");
    expect(wrapper.find(".tree").text()).toContain("其中：1.8.1信贷资产证券化 × B·投资收入（年初至报告期末数）");
  });

  it("focuses the exact matched signal when opened from an impact item code", () => {
    const workflow = workflowWithSignal({
      indicator_hint: "修正久期",
      matched_item_code: "G31.PART_I.1_0.C_修正久期",
      match_status: "MATCHED_EXISTING",
    });
    workflow.document_profile!.change_signals.push({
      table_code: "G31",
      section_hint: "PART_I",
      indicator_hint: "穿透后期末余额",
      change_type: "MODIFY",
      evidence_text: "穿透后期末余额发生调整",
      confidence: 0.9,
      evidence_verified: true,
      matched_item_code: "G31.PART_I.1_0.单位_万元_E_穿透后_期末余额",
      match_status: "MATCHED_EXISTING",
    });
    workflow.field_mappings.push({
      object_code: "G31",
      item_code: "G31.PART_I.1_0.单位_万元_E_穿透后_期末余额",
      regulatory_term: "1 行·E 列 · 穿透后·期末余额（单位：万元）",
      field_code: "dm_g31_position.position_balance",
      field_name: "投资持仓余额",
      column_name: "position_balance",
      table_name: "dm_g31_position",
      system_name: "投资业务数据集市",
      system_code: "DM_INVESTMENT",
      lineage_role: "SOURCE_FIELD",
      mapping_status: "DRAFT",
    });

    const wrapper = mount(LineageView, {
      props: {
        workflow,
        focusItemCode: "G31.PART_I.1_0.单位_万元_E_穿透后_期末余额",
      },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.find(".field-detail h3").text()).toContain("穿透后期末余额");
    expect(wrapper.text()).toContain("投资持仓余额");
    expect(wrapper.find(".field-detail").text()).not.toContain("修正久期");
  });

  it("formats tracked-change evidence into readable action rows", () => {
    const wrapper = mount(LineageView, {
      props: {
        workflow: workflowWithSignal({
          indicator_hint: "C.修正久期",
          evidence_text: [
            "- [新增 | 陈施霖 | 2024-11-22] [C.",
            "- [新增 | 陈施霖 | 2024-11-22] 修正久期",
            "- [新增 | 陈施霖 | 2024-11-22] ]",
            "- [新增 | 陈施霖 | 2024-12-20] MD=-(dP/P)/dy=D/(1+y/k)",
          ].join("；"),
          confidence: 0.96,
        }),
      },
      global: { stubs: { LineageGraph: true } },
    });

    const rows = wrapper.findAll(".evidence-row");

    // 同一作者 + 同一动作的多次留痕修订应当合并为一行，
    // 日期以区间形式展示，避免 Word 里一整段被切成多张卡。
    expect(rows).toHaveLength(1);
    expect(rows[0].find(".evidence-meta").text()).toContain("新增 · 陈施霖 · 2024-11-22 ~ 2024-12-20");
    expect(rows[0].find(".evidence-body").text()).toContain("C. 修正久期");
    expect(rows[0].find(".evidence-body").text()).toContain("MD=-(dP/P)/dy=D/(1+y/k)");
    expect(rows[0].find(".evidence-body").text()).not.toContain("[新增");
  });

  it("surfaces the changed institution from a scope paragraph", () => {
    const wrapper = mount(LineageView, {
      props: {
        workflow: workflowWithSignal({
          indicator_hint: "填报机构范围",
          evidence_text: [
            "[新增 | 陈施霖 | 2024-12-16] 直销银行、",
            "3．填报机构：政策性银行（含开发银行）、大型商业银行（含邮储银行）、股份制商业银行、城市商业银行、直销银行、企业集团财务公司。",
          ].join("；"),
          confidence: 0.78,
        }),
      },
      global: { stubs: { LineageGraph: true } },
    });

    const rows = wrapper.findAll(".evidence-row");

    expect(rows[0].find(".evidence-meta").text()).toContain("新增 · 陈施霖 · 2024-12-16");
    expect(rows[0].find(".evidence-body").text()).toContain("直销银行");
    expect(rows[1].find(".evidence-body").text()).toContain("3．填报机构");
  });

  it("shows composite semantic match fields and filter conditions", () => {
    const wrapper = mount(LineageView, {
      props: {
        workflow: workflowWithSignal({
          match_status: "COMPOSITE_SEMANTIC_MATCH",
          composite_match: {
            match_type: "COMPOSITE_SEMANTIC_MATCH",
            pattern_code: "G31_CLASSIFICATION_MEASURE",
            indicator_hint: "优先股投资余额",
            measure_phrase: "投资余额",
            condition_phrase: "优先股",
            reporting_item_codes: ["G31.PART_I.1_0.A_穿透前_期末余额"],
            measure_field_codes: [
              "dm_g31_position.position_balance",
              "ods_invest_position.book_balance",
            ],
            condition_field_codes: ["ods_invest_position.asset_type"],
            matched_concepts: [
              {
                concept_code: "CON_PREFERRED_STOCK",
                concept_name: "优先股",
                concept_type: "CLASSIFICATION",
                matched_alias: "优先股",
              },
              {
                concept_code: "MEASURE_INVESTMENT_BALANCE",
                concept_name: "投资余额",
                concept_type: "MEASURE",
                matched_alias: "投资余额",
              },
            ],
            measure_fields: [
              {
                field_code: "dm_g31_position.position_balance",
                field_name: "投资持仓余额",
                table_name: "dm_g31_position",
                column_name: "position_balance",
                field_role: "MEASURE_FIELD",
                confidence_score: 0.9,
              },
              {
                field_code: "ods_invest_position.book_balance",
                field_name: "投资账面余额",
                table_name: "ods_invest_position",
                column_name: "book_balance",
                field_role: "SOURCE_MEASURE_FIELD",
                confidence_score: 0.85,
              },
            ],
            filter_conditions: [
              {
                field_code: "ods_invest_position.asset_type",
                field_name: "投资资产类型",
                operator: "=",
                value_code: "PREFERRED_STOCK",
                value_name: "优先股",
                confidence_level: "HIGH",
              },
            ],
            confidence: 0.86,
            review_status: "PENDING",
            needs_review: true,
            evidence_text: "从 G31 移出：优先股不再计入债券投资余额",
          },
        }),
      },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.text()).toContain("组合命中");
    expect(wrapper.text()).toContain("待确认");
    expect(wrapper.text()).toContain("投资持仓余额");
    expect(wrapper.text()).toContain("投资账面余额");
    expect(wrapper.text()).toContain("投资资产类型 = 优先股");
    expect(wrapper.text()).not.toContain("暂无字段映射数据");
    expect(wrapper.text()).not.toContain("G31穿透前期末余额");
  });

  it("focuses a composite semantic signal from a synthetic impact code", () => {
    const workflow = workflowWithSignal({
      indicator_hint: "修正久期",
      matched_item_code: "G31.PART_I.1_0.C_修正久期",
      match_status: "MATCHED_EXISTING",
    });
    workflow.document_profile!.change_signals.push({
      table_code: "G31",
      section_hint: "PART_I",
      indicator_hint: "优先股投资余额",
      change_type: "DELETE",
      evidence_text: "从 G31 移出：优先股不再计入债券投资余额",
      confidence: 0.82,
      evidence_verified: true,
      matched_item_code: "",
      match_status: "COMPOSITE_SEMANTIC_MATCH",
      composite_match: {
        match_type: "COMPOSITE_SEMANTIC_MATCH",
        pattern_code: "G31_CLASSIFICATION_MEASURE",
        indicator_hint: "优先股投资余额",
        measure_phrase: "投资余额",
        condition_phrase: "优先股",
        reporting_item_codes: ["G31.PART_I.1_0.A_穿透前_期末余额"],
        measure_field_codes: ["dm_g31_position.position_balance"],
        condition_field_codes: ["ods_invest_position.asset_type"],
        matched_concepts: [],
        measure_fields: [
          {
            field_code: "dm_g31_position.position_balance",
            field_name: "投资持仓余额",
            table_name: "dm_g31_position",
            column_name: "position_balance",
            field_role: "MEASURE_FIELD",
            confidence_score: 0.9,
          },
        ],
        filter_conditions: [
          {
            field_code: "ods_invest_position.asset_type",
            field_name: "投资资产类型",
            operator: "=",
            value_code: "PREFERRED_STOCK",
            value_name: "优先股",
            confidence_level: "HIGH",
          },
        ],
        confidence: 0.82,
        review_status: "PENDING",
        needs_review: true,
        evidence_text: "从 G31 移出：优先股不再计入债券投资余额",
      },
    });

    const wrapper = mount(LineageView, {
      props: {
        workflow,
        focusItemCode: "G31.COMPOSITE.优先股投资余额",
      },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.find(".field-detail h3").text()).toContain("优先股投资余额");
    expect(wrapper.text()).toContain("组合命中");
    expect(wrapper.text()).toContain("投资资产类型 = 优先股");
    expect(wrapper.find(".field-detail").text()).not.toContain("修正久期");
  });

  it("shows semantic field matches for dimension changes", () => {
    const wrapper = mount(LineageView, {
      props: {
        workflow: workflowWithSignal({
          indicator_hint: "发行人类型",
          change_type: "MODIFY",
          match_status: "SEMANTIC_FIELD_MATCH",
          composite_match: {
            match_type: "SEMANTIC_FIELD_MATCH",
            pattern_code: "G31_SEMANTIC_FIELD",
            indicator_hint: "发行人类型",
            measure_phrase: "",
            condition_phrase: "发行人类型",
            reporting_item_codes: ["G31.PART_I.BOND_INVESTMENT_BALANCE"],
            measure_field_codes: ["bond_investment.issuer_type"],
            condition_field_codes: [],
            matched_concepts: [
              {
                concept_code: "CON_ISSUER_TYPE",
                concept_name: "发行人类型",
                concept_type: "DIMENSION",
                matched_alias: "发行人类型",
              },
            ],
            measure_fields: [
              {
                field_code: "bond_investment.issuer_type",
                field_name: "债券发行人类型",
                table_name: "bond_investment",
                column_name: "issuer_type",
                field_role: "DIMENSION_FIELD",
                confidence_score: 0.8,
              },
            ],
            filter_conditions: [],
            confidence: 0.8,
            review_status: "PENDING",
            needs_review: true,
            evidence_text: "发行人类型枚举值细化。",
          },
        }),
      },
      global: { stubs: { LineageGraph: true } },
    });

    expect(wrapper.text()).toContain("语义字段命中");
    expect(wrapper.text()).toContain("债券发行人类型");
    expect(wrapper.text()).toContain("bond_investment.issuer_type");
    expect(wrapper.text()).not.toContain("暂无字段映射数据");
  });
});
