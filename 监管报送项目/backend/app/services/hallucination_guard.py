from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping

from pydantic import BaseModel


VERIFIED = "VERIFIED"
PARTIAL = "PARTIAL"
UNVERIFIED = "UNVERIFIED"
RULE_BASED = "RULE_BASED"

_REVIEW_ACCEPTED = {"ACCEPTED", "CORRECTED"}
_RULE_BASED_SOURCES = {"EXCEL_DIFF", "REVISION_TABLE", "RULE_BASED"}
_ACTION_GROUPS = (
    ("新增", "增加", "新设"),
    ("删除", "移除", "停报", "取消"),
    ("修改", "调整", "变更"),
)


class GroundingResult(BaseModel):
    status: str
    coverage: float
    matched_excerpt: str = ""


class HallucinationMetrics(BaseModel):
    total_signals: int = 0
    ai_signals: int = 0
    rule_based_signals: int = 0
    verified_signals: int = 0
    partial_signals: int = 0
    unverified_signals: int = 0
    isolated_signals: int = 0
    grounding_rate: float = 0.0
    suspected_hallucination_rate: float = 0.0
    isolation_rate: float = 0.0
    pending_review_signals: int = 0
    accepted_signals: int = 0
    rejected_signals: int = 0
    corrected_signals: int = 0
    human_acceptance_rate: float = 0.0


def classify_grounding(
    *,
    evidence_text: str,
    document_text: str,
    source_type: str = "LLM",
) -> GroundingResult:
    source = _normalize_source_type(source_type)
    if source in _RULE_BASED_SOURCES:
        return GroundingResult(status=RULE_BASED, coverage=1.0, matched_excerpt=evidence_text)

    evidence_normalized = _normalize_text(evidence_text)
    document_normalized = _normalize_text(document_text)
    if not evidence_normalized or not document_normalized:
        return GroundingResult(status=UNVERIFIED, coverage=0.0)

    if evidence_normalized in document_normalized:
        return GroundingResult(status=VERIFIED, coverage=1.0, matched_excerpt=evidence_text.strip())

    match = SequenceMatcher(None, evidence_normalized, document_normalized).find_longest_match()
    coverage = match.size / len(evidence_normalized)
    if _has_unsupported_action(evidence_normalized, document_normalized):
        coverage = min(coverage, 0.25)
    coverage = round(coverage, 4)
    matched_excerpt = document_normalized[match.b : match.b + match.size]
    if coverage >= 0.85:
        status = VERIFIED
    elif coverage >= 0.5:
        status = PARTIAL
    else:
        status = UNVERIFIED
    return GroundingResult(status=status, coverage=coverage, matched_excerpt=matched_excerpt)


def apply_grounding(signal: Any, document_text: str) -> Any:
    result = classify_grounding(
        evidence_text=str(getattr(signal, "evidence_text", "") or ""),
        document_text=document_text,
        source_type=str(getattr(signal, "source_type", "LLM") or "LLM"),
    )
    confidence = float(getattr(signal, "confidence", 0.7) or 0.0)
    if result.status == UNVERIFIED:
        confidence = min(confidence, 0.3)
    return signal.model_copy(
        update={
            "confidence": confidence,
            "evidence_verified": result.status in {VERIFIED, RULE_BASED},
            "grounding_status": result.status,
            "grounding_coverage": result.coverage,
            "matched_excerpt": result.matched_excerpt,
        }
    )


def is_signal_eligible_for_downstream(signal: Mapping[str, Any]) -> bool:
    # profiler 已精确匹配到 catalog item，匹配本身即为接地证明，直接放行。
    if signal.get("matched_item_code"):
        return True
    source = _normalize_source_type(str(signal.get("source_type", "LLM") or "LLM"))
    status = _grounding_status(signal)
    review_status = str(signal.get("human_review_status", "PENDING") or "PENDING").upper()
    return not (source == "LLM" and status == UNVERIFIED and review_status not in _REVIEW_ACCEPTED)


def summarize_signal_metrics(signals: list[Mapping[str, Any]]) -> HallucinationMetrics:
    metrics = HallucinationMetrics(total_signals=len(signals))
    for signal in signals:
        source = _normalize_source_type(str(signal.get("source_type", "LLM") or "LLM"))
        grounding_status = _grounding_status(signal)
        review_status = str(signal.get("human_review_status", "PENDING") or "PENDING").upper()

        if source in _RULE_BASED_SOURCES:
            metrics.rule_based_signals += 1
        else:
            metrics.ai_signals += 1
            if grounding_status == VERIFIED:
                metrics.verified_signals += 1
            elif grounding_status == PARTIAL:
                metrics.partial_signals += 1
            elif grounding_status == UNVERIFIED:
                metrics.unverified_signals += 1
                if review_status not in _REVIEW_ACCEPTED:
                    metrics.isolated_signals += 1

        if grounding_status in {PARTIAL, UNVERIFIED} and review_status == "PENDING":
            metrics.pending_review_signals += 1
        if review_status == "ACCEPTED":
            metrics.accepted_signals += 1
        elif review_status == "REJECTED":
            metrics.rejected_signals += 1
        elif review_status == "CORRECTED":
            metrics.corrected_signals += 1

    if metrics.ai_signals:
        metrics.grounding_rate = metrics.verified_signals / metrics.ai_signals
        metrics.suspected_hallucination_rate = (
            metrics.partial_signals + metrics.unverified_signals
        ) / metrics.ai_signals
        metrics.isolation_rate = metrics.isolated_signals / metrics.ai_signals
    reviewed = metrics.accepted_signals + metrics.rejected_signals + metrics.corrected_signals
    if reviewed:
        metrics.human_acceptance_rate = (metrics.accepted_signals + metrics.corrected_signals) / reviewed
    return metrics


def _grounding_status(signal: Mapping[str, Any]) -> str:
    status = str(signal.get("grounding_status", "") or "").upper()
    if status:
        return status
    source = _normalize_source_type(str(signal.get("source_type", "LLM") or "LLM"))
    if source in _RULE_BASED_SOURCES:
        return RULE_BASED
    return VERIFIED if bool(signal.get("evidence_verified", True)) else UNVERIFIED


def _normalize_source_type(source_type: str) -> str:
    return source_type.strip().upper() or "LLM"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _has_unsupported_action(evidence_text: str, document_text: str) -> bool:
    supported_action_found = False
    unsupported_action_found = False
    for group in _ACTION_GROUPS:
        evidence_actions = {keyword for keyword in group if keyword in evidence_text}
        if not evidence_actions:
            continue
        if any(keyword in document_text for keyword in group):
            supported_action_found = True
        else:
            unsupported_action_found = True
    return unsupported_action_found and not supported_action_found
