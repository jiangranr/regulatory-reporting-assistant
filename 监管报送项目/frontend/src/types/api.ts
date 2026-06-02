export type DocumentStatus = "UPLOADED" | "PARSED" | "FAILED";
export type TaskStatus = "CREATED" | "RULE_EXTRACTED" | "IMPACT_ANALYZED" | "TICKET_GENERATED";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface DashboardStats {
  confirmed_lineage: number;
  total_lineage: number;
  pending_tickets: number;
  confirmed_tickets_month: number;
  active_tasks: number;
  pending_review: number;
}

export interface SourceFieldDependency {
  reporting_item_code: string;
  reporting_item_name: string;
  reporting_object_code: string;
  lineage_role: string;
  mapping_status: string;
  confidence_level: string;
}

export interface SourceFieldDependencies {
  field_code: string;
  field_name: string;
  owner_team: string;
  system_code: string;
  system_name: string;
  regulatory_dependencies: SourceFieldDependency[];
  dependency_count: number;
}

export interface SourceField {
  field_code: string;
  field_name: string;
  system_code: string;
  system_name: string;
  owner_team: string;
  regulatory_dependency_count: number;
}
export type WorkflowStepStatus = "PENDING" | "RUNNING" | "DONE" | "REVIEW_REQUIRED" | "FAILED";

export interface RegDocument {
  id: number;
  filename: string;
  content_type: string;
  storage_path: string;
  title: string;
  text_excerpt: string;
  parsed_text: string;
  status: DocumentStatus;
  parse_status: DocumentStatus;
  parser: string;
  char_count: number;
  paragraph_count: number;
  table_count: number;
  parse_quality: string;
  parse_error_message: string;
  created_at: string;
}

export interface RawDocumentFile {
  filename: string;
  role: string;
  role_label: string;
  source: string;
  text: string;
  error_message?: string;
}

export interface RawDocumentText {
  document_id: number;
  title: string;
  filename: string;
  source: string;
  text: string;
  files?: RawDocumentFile[];
}

export interface RegTask {
  id: number;
  document_id: number;
  title: string;
  status: TaskStatus;
  risk_level: RiskLevel;
  created_at: string;
  updated_at: string;
}

export interface ImpactItem {
  reporting_item_code: string;
  reporting_item_name?: string;
  impact_type: string;
  impacted_reporting_field: string;
  impacted_source_fields: string[];
  impacted_lineage_roles: string[];
  impact_reason: string;
  recommended_action: string;
  confidence_level: string;
  risk_level: RiskLevel;
  /** ROW = 行指标新增/删除；COLUMN = 列度量变更；CELL = 单 cell 口径；UNCLEAR = 未知 */
  change_axis?: string;
  /** true = 经过真实 LLM 分析；false = mock/关键词路由 */
  llm_analyzed?: boolean;
}

export interface TicketDraft {
  id: number | null;
  task_id: number;
  title: string;
  content: string;
  parent_ticket_id: number | null;
  ticket_role: "PARENT" | "CHILD";
  change_ticket_type: string;
  action_ticket_type: string;
  severity_level: "" | "L1" | "L2" | "L3" | "L4";
  severity_score: number;
  severity_signals: string;
  severity_forced_reason: string;
  severity_overridden_by: string;
  owner_role: string;
  executor_role: string;
  depends_on_lineage: boolean;
  business_signoff_required: boolean;
  closure_review_required: boolean;
  related_impact_codes: string;
  summary: string;
  responsible_system: string;
  affected_systems: string;
  affected_assets: string;
  business_note: string;
  must_do: string;
  must_confirm: string;
  output_artifacts: string;
  acceptance_criteria_structured: string;
  blockers: string;
  evidence_refs: string;
  historical_cases: string;
  quality_score: number;
  quality_flags: string;
  status: string;
  created_at: string | null;
}

export interface TicketPlanResponse {
  parent: TicketDraft;
  children: TicketDraft[];
}

export type ResponsibleSystem =
  | "REG_REPORTING_SYSTEM"
  | "DATA_GOVERNANCE_PLATFORM"
  | "DATA_MART_ETL"
  | "SOURCE_SYSTEM"
  | "DATA_QUALITY_PLATFORM"
  | "TEST_ACCEPTANCE"
  | "KNOWLEDGE_ARCHIVE";

export type ImpactReviewStatus = "EDITING" | "SAVED" | "CONFIRMED";
export type ImpactReviewFieldSource = "AI" | "BUSINESS";

export interface ImpactReviewField {
  field_code: string;
  field_name: string;
  lineage_role: string;
  source: ImpactReviewFieldSource;
  selected: boolean;
  edited?: boolean;
  removed?: boolean;
  is_required?: boolean;
}

export interface ImpactReviewSystem {
  // 后端按真实 data_system_catalog.system_code 分桶（如 "RPT_1104"/"VALUATION"），
  // 不再局限于抽象的 ResponsibleSystem enum；保留 ResponsibleSystem 类型用于兼容
  // 旧支持单（TEST_ACCEPTANCE/KNOWLEDGE_ARCHIVE 等）。
  responsible_system: ResponsibleSystem | string;
  responsible_system_zh: string;
  // 用于下游推 action_type/owner_team，缺失时取空串
  system_type?: string;
  owner_team?: string;
  fields: ImpactReviewField[];
}

export interface ImpactReviewItem {
  reporting_item_code: string;
  reporting_item_name: string;
  removed: boolean;
  business_note: string;
  systems: ImpactReviewSystem[];
}

export interface ImpactReviewContent {
  version: "v1";
  items: ImpactReviewItem[];
}

export interface ImpactReviewStats {
  total_items: number;
  total_systems: number;
  selected_fields: number;
  business_added_fields: number;
  business_removed_fields: number;
}

export interface ImpactReviewSystemOption {
  system_code: string;
  system_name: string;
  system_type: string;
  owner_team: string;
}

export interface ImpactReviewResponse {
  status: ImpactReviewStatus;
  review: ImpactReviewContent;
  ai_baseline: ImpactReviewContent;
  stats: ImpactReviewStats;
  system_options: ImpactReviewSystemOption[];
}

export interface ExecutionTask {
  team: ResponsibleSystem;
  team_zh: string;
  action: string;
  ticket_id: number;
  is_blocker: boolean;
  blocker_reason?: string | null;
}

// ── 参考 SQL API types ─────────────────────────────────────────────────────
// Keep synchronized with backend/app/models/schemas.py::ReferenceSqlResponse

export type SqlStatus =
  | "NOT_GENERATED"
  | "READY"
  | "DEGRADED"
  | "EDITED_BY_USER"
  | "STALE"
  | "NOT_APPLICABLE";

export type SqlAbility =
  | "CAN_GENERATE"
  | "PARTIAL"
  | "VALIDATION_ONLY"
  | "NOT_APPLICABLE"
  | "";

export type SqlWarningSeverity = "ERROR" | "WARNING" | "INFO";

export type SqlWarningType =
  | "FIELD_NOT_IN_SCOPE"
  | "TABLE_NOT_IN_CATALOG"
  | "SYNTAX_ERROR"
  | "LLM_FAILED";

export interface SqlWarning {
  type: SqlWarningType | string;
  message: string;
  field_code: string;
  severity: SqlWarningSeverity;
}

export interface ReferenceSqlResponse {
  ticket_id: number;
  status: SqlStatus;
  ability: SqlAbility;
  reference_sql: string;
  sql_dialect: string;
  confidence: number;
  explanation: string;
  assumptions: string[];
  warnings: SqlWarning[];
  not_applicable_reason: string;
  generated_at: string | null;
  generated_by: string;
}

export interface ExecutionPhase {
  phase_name: string;
  tasks: ExecutionTask[];
}

export interface CriticalRisk {
  severity: "HIGH" | "MEDIUM" | "LOW";
  description: string;
  ticket_id_ref: number | null;
  mitigation: string;
}

export interface ExecutionPlan {
  task_id: number;
  executive_summary: string;
  estimated_duration: string;
  execution_phases: ExecutionPhase[];
  critical_risks: CriticalRisk[];
  team_coordination: string;
  generated_at: string;
  generated_by: string;
  confidence: number;
  needs_human_review: boolean;
}

export interface ExecutionPlanResponse {
  status: "NOT_GENERATED" | "READY" | "DEGRADED" | "STALE";
  plan: ExecutionPlan | null;
  warning?: string;
}

export interface RegClause {
  id: number;
  document_id: number;
  clause_no: string;
  clause_text: string;
  clause_level: number;
  review_status: string;
  created_at: string;
}

export interface RegSemanticItem {
  id: number;
  clause_id: number;
  semantic_type: string;
  semantic_name: string;
  semantic_value: string;
  evidence_text: string;
  confidence_score: number;
  review_status: string;
}

// 旧 rule_library 主线已删除（RuleLibrarySeed / BusinessObject / MetadataField /
// ObjectFieldMapping 已下线，详见 docs/rule-card-and-concept-kb-design.md 第 1.5 节）。

export interface ObjectFieldMapping {
  // 保留 ObjectFieldMapping 类型以兼容 TaskWorkflow.field_mappings 字段，后端
  // 当前总是返回空数组。二期清理。
  id?: number | null;
  object_code: string;
  item_code: string;
  regulatory_term: string;
  field_code: string;
  field_name: string;
  column_name: string;
  table_name: string;
  system_name: string;
  system_code: string;
  lineage_role: string;
  mapping_type?: string;
  confidence_level?: string;
  mapping_status: string;
}

export type TableChangeType =
  | "ADD"
  | "MODIFY"
  | "DELETE"
  | "SCOPE_ADJUST"
  | "INSTRUCTION_ADJUST"
  | "UNCLEAR";

export interface RevisionSpan {
  type: "TEXT" | "INSERT" | "DELETE";
  text: string;
  author?: string;
  date?: string;
  action?: string;
}

export interface TableChangeSignal {
  business_signal_id?: string;
  item_codes?: string[];
  table_code: string;
  section_hint: string;
  indicator_hint: string;
  change_type: TableChangeType;
  evidence_text: string;
  change_summary?: string;
  business_summary?: string;
  changed_dimension?: string;
  changed_from?: string;
  changed_to?: string;
  summary_confidence?: number;
  revision_actions?: Record<string, unknown>[];
  revision_spans?: RevisionSpan[];
  candidate_sources?: Partial<TableChangeSignal>[];
  confidence: number;
  evidence_verified: boolean;
  source_type?: "LLM" | "REVISION_TABLE" | "EXCEL_DIFF" | "RULE_BASED";
  grounding_status?: "VERIFIED" | "PARTIAL" | "UNVERIFIED" | "RULE_BASED";
  grounding_coverage?: number;
  matched_excerpt?: string;
  human_review_status?: "PENDING" | "ACCEPTED" | "REJECTED" | "CORRECTED";
  matched_item_code?: string;
  match_status?: string;
  composite_match?: CompositeSemanticMatch;
  llm_summary?: string | {
    change_summary?: string;
    business_summary?: string;
    display_title?: string;
    business_meaning?: string;
  };
}

export interface HallucinationMetrics {
  total_signals: number;
  ai_signals: number;
  rule_based_signals: number;
  verified_signals: number;
  partial_signals: number;
  unverified_signals: number;
  isolated_signals: number;
  grounding_rate: number;
  suspected_hallucination_rate: number;
  isolation_rate: number;
  pending_review_signals: number;
  accepted_signals: number;
  rejected_signals: number;
  corrected_signals: number;
  human_acceptance_rate: number;
}

export interface SignalReviewResponse {
  signal: TableChangeSignal;
  metrics: HallucinationMetrics;
}

export interface CompositeSemanticMatch {
  match_type: string;
  pattern_code: string;
  indicator_hint: string;
  measure_phrase: string;
  condition_phrase: string;
  reporting_item_codes: string[];
  measure_field_codes: string[];
  condition_field_codes: string[];
  matched_concepts: Array<{
    concept_code: string;
    concept_name: string;
    concept_type: string;
    matched_alias: string;
  }>;
  measure_fields: Array<{
    field_code: string;
    field_name: string;
    table_name: string;
    column_name: string;
    field_role: string;
    confidence_score: number;
  }>;
  filter_conditions: Array<{
    field_code: string;
    field_name: string;
    operator: string;
    value_code: string;
    value_name: string;
    confidence_level: string;
  }>;
  conditions?: Array<{
    field_code: string;
    field_name: string;
    operator: string;
    value_code: string;
    value_name: string;
    confidence_level: string;
  }>;
  confidence: number;
  review_status: string;
  needs_review: boolean;
  evidence_text: string;
}

export interface DocumentTaskProfile {
  id: number | null;
  document_id: number;
  document_type: string;
  // 1104 指标变更扫描结果
  affected_table_codes: string[];
  change_signals: TableChangeSignal[];
  in_scope_tables: string[];
  out_of_scope_tables: string[];
  // 通用决策字段
  suggested_route: string;
  should_create_task: boolean;
  confidence_score: number;
  reason: string;
  evidence_text: string;
  llm_model: string;
  review_status: string;
  raw_response: string;
  created_at: string | null;
}

// 报送规则卡片(L1/L2/L3)。对应后端 reg_reporting_rule_card 表。
// 详细设计：docs/rule-card-and-concept-kb-design.md 第 3 节。
export type CardLevel = "L1" | "L2" | "L3";
export type CardPredicate =
  | "INCLUDES"
  | "EXCLUDES"
  | "EQUALS"
  | "DEPENDS_ON"
  | "APPLIES_WHEN"
  | "CONSTRAINS";

export interface RuleCard {
  id: number | null;
  card_code: string;
  reporting_object_code: string | null;
  reporting_item_code: string | null;
  card_level: CardLevel;
  card_title: string;
  card_text: string;
  card_subject?: string | null;
  card_predicate?: CardPredicate | null;
  card_object?: string | null;
  card_qualifier?: string | null;
  source_document_id?: number | null;
  source_location: string;
  evidence_text: string;
  evidence_verified: boolean;
  effective_from_version?: string | null;
  effective_to_version?: string | null;
  confidence_level: "HIGH" | "MEDIUM" | "LOW";
  review_status:
    | "PENDING"
    | "CONFIRMED"
    | "AUTO_APPROVED"
    | "REJECTED"
    | "DEPRECATED";
  status: "ACTIVE" | "DRAFT" | "ARCHIVED";
  related_concept_codes: string[];
}

// 监管报送概念知识库
export type ConceptType =
  | "METRIC"
  | "SCOPE"
  | "CLASSIFICATION"
  | "CALCULATION"
  | "DIMENSION"
  | "ENTITY";

export interface Concept {
  id: number | null;
  concept_code: string;
  canonical_name: string;
  short_definition: string;
  full_definition: string;
  concept_type: ConceptType;
  reporting_system_scope: string;
  current_version_no: number;
  is_locked: boolean;
  status: string;
  aliases: string[];
  related_reporting_item_codes: string[];
}

export interface ConceptMatchHit {
  concept_code: string;
  canonical_name: string;
  matched_alias: string;
  match_offset: number;
  match_length: number;
  related_reporting_item_codes: string[];
  /** 召回路径，元素取值 'alias' / 'definition' / 'embedding'，可多路同时命中 */
  paths?: string[];
  /** 多路加权得分，前端可按需做排序/透传 */
  score?: number;
}

// 手动抽取结果(POST /api/extraction-jobs/manual 返回)
export interface ExtractionResult {
  document_id: number;
  inferred_object_code: string;
  rule_cards_created: number;
  concepts_created: number;
  aliases_created: number;
  card_concept_links_created: number;
  rule_cards_skipped: number;
  concepts_skipped: number;
  llm_used: boolean;
  error_message: string;
}

export interface WorkflowStep {
  code: "document" | "clauses" | "impact" | "rule_cards" | "ticket";
  name: string;
  status: WorkflowStepStatus;
}

export interface TaskWorkflow {
  task: RegTask;
  document: RegDocument;
  document_profile: DocumentTaskProfile | null;
  steps: WorkflowStep[];
  clauses: RegClause[];
  semantic_items: RegSemanticItem[];
  field_mappings: ObjectFieldMapping[];
  reporting_candidates: Array<{
    reporting_system_code: string;
    reporting_object_code: string;
    reporting_item_code: string;
    change_type: string;
    evidence_text: string;
    confidence_score: number;
    review_status: string;
  }>;
  lineage_candidates: Array<{
    field_code: string;
    field_name: string;
    table_name: string;
    column_name: string;
    data_type: string;
    business_meaning: string;
    owner_team: string;
    lineage_role: string;
    transform_expression: string;
    confidence_level: string;
    mapping_status: string;
  }>;
  impact_items: ImpactItem[];
  rule_cards: RuleCard[];
  ticket_drafts: TicketDraft[];
}

export interface InstructionChangeItem {
  category: string;
  change: string;
  evidence: string;
}

export interface InstructionChangeAnalysis {
  object_code: string;
  summary: string;
  key_changes: InstructionChangeItem[];
  attention_items: string[];
  uncertain_items: string[];
  comments_count: number;
  revisions_count: number;
  highlights_count: number;
  llm_model: string;
  error_message: string;
}

export interface CatalogBatchItem {
  id: number;
  object_code: string;
  change_type: string;           // NEW | MODIFIED | INSTRUCTION_ONLY
  table_category: string;
  parse_status: 'PENDING' | 'PARSING' | 'DONE' | 'FAILED';
  parse_error: string;
  change_summary: string;
  items_count: number;
}

export interface RevisionEntry {
  table_code: string;
  section: string;
  row_label: string;
  column_label: string;
  change_type: "NEW" | "MODIFIED" | "DELETED" | "UNCHANGED";
  change_desc: string;
}

export interface ExcelDiffEntry {
  item_code: string;
  row_label: string;
  column_label: string;
  diff_type: "NEW" | "REMOVED" | "LABEL_CHANGED" | "UNCHANGED";
  old_row_label: string;
  old_col_label: string;
  evidence: string;
}

export type LaneSource = "REVISION_TABLE" | "EXCEL_DIFF" | "INSTRUCTION";

export interface ItemChangeScanResult {
  item_code: string;
  row_label: string;
  column_label: string;
  old_status: string;
  new_status: string;
  source: LaneSource;
  confidence: number;
  evidence: string;
  overridden_sources: LaneSource[];
}

export interface LaneSignal {
  item_code: string;
  row_label: string;
  column_label: string;
  change_type: string;
  confidence: number;
  evidence: string;
  won: boolean;
}

export interface RevisionCandidate {
  table_code: string;
  section: string;
  row_label: string;
  column_label: string;
  change_type: string;
  change_desc: string;
  match_status: string;
  matched_item_code: string;
  confidence: number;
  evidence: string;
  reason: string;
  // —— v2 字段维度 ——
  revision_id?: string;
  regime_version?: string;
  field_code?: string;
  field_name?: string;
  change_dimensions?: string[];
  change_summary?: string;
  before_value?: Record<string, unknown>;
  after_value?: Record<string, unknown>;
  regulation_evidence?: string;
  evidence_source_ref?: string;
  affected_cells?: string[];
  effective_date?: string;
  matched_item_codes?: string[];
}

export interface TripletUploadResponse {
  document: RegDocument;
  template_parsed: boolean;
  instruction_parsed: boolean;
  revision_table_parsed: boolean;
  revision_entry_count: number;
  excel_diff_count: number;
  scan_results: ItemChangeScanResult[];
  scan_summary: string;
  excel_diff: ExcelDiffEntry[];
  revision_entries: RevisionEntry[];
  revision_lane: LaneSignal[];
  excel_lane: LaneSignal[];
  instruction_lane: LaneSignal[];
  revision_candidates: RevisionCandidate[];
  error_messages: string[];
}

export interface CatalogBatch {
  id: number;
  batch_code: string;
  version_label: string;
  source_zip_filename: string;
  source_document_ref?: string;
  total_count: number;
  done_count: number;
  fail_count: number;
  status: 'PENDING' | 'PROCESSING' | 'DONE' | 'PARTIAL_FAIL';
  created_at: string;
  finished_at?: string;
  items?: CatalogBatchItem[];
}

// ── 指标问答 ──────────────────────────────────────────────────────────────────

export type QAMode = 'explanation' | 'anomaly';
export type HypothesisStatus = 'checked' | 'uncertain' | 'out_of_scope';

export interface QAHypothesis {
  label: string;
  status: HypothesisStatus;
  evidence: string;
  action: string;
}

export interface QAInstructionExcerpt {
  text: string;
  source_label: string;
  item_name?: string;
  field_tag?: string;
  match_type?: "exact" | "keyword" | "semantic";
  score?: number;
}

export interface QALineageField {
  field_code: string;
  field_name: string;
  table_name: string;
  system_name: string;
  lineage_role: string;
}

export interface QARelatedTicket {
  ticket_id: number;
  title: string;
  status: string;
}

export interface QAResponse {
  mode: QAMode;
  item_code: string;
  item_name: string;
  // 解释模式
  instruction_excerpts: QAInstructionExcerpt[];
  plain_explanation: string;
  key_points: string[];
  // 排查模式
  hypotheses: QAHypothesis[];
  // 通用
  lineage_fields: QALineageField[];
  related_tickets: QARelatedTicket[];
  error: string;
}

export interface QAQueryableItem {
  item_code: string;
  item_name: string;
}
