"""pytest 入口：parametrize 跑所有 eval case。

跑法：
    uv run pytest tests/eval/ -v

输出更详细（含每条 signal 摘要）：
    uv run python scripts/run_eval.py

新增 case 只需在 `tests/eval/cases/` 放一个 JSON 文件即可被发现。
"""

from __future__ import annotations

from pathlib import Path

import pytest

# noqa: F401 - 导入触发 target 注册
from . import targets  # noqa: F401
from .framework import EvalCase, list_cases, run_case

CASES_DIR = Path(__file__).parent / "cases"


def _discover_cases() -> list[EvalCase]:
    return list_cases(CASES_DIR)


@pytest.mark.parametrize(
    "case",
    _discover_cases(),
    ids=lambda c: c.case_id,
)
def test_eval_case(case: EvalCase) -> None:
    """一个 JSON case = 一个 pytest 用例。"""

    result = run_case(case)

    if result.error:
        pytest.fail(f"[{case.case_id}] 执行期错误：{result.error}")

    if not result.passed:
        lines = [
            f"[{case.case_id}] eval 失败 ({result.fail_count()}/{len(result.assertions)} 条断言未通过)",
            f"实际信号数: {result.actual_signal_count}",
            "前几条 signal 摘要：",
        ]
        for s in result.actual_summary:
            lines.append(f"  - {s['change_type']} {s['table_code']} {s['indicator_hint']}")
        lines.append("")
        lines.append("失败断言：")
        for a in result.assertions:
            if a.passed:
                continue
            lines.append(
                f"  ❌ {a.expectation.kind} spec={a.expectation.spec} "
                f"reason={a.expectation.reason!r} → {a.detail}"
            )
        pytest.fail("\n".join(lines))
