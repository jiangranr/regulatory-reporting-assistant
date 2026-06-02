import type { ImpactReviewResponse } from "@/types/api";

// G24 影响范围复核 fixture：跨 RPT（报送集市）+ INTERBANK_CORE（同业源系统）两个真实系统。
// 桶按真实 system_code 划分，与后端 build_baseline_from_impacts 的输出保持一致。
export const IMPACT_REVIEW_RESPONSE = {
  status: "EDITING",
  review: {
    version: "v1",
    items: [
      {
        reporting_item_code: "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
        reporting_item_name: "最大百家金融机构同业融入余额",
        removed: false,
        business_note: "",
        systems: [
          {
            responsible_system: "RPT",
            responsible_system_zh: "监管报送系统",
            system_type: "REPORTING",
            owner_team: "监管报送团队",
            fields: [
              {
                field_code: "rpt_g24.interbank_borrowing_bal_top100",
                field_name: "同业融入余额",
                lineage_role: "REPORT_FIELD",
                source: "AI",
                selected: true,
                edited: false,
                removed: false,
                is_required: true,
              },
            ],
          },
          {
            responsible_system: "INTERBANK_CORE",
            responsible_system_zh: "同业业务系统",
            system_type: "SOURCE",
            owner_team: "金融市场科技团队",
            fields: [
              {
                field_code: "interbank_deal.balance",
                field_name: "同业交易余额",
                lineage_role: "SOURCE_FIELD",
                source: "AI",
                selected: true,
                edited: false,
                removed: false,
                is_required: false,
              },
            ],
          },
        ],
      },
    ],
  },
  ai_baseline: {
    version: "v1",
    items: [],
  },
  stats: {
    total_items: 1,
    total_systems: 2,
    selected_fields: 2,
    business_added_fields: 0,
    business_removed_fields: 0,
  },
  system_options: [
    {
      system_code: "RPT",
      system_name: "监管报送系统",
      system_type: "REPORTING",
      owner_team: "监管报送团队",
    },
    {
      system_code: "INTERBANK_CORE",
      system_name: "同业业务系统",
      system_type: "SOURCE",
      owner_team: "金融市场科技团队",
    },
    {
      system_code: "VALUATION",
      system_name: "估值计量系统",
      system_type: "SOURCE",
      owner_team: "估值核算团队",
    },
  ],
} satisfies ImpactReviewResponse;
