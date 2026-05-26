# LLM / 规则 Eval 框架

> 更新日期：2026-05-26
> 定位：业务级回归测试。和 `tests/test_*.py` 的单元测试**互补不替代**。

## 它是什么 / 不是什么

| 层 | 关注点 | 例子 |
|---|---|---|
| **Unit test**（已有 88 条） | 函数返回值符合代码逻辑 | `diff_excel_with_db()` 返回特定 ExcelDiffEntry |
| **Eval**（这里） | 业务输出符合业务事实 | 上传 G31(252).xls 后 UI 上应出现"删除资产支持证券"且**不应**出现"新增 250 个" |

Eval 把每个 case 写成 JSON，由 framework 自动跑 + 出报告。改 prompt / 改抽取代码 / 换模型时，跑一遍立刻知道"哪条变好 / 变差 / 没动"，避免肉眼回归。

## 目录结构

```
tests/eval/
├── README.md            ← 你正在读
├── framework.py         ← 核心：EvalCase / 断言 DSL / Runner
├── targets.py           ← 业务路径 executor 注册（triplet_excel_diff 等）
├── reporter.py          ← 把结果渲染成 Markdown
├── test_run_eval.py     ← pytest 入口（parametrize 所有 case）
└── cases/               ← 每个 JSON 文件 = 一个 case
    └── g31_252_vs_251.json

scripts/run_eval.py      ← CLI：跑全套 + 写 Markdown 报告
reports/eval-latest.md   ← 最近一次报告（gitignore）
```

## 怎么跑

```bash
# pytest 模式（融进既有测试套）
uv run pytest tests/eval/ -v

# CLI 模式（独立跑 + Markdown 报告 + 可过滤）
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --filter g31
uv run python scripts/run_eval.py --out reports/eval-2026-05-26.md
```

退出码：`0` 全过 / `1` 有失败 / `2` 框架错误（CI 可直接接）。

## 怎么加新 case

1. 在 `cases/` 下新建 `<case_id>.json`，结构：

```jsonc
{
  "id": "g24_某次发文_某变更",
  "description": "一句话讲清楚这条 case 在测什么业务事实",
  "category": "rule_based",         // rule_based | llm
  "target": "triplet_excel_diff",   // 必须在 targets.py 已注册
  "tags": ["1104", "G24"],
  "inputs": {
    "object_code": "G24",
    "baseline_file": "路径（相对项目根或绝对）",
    "template_file": "路径"
  },
  "expectations": [
    {
      "kind": "signal_count",
      "spec": { "min": 1, "max": 10 },
      "reason": "为什么这个范围"
    }
    // 见下方"断言类型"
  ]
}
```

2. `uv run pytest tests/eval/ -v` 跑一遍，绿了就提交。
3. 后续 bug 修复时**先在这里加一条 must_not_contain 断言**作为回归防线，再去改代码。

## 断言类型（spec DSL）

| kind | spec 字段 | 语义 |
|---|---|---|
| `signal_count` | `min` / `max` | 总条数边界 |
| `must_contain` | `change_type` / `table_code` / `keyword` / `keyword_any` / `keyword_all` / `regex` | 至少一条 signal 匹配 |
| `must_not_contain` | 同上 | 不能有任何一条匹配（防回归利器） |
| `all_signals_match` | `field` + `in` | 全部 signal 在某字段满足白名单 |

匹配字段：`change_type` 和 `table_code` 精确匹配；keyword/regex 在拼接的 haystack（`table_code | section_hint | indicator_hint | evidence_text | change_type`）上匹配。

## 新增 target（业务路径）

举例：要把 `document_profiler.generate_document_profile`（走真实 LLM 的文本路径）加为 target：

```python
# targets.py
from app.services import document_profiler

@register_target("document_profiler_llm")
def _run_profiler(inputs: dict) -> list[dict]:
    document = build_fake_reg_document(inputs["text"])
    context = load_profile_context_from_inputs(inputs)
    draft = document_profiler.generate_document_profile(document, context)
    return [s.model_dump() for s in draft.change_signals]
```

⚠️ 注意：调真 LLM 的 case 会消耗 token。建议这类 case：
- 加 tag `["llm", "expensive"]`
- 用 `pytest -k "not llm"` 跑只测规则路径的快通道
- CLI 加 `--filter llm` 单独跑

## 设计原则

1. **case 文件就是文档**：description / reason 字段都要写清楚业务原因，不要只写"测试 X"
2. **回归优先**：每修一个 bug，先在 case 里加一条 `must_not_contain`，然后再改代码
3. **不追求覆盖率**：10-30 条高价值 case 远胜 1000 条无聊 case
4. **真实数据 > mock 数据**：能用 `一表通/` 下的真实材料就别造假数据
