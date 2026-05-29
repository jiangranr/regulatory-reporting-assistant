import type { ImpactReviewResponse } from "@/types/api";

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
            responsible_system: "DATA_MART_ETL",
            responsible_system_zh: "数据集市/ETL",
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
            responsible_system: "SOURCE_SYSTEM",
            responsible_system_zh: "业务源系统",
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
} satisfies ImpactReviewResponse;
