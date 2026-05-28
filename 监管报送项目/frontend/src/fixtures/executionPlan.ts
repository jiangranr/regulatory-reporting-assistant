// Keep synchronized with backend/tests/fixtures/execution_plan_samples.py.
// Frontend/backend execution plan fixture shapes must stay 1:1 aligned.
import type { ExecutionPlanResponse } from "../types/api";

export const EXECUTION_PLAN_HAPPY = {
  status: "READY",
  plan: {
    task_id: 2401,
    executive_summary:
      "G24 同业融入口径调整涉及同业资产分类、G31 投资穿透口径与报送校验规则联动，建议按口径确认、数据改造、联测验收三阶段推进。",
    estimated_duration: "1-2 周",
    execution_phases: [
      {
        phase_name: "口径确认与影响锁定",
        tasks: [
          {
            team: "REG_REPORTING_SYSTEM",
            team_zh: "监管报送团队",
            action:
              "确认 G24 同业融入口径调整边界，固化受影响项目、字段及报送批次。",
            ticket_id: 5011,
            is_blocker: true,
            blocker_reason: "口径边界未确认前，系统改造与验收规则无法冻结。",
          },
          {
            team: "DATA_GOVERNANCE_PLATFORM",
            team_zh: "业务复核团队",
            action: "复核同业融资业务分类、交易对手类型与存量数据映射关系。",
            ticket_id: 5012,
            is_blocker: false,
            blocker_reason: null,
          },
        ],
      },
      {
        phase_name: "数据改造与规则配置",
        tasks: [
          {
            team: "DATA_MART_ETL",
            team_zh: "数据平台团队",
            action:
              "调整同业融资源表取数逻辑，补齐交易对手与产品类型映射字段。",
            ticket_id: 5013,
            is_blocker: true,
            blocker_reason: "源数据口径不一致会导致 G24 与 G31 跨表校验失败。",
          },
          {
            team: "SOURCE_SYSTEM",
            team_zh: "报送系统团队",
            action:
              "更新 G24 报表生成规则和 G31 投资穿透关联校验规则，保留变更审计记录。",
            ticket_id: 5014,
            is_blocker: false,
            blocker_reason: null,
          },
        ],
      },
      {
        phase_name: "联测验收与上线准备",
        tasks: [
          {
            team: "TEST_ACCEPTANCE",
            team_zh: "测试验证团队",
            action:
              "执行存量样本回归、跨表勾稽校验和异常案例复核，输出验收证据。",
            ticket_id: 5013,
            is_blocker: false,
            blocker_reason: null,
          },
          {
            team: "KNOWLEDGE_ARCHIVE",
            team_zh: "生产运维团队",
            action:
              "准备上线窗口、回退方案和首批报送监控清单，确认人工复核入口。",
            ticket_id: 5014,
            is_blocker: false,
            blocker_reason: null,
          },
        ],
      },
    ],
    critical_risks: [
      {
        severity: "HIGH",
        description:
          "G24 同业融入口径与 G31 投资穿透口径存在交叉，若分类边界不一致会造成跨表校验差异。",
        ticket_id_ref: 5011,
        mitigation:
          "由监管报送团队牵头形成口径确认纪要，并将确认结果同步到规则配置与测试用例。",
      },
      {
        severity: "MEDIUM",
        description:
          "历史存量业务交易对手字段可能缺失，影响调整后口径下的自动归类准确性。",
        ticket_id_ref: 5013,
        mitigation:
          "对缺失字段建立补录清单，优先覆盖本期报送样本，并保留人工复核记录。",
      },
    ],
    team_coordination:
      "监管报送团队负责口径裁决，数据平台和报送系统团队并行改造，测试验证团队按同一批样本执行回归，所有阻塞项每日同步。",
    generated_at: "2026-05-28T14:30:00+08:00",
    generated_by: "execution-planner-fixture",
    confidence: 0.82,
    needs_human_review: false,
  },
} satisfies ExecutionPlanResponse;

export const EXECUTION_PLAN_DEGRADED = {
  status: "DEGRADED",
  plan: {
    task_id: 2401,
    executive_summary:
      "当前仅能基于已生成工单形成执行骨架，G24 同业融入口径调整的部分依赖关系仍需人工补充确认。",
    estimated_duration: "1-2 周",
    execution_phases: [
      {
        phase_name: "人工补全执行计划",
        tasks: [
          {
            team: "REG_REPORTING_SYSTEM",
            team_zh: "监管报送团队",
            action:
              "补充口径确认、数据改造、测试验收的实际责任人与先后依赖。",
            ticket_id: 5011,
            is_blocker: true,
            blocker_reason: "AI 规划上下文不足，无法可靠判断完整执行顺序。",
          },
        ],
      },
    ],
    critical_risks: [],
    team_coordination:
      "建议由监管报送团队先完成依赖关系确认，再触发数据平台和报送系统团队排期。",
    generated_at: "2026-05-28T14:30:00+08:00",
    generated_by: "execution-planner-fixture",
    confidence: 0.35,
    needs_human_review: true,
  },
  warning: "执行规划上下文不完整，已降级为人工补全骨架。",
} satisfies ExecutionPlanResponse;

export const EXECUTION_PLAN_NOT_GENERATED = {
  status: "NOT_GENERATED",
  plan: null,
} satisfies ExecutionPlanResponse;
