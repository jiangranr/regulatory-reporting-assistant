"""CLI：跑全套 eval case，输出终端摘要 + Markdown 报告。

用法：
    uv run python scripts/run_eval.py
    uv run python scripts/run_eval.py --out reports/eval-2026-05-26.md
    uv run python scripts/run_eval.py --filter g31

报告默认写到 `reports/eval-latest.md`（仓库已 ignore reports/）。
退出码：0 全过 / 1 有失败 / 2 框架错误。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让脚本能直接 `python scripts/run_eval.py` 跑（无需 PYTHONPATH=.）
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.eval import targets  # noqa: F401 - 触发 target 注册  # noqa: E402
from tests.eval.framework import list_cases, run_case  # noqa: E402
from tests.eval.reporter import render_markdown, write_report  # noqa: E402

CASES_DIR = ROOT / "tests" / "eval" / "cases"


def _filter_cases(cases, pattern: str | None):
    if not pattern:
        return cases
    return [c for c in cases if pattern.lower() in c.case_id.lower()]


def main() -> int:
    parser = argparse.ArgumentParser(description="跑监管报送项目的 LLM/规则 eval 套件")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "reports" / "eval-latest.md",
        help="Markdown 报告输出路径（默认 reports/eval-latest.md）",
    )
    parser.add_argument("--filter", default=None, help="按 case_id 子串过滤（不区分大小写）")
    parser.add_argument("--quiet", action="store_true", help="只输出总览，不打印每个 case 详情")
    args = parser.parse_args()

    cases = list_cases(CASES_DIR)
    cases = _filter_cases(cases, args.filter)
    if not cases:
        print(f"[!] 在 {CASES_DIR} 下未找到任何 case", file=sys.stderr)
        return 2

    results = []
    for case in cases:
        result = run_case(case)
        results.append(result)
        status = "✅" if result.passed else "❌"
        if not args.quiet:
            print(
                f"{status} {case.case_id:<36} "
                f"signals={result.actual_signal_count:<3} "
                f"assertions={sum(1 for a in result.assertions if a.passed)}"
                f"/{len(result.assertions)}"
            )
            if result.error:
                print(f"   ⚠ 执行期错误: {result.error}")
            elif not result.passed:
                for a in result.assertions:
                    if a.passed:
                        continue
                    print(
                        f"   ❌ {a.expectation.kind} {a.expectation.spec} "
                        f"→ {a.detail}"
                    )

    out_path = write_report(results, args.out)
    passed = sum(1 for r in results if r.passed)
    print()
    print(f"总计 {len(results)} 个 case：{passed} 通过 / {len(results) - passed} 失败")
    print(f"Markdown 报告：{out_path}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())


# 简单自测，确保 render_markdown 可独立导入
_ = render_markdown
