from datetime import datetime

from sqlalchemy import Column, LargeBinary, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.enums import DocumentStatus, RiskLevel, TaskStatus


class RegDocument(SQLModel, table=True):
    __tablename__ = "reg_documents"

    id: int | None = Field(default=None, primary_key=True)
    filename: str
    content_type: str = "application/octet-stream"
    storage_path: str
    title: str
    text_excerpt: str = Field(default="", sa_column=Column(Text))
    parsed_text: str = Field(default="", sa_column=Column(Text))
    status: DocumentStatus = DocumentStatus.UPLOADED
    parse_status: DocumentStatus = DocumentStatus.UPLOADED
    parser: str = ""
    char_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    parse_quality: str = "UNKNOWN"
    parse_error_message: str = Field(default="", sa_column=Column(Text))
    # 监管元数据（由 instruction_parser.extract_regulatory_metadata 填充）
    document_no: str = ""                 # 〔2026〕第 15 号
    issuing_authority: str = ""           # 国家金融监督管理总局/中国人民银行/...
    published_at: str = ""                # 2026-05-26（落款日期）
    effective_date: str = ""              # 2026-07-01（自...起施行）
    first_report_period: str = ""         # 2026Q3 / 2026-09-30（首次报送时点）
    regulatory_intent: str = Field(default="", sa_column=Column(Text))  # 政策目的段（限 300 字）
    metadata_extraction_status: str = "PENDING"  # PENDING / OK / PARTIAL / FAILED
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegTask(SQLModel, table=True):
    __tablename__ = "reg_tasks"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(index=True)
    title: str
    status: TaskStatus = TaskStatus.CREATED
    risk_level: RiskLevel = RiskLevel.MEDIUM
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RegTaskExecutionPlan(SQLModel, table=True):
    """Module D · AI 工单执行规划。

    一条任务对应至多一条规划（task_id 唯一索引），重新生成走 UPDATE。
    plan_content 为 ExecutionPlan 的 JSON 字符串（按 prompt schema）。
    """

    __tablename__ = "reg_task_execution_plan"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True, unique=True)
    plan_content: str = Field(sa_column=Column(Text))
    status: str = Field(default="READY", index=True)  # READY / DEGRADED / STALE / INVALID
    confidence: float = 0.0
    needs_human_review: bool = False
    warning: str = Field(default="", sa_column=Column(Text))
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = ""           # 如 "planner_v1@2026-05-28"
    feedback_thumbs_up: int = 0
    feedback_thumbs_down: int = 0
    last_feedback_comment: str = Field(default="", sa_column=Column(Text))
    updated_at: datetime = Field(default_factory=datetime.utcnow)



class RegReportingSystem(SQLModel, table=True):
    __tablename__ = "reg_reporting_systems"

    id: int | None = Field(default=None, primary_key=True)
    system_code: str = Field(index=True, unique=True)
    system_name: str
    regulator: str = ""
    description: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingVersion(SQLModel, table=True):
    __tablename__ = "reg_reporting_versions"

    id: int | None = Field(default=None, primary_key=True)
    reporting_system_id: int = Field(index=True)
    version_code: str = Field(index=True)
    version_name: str
    effective_date: str = ""
    source_file: str = ""
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingObject(SQLModel, table=True):
    __tablename__ = "reg_reporting_objects"

    id: int | None = Field(default=None, primary_key=True)
    reporting_system_id: int = Field(index=True)
    reporting_version_id: int = Field(index=True)
    object_code: str = Field(index=True)
    object_name: str
    object_category: str = ""
    report_frequency: str = ""
    submit_deadline: str = ""
    description: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    # 新增字段（catalog zip 上传后填充）
    change_type: str = ""          # NEW / MODIFIED
    table_category: str = ""       # 目录文件夹名
    current_version_label: str = ""  # "251"
    latest_batch_item_id: int | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingSection(SQLModel, table=True):
    __tablename__ = "reg_reporting_sections"

    id: int | None = Field(default=None, primary_key=True)
    reporting_object_id: int = Field(index=True)
    section_code: str = Field(index=True)
    section_name: str
    display_order: int = 0
    description: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingItem(SQLModel, table=True):
    __tablename__ = "reg_reporting_items"

    id: int | None = Field(default=None, primary_key=True)
    reporting_object_id: int = Field(index=True)
    reporting_section_id: int | None = Field(default=None, index=True)
    item_code: str = Field(index=True, unique=True)
    item_name: str
    item_type: str = "MEASURE"
    row_label: str = ""
    column_label: str = ""
    measure_type: str = ""
    unit: str = ""
    definition: str = Field(default="", sa_column=Column(Text))
    fill_requirement: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    # 新增字段（catalog zip 上传后填充）
    batch_item_id: int | None = Field(default=None, index=True)
    change_status: str = ""        # NEW / MODIFIED / UNCHANGED
    source_cell_ref: str = ""      # "D8"
    cell_role: str = ""            # FILLABLE / DERIVED / NO_DATA
    is_fillable: bool = True
    is_derived: bool = False
    data_type: str = "DECIMAL"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingInstruction(SQLModel, table=True):
    __tablename__ = "reg_reporting_instructions"

    id: int | None = Field(default=None, primary_key=True)
    reporting_item_id: int | None = Field(default=None, index=True)
    reporting_object_id: int = Field(index=True)
    instruction_code: str = Field(index=True)
    instruction_text: str = Field(sa_column=Column(Text))
    source_reference: str = ""
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingRule(SQLModel, table=True):
    __tablename__ = "reg_reporting_rules"

    id: int | None = Field(default=None, primary_key=True)
    reporting_item_id: int | None = Field(default=None, index=True)
    rule_code: str = Field(index=True, unique=True)
    rule_name: str
    rule_type: str = "VALIDATION"
    rule_expression: str = Field(default="", sa_column=Column(Text))
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DataSystemCatalog(SQLModel, table=True):
    __tablename__ = "data_system_catalog"

    id: int | None = Field(default=None, primary_key=True)
    system_code: str = Field(index=True, unique=True)
    system_name: str
    system_type: str = ""
    owner_team: str = ""
    description: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DataFieldCatalog(SQLModel, table=True):
    __tablename__ = "data_field_catalog"

    id: int | None = Field(default=None, primary_key=True)
    data_system_id: int | None = Field(default=None, index=True)
    field_code: str = Field(index=True, unique=True)
    field_name: str
    table_name: str
    column_name: str
    data_type: str = "VARCHAR"
    business_meaning: str = Field(default="", sa_column=Column(Text))
    owner_team: str = ""
    sensitive_level: str = "INTERNAL"
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DataFieldCodeValue(SQLModel, table=True):
    __tablename__ = "data_field_code_values"
    __table_args__ = (UniqueConstraint("field_code", "value_code", name="uk_field_value"),)

    id: int | None = Field(default=None, primary_key=True)
    field_code: str = Field(index=True)
    code_set: str = Field(index=True)
    value_code: str = Field(index=True)
    value_name: str = Field(index=True)
    value_aliases: str = Field(default="[]", sa_column=Column(Text))
    parent_value_code: str = ""
    effective_from: str = ""
    effective_to: str = ""
    source: str = ""
    confidence_level: str = "MEDIUM"
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BusinessConceptValueMapping(SQLModel, table=True):
    __tablename__ = "business_concept_value_mappings"
    __table_args__ = (
        UniqueConstraint("concept_code", "field_code", "value_code", name="uk_concept_field_value"),
    )

    id: int | None = Field(default=None, primary_key=True)
    concept_code: str = Field(index=True)
    concept_name: str = Field(index=True)
    field_code: str = Field(index=True)
    value_code: str = Field(index=True)
    value_name: str = ""
    match_aliases: str = Field(default="[]", sa_column=Column(Text))
    mapping_status: str = "DRAFT"
    confidence_score: float = 0.7
    evidence_text: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MeasureFieldMapping(SQLModel, table=True):
    __tablename__ = "measure_field_mappings"
    __table_args__ = (
        UniqueConstraint(
            "measure_concept_code",
            "reporting_object_code",
            "field_code",
            name="uk_measure_object_field",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    measure_concept_code: str = Field(index=True)
    measure_concept_name: str = Field(index=True)
    reporting_system_code: str = Field(default="1104", index=True)
    reporting_object_code: str = Field(index=True)
    reporting_section_code: str = ""
    field_code: str = Field(index=True)
    field_role: str = "MEASURE_FIELD"
    priority: int = 100
    confidence_score: float = 0.7
    status: str = "ACTIVE"
    evidence_text: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReportingItemLineage(SQLModel, table=True):
    __tablename__ = "reporting_item_lineage"

    id: int | None = Field(default=None, primary_key=True)
    reporting_item_id: int = Field(index=True)
    data_field_id: int = Field(index=True)
    lineage_role: str = Field(index=True)
    transform_expression: str = Field(default="", sa_column=Column(Text))
    confidence_level: str = "MEDIUM"
    mapping_status: str = "DRAFT"
    evidence: str = Field(default="", sa_column=Column(Text))
    owner_team: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)




class RegReportingChangeCandidate(SQLModel, table=True):
    __tablename__ = "reg_reporting_change_candidates"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    reporting_system_code: str = Field(index=True)
    reporting_object_code: str = Field(index=True)
    reporting_item_code: str = Field(index=True)
    change_type: str
    evidence_text: str = Field(default="", sa_column=Column(Text))
    confidence_score: float = 0.0
    review_status: str = "PENDING"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # —— 修订对照表 v2 字段（来自字段级修订条目，由 item_change_scanner 写入） ——
    revision_id: str = Field(default="", index=True)                              # "REV-1104-2026Q1-G31-007"
    field_code: str = Field(default="", index=True)                               # snake_case "indirect_holding_balance"
    change_dimensions: str = Field(default="[]", sa_column=Column(Text))          # JSON list ["口径","校验规则"]
    change_summary: str = Field(default="", sa_column=Column(Text))               # 一句话人话摘要
    before_after_snapshot: str = Field(default="{}", sa_column=Column(Text))      # JSON {"before":{...},"after":{...}}
    affected_cells: str = Field(default="[]", sa_column=Column(Text))             # JSON: item_code 列表


class RegReportingImpactItem(SQLModel, table=True):
    __tablename__ = "reg_reporting_impact_items"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    reporting_item_code: str = Field(index=True)
    impact_type: str
    impacted_reporting_field: str = ""
    impacted_source_fields: str = Field(default="[]", sa_column=Column(Text))
    impacted_lineage_roles: str = Field(default="[]", sa_column=Column(Text))
    impact_reason: str = Field(default="", sa_column=Column(Text))
    recommended_action: str = Field(default="", sa_column=Column(Text))
    ticket_parent_type: str = ""
    required_sub_ticket_types: str = Field(default="[]", sa_column=Column(Text))
    conditional_sub_ticket_types: str = Field(default="[]", sa_column=Column(Text))
    sub_ticket_triggers: str = Field(default="{}", sa_column=Column(Text))
    confidence_level: str = "MEDIUM"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReportingImpactReview(SQLModel, table=True):
    __tablename__ = "reporting_impact_review"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True, unique=True)
    status: str = Field(default="EDITING", max_length=20)
    review_content: str = Field(default="{}", sa_column=Column(Text))
    ai_baseline_content: str = Field(default="{}", sa_column=Column(Text))
    confirmed_at: datetime | None = None
    confirmed_by: str = Field(default="", max_length=64)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TicketDraft(SQLModel, table=True):
    __tablename__ = "ticket_drafts"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    title: str
    content: str = Field(sa_column=Column(Text))
    # 母子单结构相关字段
    parent_ticket_id: int | None = Field(default=None, index=True)
    ticket_role: str = Field(default="PARENT", index=True)           # PARENT / CHILD
    change_ticket_type: str = ""                                     # ChangeTicketType
    action_ticket_type: str = ""                                     # ActionTicketType
    severity_level: str = ""                                         # L1/L2/L3/L4
    severity_score: int = 0
    severity_signals: str = Field(default="[]", sa_column=Column(Text))
    severity_forced_reason: str = ""
    severity_overridden_by: str = ""
    owner_role: str = ""
    executor_role: str = ""
    depends_on_lineage: bool = False
    business_signoff_required: bool = False
    closure_review_required: bool = False
    related_impact_codes: str = Field(default="[]", sa_column=Column(Text))
    summary: str = Field(default="", sa_column=Column(Text))
    responsible_system: str = Field(default="", max_length=80)
    affected_systems: str = Field(default="[]", sa_column=Column(Text))
    affected_assets: str = Field(default="{}", sa_column=Column(Text))
    business_note: str = Field(default="", sa_column=Column(Text))
    must_do: str = Field(default="[]", sa_column=Column(Text))
    must_confirm: str = Field(default="[]", sa_column=Column(Text))
    output_artifacts: str = Field(default="[]", sa_column=Column(Text))
    acceptance_criteria_structured: str = Field(default="[]", sa_column=Column(Text))
    blockers: str = Field(default="[]", sa_column=Column(Text))
    evidence_refs: str = Field(default="[]", sa_column=Column(Text))
    historical_cases: str = Field(default="[]", sa_column=Column(Text))
    quality_score: int = 0
    quality_flags: str = Field(default="[]", sa_column=Column(Text))
    status: str = "DRAFT"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    action: str
    target_type: str
    target_id: int | None = None
    detail: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegClause(SQLModel, table=True):
    __tablename__ = "reg_clauses"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(index=True)
    chapter_no: str = ""
    chapter_title: str = ""
    clause_no: str = ""
    clause_text: str = Field(sa_column=Column(Text))
    clause_level: int = 1
    parent_clause_id: int | None = None
    source_page: int | None = None
    source_position: str = ""
    text_hash: str = ""
    review_status: str = "PENDING"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegSemanticItem(SQLModel, table=True):
    __tablename__ = "reg_semantic_items"

    id: int | None = Field(default=None, primary_key=True)
    clause_id: int = Field(index=True)
    semantic_type: str
    semantic_name: str
    semantic_value: str
    normalized_value: str = ""
    evidence_text: str = Field(default="", sa_column=Column(Text))
    confidence_score: float = 0.8
    extract_method: str = "MOCK_RULE"
    review_status: str = "PENDING"
    reviewer: str = ""
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)



class DocumentTaskProfile(SQLModel, table=True):
    __tablename__ = "document_task_profiles"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(index=True)
    document_type: str = ""
    # 1104指标变更扫描结果（新字段）
    affected_table_codes: str = Field(default="[]", sa_column=Column(Text))
    change_signals: str = Field(default="[]", sa_column=Column(Text))
    in_scope_tables: str = Field(default="[]", sa_column=Column(Text))
    out_of_scope_tables: str = Field(default="[]", sa_column=Column(Text))
    # 旧版通用分类字段（保留兼容）
    regulatory_topics: str = Field(default="[]", sa_column=Column(Text))
    matched_business_objects: str = Field(default="[]", sa_column=Column(Text))
    matched_terms: str = Field(default="[]", sa_column=Column(Text))
    candidate_domains: str = Field(default="[]", sa_column=Column(Text))
    candidate_impacts: str = Field(default="[]", sa_column=Column(Text))
    task_type: str = "MANUAL_REVIEW"
    requires_business_object_match: bool = False
    data_governance_relevance: str = "UNCERTAIN"
    suggested_route: str = "MANUAL_REVIEW"
    should_create_task: bool = False
    confidence_score: float = 0.0
    reason: str = Field(default="", sa_column=Column(Text))
    evidence_text: str = Field(default="", sa_column=Column(Text))
    llm_model: str = ""
    raw_response: str = Field(default="", sa_column=Column(Text))
    review_status: str = "PENDING"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingRuleCard(SQLModel, table=True):
    """报送规则卡片（L1/L2/L3）。承载填报说明里"一条规则"的结构化形态。

    见 docs/rule-card-and-concept-kb-design.md 第 3 节。
    """

    __tablename__ = "reg_reporting_rule_card"

    id: int | None = Field(default=None, primary_key=True)
    card_code: str = Field(index=True, unique=True)  # 业务主键 RC_G31_BOND_SCOPE_001
    reporting_object_code: str | None = Field(default=None, index=True)  # 对象级时仅填此项
    reporting_item_code: str | None = Field(default=None, index=True)
    card_level: str = Field(default="L1", index=True)  # L1 / L2 / L3
    card_title: str
    card_text: str = Field(sa_column=Column(Text))  # L1 原文摘录；L2/L3 也保留人话版本

    # L2 四元组
    card_subject: str | None = None
    card_predicate: str | None = None  # INCLUDES / EXCLUDES / EQUALS / DEPENDS_ON / APPLIES_WHEN / CONSTRAINS
    card_object: str | None = Field(default=None, sa_column=Column(Text))
    card_qualifier: str | None = Field(default=None, sa_column=Column(Text))

    # L3 可执行表达式（一期不实现，字段预留）
    card_expression: str | None = Field(default=None, sa_column=Column(Text))
    card_expression_lang: str | None = None  # SQL / DSL

    # 来源与防幻觉锚点
    source_document_id: int | None = Field(default=None, index=True)
    source_location: str = ""
    evidence_text: str = Field(default="", sa_column=Column(Text))
    evidence_verified: bool = False

    # 生效版本
    effective_from_version: str | None = None
    effective_to_version: str | None = None

    confidence_level: str = "MEDIUM"  # HIGH / MEDIUM / LOW
    review_status: str = Field(default="PENDING", index=True)  # PENDING / CONFIRMED / AUTO_APPROVED / REJECTED / DEPRECATED
    status: str = Field(default="DRAFT", index=True)  # ACTIVE / DRAFT / ARCHIVED

    created_by: str = ""
    updated_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingRuleCardConceptMap(SQLModel, table=True):
    """规则卡片 ↔ 概念，多对多。"""

    __tablename__ = "reg_reporting_rule_card_concept_map"
    __table_args__ = (UniqueConstraint("card_id", "concept_id", "role", name="uk_card_concept_role"),)

    id: int | None = Field(default=None, primary_key=True)
    card_id: int = Field(index=True)
    concept_id: int = Field(index=True)
    role: str  # SUBJECT / OBJECT / QUALIFIER / RELATED
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingRuleCardValidation(SQLModel, table=True):
    """工单提交后由卡片驱动的 AI 复核记录。提示不阻断。"""

    __tablename__ = "reg_reporting_rule_card_validation"

    id: int | None = Field(default=None, primary_key=True)
    card_id: int = Field(index=True)
    ticket_draft_id: int = Field(index=True)
    validation_result: str  # PASS / SUSPECTED_VIOLATION / UNCLEAR / NOT_APPLICABLE
    validation_reason: str = Field(default="", sa_column=Column(Text))
    validator_type: str  # LLM_JUDGE / SQL_EXEC / MANUAL
    evidence_snippet: str = Field(default="", sa_column=Column(Text))
    human_override: str = "UNDECIDED"  # ACCEPT / REJECT / UNDECIDED
    human_comment: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegConcept(SQLModel, table=True):
    """监管报送概念主表（轻量本体的"实体"层）。"""

    __tablename__ = "reg_concept"

    id: int | None = Field(default=None, primary_key=True)
    concept_code: str = Field(index=True, unique=True)  # CON_BOND_INVESTMENT_BAL
    canonical_name: str = Field(index=True)
    short_definition: str = ""
    full_definition: str = Field(default="", sa_column=Column(Text))
    concept_type: str = Field(default="METRIC", index=True)  # METRIC / SCOPE / CLASSIFICATION / CALCULATION / DIMENSION / ENTITY
    reporting_system_scope: str = Field(default="", index=True)  # 1104 / EAST / CROSS
    current_version_no: int = 1
    is_locked: bool = False  # True 时禁止 LLM 自动 apply 修改
    status: str = Field(default="ACTIVE", index=True)
    created_by: str = ""
    reviewed_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RegConceptAlias(SQLModel, table=True):
    """概念别名/同义词。监管发文常常换说法，由此回归到 canonical_name。"""

    __tablename__ = "reg_concept_alias"
    __table_args__ = (UniqueConstraint("concept_id", "alias_text", name="uk_concept_alias"),)

    id: int | None = Field(default=None, primary_key=True)
    concept_id: int = Field(index=True)
    alias_text: str = Field(index=True)
    alias_source: str = "INTERNAL"  # REGULATION / INTERNAL / SYNONYM / HISTORICAL
    source_document_id: int | None = None
    evidence_text: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegConceptVersion(SQLModel, table=True):
    """概念定义的演化历史。这是"全年 N 次小改动"的载体。"""

    __tablename__ = "reg_concept_version"
    __table_args__ = (UniqueConstraint("concept_id", "version_no", name="uk_concept_version"),)

    id: int | None = Field(default=None, primary_key=True)
    concept_id: int = Field(index=True)
    version_no: int
    definition_text: str = Field(sa_column=Column(Text))
    change_summary: str = Field(default="", sa_column=Column(Text))
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    source_document_id: int | None = None
    evidence_text: str = Field(default="", sa_column=Column(Text))
    extraction_job_id: int | None = Field(default=None, index=True)
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegConceptRelation(SQLModel, table=True):
    """概念三元组（RDF 风格）。"""

    __tablename__ = "reg_concept_relation"
    __table_args__ = (
        UniqueConstraint("from_concept_id", "to_concept_id", "relation_type", name="uk_relation"),
    )

    id: int | None = Field(default=None, primary_key=True)
    from_concept_id: int = Field(index=True)
    to_concept_id: int = Field(index=True)
    relation_type: str  # INCLUDES / EXCLUDES / SUBSET_OF / DEPENDS_ON / SYNONYM / PREDECESSOR / REPLACES
    confidence_level: str = "MEDIUM"
    evidence_ref: str = ""
    created_by: str = ""
    reviewed_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegConceptReportingItemMap(SQLModel, table=True):
    """概念 ↔ 报送项映射。新发文命中一个概念时，由此放大召回到所有相关报送项。"""

    __tablename__ = "reg_concept_reporting_item_map"
    __table_args__ = (
        UniqueConstraint("concept_id", "reporting_item_code", "role", name="uk_concept_item_role"),
    )

    id: int | None = Field(default=None, primary_key=True)
    concept_id: int = Field(index=True)
    reporting_item_code: str = Field(index=True)
    role: str  # PRIMARY_METRIC / FILTER / EXCLUSION / DENOMINATOR / DIMENSION / ANNOTATION
    confidence_level: str = "MEDIUM"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegConceptEmbedding(SQLModel, table=True):
    """概念向量缓存（独立表）。

    设计依据 docs/concept-and-ticket-reuse-design.md §3 补丁 A 路 4。

    为什么独立表（不放主表字段）：
    - 未来换 embedding 模型时可并存多套向量，按 model_name 切换；不污染主表
    - 主表 RegConcept 保持业务字段纯净，迁移代价低
    - 向量列是 BLOB，与文本检索完全解耦

    vector 字段为 float32 小端序列化（struct.pack("<{dim}f", ...)），
    避免 JSON 浮点精度损失 + 体积膨胀。
    """

    __tablename__ = "reg_concept_embedding"
    __table_args__ = (
        UniqueConstraint("concept_id", "model_name", name="uk_concept_embedding"),
    )

    id: int | None = Field(default=None, primary_key=True)
    concept_id: int = Field(index=True)
    model_name: str = Field(index=True)  # 例 text-embedding-v3 / bge-m3
    dim: int  # 向量维度
    vector: bytes = Field(sa_column=Column(LargeBinary))  # float32 序列化
    source_text: str = Field(default="", sa_column=Column(Text))  # 生成时喂给模型的文本
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RegCatalogBatch(SQLModel, table=True):
    __tablename__ = "reg_catalog_batches"

    id: int | None = Field(default=None, primary_key=True)
    batch_code: str = Field(index=True, unique=True)
    source_zip_filename: str = ""
    source_document_ref: str = ""
    version_label: str = ""
    total_count: int = 0
    done_count: int = 0
    fail_count: int = 0
    status: str = "PENDING"   # PENDING / PROCESSING / DONE / PARTIAL_FAIL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class RegCatalogBatchItem(SQLModel, table=True):
    __tablename__ = "reg_catalog_batch_items"

    id: int | None = Field(default=None, primary_key=True)
    batch_id: int = Field(index=True)
    object_code: str = Field(index=True)
    change_type: str = ""          # NEW / MODIFIED / INSTRUCTION_ONLY
    table_category: str = ""
    excel_filename: str = ""
    doc_filename: str = ""
    parse_status: str = "PENDING"  # PENDING / PARSING / DONE / FAILED
    parse_error: str = Field(default="", sa_column=Column(Text))
    change_summary: str = Field(default="", sa_column=Column(Text))
    items_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class RegReportingTemplate(SQLModel, table=True):
    __tablename__ = "reg_reporting_templates"

    id: int | None = Field(default=None, primary_key=True)
    reporting_object_id: int = Field(index=True)
    batch_item_id: int | None = Field(default=None, index=True)
    template_code: str = Field(index=True, unique=True)
    template_name: str
    version_label: str = ""
    sheet_name: str = ""
    source_file: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingTemplateCell(SQLModel, table=True):
    __tablename__ = "reg_reporting_template_cells"

    id: int | None = Field(default=None, primary_key=True)
    template_id: int = Field(index=True)
    sheet_name: str = ""
    row_index: int = 0
    col_index: int = 0
    excel_ref: str = ""            # "D8"
    raw_text: str = Field(default="", sa_column=Column(Text))
    cell_type: str = ""            # FILLABLE / DERIVED / NO_DATA / HEADER
    style_json: str = Field(default="{}", sa_column=Column(Text))
    merge_json: str = Field(default="{}", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingDimension(SQLModel, table=True):
    __tablename__ = "reg_reporting_dimensions"

    id: int | None = Field(default=None, primary_key=True)
    reporting_object_id: int = Field(index=True)
    dimension_code: str = Field(index=True, unique=True)
    dimension_name: str
    axis: str = "ROW"              # ROW / COLUMN
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingDimensionMember(SQLModel, table=True):
    __tablename__ = "reg_reporting_dimension_members"

    id: int | None = Field(default=None, primary_key=True)
    dimension_id: int = Field(index=True)
    member_code: str = Field(index=True, unique=True)
    member_name: str
    parent_member_id: int | None = Field(default=None, index=True)
    level_no: int = 1
    display_order: int = 0
    source_cell_ref: str = ""
    metadata_json: str = Field(default="{}", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingItemDimension(SQLModel, table=True):
    __tablename__ = "reg_reporting_item_dimensions"
    __table_args__ = (UniqueConstraint("reporting_item_id", "dimension_id", "member_id"),)

    id: int | None = Field(default=None, primary_key=True)
    reporting_item_id: int = Field(index=True)
    dimension_id: int = Field(index=True)
    member_id: int = Field(index=True)
    axis: str = "ROW"              # ROW / COLUMN
    display_order: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
