"""把 CaseResult 渲染成人可读的报告。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .framework import CaseResult


def render_markdown(results: list[CaseResult], header: str = "") -> str:
    """生成 Markdown 报告（适合 commit / 贴评审 / CI artifact）。"""

    lines: list[str] = []
    title = header or "LLM/规则 Eval 报告"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    lines.append("## 总览")
    lines.append("")
    lines.append(f"- 总 case：**{total}**")
    lines.append(f"- 通过：**{passed}**")
    lines.append(f"- 失败：**{failed}**")
    lines.append("")

    lines.append("| Case | 状态 | 实际信号数 | 断言 通过/总 | 备注 |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        status = "✅" if r.passed else "❌"
        a_total = len(r.assertions)
        a_pass = sum(1 for a in r.assertions if a.passed)
        note = r.error if r.error else r.case.description[:40]
        lines.append(
            f"| {r.case.case_id} | {status} | {r.actual_signal_count} | {a_pass}/{a_total} | {note} |"
        )
    lines.append("")

    # 失败明细
    failed_results = [r for r in results if not r.passed]
    if failed_results:
        lines.append("## 失败明细")
        lines.append("")
        for r in failed_results:
            lines.append(f"### ❌ {r.case.case_id}")
            lines.append("")
            lines.append(f"- target: `{r.case.target}`")
            lines.append(f"- 描述：{r.case.description}")
            if r.error:
                lines.append(f"- **执行期错误**：`{r.error}`")
                lines.append("")
                continue
            lines.append(f"- 实际信号数：{r.actual_signal_count}")
            if r.actual_summary:
                lines.append("- 实际前几条 signal：")
                for s in r.actual_summary:
                    lines.append(
                        f"  - `{s['change_type']}` `{s['table_code']}` "
                        f"{s['indicator_hint']}"
                    )
            lines.append("")
            lines.append("**断言结果：**")
            lines.append("")
            for a in r.assertions:
                mark = "✅" if a.passed else "❌"
                kind = a.expectation.kind
                spec = a.expectation.spec
                reason = a.expectation.reason
                bits = [f"{mark} `{kind}`", f"spec=`{spec}`"]
                if reason:
                    bits.append(f"reason=`{reason}`")
                if a.detail:
                    bits.append(f"→ {a.detail}")
                lines.append("- " + "  ".join(bits))
            lines.append("")

    return "\n".join(lines) + "\n"


def write_report(results: list[CaseResult], out_path: Path) -> Path:
    """写到磁盘并返回路径。"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(results), encoding="utf-8")
    return out_path
