from app.services.hallucination_guard import (
    RULE_BASED,
    UNVERIFIED,
    VERIFIED,
    PARTIAL,
    classify_grounding,
    is_signal_eligible_for_downstream,
    summarize_signal_metrics,
)


def test_classify_grounding_marks_exact_llm_evidence_verified():
    result = classify_grounding(
        evidence_text="本期新增绿色债券投资余额字段。",
        document_text="监管通知：本期新增绿色债券投资余额字段。请按季报送。",
        source_type="LLM",
    )

    assert result.status == VERIFIED
    assert result.coverage == 1.0
    assert result.matched_excerpt == "本期新增绿色债券投资余额字段。"


def test_classify_grounding_marks_partially_supported_llm_evidence_for_review():
    result = classify_grounding(
        evidence_text="本期新增绿色债券投资余额字段，并删除旧口径。",
        document_text="监管通知：本期新增绿色债券投资余额字段。请按季报送。",
        source_type="LLM",
    )

    assert result.status == PARTIAL
    assert 0.5 <= result.coverage < 0.85


def test_classify_grounding_isolates_unsupported_llm_evidence():
    result = classify_grounding(
        evidence_text="本期删除绿色债券投资余额字段。",
        document_text="监管通知：本期新增绿色债券投资余额字段。请按季报送。",
        source_type="LLM",
    )

    assert result.status == UNVERIFIED
    assert result.coverage < 0.5


def test_classify_grounding_keeps_rule_based_signal_separate_from_llm_metrics():
    result = classify_grounding(
        evidence_text="Excel 差异：新增 C08 列",
        document_text="",
        source_type="EXCEL_DIFF",
    )

    assert result.status == RULE_BASED
    assert result.coverage == 1.0


def test_unverified_llm_signal_is_not_eligible_for_downstream_until_accepted():
    isolated = {
        "source_type": "LLM",
        "grounding_status": "UNVERIFIED",
        "human_review_status": "PENDING",
    }

    assert is_signal_eligible_for_downstream(isolated) is False
    assert is_signal_eligible_for_downstream({**isolated, "human_review_status": "ACCEPTED"}) is True


def test_summarize_signal_metrics_counts_llm_grounding_and_rule_based_sources():
    metrics = summarize_signal_metrics(
        [
            {"source_type": "LLM", "grounding_status": "VERIFIED", "human_review_status": "PENDING"},
            {"source_type": "LLM", "grounding_status": "PARTIAL", "human_review_status": "PENDING"},
            {"source_type": "LLM", "grounding_status": "UNVERIFIED", "human_review_status": "REJECTED"},
            {"source_type": "EXCEL_DIFF", "grounding_status": "RULE_BASED"},
        ]
    )

    assert metrics.total_signals == 4
    assert metrics.ai_signals == 3
    assert metrics.rule_based_signals == 1
    assert metrics.verified_signals == 1
    assert metrics.partial_signals == 1
    assert metrics.unverified_signals == 1
    assert metrics.isolated_signals == 1
    assert metrics.grounding_rate == 1 / 3
    assert metrics.suspected_hallucination_rate == 2 / 3
    assert metrics.isolation_rate == 1 / 3
    assert metrics.pending_review_signals == 1


def test_summarize_signal_metrics_releases_accepted_unverified_signal_from_isolation():
    metrics = summarize_signal_metrics(
        [
            {
                "source_type": "LLM",
                "grounding_status": "UNVERIFIED",
                "human_review_status": "ACCEPTED",
            }
        ]
    )

    assert metrics.unverified_signals == 1
    assert metrics.isolated_signals == 0
    assert metrics.isolation_rate == 0.0
