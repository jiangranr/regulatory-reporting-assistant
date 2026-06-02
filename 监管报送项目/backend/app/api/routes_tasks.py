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
from app.services.reporting_seed import ReportingSeedCatalog
from app.services.reporting_ticket_generator import (
    ChildTicketPlan,
    ParentTicketPlan,
    build_ticket_plan,
)
from app.services.impact_review_service import (
    SYSTEM_LABELS,
    apply_confirmed_review_to_lineage,
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


def _profile_aware_changes(
    document_id: int,
    document_text: str,
    seed: ReportingSeedCatalog,
    session: Session,
) -> list[ReportingChangeDraft]:
    profile = session.exec(
        select(DocumentTaskProfile)
        .where(DocumentTaskProfile.document_id == document_id)
        .order_by(DocumentTaskProfile.created_at.desc())
    ).first()
    if profile and profile.change_signals and profile.change_signals != "[]":
        return signals_to_changes(json.loads(profile.change_signals), seed.reporting_items)
    return extract_reporting_changes(document_text)


@router.post("/{task_id}/analyze-impact", response_model=ImpactAnalysisResponse)
def analyze_task_impact(task_id: int, session: Session = Depends(get_session)) -> ImpactAnalysisResponse:
    task = _get_task_or_404(task_id, session)
    document = session.get(RegDocument, task.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 读路径走 DB：保证影响分析看到的指标颗粒度和血缘和"字段定位"页一致。
    # 不要回退到 build_1104_seed_catalog —— 那样会让 bootstrap 未执行的环境静默吃旧数据。
    seed = load_catalog_from_db(session)

    changes = _profile_aware_changes(document.id, document.parsed_text, seed, session)

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
        seed = load_catalog_from_db(session)
        changes = _profile_aware_changes(task.document_id, document_text, seed, session)
        draft_impacts = analyze_reporting_impacts(changes, seed)
        _replace_reporting_candidates(task_id, changes, session)
        _replace_reporting_impacts(task_id, draft_impacts, session)
        impacts = [_impact_read_from_draft(item) for item in draft_impacts]

    impact_drafts = _enrich_impact_drafts_with_catalog(
        [_impact_draft_from_read(item) for item in impacts],
        session,
    )
    change_drafts = _load_change_drafts(task_id, session) or _profile_aware_changes(
        task.document_id,
        document_text,
        load_catalog_from_db(session),
        session,
    )
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
        system_options=_load_data_system_options(session),
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
        system_options=_load_data_system_options(session),
    )


def _load_data_system_options(session: Session) -> list[dict[str, str]]:
    return [
        {
            "system_code": system.system_code,
            "system_name": system.system_name,
            "system_type": system.system_type or "",
            "owner_team": system.owner_team or "",
        }
        for system in session.exec(
            select(DataSystemCatalog)
            .where(DataSystemCatalog.status == "ACTIVE")
            .order_by(DataSystemCatalog.system_code)
        ).all()
    ]


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

    apply_confirmed_review_to_lineage(review, session)

    impacts = _load_impact_items(task_id, session)
    if not impacts:
        seed = load_catalog_from_db(session)
        changes = _profile_aware_changes(task.document_id, document_text, seed, session)
        draft_impacts = analyze_reporting_impacts(changes, seed)
        _replace_reporting_candidates(task_id, changes, session)
        _replace_reporting_impacts(task_id, draft_impacts, session)
        impacts = [_impact_read_from_draft(item) for item in draft_impacts]
    impact_drafts = _enrich_impact_drafts_with_catalog(
        [_impact_draft_from_read(item) for item in impacts],
        session,
    )
    change_drafts = _load_change_drafts(task_id, session) or _profile_aware_changes(
        task.document_id,
        document_text,
        load_catalog_from_db(session),
        session,
    )
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
    action_type = _action_type_for_system_type(group.get("system_type") or "")
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
        responsible_system=card.responsible_system,
        affected_systems=json.dumps([card.responsible_system], ensure_ascii=False),
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
        "system_type": "",
        "owner_team": "",
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
        responsible_system=card.responsible_system,
        affected_systems=json.dumps([card.responsible_system], ensure_ascii=False),
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
        # 新流程传 system_code（如 "RPT_1104"），旧支持单传 ResponsibleSystem 的 enum value，
        # 都是字符串，TicketTaskCard.responsible_system 已经放宽到 str。
        responsible_system=str(group["responsible_system"]),
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


def _action_type_for_system_type(system_type: str) -> ActionTicketType:
    """按 data_system_catalog.system_type 推子单 action_type。

    - REPORTING/MART/DM：报送加工类（数据开发团队改 SQL/ETL）
    - SOURCE/ODS/MDM：源系统改造类（源系统团队补字段/接口）
    - 缺失或未识别：兜底走 DATA_MAPPING（数据治理走映射核对）

    旧抽象桶（TEST_ACCEPTANCE/KNOWLEDGE_ARCHIVE）走的是 _persist_review_support_child_ticket，
    那条路径直接传 ActionTicketType，不经过这里。
    """
    normalized = (system_type or "").strip().upper()
    if normalized in {"REPORTING", "MART", "DM"}:
        return ActionTicketType.REPORT_PROCESSING
    if normalized in {"SOURCE", "ODS", "MDM"}:
        return ActionTicketType.SOURCE_SYSTEM_CHANGE
    return ActionTicketType.DATA_MAPPING


def _render_review_child_markdown(card: TicketTaskCard, notes: list[str]) -> str:
    lines = [
        f"# {card.responsible_system} 系统子单",
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
        responsible_system=card.responsible_system if has_card else "",
        affected_systems=(
            json.dumps([card.responsible_system], ensure_ascii=False)
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
            impacted_source_field_details=json.loads(row.impacted_source_field_details or "[]"),
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
                impacted_source_field_details=json.dumps(
                    impact.impacted_source_field_details, ensure_ascii=False
                ),
                impact_reason=impact.impact_reason,
                recommended_action=impact.recommended_action,
                confidence_level=impact.confidence_level,
                risk_level=impact.risk_level,
            )
        )


def _impact_read_from_draft(impact: ReportingImpactDraft) -> ReportingImpactItemRead:
    return ReportingImpactItemRead(
        reporting_item_code=impact.reporting_item_code,
        reporting_item_name=impact.reporting_item_name,
        impact_type=impact.impact_type,
        impacted_reporting_field=impact.impacted_reporting_field,
        impacted_source_fields=impact.impacted_source_fields,
        impacted_lineage_roles=impact.impacted_lineage_roles,
        impacted_source_field_details=impact.impacted_source_field_details,
        impact_reason=impact.impact_reason,
        recommended_action=impact.recommended_action,
        ticket_parent_type=impact.ticket_parent_type,
        required_sub_ticket_types=impact.required_sub_ticket_types,
        conditional_sub_ticket_types=impact.conditional_sub_ticket_types,
        sub_ticket_triggers=impact.sub_ticket_triggers,
        confidence_level=impact.confidence_level,
        risk_level=impact.risk_level,
        change_axis=impact.change_axis,
    )


def _impact_draft_from_read(impact: ReportingImpactItemRead) -> ReportingImpactDraft:
    return ReportingImpactDraft(
        reporting_item_code=impact.reporting_item_code,
        reporting_item_name=impact.reporting_item_name,
        impact_type=impact.impact_type,
        impacted_reporting_field=impact.impacted_reporting_field,
        impacted_source_fields=impact.impacted_source_fields,
        impacted_lineage_roles=impact.impacted_lineage_roles,
        impacted_source_field_details=impact.impacted_source_field_details,
        impact_reason=impact.impact_reason,
        recommended_action=impact.recommended_action,
        ticket_parent_type=impact.ticket_parent_type,
        required_sub_ticket_types=impact.required_sub_ticket_types,
        conditional_sub_ticket_types=impact.conditional_sub_ticket_types,
        sub_ticket_triggers=impact.sub_ticket_triggers,
        confidence_level=impact.confidence_level,
        risk_level=impact.risk_level,
        change_axis=impact.change_axis,
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


# ============================================================================
# 参考 SQL 生成（Reference SQL Generator）
# 见 docs/superpowers/plans/2026-05-29-reference-sql-generator.md
# ============================================================================

from app.models.schemas import (  # noqa: E402
    ReferenceSqlResponse,
    ReferenceSqlSaveRequest,
    ReferenceSqlFeedbackRequest,
    ReferenceSqlFeedbackResponse,
    SqlWarningRead,
)
from app.services.ticket_sql_generator import (  # noqa: E402
    FieldContext,
    RegDocumentContext,
    ReportingItemContext,
    SqlGenerationInput,
    generate_reference_sql,
)

# ──────────────────────────────────────────────────────────────────────────────
# 字段变更检测 & 六路由工单
# ──────────────────────────────────────────────────────────────────────────────

from app.models.db_models import RegFieldChangeRecord  # noqa: E402
from app.services.field_change_detector import detect_field_changes, enrich_with_library_hit  # noqa: E402
from app.services.field_change_ticket_router import route_all_pending  # noqa: E402


@router.post("/{task_id}/field-changes/detect")
def detect_task_field_changes(
    task_id: int,
    object_codes: list[str] | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """触发字段目录版本对比，将变更清单写入 reg_field_change_records。

    Demo 模式使用内置 mock 新版字段目录，production 接监管系统抽数。
    object_codes 可指定报表范围，如 ["G31"]。
    """
    _get_task_or_404(task_id, session)

    # 清除该任务之前的变更记录，保持幂等
    old_records = session.exec(
        select(RegFieldChangeRecord).where(RegFieldChangeRecord.task_id == task_id)
    ).all()
    for r in old_records:
        session.delete(r)
    session.commit()

    # 检测变更
    changes = detect_field_changes(object_codes=object_codes)
    changes = enrich_with_library_hit(changes, session)

    # 写入 DB
    records = []
    for ch in changes:
        record = RegFieldChangeRecord(
            task_id=task_id,
            reporting_object_code=ch.reporting_object_code,
            reporting_item_code=ch.reporting_item_code,
            item_name=ch.item_name,
            change_type=ch.change_type,
            before_snapshot=json.dumps(ch.before_snapshot, ensure_ascii=False),
            after_snapshot=json.dumps(ch.after_snapshot, ensure_ascii=False),
            library_hit=ch.library_hit,
            status="PENDING",
        )
        session.add(record)
        records.append(record)
    session.commit()

    return {
        "task_id": task_id,
        "total": len(records),
        "added": sum(1 for r in records if r.change_type == "ADDED"),
        "deleted": sum(1 for r in records if r.change_type == "DELETED"),
        "modified": sum(1 for r in records if r.change_type == "MODIFIED"),
        "library_hit_count": sum(1 for r in records if r.library_hit),
    }


@router.get("/{task_id}/field-changes")
def list_task_field_changes(
    task_id: int,
    session: Session = Depends(get_session),
) -> list[dict]:
    """返回该任务下的变更清单。"""
    _get_task_or_404(task_id, session)
    records = session.exec(
        select(RegFieldChangeRecord)
        .where(RegFieldChangeRecord.task_id == task_id)
        .order_by(RegFieldChangeRecord.change_type, RegFieldChangeRecord.reporting_item_code)
    ).all()

    return [
        {
            "id": r.id,
            "reporting_object_code": r.reporting_object_code,
            "reporting_item_code": r.reporting_item_code,
            "item_name": r.item_name,
            "change_type": r.change_type,
            "library_hit": r.library_hit,
            "ticket_id": r.ticket_id,
            "status": r.status,
            "before_snapshot": _safe_json_loads(r.before_snapshot, {}),
            "after_snapshot": _safe_json_loads(r.after_snapshot, {}),
        }
        for r in records
    ]


@router.post("/{task_id}/field-changes/route-tickets")
def route_field_change_tickets(
    task_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """对所有 PENDING 状态的变更记录按六路由矩阵生成工单。"""
    _get_task_or_404(task_id, session)

    pending_count = len(session.exec(
        select(RegFieldChangeRecord).where(
            RegFieldChangeRecord.task_id == task_id,
            RegFieldChangeRecord.status == "PENDING",
        )
    ).all())

    if pending_count == 0:
        raise HTTPException(status_code=400, detail="无待处理的变更记录，请先执行 detect")

    tickets = route_all_pending(task_id, session)

    return {
        "task_id": task_id,
        "tickets_generated": len(tickets),
        "ticket_ids": [t.id for t in tickets if t.id],
    }


@router.post("/{task_id}/tickets/{ticket_id}/confirm")
def confirm_field_change_ticket(
    task_id: int,
    ticket_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """业务确认字段变更工单后，根据工单类型更新 ReportingItemLineage。

    - LINEAGE_BUILD（新增/告警）→ 确认后血缘状态 = CONFIRMED
    - DATA_MAPPING（变更）      → 更新已有血缘状态 = CONFIRMED
    - REPORT_DECOMMISSION（删除）→ 血缘状态 = RETIRED
    """
    _get_task_or_404(task_id, session)
    ticket = session.get(TicketDraft, ticket_id)
    if ticket is None or ticket.task_id != task_id:
        raise HTTPException(status_code=404, detail="工单不存在或不属于该任务")

    ticket.status = "CONFIRMED"
    session.add(ticket)

    action_type = ticket.action_ticket_type or ""
    item_codes: list[str] = []
    try:
        item_codes = json.loads(ticket.related_impact_codes or "[]")
    except Exception:
        pass

    confirmed = 0
    retired = 0

    for item_code in item_codes:
        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == item_code)
        ).first()
        if not item or not item.id:
            continue

        from app.models.db_models import ReportingItemLineage
        lineages = session.exec(
            select(ReportingItemLineage).where(
                ReportingItemLineage.reporting_item_id == item.id
            )
        ).all()

        if action_type == "REPORT_DECOMMISSION":
            for lin in lineages:
                if lin.mapping_status != "RETIRED":
                    lin.mapping_status = "RETIRED"
                    session.add(lin)
                    retired += 1
        else:  # LINEAGE_BUILD / DATA_MAPPING
            for lin in lineages:
                if lin.mapping_status in ("SEED_CONFIRMED", "DRAFT", "PENDING"):
                    lin.mapping_status = "CONFIRMED"
                    session.add(lin)
                    confirmed += 1

    session.commit()
    return {
        "ticket_id": ticket_id,
        "status": "CONFIRMED",
        "lineage_confirmed": confirmed,
        "lineage_retired": retired,
    }


ticket_router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _get_ticket_or_404(ticket_id: int, session: Session) -> TicketDraft:
    ticket = session.get(TicketDraft, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _sql_safe_json(raw: str, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _extract_codes(raw_list: list) -> list[str]:
    """从 dict-or-str 混合列表里提取 code 字段，过滤空值。"""
    result: list[str] = []
    for item in raw_list:
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
        else:
            code = str(item or "").strip()
        if code:
            result.append(code)
    return result


def _build_sql_input(ticket: TicketDraft, session: Session) -> SqlGenerationInput:
    """从工单 + 影响资产 + 字段目录 + 血缘 + 监管元数据组装 SQL 生成输入。"""
    assets = _sql_safe_json(ticket.affected_assets, {})
    # _build_affected_assets 写入的 key 是 "reporting_items" / "source_fields"，值是 dict 列表
    item_codes = _extract_codes(assets.get("reporting_items", []) if isinstance(assets, dict) else [])
    source_field_codes = _extract_codes(assets.get("source_fields", []) if isinstance(assets, dict) else [])
    # 报送集市子单（REPORT_PROCESSING）的 source_fields 可能为空，其 REPORT_FIELD 就是要加工的目标字段
    # 回退到 reporting_fields，让 SQL 生成器能看到 rpt_xxx 字段
    if not source_field_codes and isinstance(assets, dict):
        source_field_codes = _extract_codes(assets.get("reporting_fields", []))

    reporting_items: list[ReportingItemContext] = []
    item_ids: list[int] = []
    for code in item_codes:
        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == code)
        ).first()
        if item:
            if item.id is not None:
                item_ids.append(item.id)
            reporting_items.append(ReportingItemContext(
                code=code,
                name=item.item_name or "",
                definition=item.definition or "",
                evidence_text=ticket.summary or "",
            ))
        else:
            reporting_items.append(ReportingItemContext(code=code, evidence_text=ticket.summary or ""))

    # 血缘 transform_expression：按相关报送项聚合 {data_field_code: expr}
    transform_by_field: dict[str, str] = {}
    if item_ids:
        lineage_rows = session.exec(
            select(ReportingItemLineage).where(ReportingItemLineage.reporting_item_id.in_(item_ids))
        ).all()
        for lin in lineage_rows:
            field_code = ""
            if lin.data_field_id is not None:
                catalog = session.get(DataFieldCatalog, lin.data_field_id)
                field_code = catalog.field_code if catalog else ""
            if field_code and lin.transform_expression and field_code not in transform_by_field:
                transform_by_field[field_code] = lin.transform_expression

    available_fields: list[FieldContext] = []
    for code in source_field_codes:
        catalog = session.exec(
            select(DataFieldCatalog).where(DataFieldCatalog.field_code == code)
        ).first()
        if catalog:
            available_fields.append(FieldContext(
                code=code,
                table_name=catalog.table_name or "",
                column_name=catalog.column_name or "",
                data_type=catalog.data_type or "",
                business_meaning=catalog.business_meaning or "",
                transform_expression=transform_by_field.get(code, ""),
            ))
        else:
            table_name, _, column_name = code.partition(".")
            available_fields.append(FieldContext(
                code=code,
                table_name=table_name,
                column_name=column_name,
                transform_expression=transform_by_field.get(code, ""),
            ))

    task = session.get(RegTask, ticket.task_id)
    document = session.get(RegDocument, task.document_id) if task else None
    reg_doc = RegDocumentContext(
        document_no=document.document_no if document else "",
        effective_date=document.effective_date if document else "",
        first_report_period=document.first_report_period if document else "",
        regulatory_intent=document.regulatory_intent if document else "",
    )

    return SqlGenerationInput(
        ticket_title=ticket.title,
        action_type=ticket.action_ticket_type or "",
        reporting_items=reporting_items,
        available_fields=available_fields,
        reg_document=reg_doc,
        business_note=ticket.business_note or "",
    )


def _ticket_to_sql_response(ticket: TicketDraft) -> ReferenceSqlResponse:
    warnings_raw = _sql_safe_json(ticket.sql_warnings, [])
    warnings = [SqlWarningRead(**w) for w in warnings_raw if isinstance(w, dict)]
    return ReferenceSqlResponse(
        ticket_id=ticket.id or 0,
        status=ticket.sql_status or "NOT_GENERATED",
        ability=ticket.sql_ability or "",
        reference_sql=ticket.reference_sql or "",
        sql_dialect=ticket.sql_dialect or "ANSI",
        confidence=ticket.sql_confidence or 0.0,
        not_applicable_reason=ticket.sql_not_applicable_reason or "",
        warnings=warnings,
        generated_at=ticket.sql_generated_at,
        generated_by=ticket.sql_generated_by or "",
    )


@ticket_router.get("/{ticket_id}/reference-sql", response_model=ReferenceSqlResponse)
def get_reference_sql(ticket_id: int, session: Session = Depends(get_session)) -> ReferenceSqlResponse:
    ticket = _get_ticket_or_404(ticket_id, session)
    return _ticket_to_sql_response(ticket)


@ticket_router.post("/{ticket_id}/reference-sql/generate", response_model=ReferenceSqlResponse)
def generate_ticket_reference_sql(
    ticket_id: int, session: Session = Depends(get_session)
) -> ReferenceSqlResponse:
    ticket = _get_ticket_or_404(ticket_id, session)
    payload = _build_sql_input(ticket, session)
    result = generate_reference_sql(payload)

    ticket.sql_ability = result.ability
    ticket.sql_status = result.status
    ticket.sql_not_applicable_reason = result.not_applicable_reason
    if result.status != "NOT_APPLICABLE":
        ticket.reference_sql = result.sql
        ticket.sql_dialect = result.dialect
        ticket.sql_confidence = result.confidence
        ticket.sql_warnings = json.dumps(
            [w.to_dict() for w in result.warnings], ensure_ascii=False
        )
        ticket.sql_generated_at = datetime.utcnow()
        ticket.sql_generated_by = result.generated_by
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    resp = _ticket_to_sql_response(ticket)
    resp.explanation = result.explanation
    resp.assumptions = result.assumptions
    return resp


@ticket_router.put("/{ticket_id}/reference-sql", response_model=ReferenceSqlResponse)
def save_reference_sql(
    ticket_id: int,
    payload: ReferenceSqlSaveRequest,
    session: Session = Depends(get_session),
) -> ReferenceSqlResponse:
    ticket = _get_ticket_or_404(ticket_id, session)
    ticket.reference_sql = payload.reference_sql
    ticket.sql_status = "EDITED_BY_USER"
    ticket.sql_generated_by = "user"
    ticket.sql_generated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return _ticket_to_sql_response(ticket)


@ticket_router.post(
    "/{ticket_id}/reference-sql/feedback", response_model=ReferenceSqlFeedbackResponse
)
def submit_reference_sql_feedback(
    ticket_id: int,
    payload: ReferenceSqlFeedbackRequest,
    session: Session = Depends(get_session),
) -> ReferenceSqlFeedbackResponse:
    ticket = _get_ticket_or_404(ticket_id, session)
    thumbs = payload.thumbs.lower()
    if thumbs == "up":
        ticket.sql_feedback_thumbs_up = (ticket.sql_feedback_thumbs_up or 0) + 1
    elif thumbs == "down":
        ticket.sql_feedback_thumbs_down = (ticket.sql_feedback_thumbs_down or 0) + 1
    else:
        raise HTTPException(status_code=400, detail="thumbs 必须是 'up' 或 'down'")
    session.add(ticket)
    session.commit()
    return ReferenceSqlFeedbackResponse(ok=True)


@ticket_router.post("/{ticket_id}/reference-sql/mark-stale", response_model=ReferenceSqlResponse)
def mark_reference_sql_stale(
    ticket_id: int, session: Session = Depends(get_session)
) -> ReferenceSqlResponse:
    ticket = _get_ticket_or_404(ticket_id, session)
    if ticket.sql_status in {"READY", "DEGRADED", "EDITED_BY_USER"}:
        ticket.sql_status = "STALE"
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
    return _ticket_to_sql_response(ticket)
