import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.db_models import (
    DocumentTaskProfile,
    DataFieldCatalog,
    DataSystemCatalog,
    RegClause,
    RegDocument,
    RegReportingChangeCandidate,
    RegReportingImpactItem,
    RegReportingObject,
    RegReportingItem,
    RegReportingRuleCard,
    RegReportingRuleCardConceptMap,
    RegConcept,
    RegTaskExecutionPlan,
    ReportingImpactReview,
    ReportingItemLineage,
    RegSemanticItem,
    RegTask,
    TicketDraft,
)
from app.models.enums import ActionTicketType, ResponsibleSystem, RiskLevel, TaskStatus
from app.models.schemas import (
    DocumentTaskProfileRead,
    ExecutionPlanFeedbackRequest,
    ExecutionPlanFeedbackResponse,
    ExecutionPlanRead,
    ExecutionPlanResponse,
    ImpactReviewResponse,
    ImpactReviewSaveRequest,
    ImpactReviewSaveResponse,
    ImpactAnalysisResponse,
    RegClauseRead,
    RegDocumentRead,
    ReportingChangeCandidateRead,
    ReportingImpactItemRead,
    ReportingLineageFieldRead,
    RegSemanticItemRead,
    RegTaskRead,
    RuleCardRead,
    TableChangeSignalRead,
    TaskWorkflowResponse,
    TicketDraftRead,
    WorkflowStepRead,
)
from app.services.change_severity_classifier import classify_change
from app.services.reporting_change_extractor import extract_reporting_changes, signals_to_changes
from app.services.reporting_change_extractor import ReportingChangeDraft
from app.services.reporting_impact_analyzer import ReportingImpactDraft, analyze_reporting_impacts
from app.services.reporting_catalog_loader import load_catalog_from_db
from app.services.reporting_item_scope import filter_analysis_items
from app.services.reporting_ticket_generator import (
    ChildTicketPlan,
    ParentTicketPlan,
    TicketPlan,
    build_ticket_plan,
    generate_reporting_ticket_markdown,
)
from app.services.impact_review_service import (
    SYSTEM_LABELS,
    build_baseline_from_impacts,
    compute_stats,
    dump_review_content,
    now_utc,
    parse_review_content,
    reset_to_baseline,
    selected_fields_by_system,
)
from app.services.ticket_card_builder import TicketTaskCard, _ACTION_CARD_SPECS
from app.services.ticket_execution_planner import (
    ChildTicketContext,
    ExecutionPlannerInput,
    ParentTicketContext,
    RegulatoryDocumentContext,
    generate_execution_plan,
)
from app.services.ticket_quality_checker import check_ticket_card_quality
from app.models.schemas import TicketPlanResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/from-document/{document_id}", response_model=RegTaskRead, status_code=status.HTTP_201_CREATED)
def create_task_from_document(document_id: int, session: Session = Depends(get_session)) -> RegTask:
    document = session.get(RegDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    task = RegTask(
        document_id=document.id or 0,
        title=f"{document.title}规则加工任务",
        risk_level=RiskLevel.HIGH,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[RegTaskRead])
def list_tasks(session: Session = Depends(get_session)) -> list[RegTask]:
    return list(session.exec(select(RegTask).order_by(RegTask.created_at.desc())).all())


@router.get("/{task_id}", response_model=RegTaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)) -> RegTask:
    task = session.get(RegTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/workflow", response_model=TaskWorkflowResponse)
def get_task_workflow(task_id: int, session: Session = Depends(get_session)) -> TaskWorkflowResponse:
    task = _get_task_or_404(task_id, session)
    document = session.get(RegDocument, task.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    clauses = list(session.exec(select(RegClause).where(RegClause.document_id == document.id)).all())
    clause_ids = [clause.id for clause in clauses if clause.id is not None]
    semantic_items = _load_semantic_items(clause_ids, session)
    impacts = _load_impact_items(task_id, session)
    reporting_candidates = _load_reporting_candidates(task_id, session)
    lineage_candidates = _load_lineage_candidates(impacts, session)
    field_mappings = _load_field_mappings(reporting_candidates, session)
    rule_cards = _load_rule_cards(task, document, session)
    tickets = list(session.exec(select(TicketDraft).where(TicketDraft.task_id == task_id)).all())
    profile = session.exec(
        select(DocumentTaskProfile)
        .where(DocumentTaskProfile.document_id == document.id)
        .order_by(DocumentTaskProfile.created_at.desc())
    ).first()

    return TaskWorkflowResponse(
        task=RegTaskRead.model_validate(task),
        document=RegDocumentRead.model_validate(document),
        document_profile=_profile_read(profile) if profile else None,
        steps=_build_workflow_steps(document, clauses, semantic_items, impacts, rule_cards, tickets),
        clauses=[RegClauseRead.model_validate(clause) for clause in clauses],
        semantic_items=[RegSemanticItemRead.model_validate(item) for item in semantic_items],
        field_mappings=field_mappings,
        reporting_candidates=reporting_candidates,
        lineage_candidates=lineage_candidates,
        impact_items=impacts,
        rule_cards=rule_cards,
        ticket_drafts=[TicketDraftRead.model_validate(ticket) for ticket in tickets],
    )


def _profile_read(profile: DocumentTaskProfile) -> DocumentTaskProfileRead:
    return DocumentTaskProfileRead(
        id=profile.id,
        document_id=profile.document_id,
        document_type=profile.document_type or "",
        affected_table_codes=_load_json_list(profile.affected_table_codes),
        change_signals=_load_change_signals(profile.change_signals),
        in_scope_tables=_load_json_list(profile.in_scope_tables),
        out_of_scope_tables=_load_json_list(profile.out_of_scope_tables),
        suggested_route=profile.suggested_route,
        should_create_task=profile.should_create_task,
        confidence_score=profile.confidence_score,
        reason=profile.reason or "",
        evidence_text=profile.evidence_text or "",
        llm_model=profile.llm_model or "",
        review_status=profile.review_status or "PENDING",
        created_at=profile.created_at,
    )


def _load_json_list(value: str) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _load_change_signals(value: str) -> list[TableChangeSignalRead]:
    try:
        raw = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    signals = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            signals.append(TableChangeSignalRead(**item))
        except Exception:
            continue
    return signals


@router.post("/{task_id}/analyze-impact", response_model=ImpactAnalysisResponse)
def analyze_task_impact(task_id: int, session: Session = Depends(get_session)) -> ImpactAnalysisResponse:
    task = _get_task_or_404(task_id, session)
    document = session.get(RegDocument, task.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 读路径走 DB：保证影响分析看到的指标颗粒度和血缘和"字段定位"页一致。
    # 不要回退到 build_1104_seed_catalog —— 那样会让 bootstrap 未执行的环境静默吃旧数据。
    seed = load_catalog_from_db(session)

    # 优先使用文档画像中的 change_signals（1104指标变更扫描结果）
    profile = session.exec(
        select(DocumentTaskProfile)
        .where(DocumentTaskProfile.document_id == document.id)
        .order_by(DocumentTaskProfile.created_at.desc())
    ).first()

    if profile and profile.change_signals and profile.change_signals != "[]":
        raw_signals = json.loads(profile.change_signals)
        changes = signals_to_changes(raw_signals, seed.reporting_items)
    else:
        # 兜底：关键词匹配
        changes = extract_reporting_changes(document.parsed_text)

    impacts = analyze_reporting_impacts(changes, seed)
    _replace_reporting_candidates(task_id, changes, session)
    _replace_reporting_impacts(task_id, impacts, session)

    task.status = TaskStatus.IMPACT_ANALYZED
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    return ImpactAnalysisResponse(task_id=task_id, impacts=[_impact_read_from_draft(item) for item in impacts])


@router.post("/{task_id}/generate-ticket", response_model=TicketPlanResponse)
def generate_task_ticket(task_id: int, session: Session = Depends(get_session)) -> TicketPlanResponse:
    """
    生成母单 + 子单：
      1. 加载/补齐影响项与变更候选
      2. 调用 classify_change 决定母单类型 + 严重等级
      3. build_ticket_plan 展开子单
      4. 母单先落库拿到 id，再把子单的 parent_ticket_id 指向它，一并落库
    """
    task = _get_task_or_404(task_id, session)
    document = session.get(RegDocument, task.document_id)
    document_text = document.parsed_text if document else ""

    impacts = _load_impact_items(task_id, session)
    if not impacts:
        changes = extract_reporting_changes(document_text)
        draft_impacts = analyze_reporting_impacts(changes, load_catalog_from_db(session))
        _replace_reporting_candidates(task_id, changes, session)
        _replace_reporting_impacts(task_id, draft_impacts, session)
        impacts = [_impact_read_from_draft(item) for item in draft_impacts]

    impact_drafts = _enrich_impact_drafts_with_catalog(
        [_impact_draft_from_read(item) for item in impacts],
        session,
    )
    change_drafts = _load_change_drafts(task_id, session) or extract_reporting_changes(document_text)
    confirmed_review = _load_confirmed_impact_review(task_id, session)
    if confirmed_review is not None:
        return _generate_review_ticket_plan(
            task=task,
            document_text=document_text,
            review=parse_review_content(confirmed_review.review_content),
            impact_drafts=impact_drafts,
            change_drafts=change_drafts,
            session=session,
        )
    existing_report_codes = _load_existing_report_codes(session)

    classification = classify_change(
        changes=change_drafts,
        impacts=impact_drafts,
        document_text=document_text,
        existing_report_codes=existing_report_codes,
    )
    rule_cards_by_key = _build_rule_cards_lookup(impact_drafts, session)
    # historical_cases 现阶段是 stub（W2 后改为真实决策档案查询）
    from app.services.decision_archive_service import search_similar_decisions

    historical_cases_by_key = search_similar_decisions(
        impact_drafts,
        session=session,
        exclude_task_id=task_id,
    )
    plan = build_ticket_plan(
        classification,
        impact_drafts,
        task.title,
        rule_cards_by_key=rule_cards_by_key,
        historical_cases_by_key=historical_cases_by_key,
        document_text=document_text,
    )

    # 清掉旧的工单草稿，重新落本次生成的母子单
    for old in session.exec(select(TicketDraft).where(TicketDraft.task_id == task_id)).all():
        session.delete(old)
    session.flush()

    parent_row = _persist_parent_ticket(task_id, plan.parent, session)
    child_rows = [
        _persist_child_ticket(task_id, parent_row.id, child, session)
        for child in plan.children
    ]

    task.status = TaskStatus.TICKET_GENERATED
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(parent_row)
    for row in child_rows:
        session.refresh(row)

    return TicketPlanResponse(
        parent=TicketDraftRead.model_validate(parent_row),
        children=[TicketDraftRead.model_validate(row) for row in child_rows],
    )


@router.get("/{task_id}/impact-review", response_model=ImpactReviewResponse)
def get_impact_review(task_id: int, session: Session = Depends(get_session)) -> ImpactReviewResponse:
    _get_task_or_404(task_id, session)
    row = _get_or_create_impact_review(task_id, session)
    review = parse_review_content(row.review_content)
    baseline = parse_review_content(row.ai_baseline_content)
    return ImpactReviewResponse(
        status=row.status,
        review=review,
        ai_baseline=baseline,
        stats=compute_stats(review),
    )


@router.put("/{task_id}/impact-review", response_model=ImpactReviewSaveResponse)
def save_impact_review(
    task_id: int,
    payload: ImpactReviewSaveRequest,
    session: Session = Depends(get_session),
) -> ImpactReviewSaveResponse:
    _get_task_or_404(task_id, session)
    row = _get_or_create_impact_review(task_id, session)
    row.review_content = dump_review_content(payload.review)
    row.status = "SAVED"
    row.updated_at = now_utc()
    session.add(row)
    session.commit()
    session.refresh(row)
    return ImpactReviewSaveResponse(ok=True, updated_at=row.updated_at)


@router.post("/{task_id}/impact-review/reset", response_model=ImpactReviewResponse)
def reset_impact_review(task_id: int, session: Session = Depends(get_session)) -> ImpactReviewResponse:
    _get_task_or_404(task_id, session)
    row = _get_or_create_impact_review(task_id, session)
    baseline = parse_review_content(row.ai_baseline_content)
    review = reset_to_baseline(baseline)
    row.review_content = dump_review_content(review)
    row.status = "EDITING"
    row.confirmed_at = None
    row.updated_at = now_utc()
    session.add(row)
    session.commit()
    session.refresh(row)
    return ImpactReviewResponse(
        status=row.status,
        review=review,
        ai_baseline=baseline,
        stats=compute_stats(review),
    )


@router.post("/{task_id}/impact-review/confirm", response_model=TicketPlanResponse)
def confirm_impact_review(
    task_id: int,
    payload: ImpactReviewSaveRequest | None = None,
    session: Session = Depends(get_session),
) -> TicketPlanResponse:
    task = _get_task_or_404(task_id, session)
    document = session.get(RegDocument, task.document_id)
    document_text = document.parsed_text if document else ""
    row = _get_or_create_impact_review(task_id, session)
    review = payload.review if payload is not None else parse_review_content(row.review_content)
    row.review_content = dump_review_content(review)
    row.status = "CONFIRMED"
    row.confirmed_at = now_utc()
    row.updated_at = row.confirmed_at
    session.add(row)

    impacts = _load_impact_items(task_id, session)
    if not impacts:
        changes = extract_reporting_changes(document_text)
        draft_impacts = analyze_reporting_impacts(changes, load_catalog_from_db(session))
        _replace_reporting_candidates(task_id, changes, session)
        _replace_reporting_impacts(task_id, draft_impacts, session)
        impacts = [_impact_read_from_draft(item) for item in draft_impacts]
    impact_drafts = _enrich_impact_drafts_with_catalog(
        [_impact_draft_from_read(item) for item in impacts],
        session,
    )
    change_drafts = _load_change_drafts(task_id, session) or extract_reporting_changes(document_text)
    return _generate_review_ticket_plan(
        task=task,
        document_text=document_text,
        review=review,
        impact_drafts=impact_drafts,
        change_drafts=change_drafts,
        session=session,
    )


def _get_or_create_impact_review(task_id: int, session: Session) -> ReportingImpactReview:
    row = session.exec(
        select(ReportingImpactReview).where(ReportingImpactReview.task_id == task_id)
    ).first()
    if row is not None:
        return row
    baseline = build_baseline_from_impacts(_load_impact_items(task_id, session))
    row = ReportingImpactReview(
        task_id=task_id,
        status="EDITING",
        review_content=dump_review_content(baseline),
        ai_baseline_content=dump_review_content(baseline),
        updated_at=now_utc(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _load_confirmed_impact_review(task_id: int, session: Session) -> ReportingImpactReview | None:
    return session.exec(
        select(ReportingImpactReview).where(
            ReportingImpactReview.task_id == task_id,
            ReportingImpactReview.status == "CONFIRMED",
        )
    ).first()


def _generate_review_ticket_plan(
    *,
    task: RegTask,
    document_text: str,
    review: dict,
    impact_drafts: list[ReportingImpactDraft],
    change_drafts: list[ReportingChangeDraft],
    session: Session,
) -> TicketPlanResponse:
    task_id = task.id or 0
    existing_report_codes = _load_existing_report_codes(session)
    classification = classify_change(
        changes=change_drafts,
        impacts=impact_drafts,
        document_text=document_text,
        existing_report_codes=existing_report_codes,
    )
    rule_cards_by_key = _build_rule_cards_lookup(impact_drafts, session)
    parent_plan = build_ticket_plan(
        classification,
        impact_drafts,
        task.title,
        rule_cards_by_key=rule_cards_by_key,
        historical_cases_by_key={},
        document_text=document_text,
    ).parent

    for old in session.exec(select(TicketDraft).where(TicketDraft.task_id == task_id)).all():
        session.delete(old)
    session.flush()

    parent_row = _persist_parent_ticket(task_id, parent_plan, session)
    grouped = selected_fields_by_system(review)
    child_rows = [
        _persist_review_system_child_ticket(task_id, parent_row.id, group, session)
        for _, group in sorted(grouped.items())
    ]
    if len(grouped) >= 2:
        child_rows.append(
            _persist_review_support_child_ticket(
                task_id,
                parent_row.id,
                ActionTicketType.TEST_ACCEPTANCE,
                grouped,
                session,
            )
        )
        child_rows.append(
            _persist_review_support_child_ticket(
                task_id,
                parent_row.id,
                ActionTicketType.ARCHIVE_REVIEW,
                grouped,
                session,
            )
        )

    task.status = TaskStatus.TICKET_GENERATED
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(parent_row)
    for row in child_rows:
        session.refresh(row)

    return TicketPlanResponse(
        parent=TicketDraftRead.model_validate(parent_row),
        children=[TicketDraftRead.model_validate(row) for row in child_rows],
    )


def _persist_review_system_child_ticket(
    task_id: int,
    parent_id: int | None,
    group: dict,
    session: Session,
) -> TicketDraft:
    action_type = _action_type_for_system(group["responsible_system"])
    card = _review_group_card(action_type, group)
    quality = check_ticket_card_quality(card)
    row = TicketDraft(
        task_id=task_id,
        title=f"按系统处理｜{group['responsible_system_zh']}",
        content=_render_review_child_markdown(card, group.get("business_notes", [])),
        parent_ticket_id=parent_id,
        ticket_role="CHILD",
        action_ticket_type=action_type.value,
        owner_role=card.owner_role.value,
        executor_role=card.executor_role.value,
        depends_on_lineage=card.action_type in {ActionTicketType.DATA_MAPPING, ActionTicketType.REPORT_PROCESSING},
        business_signoff_required=bool(group.get("business_notes")),
        related_impact_codes=json.dumps(_all_group_item_codes(group), ensure_ascii=False),
        summary=card.summary,
        responsible_system=card.responsible_system.value,
        affected_systems=json.dumps([card.responsible_system.value], ensure_ascii=False),
        affected_assets=json.dumps(card.affected_assets, ensure_ascii=False),
        business_note="\n".join(group.get("business_notes", [])),
        must_do=json.dumps(card.must_do, ensure_ascii=False),
        must_confirm=json.dumps(card.must_confirm, ensure_ascii=False),
        output_artifacts=json.dumps(card.output_artifacts, ensure_ascii=False),
        acceptance_criteria_structured=json.dumps(card.acceptance_criteria, ensure_ascii=False),
        blockers=json.dumps(card.blockers, ensure_ascii=False),
        evidence_refs=json.dumps(card.evidence_refs, ensure_ascii=False),
        historical_cases="[]",
        quality_score=quality.score,
        quality_flags=json.dumps(quality.flags, ensure_ascii=False),
        status="DRAFT",
    )
    session.add(row)
    session.flush()
    return row


def _persist_review_support_child_ticket(
    task_id: int,
    parent_id: int | None,
    action_type: ActionTicketType,
    grouped: dict[str, dict],
    session: Session,
) -> TicketDraft:
    system_code = (
        ResponsibleSystem.TEST_ACCEPTANCE
        if action_type == ActionTicketType.TEST_ACCEPTANCE
        else ResponsibleSystem.KNOWLEDGE_ARCHIVE
    )
    support_group = {
        "responsible_system": system_code.value,
        "responsible_system_zh": SYSTEM_LABELS[system_code.value],
        "items": [
            item
            for group in grouped.values()
            for item in group.get("items", [])
        ],
        "business_notes": [
            note
            for group in grouped.values()
            for note in group.get("business_notes", [])
        ],
    }
    card = _review_group_card(action_type, support_group)
    quality = check_ticket_card_quality(card)
    row = TicketDraft(
        task_id=task_id,
        title=f"按系统处理｜{support_group['responsible_system_zh']}",
        content=_render_review_child_markdown(card, support_group.get("business_notes", [])),
        parent_ticket_id=parent_id,
        ticket_role="CHILD",
        action_ticket_type=action_type.value,
        owner_role=card.owner_role.value,
        executor_role=card.executor_role.value,
        business_signoff_required=action_type == ActionTicketType.TEST_ACCEPTANCE,
        closure_review_required=action_type == ActionTicketType.ARCHIVE_REVIEW,
        related_impact_codes=json.dumps(_all_group_item_codes(support_group), ensure_ascii=False),
        summary=card.summary,
        responsible_system=card.responsible_system.value,
        affected_systems=json.dumps([card.responsible_system.value], ensure_ascii=False),
        affected_assets=json.dumps(card.affected_assets, ensure_ascii=False),
        business_note="\n".join(dict.fromkeys(support_group.get("business_notes", []))),
        must_do=json.dumps(card.must_do, ensure_ascii=False),
        must_confirm=json.dumps(card.must_confirm, ensure_ascii=False),
        output_artifacts=json.dumps(card.output_artifacts, ensure_ascii=False),
        acceptance_criteria_structured=json.dumps(card.acceptance_criteria, ensure_ascii=False),
        blockers=json.dumps(card.blockers, ensure_ascii=False),
        evidence_refs=json.dumps(card.evidence_refs, ensure_ascii=False),
        quality_score=quality.score,
        quality_flags=json.dumps(quality.flags, ensure_ascii=False),
        status="DRAFT",
    )
    session.add(row)
    session.flush()
    return row


def _review_group_card(action_type: ActionTicketType, group: dict) -> TicketTaskCard:
    spec = _ACTION_CARD_SPECS[action_type]
    fields = [
        field
        for item in group.get("items", [])
        for field in item.get("fields", [])
    ]
    notes = list(dict.fromkeys(group.get("business_notes", [])))
    summary = (
        f"{group['responsible_system_zh']}需处理 {len(group.get('items', []))} 个报送项、"
        f"{len(fields)} 个字段。"
    )
    if notes:
        summary += f" 业务备注：{notes[0]}"
    return TicketTaskCard(
        action_type=action_type,
        owner_role=spec.owner_role,
        executor_role=spec.executor_role,
        responsible_system=ResponsibleSystem(group["responsible_system"]),
        summary=summary,
        affected_assets=_review_affected_assets(group),
        must_do=_review_must_do(action_type, fields),
        must_confirm=spec.must_confirm,
        output_artifacts=spec.output_artifacts,
        acceptance_criteria=spec.acceptance_criteria,
        blockers=[],
        evidence_refs=[
            {
                "type": "impact_review",
                "src": f"业务复核 · {group['responsible_system_zh']}",
                "text": f"业务确认纳入 {len(fields)} 个字段。",
            }
        ],
        historical_cases=[],
    )


def _review_affected_assets(group: dict) -> dict:
    reporting_items = []
    reporting_fields = []
    source_fields = []
    roles = []
    seen_items: set[str] = set()
    seen_fields: set[str] = set()
    for item in group.get("items", []):
        item_code = item.get("reporting_item_code") or ""
        if item_code and item_code not in seen_items:
            seen_items.add(item_code)
            reporting_items.append({"code": item_code, "name": item.get("reporting_item_name") or item_code})
        for field in item.get("fields", []):
            code = field.get("field_code") or ""
            if not code or code in seen_fields:
                continue
            seen_fields.add(code)
            role = field.get("lineage_role") or ""
            roles.append(role)
            target = reporting_fields if role == "REPORT_FIELD" else source_fields
            target.append({"code": code, "name": field.get("field_name") or code, "role": role})
    return {
        "reporting_items": reporting_items,
        "reporting_fields": reporting_fields,
        "source_fields": source_fields,
        "lineage_roles": list(dict.fromkeys([role for role in roles if role])),
    }


def _review_must_do(action_type: ActionTicketType, fields: list[dict]) -> list[str]:
    spec_items = _ACTION_CARD_SPECS[action_type].must_do[:4]
    field_codes = [str(field.get("field_code") or "").strip() for field in fields if field.get("field_code")]
    if field_codes:
        return [*spec_items, f"按业务复核结果处理字段：{', '.join(field_codes[:6])}。"]
    return spec_items


def _action_type_for_system(system_code: str) -> ActionTicketType:
    mapping = {
        ResponsibleSystem.REG_REPORTING_SYSTEM.value: ActionTicketType.SCOPE_CONFIRM,
        ResponsibleSystem.DATA_GOVERNANCE_PLATFORM.value: ActionTicketType.DATA_MAPPING,
        ResponsibleSystem.DATA_MART_ETL.value: ActionTicketType.REPORT_PROCESSING,
        ResponsibleSystem.SOURCE_SYSTEM.value: ActionTicketType.SOURCE_SYSTEM_CHANGE,
        ResponsibleSystem.DATA_QUALITY_PLATFORM.value: ActionTicketType.VALIDATION_RULE,
        ResponsibleSystem.TEST_ACCEPTANCE.value: ActionTicketType.TEST_ACCEPTANCE,
        ResponsibleSystem.KNOWLEDGE_ARCHIVE.value: ActionTicketType.ARCHIVE_REVIEW,
    }
    return mapping.get(system_code, ActionTicketType.DATA_MAPPING)


def _render_review_child_markdown(card: TicketTaskCard, notes: list[str]) -> str:
    lines = [
        f"# {card.responsible_system.value} 系统子单",
        "",
        f"## 摘要\n{card.summary}",
        "",
        "## 必做动作",
        *[f"- {item}" for item in card.must_do],
    ]
    if notes:
        lines.extend(["", "## 业务备注", *[f"- {note}" for note in dict.fromkeys(notes)]])
    return "\n".join(lines)


def _all_group_item_codes(group: dict) -> list[str]:
    return list(dict.fromkeys(
        item.get("reporting_item_code")
        for item in group.get("items", [])
        if item.get("reporting_item_code")
    ))


def _persist_parent_ticket(
    task_id: int, parent: ParentTicketPlan, session: Session
) -> TicketDraft:
    row = TicketDraft(
        task_id=task_id,
        title=parent.title,
        content=parent.content_markdown,
        ticket_role="PARENT",
        change_ticket_type=parent.change_ticket_type.value,
        action_ticket_type="",
        severity_level=parent.severity.level.value,
        severity_score=parent.severity.score,
        severity_signals=json.dumps(parent.severity.triggered_signals, ensure_ascii=False),
        severity_forced_reason=parent.severity.forced_reason or "",
        owner_role=parent.overall_owner_role.value,
        executor_role="",
        depends_on_lineage=False,
        business_signoff_required=False,
        closure_review_required=parent.closure_review_required,
        related_impact_codes="[]",
        status="DRAFT",
    )
    session.add(row)
    session.flush()
    return row


def _persist_child_ticket(
    task_id: int,
    parent_id: int | None,
    child: ChildTicketPlan,
    session: Session,
) -> TicketDraft:
    """落库子单。

    Task 4 升级：子单可能携带结构化任务卡 (child.card) + 质量评分 (child.quality)，
    把它们 JSON 序列化进 TicketDraft 新增字段；旧的 content Markdown 同步落库
    作为兼容回退视图，前端结构化字段优先、为空时回退 content。
    """
    card = child.card
    quality = child.quality

    has_card = card is not None
    has_quality = quality is not None

    row = TicketDraft(
        task_id=task_id,
        title=child.title,
        content=child.content_markdown,
        parent_ticket_id=parent_id,
        ticket_role="CHILD",
        change_ticket_type="",
        action_ticket_type=child.action_type.value,
        severity_level="",
        severity_score=0,
        owner_role=child.spec.owner_role.value,
        executor_role=child.spec.executor_role.value,
        depends_on_lineage=child.spec.depends_on_lineage,
        business_signoff_required=child.spec.business_signoff_required,
        closure_review_required=False,
        related_impact_codes=json.dumps(child.related_impact_codes, ensure_ascii=False),
        # 结构化任务卡字段（仅触发器路径有，固定矩阵/L1 兜底分支留空字符串保持向后兼容）
        summary=card.summary if has_card else "",
        responsible_system=card.responsible_system.value if has_card else "",
        affected_systems=(
            json.dumps([card.responsible_system.value], ensure_ascii=False)
            if has_card
            else "[]"
        ),
        affected_assets=(
            json.dumps(card.affected_assets, ensure_ascii=False) if has_card else "{}"
        ),
        must_do=(
            json.dumps(card.must_do, ensure_ascii=False) if has_card else "[]"
        ),
        must_confirm=(
            json.dumps(card.must_confirm, ensure_ascii=False) if has_card else "[]"
        ),
        output_artifacts=(
            json.dumps(card.output_artifacts, ensure_ascii=False) if has_card else "[]"
        ),
        acceptance_criteria_structured=(
            json.dumps(card.acceptance_criteria, ensure_ascii=False)
            if has_card
            else "[]"
        ),
        blockers=(
            json.dumps(card.blockers, ensure_ascii=False) if has_card else "[]"
        ),
        evidence_refs=(
            json.dumps(card.evidence_refs, ensure_ascii=False) if has_card else "[]"
        ),
        historical_cases=(
            json.dumps(card.historical_cases, ensure_ascii=False) if has_card else "[]"
        ),
        quality_score=quality.score if has_quality else 0,
        quality_flags=(
            json.dumps(quality.flags, ensure_ascii=False) if has_quality else "[]"
        ),
        status="DRAFT",
    )
    session.add(row)
    session.flush()
    return row


def _load_change_drafts(task_id: int, session: Session) -> list[ReportingChangeDraft]:
    rows = session.exec(
        select(RegReportingChangeCandidate).where(RegReportingChangeCandidate.task_id == task_id)
    ).all()
    return [
        ReportingChangeDraft(
            evidence_text=row.evidence_text or "",
            reporting_system_code=row.reporting_system_code,
            reporting_object_code=row.reporting_object_code,
            reporting_item_code=row.reporting_item_code,
            change_type=row.change_type,
            confidence_score=row.confidence_score,
        )
        for row in rows
    ]


def _load_existing_report_codes(session: Session) -> set[str]:
    rows = session.exec(select(RegReportingObject.object_code)).all()
    return {code for code in rows if code}


def _get_task_or_404(task_id: int, session: Session) -> RegTask:
    task = session.get(RegTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _load_impact_items(task_id: int, session: Session) -> list[ReportingImpactItemRead]:
    rows = session.exec(
        select(RegReportingImpactItem).where(RegReportingImpactItem.task_id == task_id)
    ).all()
    return [
        ReportingImpactItemRead(
            reporting_item_code=row.reporting_item_code,
            impact_type=row.impact_type,
            impacted_reporting_field=row.impacted_reporting_field,
            impacted_source_fields=json.loads(row.impacted_source_fields or "[]"),
            impacted_lineage_roles=json.loads(row.impacted_lineage_roles or "[]"),
            impact_reason=row.impact_reason,
            recommended_action=row.recommended_action,
            confidence_level=row.confidence_level,
            risk_level=row.risk_level,
        )
        for row in rows
    ]


def _load_reporting_candidates(task_id: int, session: Session) -> list[ReportingChangeCandidateRead]:
    rows = session.exec(
        select(RegReportingChangeCandidate).where(RegReportingChangeCandidate.task_id == task_id)
    ).all()
    return [
        ReportingChangeCandidateRead(
            reporting_system_code=row.reporting_system_code,
            reporting_object_code=row.reporting_object_code,
            reporting_item_code=row.reporting_item_code,
            change_type=row.change_type,
            evidence_text=row.evidence_text,
            confidence_score=row.confidence_score,
            review_status=row.review_status,
        )
        for row in rows
    ]


def _load_lineage_candidates(
    impacts: list[ReportingImpactItemRead],
    session: Session,
) -> list[ReportingLineageFieldRead]:
    field_codes = {field_code for impact in impacts for field_code in impact.impacted_source_fields}
    if not field_codes:
        return []
    fields = session.exec(select(DataFieldCatalog).where(DataFieldCatalog.field_code.in_(field_codes))).all()
    role_by_field = {
        field_code: role
        for impact in impacts
        for field_code, role in zip(impact.impacted_source_fields, impact.impacted_lineage_roles, strict=False)
    }
    return [
        ReportingLineageFieldRead(
            field_code=field.field_code,
            field_name=field.field_name,
            table_name=field.table_name,
            column_name=field.column_name,
            data_type=field.data_type,
            business_meaning=field.business_meaning,
            owner_team=field.owner_team,
            lineage_role=role_by_field.get(field.field_code, "SOURCE_FIELD"),
        )
        for field in fields
    ]


def _load_field_mappings(
    candidates: list[ReportingChangeCandidateRead],
    session: Session,
) -> list[dict]:
    """
    为变更候选中涉及的报表对象，加载已有字段血缘映射。
    路径：reporting_candidates.object_code
       → reg_reporting_objects.id
       → reg_reporting_items.reporting_object_id
       → reporting_item_lineage.reporting_item_id
       → data_field_catalog.id / data_system_catalog.id
    """
    object_codes = list({c.reporting_object_code for c in candidates})
    if not object_codes:
        return []

    # Step 1: 取 reporting objects
    objects = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code.in_(object_codes))
    ).all()
    object_id_to_code: dict[int, str] = {
        obj.id: obj.object_code for obj in objects if obj.id is not None
    }
    if not object_id_to_code:
        return []

    # Step 2: 取该 object 下所有 reporting items
    items = filter_analysis_items(session.exec(
        select(RegReportingItem).where(
            RegReportingItem.reporting_object_id.in_(list(object_id_to_code.keys()))
        )
    ).all())
    item_id_to_item: dict[int, RegReportingItem] = {
        item.id: item for item in items if item.id is not None
    }
    if not item_id_to_item:
        return []

    # Step 3: 取血缘记录
    lineages = session.exec(
        select(ReportingItemLineage).where(
            ReportingItemLineage.reporting_item_id.in_(list(item_id_to_item.keys()))
        )
    ).all()
    if not lineages:
        return []

    # Step 4: 取字段目录
    field_ids = {lin.data_field_id for lin in lineages}
    fields = session.exec(
        select(DataFieldCatalog).where(DataFieldCatalog.id.in_(field_ids))
    ).all()
    field_map: dict[int, DataFieldCatalog] = {f.id: f for f in fields if f.id is not None}

    # Step 5: 取来源系统
    system_ids = {f.data_system_id for f in fields if f.data_system_id}
    systems = session.exec(
        select(DataSystemCatalog).where(DataSystemCatalog.id.in_(system_ids))
    ).all()
    system_map: dict[int, DataSystemCatalog] = {s.id: s for s in systems if s.id is not None}

    # Step 6: 组装结果
    result: list[dict] = []
    for lin in lineages:
        item = item_id_to_item.get(lin.reporting_item_id)
        field = field_map.get(lin.data_field_id)
        if not item or not field:
            continue
        system = system_map.get(field.data_system_id) if field.data_system_id else None
        result.append({
            "object_code": object_id_to_code.get(item.reporting_object_id, ""),
            "item_code": item.item_code,
            "regulatory_term": item.item_name,
            "field_code": field.field_code,
            "field_name": field.field_name,
            "column_name": field.column_name,
            "table_name": field.table_name,
            "system_name": system.system_name if system else "",
            "system_code": system.system_code if system else "",
            "lineage_role": lin.lineage_role,
            "mapping_status": lin.mapping_status,
        })
    return result


def _replace_reporting_candidates(
    task_id: int,
    changes: list[ReportingChangeDraft],
    session: Session,
) -> None:
    for row in session.exec(
        select(RegReportingChangeCandidate).where(RegReportingChangeCandidate.task_id == task_id)
    ).all():
        session.delete(row)
    for change in changes:
        session.add(
            RegReportingChangeCandidate(
                task_id=task_id,
                reporting_system_code=change.reporting_system_code,
                reporting_object_code=change.reporting_object_code,
                reporting_item_code=change.reporting_item_code,
                change_type=change.change_type,
                evidence_text=change.evidence_text,
                confidence_score=change.confidence_score,
            )
        )


def _replace_reporting_impacts(
    task_id: int,
    impacts: list[ReportingImpactDraft],
    session: Session,
) -> None:
    for row in session.exec(
        select(RegReportingImpactItem).where(RegReportingImpactItem.task_id == task_id)
    ).all():
        session.delete(row)
    for impact in impacts:
        session.add(
            RegReportingImpactItem(
                task_id=task_id,
                reporting_item_code=impact.reporting_item_code,
                impact_type=impact.impact_type,
                impacted_reporting_field=impact.impacted_reporting_field,
                impacted_source_fields=json.dumps(impact.impacted_source_fields, ensure_ascii=False),
                impacted_lineage_roles=json.dumps(impact.impacted_lineage_roles, ensure_ascii=False),
                impact_reason=impact.impact_reason,
                recommended_action=impact.recommended_action,
                confidence_level=impact.confidence_level,
                risk_level=impact.risk_level,
            )
        )


def _impact_read_from_draft(impact: ReportingImpactDraft) -> ReportingImpactItemRead:
    return ReportingImpactItemRead(
        reporting_item_code=impact.reporting_item_code,
        impact_type=impact.impact_type,
        impacted_reporting_field=impact.impacted_reporting_field,
        impacted_source_fields=impact.impacted_source_fields,
        impacted_lineage_roles=impact.impacted_lineage_roles,
        impact_reason=impact.impact_reason,
        recommended_action=impact.recommended_action,
        ticket_parent_type=impact.ticket_parent_type,
        required_sub_ticket_types=impact.required_sub_ticket_types,
        conditional_sub_ticket_types=impact.conditional_sub_ticket_types,
        sub_ticket_triggers=impact.sub_ticket_triggers,
        confidence_level=impact.confidence_level,
        risk_level=impact.risk_level,
    )


def _impact_draft_from_read(impact: ReportingImpactItemRead) -> ReportingImpactDraft:
    return ReportingImpactDraft(
        reporting_item_code=impact.reporting_item_code,
        impact_type=impact.impact_type,
        impacted_reporting_field=impact.impacted_reporting_field,
        impacted_source_fields=impact.impacted_source_fields,
        impacted_lineage_roles=impact.impacted_lineage_roles,
        impact_reason=impact.impact_reason,
        recommended_action=impact.recommended_action,
        ticket_parent_type=impact.ticket_parent_type,
        required_sub_ticket_types=impact.required_sub_ticket_types,
        conditional_sub_ticket_types=impact.conditional_sub_ticket_types,
        sub_ticket_triggers=impact.sub_ticket_triggers,
        confidence_level=impact.confidence_level,
        risk_level=impact.risk_level,
    )


def _enrich_impact_drafts_with_catalog(
    impacts: list[ReportingImpactDraft],
    session: Session,
) -> list[ReportingImpactDraft]:
    """补齐工单展示需要的中文资产名称。

    影响项表只持久化技术编码；工单生成前从报送目录和字段目录回填中文名，
    让 ticket_drafts.affected_assets 能直接服务前端展示。
    """
    item_codes = {impact.reporting_item_code for impact in impacts if impact.reporting_item_code}
    field_codes = {
        field_code
        for impact in impacts
        for field_code in [impact.impacted_reporting_field, *impact.impacted_source_fields]
        if field_code
    }
    items = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code.in_(item_codes))
    ).all() if item_codes else []
    fields = session.exec(
        select(DataFieldCatalog).where(DataFieldCatalog.field_code.in_(field_codes))
    ).all() if field_codes else []
    item_name_by_code = {item.item_code: item.item_name for item in items}
    field_name_by_code = {field.field_code: field.field_name for field in fields}

    item_id_by_code = {item.item_code: item.id for item in items if item.id is not None}
    field_id_by_code = {field.field_code: field.id for field in fields if field.id is not None}
    lineage_role_by_pair: dict[tuple[int, int], str] = {}
    if item_id_by_code and field_id_by_code:
        lineages = session.exec(
            select(ReportingItemLineage).where(
                ReportingItemLineage.reporting_item_id.in_(list(item_id_by_code.values())),
                ReportingItemLineage.data_field_id.in_(list(field_id_by_code.values())),
            )
        ).all()
        lineage_role_by_pair = {
            (lineage.reporting_item_id, lineage.data_field_id): lineage.lineage_role
            for lineage in lineages
        }

    enriched: list[ReportingImpactDraft] = []
    for impact in impacts:
        item_id = item_id_by_code.get(impact.reporting_item_code)
        source_details = []
        for field_code in impact.impacted_source_fields:
            field_id = field_id_by_code.get(field_code)
            role = (
                lineage_role_by_pair.get((item_id, field_id), "")
                if item_id is not None and field_id is not None
                else ""
            )
            source_details.append({
                "code": field_code,
                "name": field_name_by_code.get(field_code, field_code),
                "role": role,
            })
        enriched.append(
            impact.model_copy(
                update={
                    "reporting_item_name": impact.reporting_item_name
                    or item_name_by_code.get(impact.reporting_item_code, impact.reporting_item_code),
                    "impacted_reporting_field_name": impact.impacted_reporting_field_name
                    or field_name_by_code.get(impact.impacted_reporting_field, impact.impacted_reporting_field),
                    "impacted_source_field_details": impact.impacted_source_field_details
                    or source_details,
                }
            )
        )
    return enriched


def _load_semantic_items(clause_ids: list[int], session: Session) -> list[RegSemanticItem]:
    if not clause_ids:
        return []
    return list(session.exec(select(RegSemanticItem).where(RegSemanticItem.clause_id.in_(clause_ids))).all())


def _build_rule_cards_lookup(
    impacts: list[ReportingImpactDraft], session: Session
) -> dict[str, list[dict]]:
    """为工单 markdown 渲染准备"报送项/对象 → 规则卡片"映射。

    Key 形如:
      - 'G31.PART_I.BOND_INVESTMENT_BALANCE' (指标级)
      - 'G31' (对象级,适用整张表)
    Value 是规则卡片的 dict 列表(已含 related_concept_codes)。
    """
    item_codes = {i.reporting_item_code for i in impacts if i.reporting_item_code}
    object_codes = {c.split(".")[0] for c in item_codes if "." in c}
    if not item_codes and not object_codes:
        return {}

    query = select(RegReportingRuleCard).where(RegReportingRuleCard.status == "ACTIVE")
    if item_codes and object_codes:
        query = query.where(
            (RegReportingRuleCard.reporting_item_code.in_(item_codes))
            | (
                (RegReportingRuleCard.reporting_object_code.in_(object_codes))
                & (RegReportingRuleCard.reporting_item_code.is_(None))
            )
        )
    elif item_codes:
        query = query.where(RegReportingRuleCard.reporting_item_code.in_(item_codes))
    else:
        query = query.where(
            (RegReportingRuleCard.reporting_object_code.in_(object_codes))
            & (RegReportingRuleCard.reporting_item_code.is_(None))
        )
    cards = list(session.exec(query).all())
    if not cards:
        return {}

    card_ids = [c.id for c in cards if c.id is not None]
    concept_rows = list(
        session.exec(
            select(RegReportingRuleCardConceptMap, RegConcept)
            .where(RegReportingRuleCardConceptMap.card_id.in_(card_ids))
            .where(RegConcept.id == RegReportingRuleCardConceptMap.concept_id)
        ).all()
    )
    related_by_card: dict[int, list[str]] = {}
    for mapping, concept in concept_rows:
        related_by_card.setdefault(mapping.card_id, []).append(concept.concept_code)

    lookup: dict[str, list[dict]] = {}
    for card in cards:
        payload = card.model_dump()
        payload["related_concept_codes"] = related_by_card.get(card.id or 0, [])
        key = card.reporting_item_code or card.reporting_object_code
        if not key:
            continue
        lookup.setdefault(key, []).append(payload)
    return lookup


def _load_rule_cards(task: RegTask, document: RegDocument, session: Session) -> list[RuleCardRead]:
    """Load 报送规则卡片 relevant to this task.

    Heuristic for P0: collect all impact items' reporting_object_code 和 reporting_item_code,
    然后查命中(同 item_code 或同 object_code 的对象级)卡片。L1 优先,排除 ARCHIVED。
    """
    impacts = list(
        session.exec(
            select(RegReportingImpactItem).where(RegReportingImpactItem.task_id == task.id)
        ).all()
    )
    item_codes = {impact.reporting_item_code for impact in impacts if impact.reporting_item_code}
    # item_code 形如 "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" 第一段即 object_code
    object_codes = {code.split(".")[0] for code in item_codes if "." in code}
    if not object_codes and not item_codes:
        return []

    query = select(RegReportingRuleCard).where(RegReportingRuleCard.status != "ARCHIVED")
    if item_codes and object_codes:
        query = query.where(
            (RegReportingRuleCard.reporting_item_code.in_(item_codes))
            | (
                (RegReportingRuleCard.reporting_object_code.in_(object_codes))
                & (RegReportingRuleCard.reporting_item_code.is_(None))
            )
        )
    elif item_codes:
        query = query.where(RegReportingRuleCard.reporting_item_code.in_(item_codes))
    else:
        query = query.where(
            (RegReportingRuleCard.reporting_object_code.in_(object_codes))
            & (RegReportingRuleCard.reporting_item_code.is_(None))
        )
    rows = list(session.exec(query).all())
    if not rows:
        return []

    card_ids = [row.id for row in rows if row.id is not None]
    concept_map_rows = list(
        session.exec(
            select(RegReportingRuleCardConceptMap, RegConcept)
            .where(RegReportingRuleCardConceptMap.card_id.in_(card_ids))
            .where(RegConcept.id == RegReportingRuleCardConceptMap.concept_id)
        ).all()
    )
    related_codes_by_card: dict[int, list[str]] = {}
    for mapping, concept in concept_map_rows:
        related_codes_by_card.setdefault(mapping.card_id, []).append(concept.concept_code)

    return [_to_rule_card_read(card, related_codes_by_card.get(card.id or 0, [])) for card in rows]


def _to_rule_card_read(card: RegReportingRuleCard, related_concept_codes: list[str]) -> RuleCardRead:
    return RuleCardRead.model_validate(
        {
            **card.model_dump(),
            "related_concept_codes": related_concept_codes,
        }
    )


def _build_workflow_steps(
    document: RegDocument,
    clauses: list[RegClause],
    semantic_items: list[RegSemanticItem],
    impacts: list[ReportingImpactItemRead],
    rule_cards: list[RuleCardRead],
    tickets: list[TicketDraft],
) -> list[WorkflowStepRead]:
    return [
        WorkflowStepRead(
            code="document",
            name="上传发文",
            status="DONE" if document.parsed_text else "PENDING",
        ),
        WorkflowStepRead(
            code="clauses",
            name="条款证据",
            status="DONE" if clauses else "PENDING",
        ),
        WorkflowStepRead(
            code="impact",
            name="影响识别",
            status="REVIEW_REQUIRED" if semantic_items or impacts else "PENDING",
        ),
        WorkflowStepRead(
            code="rule_cards",
            name="规则卡片",
            status="DONE" if rule_cards else "PENDING",
        ),
        WorkflowStepRead(
            code="ticket",
            name="工单草稿",
            status="DONE" if tickets else "PENDING",
        ),
    ]


# ── Module D · AI 工单执行规划 ──────────────────────────────────────────────


@router.get(
    "/{task_id}/execution-plan",
    response_model=ExecutionPlanResponse,
)
def get_execution_plan(
    task_id: int, session: Session = Depends(get_session)
) -> ExecutionPlanResponse:
    """读取已生成的执行规划。不存在时返回 NOT_GENERATED。"""

    _get_task_or_404(task_id, session)
    row = session.exec(
        select(RegTaskExecutionPlan).where(RegTaskExecutionPlan.task_id == task_id)
    ).first()
    if row is None:
        return ExecutionPlanResponse(status="NOT_GENERATED", plan=None)

    try:
        plan_dict = json.loads(row.plan_content) if row.plan_content else {}
    except json.JSONDecodeError:
        return ExecutionPlanResponse(
            status="DEGRADED",
            plan=None,
            warning="持久化的 plan_content 不是合法 JSON，请重新生成",
        )

    plan_dict.setdefault("task_id", task_id)
    plan_dict.setdefault("generated_at", row.generated_at)
    plan_dict.setdefault("generated_by", row.generated_by)
    plan_dict.setdefault("confidence", row.confidence)
    plan_dict.setdefault("needs_human_review", row.needs_human_review)
    return ExecutionPlanResponse(
        status=row.status or "READY",
        plan=ExecutionPlanRead(**plan_dict),
        warning=row.warning or "",
    )


@router.post(
    "/{task_id}/execution-plan",
    response_model=ExecutionPlanResponse,
)
def generate_or_refresh_execution_plan(
    task_id: int, session: Session = Depends(get_session)
) -> ExecutionPlanResponse:
    """(重新)生成执行规划。从工单草稿 + 监管元数据构造输入。"""

    task = _get_task_or_404(task_id, session)
    document = session.get(RegDocument, task.document_id)
    parent_row, child_rows = _load_parent_and_children_for_planner(task_id, session)
    if parent_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="尚未生成工单草稿，无法规划。请先调用 /generate-ticket。",
        )

    payload = _build_planner_input(task_id, document, parent_row, child_rows)
    result = generate_execution_plan(payload)

    if result.status == "EMPTY":
        return ExecutionPlanResponse(
            status="NOT_GENERATED",
            plan=None,
            warning=result.warning,
        )

    plan = result.plan
    assert plan is not None  # READY / DEGRADED 都给 plan
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["task_id"] = task_id

    _persist_execution_plan(
        task_id=task_id,
        plan_dict=plan_dict,
        status_value=result.status,
        warning=result.warning,
        session=session,
    )

    return ExecutionPlanResponse(
        status=result.status,
        plan=ExecutionPlanRead(**plan_dict),
        warning=result.warning,
    )


@router.post(
    "/{task_id}/execution-plan/feedback",
    response_model=ExecutionPlanFeedbackResponse,
)
def submit_execution_plan_feedback(
    task_id: int,
    payload: ExecutionPlanFeedbackRequest,
    session: Session = Depends(get_session),
) -> ExecutionPlanFeedbackResponse:
    """记录用户对规划的 👍 / 👎 反馈。"""

    _get_task_or_404(task_id, session)
    row = session.exec(
        select(RegTaskExecutionPlan).where(RegTaskExecutionPlan.task_id == task_id)
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="尚无执行规划可反馈",
        )

    thumbs = payload.thumbs.lower()
    if thumbs == "up":
        row.feedback_thumbs_up = (row.feedback_thumbs_up or 0) + 1
    elif thumbs == "down":
        row.feedback_thumbs_down = (row.feedback_thumbs_down or 0) + 1
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thumbs 必须是 'up' 或 'down'",
        )
    if payload.comment:
        row.last_feedback_comment = payload.comment
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    return ExecutionPlanFeedbackResponse(ok=True)


def _load_parent_and_children_for_planner(
    task_id: int, session: Session
) -> tuple[TicketDraft | None, list[TicketDraft]]:
    drafts = session.exec(
        select(TicketDraft).where(TicketDraft.task_id == task_id)
    ).all()
    parent = next((d for d in drafts if d.ticket_role == "PARENT"), None)
    children = [d for d in drafts if d.ticket_role == "CHILD"]
    return parent, children


def _build_planner_input(
    task_id: int,
    document: RegDocument | None,
    parent_row: TicketDraft,
    child_rows: list[TicketDraft],
) -> ExecutionPlannerInput:
    reg_doc = RegulatoryDocumentContext(
        title=document.title if document else "",
        document_no=document.document_no if document else "",
        issuing_authority=document.issuing_authority if document else "",
        published_at=document.published_at if document else "",
        effective_date=document.effective_date if document else "",
        first_report_period=document.first_report_period if document else "",
        regulatory_intent=document.regulatory_intent if document else "",
    )
    parent_ctx = ParentTicketContext(
        title=parent_row.title,
        change_ticket_type=parent_row.change_ticket_type,
        severity_level=parent_row.severity_level,
    )
    child_ctxs: list[ChildTicketContext] = []
    for child in child_rows:
        if child.id is None:
            continue
        affected = _safe_json_loads(child.affected_assets, default={})
        items = affected.get("reporting_items", []) if isinstance(affected, dict) else []
        item_code = ""
        item_name = ""
        table_code = ""
        if items:
            first = items[0] if isinstance(items[0], dict) else {}
            code_full = first.get("code", "") or ""
            item_name = first.get("name", "") or ""
            if "." in code_full:
                table_code, item_code = code_full.split(".", 1)
            else:
                table_code = code_full
        blockers_list = _safe_json_loads(child.blockers, default=[])
        quality_flags = _safe_json_loads(child.quality_flags, default=[])
        child_ctxs.append(
            ChildTicketContext(
                id=child.id,
                responsible_system=child.responsible_system or "",
                table_code=table_code,
                item_code=item_code,
                item_name=item_name,
                change_type=child.action_ticket_type or child.change_ticket_type or "",
                evidence_text=child.summary or "",
                blockers=" / ".join(blockers_list) if isinstance(blockers_list, list) else "",
                quality_issues=" / ".join(quality_flags) if isinstance(quality_flags, list) else "",
            )
        )
    return ExecutionPlannerInput(
        task_id=task_id,
        reg_document=reg_doc,
        parent_ticket=parent_ctx,
        child_tickets=child_ctxs,
    )


def _safe_json_loads(raw: str, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _persist_execution_plan(
    task_id: int,
    plan_dict: dict,
    status_value: str,
    warning: str,
    session: Session,
) -> None:
    row = session.exec(
        select(RegTaskExecutionPlan).where(RegTaskExecutionPlan.task_id == task_id)
    ).first()
    plan_json = json.dumps(plan_dict, ensure_ascii=False, default=str)
    now = datetime.utcnow()
    if row is None:
        row = RegTaskExecutionPlan(
            task_id=task_id,
            plan_content=plan_json,
            status=status_value,
            confidence=plan_dict.get("confidence", 0.0),
            needs_human_review=plan_dict.get("needs_human_review", False),
            warning=warning,
            generated_at=now,
            generated_by=plan_dict.get("generated_by", ""),
            updated_at=now,
        )
    else:
        row.plan_content = plan_json
        row.status = status_value
        row.confidence = plan_dict.get("confidence", 0.0)
        row.needs_human_review = plan_dict.get("needs_human_review", False)
        row.warning = warning
        row.generated_at = now
        row.generated_by = plan_dict.get("generated_by", "")
        row.updated_at = now
    session.add(row)
    session.commit()
