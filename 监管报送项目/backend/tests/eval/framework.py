"""轻量 LLM/规则 eval 框架。

定位
----
和 `tests/test_*.py` 的 **单元测试** 互补：
- 单元测试关心"函数返回值是否符合代码逻辑"
- Eval 关心"业务最终输出（change_signals / impact_items / 工单字段）是否符合业务事实"

每个 case 用 JSON 描述：
- `target`：走哪条业务路径（例如 `triplet_excel_diff`）
- `inputs`：路径需要的真实文件
- `expectations`：基于业务语义的断言（数量边界 / 必须包含 / 禁止出现 / 全集校验）

设计目标
--------
- 跑得快：默认走规则路径，不调 LLM
- 跑得稳：每次重跑结果一致
- 看得懂：失败时报告"哪条断言没满足 + 实际 signals 摘要"
- 可扩展：新增 target 只需在 `EVAL_TARGETS` 注册一个 executor

详细约定见 `tests/eval/README.md`。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ── 数据结构 ──────────────────────────────────────────────────────────


@dataclass
class Expectation:
    """单条业务断言。"""

    kind: str  # signal_count / must_contain / must_not_contain / all_signals_match
    spec: dict[str, Any]
    reason: str = ""


@dataclass
class EvalCase:
    """一条 eval 测试用例的完整描述。"""

    case_id: str
    description: str
    category: str  # rule_based | llm
    target: str  # 业务路径名，必须注册在 EVAL_TARGETS
    inputs: dict[str, Any]
    expectations: list[Expectation]
    tags: list[str] = field(default_factory=list)


@dataclass
class AssertionResult:
    """单条断言的判定结果。"""

    expectation: Expectation
    passed: bool
    detail: str = ""  # 失败时的诊断信息


@dataclass
class CaseResult:
    """整个 case 的跑分结果。"""

    case: EvalCase
    passed: bool
    assertions: list[AssertionResult]
    actual_signal_count: int
    actual_summary: list[dict[str, Any]]  # 前 N 条 signal 的精简摘要
    error: str | None = None  # 执行期异常（target executor 抛错）

    def fail_count(self) -> int:
        return sum(1 for a in self.assertions if not a.passed)


# ── 加载 ─────────────────────────────────────────────────────────────


def load_case(path: Path) -> EvalCase:
    """从 JSON 文件加载一个 EvalCase。"""

    raw = json.loads(path.read_text(encoding="utf-8"))
    expectations = [
        Expectation(kind=item["kind"], spec=item.get("spec", {}), reason=item.get("reason", ""))
        for item in raw.get("expectations", [])
    ]
    return EvalCase(
        case_id=raw["id"],
        description=raw.get("description", ""),
        category=raw.get("category", "rule_based"),
        target=raw["target"],
        inputs=raw.get("inputs", {}),
        expectations=expectations,
        tags=raw.get("tags", []),
    )


def list_cases(cases_dir: Path) -> list[EvalCase]:
    """枚举 cases 目录下所有 JSON case。"""

    if not cases_dir.exists():
        return []
    return sorted(
        (load_case(p) for p in cases_dir.glob("*.json")),
        key=lambda c: c.case_id,
    )


# ── 断言执行 ──────────────────────────────────────────────────────────


def _signal_haystack(signal: dict[str, Any]) -> str:
    """把一条 signal 的可搜索字段拼成一个长字符串，便于关键词匹配。"""
    parts = [
        signal.get("table_code", ""),
        signal.get("section_hint", ""),
        signal.get("indicator_hint", ""),
        signal.get("evidence_text", ""),
        signal.get("change_type", ""),
    ]
    return " | ".join(str(p) for p in parts)


def _check_signal_count(signals: list[dict], spec: dict) -> AssertionResult | None:
    n = len(signals)
    min_n = spec.get("min")
    max_n = spec.get("max")
    detail_bits = [f"actual={n}"]
    ok = True
    if min_n is not None:
        detail_bits.append(f"min={min_n}")
        if n < min_n:
            ok = False
    if max_n is not None:
        detail_bits.append(f"max={max_n}")
        if n > max_n:
            ok = False
    return AssertionResult(
        expectation=Expectation(kind="signal_count", spec=spec),
        passed=ok,
        detail=" ".join(detail_bits),
    )


def _check_must_contain(signals: list[dict], spec: dict, reason: str) -> AssertionResult:
    """spec 例：{"change_type": "DELETE", "keyword_any": ["资产支持证券"]}"""
    matched = [s for s in signals if _signal_matches(s, spec)]
    return AssertionResult(
        expectation=Expectation(kind="must_contain", spec=spec, reason=reason),
        passed=bool(matched),
        detail=f"hit={len(matched)}" + (f"; 期望: {reason}" if not matched and reason else ""),
    )


def _check_must_not_contain(signals: list[dict], spec: dict, reason: str) -> AssertionResult:
    matched = [s for s in signals if _signal_matches(s, spec)]
    return AssertionResult(
        expectation=Expectation(kind="must_not_contain", spec=spec, reason=reason),
        passed=not matched,
        detail=(
            f"违规命中 {len(matched)} 条: {[s.get('indicator_hint', '') for s in matched[:3]]}"
            if matched
            else "ok"
        ),
    )


def _check_all_signals_match(signals: list[dict], spec: dict) -> AssertionResult:
    """spec 例：{"field": "change_type", "in": ["DELETE", "MODIFY"]}"""
    field_name = spec["field"]
    allowed = set(spec.get("in", []))
    violations = [s for s in signals if s.get(field_name) not in allowed]
    return AssertionResult(
        expectation=Expectation(kind="all_signals_match", spec=spec),
        passed=not violations,
        detail=(
            f"违规 {len(violations)} 条，例如 {field_name}={violations[0].get(field_name)!r}"
            if violations
            else f"全部 {len(signals)} 条满足"
        ),
    )


def _signal_matches(signal: dict, spec: dict) -> bool:
    """一条 signal 是否匹配 must_contain/must_not_contain 的 spec。

    支持字段：
    - change_type：精确匹配
    - table_code：精确匹配
    - keyword：单关键词，必须出现在 haystack 中
    - keyword_any：任一关键词出现即可
    - keyword_all：所有关键词必须都出现
    - regex：正则
    """
    if "change_type" in spec and signal.get("change_type") != spec["change_type"]:
        return False
    if "table_code" in spec and signal.get("table_code") != spec["table_code"]:
        return False
    hay = _signal_haystack(signal)
    if "keyword" in spec and spec["keyword"] not in hay:
        return False
    if "keyword_any" in spec and not any(k in hay for k in spec["keyword_any"]):
        return False
    if "keyword_all" in spec and not all(k in hay for k in spec["keyword_all"]):
        return False
    if "regex" in spec and not re.search(spec["regex"], hay):
        return False
    return True


_ASSERT_DISPATCH: dict[str, Callable[..., AssertionResult | None]] = {
    "signal_count": lambda signals, spec, reason: _check_signal_count(signals, spec),
    "must_contain": _check_must_contain,
    "must_not_contain": _check_must_not_contain,
    "all_signals_match": lambda signals, spec, reason: _check_all_signals_match(signals, spec),
}


def evaluate(signals: list[dict], case: EvalCase) -> list[AssertionResult]:
    """对一组实际 signals 跑完所有 expectations。"""

    results: list[AssertionResult] = []
    for exp in case.expectations:
        fn = _ASSERT_DISPATCH.get(exp.kind)
        if fn is None:
            results.append(
                AssertionResult(
                    expectation=exp,
                    passed=False,
                    detail=f"未知断言类型 {exp.kind!r}",
                )
            )
            continue
        result = fn(signals, exp.spec, exp.reason)
        if result is None:
            continue
        # framework 内部断言生成时不带 reason，这里补一下方便报告
        result.expectation.reason = exp.reason or result.expectation.reason
        results.append(result)
    return results


# ── target executor 注册表 ─────────────────────────────────────────────


# Executor 签名：(inputs: dict) -> list[dict signal-like]
# signal-like = dict（含 table_code/change_type/indicator_hint/evidence_text 等字段）
EVAL_TARGETS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {}


def register_target(name: str):
    """装饰器：把一个 executor 注册到 EVAL_TARGETS。"""

    def decorator(fn: Callable[[dict[str, Any]], list[dict[str, Any]]]):
        EVAL_TARGETS[name] = fn
        return fn

    return decorator


# ── 主入口 ───────────────────────────────────────────────────────────


def run_case(case: EvalCase, max_summary: int = 5) -> CaseResult:
    """跑一个 case：调 executor → 评估 expectations → 汇总结果。"""

    executor = EVAL_TARGETS.get(case.target)
    if executor is None:
        return CaseResult(
            case=case,
            passed=False,
            assertions=[],
            actual_signal_count=0,
            actual_summary=[],
            error=f"未注册的 target: {case.target!r}（可用: {sorted(EVAL_TARGETS)}）",
        )

    try:
        signals = executor(case.inputs)
    except Exception as exc:  # pragma: no cover - 诊断路径
        return CaseResult(
            case=case,
            passed=False,
            assertions=[],
            actual_signal_count=0,
            actual_summary=[],
            error=f"{type(exc).__name__}: {exc}",
        )

    assertions = evaluate(signals, case)
    summary = [
        {
            "change_type": s.get("change_type"),
            "table_code": s.get("table_code"),
            "indicator_hint": s.get("indicator_hint", "")[:60],
        }
        for s in signals[:max_summary]
    ]
    return CaseResult(
        case=case,
        passed=all(a.passed for a in assertions) and not (case.expectations and not assertions),
        assertions=assertions,
        actual_signal_count=len(signals),
        actual_summary=summary,
        error=None,
    )
