# docs 索引

本目录沉淀「监管报送变更影响分析与工单助手」的全部设计文档。文档按"业务背景 → 主线设计 → 子系统设计 → 前端/落地 → 临时事项"组织。

更新日期：2026-05-25

---

## 阅读路径建议

**新人首次进项目**（按顺序读 3 篇即可建立全景）：
1. [1104-report-introduction.md](1104-report-introduction.md) — 业务背景
2. [regulatory-workflow-implementation.md](regulatory-workflow-implementation.md) — 主线流程
3. [frontend-component-map.md](frontend-component-map.md) — 前端落地形态

**做血缘 / 影响分析**：先读 [regulatory-report-lineage-impact-design.md](regulatory-report-lineage-impact-design.md)
**做规则资产 / 知识库**：先读 [rule-card-and-concept-kb-design.md](rule-card-and-concept-kb-design.md)，再读 [field-level-revision-table-redesign.md](field-level-revision-table-redesign.md)
**评审 / 演示前 checklist**：[innovation-demo-todo.md](innovation-demo-todo.md)

---

## 文档清单

| 文档 | 用途 | 最近更新 |
|---|---|---|
| [1104-report-introduction.md](1104-report-introduction.md) | 1104 非现场监管报表的业务背景说明，作为一阶段落脚点的基础知识 | 2026-05-18 |
| [regulatory-workflow-implementation.md](regulatory-workflow-implementation.md) | 项目**主线设计**。从"监管报送变更"到"报送项 / 指标口径 / 数据血缘 / 工单沉淀"的通用影响分析框架 | 2026-05-18 |
| [regulatory-report-lineage-impact-design.md](regulatory-report-lineage-impact-design.md) | 通用血缘影响分析方法："监管对象定位 → 指标口径 → 血缘映射 → 影响分析 → 工单沉淀" | 2026-05-18 |
| [rule-card-and-concept-kb-design.md](rule-card-and-concept-kb-design.md) | 在 22 张表基础上新增"规则卡片 + 概念知识库"两层资产。一期落脚点 G31 | 2026-05-21 |
| [field-level-revision-table-redesign.md](field-level-revision-table-redesign.md) | 字段级修订对照表方案 v2 —— 独立的、长期沉淀的监管制度变更知识库 | 2026-05-24 |
| [frontend-component-map.md](frontend-component-map.md) | Vue 3 + Vite + TS 前端的页面、流程页和 API 契约主线 | 2026-05-14 |
| [innovation-demo-todo.md](innovation-demo-todo.md) | 银行创新奖一期 demo 的关键缺口与改进任务（按"看懂 / 相信 / 记住"三件事评估） | 2026-05-20 |
| [superpowers/](superpowers/) | 技能 / 模板沉淀目录（待整理） | — |

---

## 文档约定

- 每篇新文档第一段都要写：**更新日期 + 文档定位**（一句话说"这篇是干嘛的"）
- 命名 kebab-case，英文为主；中文 README / 索引除外
- 设计调整时直接改原文档并更新顶部日期，不要堆"v1 / v2 / 历史版本"；版本由 git 兜底
- 文档间互相引用用相对路径
