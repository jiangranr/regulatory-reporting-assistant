from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentStatus, RiskLevel, TaskStatus


class ParsedDocument(BaseModel):
    filename: str
    text: str
    excerpt: str
    parser: str = "text"
    char_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    quality: str = "UNKNOWN"
    error_message: str = ""


class RegDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    storage_path: str
    title: str
    text_excerpt: str
    parsed_text: str
    status: DocumentStatus
    parse_status: DocumentStatus
    parser: str
    char_count: int
    paragraph_count: int
    table_count: int
    parse_quality: str
    parse_error_message: str
    document_no: str = ""
    issuing_authority: str = ""
    published_at: str = ""
    effective_date: str = ""
    first_report_period: str = ""
    regulatory_intent: str = ""
    metadata_extraction_status: str = "PENDING"
    created_at: datetime


class RawDocumentFileRead(BaseModel):
    """单个上传文件的解析后文本。"""

    filename: str
    role: str  # template | instruction | revision_table | summary | unknown
    role_label: str = ""
    source: str  # excel_template | instruction | revision_table | parsed_text | ...
    text: str
    error_message: str = ""


class RawDocumentTextRead(BaseModel):
    document_id: int
    title: str
    filename: str
    source: str
    text: str
    files: list[RawDocumentFileRead] = []


class RegTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    title: str
    status: TaskStatus
    risk_level: RiskLevel
    created_at: datetime
    updated_at: datetime



class ReportingImpactItemRead(BaseModel):
    reporting_item_code: str
    impact_type: str
    impacted_reporting_field: str
    impacted_source_fields: list[str]
    impacted_lineage_roles: list[str] = []
    impact_reason: str = ""
    recommended_action: str
    ticket_parent_type: str = ""
    required_sub_ticket_types: list[str] = []
    conditional_sub_ticket_types: list[str] = []
    sub_ticket_triggers: dict[str, str] = {}
    confidence_level: str = "MEDIUM"
    risk_level: RiskLevel


class ImpactAnalysisResponse(BaseModel):
    task_id: int
    impacts: list[ReportingImpactItemRead]


class TicketDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    task_id: int
    title: str
    content: str
    parent_ticket_id: int | None = None
    ticket_role: str = "PARENT"
    change_ticket_type: str = ""
    action_ticket_type: str = ""
    severity_level: str = ""
    severity_score: int = 0
    severity_signals: str = "[]"
    severity_forced_reason: str = ""
    severity_overridden_by: str = ""
    owner_role: str = ""
    executor_role: str = ""
    depends_on_lineage: bool = False
    business_signoff_required: bool = False
    closure_review_required: bool = False
    related_impact_codes: str = "[]"
    summary: str = ""
    responsible_system: str = ""
    affected_systems: str = "[]"
    affected_assets: str = "{}"
    business_note: str = ""
    must_do: str = "[]"
    must_confirm: str = "[]"
    output_artifacts: str = "[]"
    acceptance_criteria_structured: str = "[]"
    blockers: str = "[]"
    evidence_refs: str = "[]"
    historical_cases: str = "[]"
    quality_score: int = 0
    quality_flags: str = "[]"
    status: str = "DRAFT"
    created_at: datetime | None = None


class TicketPlanResponse(BaseModel):
    """generate-ticket 接口返回：母单 + 全部子单。"""

    parent: TicketDraftRead
    children: list[TicketDraftRead]


class ImpactReviewSaveRequest(BaseModel):
    review: dict


class ImpactReviewResponse(BaseModel):
    status: str
    review: dict
    ai_baseline: dict
    stats: dict


class ImpactReviewSaveResponse(BaseModel):
    ok: bool = True
    updated_at: datetime


class WorkflowStepRead(BaseModel):
    code: str
    name: str
    status: str


class ReportingSeedResponse(BaseModel):
    reporting_systems: int
    reporting_versions: int
    reporting_objects: int
    reporting_sections: int
    reporting_items: int
    data_fields: int
    lineage: int
    concepts: int = 0
    rule_cards: int = 0


class ReportingObjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    object_code: str
    object_name: str
    object_category: str
    report_frequency: str
    submit_deadline: str
    status: str


class ReportingItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    reporting_object_id: int
    reporting_section_id: int | None = None
    item_code: str
    item_name: str
    item_type: str
    row_label: str
    column_label: str
    measure_type: str
    unit: str
    status: str
    change_status: str = ""
    source_cell_ref: str = ""
    cell_role: str = ""
    is_fillable: bool = True
    is_derived: bool = False
    data_type: str = "DECIMAL"


class ReportingLineageFieldRead(BaseModel):
    field_code: str
    field_name: str
    table_name: str
    column_name: str
    data_type: str
    business_meaning: str
    owner_team: str
    lineage_role: str
    transform_expression: str = ""
    confidence_level: str = "MEDIUM"
    mapping_status: str = "DRAFT"


class ReportingLineageResponse(BaseModel):
    item: ReportingItemRead
    fields: list[ReportingLineageFieldRead]


class ReportingChangeCandidateRead(BaseModel):
    reporting_system_code: str
    reporting_object_code: str
    reporting_item_code: str
    change_type: str
    evidence_text: str
    confidence_score: float
    review_status: str = "PENDING"


class TableChangeSignalRead(BaseModel):
    table_code: str
    section_hint: str = ""
    indicator_hint: str = ""
    change_type: str
    evidence_text: str = ""
    confidence: float = 0.7
    evidence_verified: bool = True
    matched_item_code: str = ""
    match_status: str = ""
    composite_match: dict = {}


class DocumentTaskProfileRead(BaseModel):
    id: int | None = None
    document_id: int
    document_type: str = ""
    # 1104 指标变更扫描结果
    affected_table_codes: list[str] = []
    change_signals: list[TableChangeSignalRead] = []
    in_scope_tables: list[str] = []
    out_of_scope_tables: list[str] = []
    # 通用决策字段
    suggested_route: str
    should_create_task: bool
    confidence_score: float
    reason: str = ""
    evidence_text: str = ""
    llm_model: str = ""
    review_status: str = "PENDING"
    raw_response: str = ""
    created_at: datetime | None = None


class RevisionEntryRead(BaseModel):
    table_code: str
    section: str
    row_label: str
    column_label: str
    change_type: str
    change_desc: str


class ExcelDiffEntryRead(BaseModel):
    item_code: str
    row_label: str
    column_label: str
    diff_type: str
    old_row_label: str = ""
    old_col_label: str = ""
    evidence: str = ""


class ItemChangeScanResultRead(BaseModel):
    item_code: str
    row_label: str
    column_label: str
    old_status: str
    new_status: str
    source: str
    confidence: float
    evidence: str
    overridden_sources: list[str] = []


class LaneSignalRead(BaseModel):
    """三路漏斗中单一信号源的原始命中（合并前）。"""
    item_code: str
    row_label: str
    column_label: str
    change_type: str
    confidence: float
    evidence: str
    won: bool = False


class RevisionCandidateRead(BaseModel):
    """修订对照表逐条候选识别结果。"""
    table_code: str
    section: str
    row_label: str
    column_label: str
    change_type: str
    change_desc: str
    match_status: str
    matched_item_code: str = ""
    confidence: float = 0.0
    evidence: str = ""
    reason: str = ""

    # —— v2 字段维度新增 ——
    revision_id: str = ""
    regime_version: str = ""
    field_code: str = ""
    field_name: str = ""
    change_dimensions: list[str] = []
    change_summary: str = ""
    before_value: dict = {}
    after_value: dict = {}
    regulation_evidence: str = ""
    evidence_source_ref: str = ""
    affected_cells: list[str] = []
    effective_date: str = ""
    matched_item_codes: list[str] = []                # v2：1 entry 命中的全部 item_code
    composite_match: dict = {}


class TripletUploadResponse(BaseModel):
    document: "RegDocumentRead"
    # 各文件解析摘要（未上传则为 None）
    template_parsed: bool = False
    instruction_parsed: bool = False
    revision_table_parsed: bool = False
    revision_entry_count: int = 0
    excel_diff_count: int = 0
    # 指标变更扫描结果（合并后）
    scan_results: list[ItemChangeScanResultRead] = []
    scan_summary: str = ""
    excel_diff: list[ExcelDiffEntryRead] = []
    revision_entries: list[RevisionEntryRead] = []
    # 三路原始信号（合并前），用于前端漏斗可视化
    revision_lane: list[LaneSignalRead] = []
    excel_lane: list[LaneSignalRead] = []
    instruction_lane: list[LaneSignalRead] = []
    revision_candidates: list[RevisionCandidateRead] = []
    error_messages: list[str] = []


class RegClauseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    clause_no: str
    clause_text: str
    clause_level: int
    review_status: str
    created_at: datetime


class ClauseSplitResponse(BaseModel):
    document_id: int
    clauses: list[RegClauseRead]


class RegSemanticItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clause_id: int
    semantic_type: str
    semantic_name: str
    semantic_value: str
    evidence_text: str
    confidence_score: float
    review_status: str


class SemanticExtractResponse(BaseModel):
    clause_id: int
    semantic_items: list[RegSemanticItemRead]


class RuleCardRead(BaseModel):
    """报送规则卡片读对象。对应 reg_reporting_rule_card 表 + 关联概念 code 列表。"""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    card_code: str
    reporting_object_code: str | None = None
    reporting_item_code: str | None = None
    card_level: str  # 'L1' / 'L2' / 'L3'
    card_title: str
    card_text: str
    card_subject: str | None = None
    card_predicate: str | None = None
    card_object: str | None = None
    card_qualifier: str | None = None
    source_document_id: int | None = None
    source_location: str = ""
    evidence_text: str = ""
    evidence_verified: bool = False
    effective_from_version: str | None = None
    effective_to_version: str | None = None
    confidence_level: str = "MEDIUM"
    review_status: str = "PENDING"
    status: str = "DRAFT"
    related_concept_codes: list[str] = []


class ConceptRead(BaseModel):
    """监管报送概念读对象。"""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    concept_code: str
    canonical_name: str
    short_definition: str
    full_definition: str = ""
    concept_type: str
    reporting_system_scope: str = ""
    current_version_no: int = 1
    is_locked: bool = False
    status: str = "ACTIVE"
    aliases: list[str] = []
    related_reporting_item_codes: list[str] = []


class ExtractionRequest(BaseModel):
    """手动从文档抽取规则卡片 + 概念候选。"""

    document_id: int


class ExtractionResultRead(BaseModel):
    """同步抽取结果。"""

    document_id: int
    inferred_object_code: str
    rule_cards_created: int
    concepts_created: int
    aliases_created: int
    card_concept_links_created: int
    rule_cards_skipped: int
    concepts_skipped: int
    llm_used: bool
    error_message: str = ""


class ReviewActionRequest(BaseModel):
    """对候选卡片 / 候选概念的人工复核动作。"""

    action: str  # ACCEPT / REJECT / HOLD
    reviewer: str = ""
    comment: str = ""


class ConceptMatchRequest(BaseModel):
    """文本→概念匹配的输入"""

    text: str
    reporting_system_scope: str | None = None
    top_k: int = 20


class ConceptMatchHit(BaseModel):
    concept_code: str
    canonical_name: str
    matched_alias: str
    match_offset: int
    match_length: int
    related_reporting_item_codes: list[str] = []
    # 该概念通过哪些召回路径命中（alias/definition/embedding）；
    # 前端据此渲染路径徽章，让业务方区分"字面命中"与"AI 语义推断"
    paths: list[str] = []
    score: float = 0.0


class ConceptMatchResponse(BaseModel):
    hits: list[ConceptMatchHit]


class ChangeItemRead(BaseModel):
    category: str
    change: str
    evidence: str = ""


class InstructionChangeAnalysisRead(BaseModel):
    object_code: str
    summary: str
    key_changes: list[ChangeItemRead] = []
    attention_items: list[str] = []
    uncertain_items: list[str] = []
    comments_count: int = 0
    revisions_count: int = 0
    highlights_count: int = 0
    llm_model: str = ""
    error_message: str = ""


class TaskWorkflowResponse(BaseModel):
    task: RegTaskRead
    document: RegDocumentRead
    document_profile: DocumentTaskProfileRead | None = None
    steps: list[WorkflowStepRead]
    clauses: list[RegClauseRead]
    semantic_items: list[RegSemanticItemRead]
    # Backward-compatible empty list for older frontend panels. New reporting
    # lineage data is returned in lineage_candidates.
    field_mappings: list[dict] = []
    reporting_candidates: list[ReportingChangeCandidateRead] = []
    lineage_candidates: list[ReportingLineageFieldRead] = []
    impact_items: list[ReportingImpactItemRead]
    rule_cards: list[RuleCardRead]
    ticket_drafts: list[TicketDraftRead]


# ── Module D · 执行规划 API schemas ────────────────────────────────────────

class ExecutionTaskRead(BaseModel):
    team: str
    team_zh: str
    action: str
    ticket_id: int
    is_blocker: bool = False
    blocker_reason: str = ""


class ExecutionPhaseRead(BaseModel):
    phase_name: str
    tasks: list[ExecutionTaskRead] = []


class CriticalRiskRead(BaseModel):
    severity: str  # HIGH / MEDIUM / LOW
    description: str
    ticket_id_ref: int | None = None
    mitigation: str = ""


class ExecutionPlanRead(BaseModel):
    """与 docs/superpowers/plans/2026-05-28-execution-planner-frontend.md
    定义的 API 契约严格对齐。"""

    task_id: int
    executive_summary: str
    estimated_duration: str
    execution_phases: list[ExecutionPhaseRead] = []
    critical_risks: list[CriticalRiskRead] = []
    team_coordination: str = ""
    generated_at: datetime
    generated_by: str
    confidence: float
    needs_human_review: bool = False


class ExecutionPlanResponse(BaseModel):
    status: str  # NOT_GENERATED / READY / DEGRADED / STALE
    plan: ExecutionPlanRead | None = None
    warning: str = ""


class ExecutionPlanFeedbackRequest(BaseModel):
    thumbs: str  # "up" / "down"
    comment: str = ""


class ExecutionPlanFeedbackResponse(BaseModel):
    ok: bool = True
