# 1104 资金同业一期建模与后端重构实施计划

> 更新日期：2026-05-18  
> 执行策略：方案 A，主线直接切换到监管报送对象、指标字段、血缘和工单沉淀，不再以早期业务对象字典作为影响分析入口。

## 1. 一期建模对象

从一表通/1104 材料中选择资金同业相关报表作为一期样板，先验证“监管变更文本 -> 1104 报表字段 -> 报送系统字段 -> 源系统字段 -> 工单草稿”的闭环。

| 报表编号 | 报表名称 | 频度 | 一期价值 |
|---|---|---|---|
| `G21` | 流动性期限缺口统计表 | 月 | 验证期限维度、现金流和流动性缺口血缘 |
| `G24` | 最大百家金融机构同业融入情况表 | 季 | 一期核心样板，直接命中同业融入、金融机构交易对手和余额口径 |
| `G25` | 流动性覆盖率和净稳定融资比例情况表 | 月 | 验证优质流动性资产和现金净流出口径 |
| `G27` | 主要负债项目明细表 | 季 | 验证同业存放等负债类资金同业指标 |
| `G31` | 投资业务情况表第 I 部分：底层资产投资情况 | 季 | 验证债券投资、底层资产和资金交易源字段 |

首批指标项：

- `G21.MAIN.LIQUIDITY_GAP_30D`
- `G24.MAIN.INTERBANK_BORROWING_BAL_TOP100`
- `G25.PART_I.HQLA_BALANCE`
- `G25.PART_I.NET_CASH_OUTFLOW_30D`
- `G27.MAIN.INTERBANK_DEPOSIT_BALANCE`
- `G31.PART_I.BOND_INVESTMENT_BALANCE`

## 2. 1104 报表字段存储方式

1104 的“某表某字段”不直接存入源系统字段表，而是先作为监管报送指标项存储，再通过血缘映射到内部物理字段。

| 内容 | 存储表 | 粒度 |
|---|---|---|
| 1104 报送体系 | `reg_reporting_systems` | 一条 `system_code='1104'` |
| 制度/表样版本 | `reg_reporting_versions` | 一套版本 |
| G21/G24/G25/G27/G31 报表 | `reg_reporting_objects` | 每张监管报表一条 |
| 主表、第 I 部分等 | `reg_reporting_sections` | 每个报表分部一条 |
| 监管指标/单元格 | `reg_reporting_items` | 影响分析最小监管对象 |
| 填报说明/口径规则 | `reg_reporting_instructions`、`reg_reporting_rules` | 每个指标的说明和规则 |
| 内部系统 | `data_system_catalog` | 报送系统、数据集市、源系统、主数据系统 |
| 内部物理字段 | `data_field_catalog` | 报送字段、数据集市字段、源系统字段、维度字段 |
| 报送指标到内部字段 | `reporting_item_lineage` | 指标到字段的角色化映射 |
| 发文定位结果 | `reg_reporting_change_candidates` | 每个候选变更一条 |
| 影响分析结果 | `reg_reporting_impact_items` | 每个影响项一条 |

G24 样例：

```text
reg_reporting_items:
  G24.MAIN.INTERBANK_BORROWING_BAL_TOP100 最大百家金融机构同业融入余额

data_field_catalog:
  rpt_g24.interbank_borrowing_bal_top100
  dm_interbank_position.balance
  interbank_deal.balance
  interbank_deal.counterparty_fin_org_code
  counterparty.institution_type

reporting_item_lineage:
  G24.MAIN.INTERBANK_BORROWING_BAL_TOP100 -> rpt_g24.interbank_borrowing_bal_top100, role=REPORT_FIELD
  G24.MAIN.INTERBANK_BORROWING_BAL_TOP100 -> interbank_deal.balance, role=SOURCE_FIELD
  G24.MAIN.INTERBANK_BORROWING_BAL_TOP100 -> interbank_deal.counterparty_fin_org_code, role=DIMENSION_FIELD
  G24.MAIN.INTERBANK_BORROWING_BAL_TOP100 -> counterparty.institution_type, role=FILTER_FIELD
```

## 3. 已执行改造

- [x] 新增 1104 资金同业一期 seed catalog。
- [x] 新增 reporting change extractor，用于从监管发文文本定位 G21/G24/G25/G27/G31 候选报表和指标。
- [x] 新增 reporting impact analyzer，用报送指标血缘生成影响项。
- [x] 新增 reporting ticket generator，生成口径确认、数据映射、报送加工、校验规则、测试验收类工单草稿。
- [x] 新增 reporting 目录 API：`/api/reporting/seed-1104`、`/api/reporting/objects`、`/api/reporting/items`、`/api/reporting/items/{item_code}/lineage`。
- [x] 更新任务影响分析接口：`/api/tasks/{task_id}/analyze-impact`。
- [x] 更新任务工单接口：`/api/tasks/{task_id}/generate-ticket`。
- [x] 更新 workflow 聚合接口，返回 `reporting_candidates`、`lineage_candidates`、`impact_items` 和 `ticket_drafts`。
- [x] 主应用入口不再把旧规则库样板 API 作为主流程入口。
- [x] 文档画像上下文从旧业务对象字典切换到 reporting 目录与血缘。
- [x] 删除旧规则库 API/服务测试，改为 1104 reporting 主线测试。

## 4. 待办事项

- [ ] 从真实 1104 Excel/填报说明中补充完整 G21/G24/G25/G27/G31 行列项目。
- [ ] 增加别名表或 synonym 字段，支持“最大百家金融机构同业融入情况表”“同业融入余额”等自然语言匹配。
- [ ] 增加人工复核接口，保存报送项定位、血缘确认和工单确认结论。
- [ ] 增加历史工单/影响项相似检索，沉淀人工判断经验。
- [ ] 引入表样差异解析，支持监管修改某表某字段时自动定位。
- [ ] 设计 EAST 复用样板，验证通用模型是否适用于明细表字段。

## 5. 验证

当前已通过后端全量测试：

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest -v
```

结果：`24 passed`。
