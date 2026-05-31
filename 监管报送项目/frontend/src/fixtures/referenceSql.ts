// Keep synchronized with backend/app/models/schemas.py::ReferenceSqlResponse.
// These fixtures drive vitest; do NOT depend on a real backend.
import type { ReferenceSqlResponse } from "../types/api";

export const SQL_NOT_GENERATED: ReferenceSqlResponse = {
  ticket_id: 101,
  status: "NOT_GENERATED",
  ability: "CAN_GENERATE",
  reference_sql: "",
  sql_dialect: "ANSI",
  confidence: 0,
  explanation: "",
  assumptions: [],
  warnings: [],
  not_applicable_reason: "",
  generated_at: null,
  generated_by: "",
};

export const SQL_READY: ReferenceSqlResponse = {
  ticket_id: 102,
  status: "READY",
  ability: "CAN_GENERATE",
  reference_sql: `SELECT
  rpt.reporting_item_code,
  SUM(src.amount) AS report_value
FROM g24_source src
JOIN reporting_catalog rpt
  ON src.product_code = rpt.source_field_code
WHERE src.report_date = :report_date
  AND src.institution_code = :institution_code
GROUP BY rpt.reporting_item_code`,
  sql_dialect: "ANSI",
  confidence: 0.87,
  explanation: "基于血缘链路 G24 → src.amount，聚合口径按报送项分组。",
  assumptions: ["源表 g24_source 已按报告期分区", "reporting_catalog 已包含最新口径映射"],
  warnings: [
    {
      type: "FIELD_NOT_IN_SCOPE",
      message: "字段 src.product_sub_type 未在业务勾选清单内，AI 可能写错或需补充勾选",
      field_code: "product_sub_type",
      severity: "WARNING",
    },
    {
      type: "TABLE_NOT_IN_CATALOG",
      message: "表 reporting_catalog 未在数据目录中登记，请确认名称",
      field_code: "",
      severity: "INFO",
    },
  ],
  not_applicable_reason: "",
  generated_at: "2026-05-29T14:30:00",
  generated_by: "claude-sonnet-4-6",
};

export const SQL_NOT_APPLICABLE: ReferenceSqlResponse = {
  ticket_id: 103,
  status: "NOT_APPLICABLE",
  ability: "NOT_APPLICABLE",
  reference_sql: "",
  sql_dialect: "ANSI",
  confidence: 0,
  explanation: "",
  assumptions: [],
  warnings: [],
  not_applicable_reason: "该子单类型为「口径确认」，无需生成取数 SQL，请在业务复核后手工填写逻辑说明。",
  generated_at: null,
  generated_by: "",
};

export const SQL_DEGRADED: ReferenceSqlResponse = {
  ticket_id: 104,
  status: "DEGRADED",
  ability: "PARTIAL",
  reference_sql: `-- ⚠️ 降级输出：LLM 未能完整推断口径，以下为骨架模板
SELECT /* TODO: 确认聚合字段 */
FROM /* TODO: 确认源表 */
WHERE report_date = :report_date`,
  sql_dialect: "ANSI",
  confidence: 0.31,
  explanation: "",
  assumptions: [],
  warnings: [
    {
      type: "LLM_FAILED",
      message: "LLM 调用超时，返回降级骨架模板，请人工补全",
      field_code: "",
      severity: "ERROR",
    },
  ],
  not_applicable_reason: "",
  generated_at: "2026-05-29T15:00:00",
  generated_by: "claude-sonnet-4-6",
};
