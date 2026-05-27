# Ticket Governance Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the ticket module from long Markdown drafts into structured, system-owned governance task cards while keeping the regulatory upload/profile/lineage/impact/workflow main flow stable.

**Architecture:** Keep `POST /api/tasks/{task_id}/generate-ticket`, `GET /api/tasks/{task_id}/workflow`, and `ticket_drafts.content` compatible. Refactor the ticket module behind the existing entrypoint into focused services: trigger engine, card builder, quality checker, historical case service, and Markdown compatibility renderer. The frontend reads structured fields when present and falls back to existing Markdown for old tickets.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Pydantic, pytest, Vue 3, TypeScript, Vitest.

---

## Scope Boundary

Do not change the main flow semantics for document upload, document profiling, field positioning, impact analysis, or workflow aggregation. The ticket generation module may be refactored and its internals may change.

Keep compatibility:

- Existing `TicketDraft.content` remains populated.
- Existing `TicketPlanResponse` shape remains `parent + children`.
- Existing `TaskWorkflowResponse.ticket_drafts` remains populated.
- Old tickets without structured fields still render through Markdown.

## File Structure

### Backend Files

- Modify `监管报送项目/backend/app/models/enums.py`
  - Add `ResponsibleSystem`.
- Modify `监管报送项目/backend/app/models/db_models.py`
  - Add nullable structured fields to `TicketDraft`.
- Modify `监管报送项目/backend/app/models/schemas.py`
  - Add matching fields to `TicketDraftRead`.
- Modify `监管报送项目/backend/app/core/database.py`
  - Add old-database column backfill for new `ticket_drafts` columns.
- Create `监管报送项目/backend/app/services/ticket_trigger_engine.py`
  - Convert impact facts into action tickets and responsible systems.
- Create `监管报送项目/backend/app/services/ticket_card_builder.py`
  - Build structured `TicketTaskCard` objects.
- Create `监管报送项目/backend/app/services/ticket_quality_checker.py`
  - Score card completeness and maintainability.
- Create `监管报送项目/backend/app/services/decision_archive_service.py`
  - Return empty or DB-derived historical cases through a stable interface.
- Modify `监管报送项目/backend/app/services/reporting_ticket_generator.py`
  - Keep public `build_ticket_plan`; internally call the new services.
- Modify `监管报送项目/backend/app/api/routes_tasks.py`
  - Persist structured fields in parent and child ticket rows.

### Backend Tests

- Create `监管报送项目/backend/tests/test_ticket_trigger_engine.py`
- Create `监管报送项目/backend/tests/test_ticket_card_builder.py`
- Create `监管报送项目/backend/tests/test_ticket_quality_checker.py`
- Modify `监管报送项目/backend/tests/test_reporting_services.py`
- Modify or add route-level assertions in `监管报送项目/backend/tests/test_api_workflow.py`

### Frontend Files

- Modify `监管报送项目/frontend/src/types/api.ts`
  - Add structured fields to `TicketDraft`.
- Modify `监管报送项目/frontend/src/views/ReviewTicketView.vue`
  - Render structured task cards when present.
  - Group children by responsible system.
  - Remove fixed generic action block and fixed SQL block from default structured rendering.
  - Keep Markdown fallback for old tickets.
- Add or modify frontend tests under `监管报送项目/frontend/src/views` or `监管报送项目/frontend/src/__tests__`.

---

### Task 1: Extend TicketDraft Contract Without Breaking Old Rows

**Files:**
- Modify: `监管报送项目/backend/app/models/enums.py`
- Modify: `监管报送项目/backend/app/models/db_models.py`
- Modify: `监管报送项目/backend/app/models/schemas.py`
- Modify: `监管报送项目/backend/app/core/database.py`
- Modify: `监管报送项目/frontend/src/types/api.ts`
- Test: `监管报送项目/backend/tests/test_database_config.py`

- [ ] **Step 1: Add backend schema test for new MySQL columns**

Add this test to `监管报送项目/backend/tests/test_database_config.py`:

```python
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.models.db_models import TicketDraft


def test_ticket_draft_has_structured_governance_fields_for_mysql():
    ticket_ddl = str(CreateTable(TicketDraft.__table__).compile(dialect=mysql.dialect()))

    assert "summary TEXT" in ticket_ddl
    assert "responsible_system VARCHAR(80)" in ticket_ddl
    assert "affected_systems TEXT" in ticket_ddl
    assert "affected_assets TEXT" in ticket_ddl
    assert "must_do TEXT" in ticket_ddl
    assert "must_confirm TEXT" in ticket_ddl
    assert "output_artifacts TEXT" in ticket_ddl
    assert "acceptance_criteria_structured TEXT" in ticket_ddl
    assert "blockers TEXT" in ticket_ddl
    assert "evidence_refs TEXT" in ticket_ddl
    assert "historical_cases TEXT" in ticket_ddl
    assert "quality_score INTEGER" in ticket_ddl
    assert "quality_flags TEXT" in ticket_ddl
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_database_config.py::test_ticket_draft_has_structured_governance_fields_for_mysql -q
```

Expected: FAIL because the new columns are not defined.

- [ ] **Step 3: Add `ResponsibleSystem` enum**

Modify `监管报送项目/backend/app/models/enums.py`:

```python
class ResponsibleSystem(StrEnum):
    REG_REPORTING_SYSTEM = "REG_REPORTING_SYSTEM"
    DATA_GOVERNANCE_PLATFORM = "DATA_GOVERNANCE_PLATFORM"
    DATA_MART_ETL = "DATA_MART_ETL"
    SOURCE_SYSTEM = "SOURCE_SYSTEM"
    DATA_QUALITY_PLATFORM = "DATA_QUALITY_PLATFORM"
    TEST_ACCEPTANCE = "TEST_ACCEPTANCE"
    KNOWLEDGE_ARCHIVE = "KNOWLEDGE_ARCHIVE"
```

- [ ] **Step 4: Add structured fields to `TicketDraft`**

Modify `TicketDraft` in `监管报送项目/backend/app/models/db_models.py` after `related_impact_codes`:

```python
    summary: str = Field(default="", sa_column=Column(Text))
    responsible_system: str = Field(default="")
    affected_systems: str = Field(default="[]", sa_column=Column(Text))
    affected_assets: str = Field(default="{}", sa_column=Column(Text))
    must_do: str = Field(default="[]", sa_column=Column(Text))
    must_confirm: str = Field(default="[]", sa_column=Column(Text))
    output_artifacts: str = Field(default="[]", sa_column=Column(Text))
    acceptance_criteria_structured: str = Field(default="[]", sa_column=Column(Text))
    blockers: str = Field(default="[]", sa_column=Column(Text))
    evidence_refs: str = Field(default="[]", sa_column=Column(Text))
    historical_cases: str = Field(default="[]", sa_column=Column(Text))
    quality_score: int = 0
    quality_flags: str = Field(default="[]", sa_column=Column(Text))
```

- [ ] **Step 5: Add structured fields to `TicketDraftRead`**

Modify `TicketDraftRead` in `监管报送项目/backend/app/models/schemas.py` after `related_impact_codes`:

```python
    summary: str = ""
    responsible_system: str = ""
    affected_systems: str = "[]"
    affected_assets: str = "{}"
    must_do: str = "[]"
    must_confirm: str = "[]"
    output_artifacts: str = "[]"
    acceptance_criteria_structured: str = "[]"
    blockers: str = "[]"
    evidence_refs: str = "[]"
    historical_cases: str = "[]"
    quality_score: int = 0
    quality_flags: str = "[]"
```

- [ ] **Step 6: Add old database compatibility columns**

Modify `_ensure_ticket_draft_columns` in `监管报送项目/backend/app/core/database.py` by adding these entries to `new_cols`:

```python
        ("summary", "TEXT"),
        ("responsible_system", "VARCHAR(80) DEFAULT ''"),
        ("affected_systems", "TEXT"),
        ("affected_assets", "TEXT"),
        ("must_do", "TEXT"),
        ("must_confirm", "TEXT"),
        ("output_artifacts", "TEXT"),
        ("acceptance_criteria_structured", "TEXT"),
        ("blockers", "TEXT"),
        ("evidence_refs", "TEXT"),
        ("historical_cases", "TEXT"),
        ("quality_score", "INTEGER DEFAULT 0"),
        ("quality_flags", "TEXT"),
```

Add these backfill statements after existing `related_impact_codes` update:

```python
        json_defaults = {
            "affected_systems": "[]",
            "affected_assets": "{}",
            "must_do": "[]",
            "must_confirm": "[]",
            "output_artifacts": "[]",
            "acceptance_criteria_structured": "[]",
            "blockers": "[]",
            "evidence_refs": "[]",
            "historical_cases": "[]",
            "quality_flags": "[]",
        }
        for column_name, default_value in json_defaults.items():
            connection.execute(
                text(f"UPDATE ticket_drafts SET `{column_name}` = :val WHERE `{column_name}` IS NULL"),
                {"val": default_value},
            )
        connection.execute(text("UPDATE ticket_drafts SET summary = '' WHERE summary IS NULL"))
        connection.execute(text("UPDATE ticket_drafts SET responsible_system = '' WHERE responsible_system IS NULL"))
```

- [ ] **Step 7: Add frontend type fields**

Modify `TicketDraft` in `监管报送项目/frontend/src/types/api.ts` after `related_impact_codes`:

```ts
  summary: string;
  responsible_system: string;
  affected_systems: string;
  affected_assets: string;
  must_do: string;
  must_confirm: string;
  output_artifacts: string;
  acceptance_criteria_structured: string;
  blockers: string;
  evidence_refs: string;
  historical_cases: string;
  quality_score: number;
  quality_flags: string;
```

- [ ] **Step 8: Run schema and frontend type checks**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_database_config.py -q
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run build
```

Expected: backend schema tests pass; frontend build passes after mock ticket data is updated if the compiler points to missing fields.

- [ ] **Step 9: Commit**

```bash
cd /Users/jiangqiuping/webproject
git add 监管报送项目/backend/app/models/enums.py \
        监管报送项目/backend/app/models/db_models.py \
        监管报送项目/backend/app/models/schemas.py \
        监管报送项目/backend/app/core/database.py \
        监管报送项目/backend/tests/test_database_config.py \
        监管报送项目/frontend/src/types/api.ts \
        监管报送项目/frontend/src/data/mock.ts
git commit -m "feat: extend ticket draft structured fields"
```

---

### Task 2: Build Trigger Engine For System-Owned Subtickets

**Files:**
- Create: `监管报送项目/backend/app/services/ticket_trigger_engine.py`
- Test: `监管报送项目/backend/tests/test_ticket_trigger_engine.py`

- [ ] **Step 1: Write trigger engine tests**

Create `监管报送项目/backend/tests/test_ticket_trigger_engine.py`:

```python
from app.models.enums import ActionTicketType, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_trigger_engine import build_ticket_triggers


def impact(**overrides):
    data = {
        "reporting_item_code": "G31.PART_I.1_0.C_DURATION",
        "impact_type": "INDICATOR_SCOPE",
        "impacted_reporting_field": "rpt_g31.duration",
        "impacted_source_fields": ["risk.duration"],
        "impacted_lineage_roles": ["REPORT_FIELD", "SOURCE_FIELD"],
        "impact_reason": "修正久期发生INDICATOR_ADD，需要复核报送字段。",
        "recommended_action": "复核字段映射。",
        "confidence_level": "HIGH",
    }
    data.update(overrides)
    return ReportingImpactDraft(**data)


def test_data_mapping_trigger_for_report_and_source_fields():
    triggers = build_ticket_triggers([impact()], document_text="")

    assert any(
        trigger.action_type == ActionTicketType.DATA_MAPPING
        and trigger.responsible_system == ResponsibleSystem.DATA_GOVERNANCE_PLATFORM
        for trigger in triggers
    )


def test_source_system_trigger_when_source_fields_missing():
    triggers = build_ticket_triggers([
        impact(impacted_source_fields=[], impacted_lineage_roles=["REPORT_FIELD"])
    ], document_text="")

    assert any(
        trigger.action_type == ActionTicketType.SOURCE_SYSTEM_CHANGE
        and trigger.responsible_system == ResponsibleSystem.SOURCE_SYSTEM
        and "SOURCE_FIELD_GAP" in trigger.trigger_reasons
        for trigger in triggers
    )


def test_validation_trigger_for_cross_table_consistency_text():
    triggers = build_ticket_triggers(
        [impact(reporting_item_code="G24.MAIN.A"), impact(reporting_item_code="G31.PART_I.B")],
        document_text="G24 与 G31 金额关系保持一致，差异超过 5% 须解释。",
    )

    assert any(
        trigger.action_type == ActionTicketType.VALIDATION_RULE
        and trigger.responsible_system == ResponsibleSystem.DATA_QUALITY_PLATFORM
        and "CROSS_REPORT_CONSISTENCY" in trigger.trigger_reasons
        for trigger in triggers
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_ticket_trigger_engine.py -q
```

Expected: FAIL because `ticket_trigger_engine.py` does not exist.

- [ ] **Step 3: Implement trigger engine**

Create `监管报送项目/backend/app/services/ticket_trigger_engine.py`:

```python
from dataclasses import dataclass, field

from app.models.enums import ActionTicketType, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft


@dataclass(frozen=True)
class TicketTrigger:
    action_type: ActionTicketType
    responsible_system: ResponsibleSystem
    trigger_reasons: list[str] = field(default_factory=list)
    related_impact_codes: list[str] = field(default_factory=list)


def build_ticket_triggers(
    impacts: list[ReportingImpactDraft],
    document_text: str,
) -> list[TicketTrigger]:
    candidates: list[TicketTrigger] = []

    impact_codes = [impact.reporting_item_code for impact in impacts if impact.reporting_item_code]
    roles = {role for impact in impacts for role in impact.impacted_lineage_roles}
    has_source_gap = any(
        impact.reporting_item_code and not impact.impacted_source_fields
        for impact in impacts
    )
    text = document_text or ""

    if impact_codes:
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.SCOPE_CONFIRM,
            responsible_system=ResponsibleSystem.REG_REPORTING_SYSTEM,
            trigger_reasons=["REPORTING_ITEM_SCOPE_CHANGE"],
            related_impact_codes=impact_codes,
        ))

    if roles & {"REPORT_FIELD", "SOURCE_FIELD", "DIMENSION_FIELD", "FILTER_FIELD"}:
        reasons = ["REPORT_OR_SOURCE_FIELD_IMPACT"]
        if roles & {"DIMENSION_FIELD", "FILTER_FIELD"}:
            reasons.append("DIMENSION_OR_FILTER_FIELD_IMPACT")
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.DATA_MAPPING,
            responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
            trigger_reasons=reasons,
            related_impact_codes=impact_codes,
        ))

    if has_source_gap:
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.SOURCE_SYSTEM_CHANGE,
            responsible_system=ResponsibleSystem.SOURCE_SYSTEM,
            trigger_reasons=["SOURCE_FIELD_GAP"],
            related_impact_codes=impact_codes,
        ))

    if _mentions_processing(text):
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.REPORT_PROCESSING,
            responsible_system=ResponsibleSystem.DATA_MART_ETL,
            trigger_reasons=["PROCESSING_LOGIC_IMPACT"],
            related_impact_codes=impact_codes,
        ))

    if _mentions_validation(text) or _is_cross_report(impact_codes):
        reasons = ["VALIDATION_RULE_IMPACT"]
        if _is_cross_report(impact_codes):
            reasons.append("CROSS_REPORT_CONSISTENCY")
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.VALIDATION_RULE,
            responsible_system=ResponsibleSystem.DATA_QUALITY_PLATFORM,
            trigger_reasons=reasons,
            related_impact_codes=impact_codes,
        ))

    if _mentions_retroactive(text):
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.HISTORICAL_DATA,
            responsible_system=ResponsibleSystem.REG_REPORTING_SYSTEM,
            trigger_reasons=["RETROACTIVE_OR_FIRST_REPORTING"],
            related_impact_codes=impact_codes,
        ))

    candidates.append(TicketTrigger(
        action_type=ActionTicketType.TEST_ACCEPTANCE,
        responsible_system=ResponsibleSystem.TEST_ACCEPTANCE,
        trigger_reasons=["REGRESSION_ACCEPTANCE_REQUIRED"],
        related_impact_codes=impact_codes,
    ))
    candidates.append(TicketTrigger(
        action_type=ActionTicketType.ARCHIVE_REVIEW,
        responsible_system=ResponsibleSystem.KNOWLEDGE_ARCHIVE,
        trigger_reasons=["GOVERNANCE_ARCHIVE_REQUIRED"],
        related_impact_codes=impact_codes,
    ))

    return _deduplicate_triggers(candidates)


def _deduplicate_triggers(candidates: list[TicketTrigger]) -> list[TicketTrigger]:
    grouped: dict[tuple[ActionTicketType, ResponsibleSystem], TicketTrigger] = {}
    for trigger in candidates:
        key = (trigger.action_type, trigger.responsible_system)
        if key not in grouped:
            grouped[key] = trigger
            continue
        existing = grouped[key]
        grouped[key] = TicketTrigger(
            action_type=existing.action_type,
            responsible_system=existing.responsible_system,
            trigger_reasons=list(dict.fromkeys(existing.trigger_reasons + trigger.trigger_reasons)),
            related_impact_codes=list(dict.fromkeys(existing.related_impact_codes + trigger.related_impact_codes)),
        )
    return list(grouped.values())


def _mentions_processing(text: str) -> bool:
    return any(keyword in text for keyword in ("加工逻辑", "汇总", "调度", "ETL", "SQL", "内部数据加工"))


def _mentions_validation(text: str) -> bool:
    return any(keyword in text for keyword in ("校验", "勾稽", "一致性", "差异超过", "表内", "表间"))


def _mentions_retroactive(text: str) -> bool:
    return any(keyword in text for keyword in ("追溯", "补报", "重算", "首次按新口径报送", "历史数据"))


def _is_cross_report(impact_codes: list[str]) -> bool:
    object_codes = {code.split(".")[0] for code in impact_codes if "." in code}
    return len(object_codes) >= 2
```

- [ ] **Step 4: Run trigger tests**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_ticket_trigger_engine.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/jiangqiuping/webproject
git add 监管报送项目/backend/app/services/ticket_trigger_engine.py \
        监管报送项目/backend/tests/test_ticket_trigger_engine.py
git commit -m "feat: add ticket trigger engine"
```

---

### Task 3: Add Structured Card Builder And Quality Checker

**Files:**
- Create: `监管报送项目/backend/app/services/ticket_card_builder.py`
- Create: `监管报送项目/backend/app/services/ticket_quality_checker.py`
- Create: `监管报送项目/backend/tests/test_ticket_card_builder.py`
- Create: `监管报送项目/backend/tests/test_ticket_quality_checker.py`

- [ ] **Step 1: Write card builder tests**

Create `监管报送项目/backend/tests/test_ticket_card_builder.py`:

```python
from app.models.enums import ActionTicketType, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_card_builder import build_ticket_card
from app.services.ticket_trigger_engine import TicketTrigger


def test_data_mapping_card_is_short_and_asset_focused():
    impact = ReportingImpactDraft(
        reporting_item_code="G31.PART_I.1_0.C_DURATION",
        impact_type="INDICATOR_SCOPE",
        impacted_reporting_field="rpt_g31.duration",
        impacted_source_fields=["risk.duration", "valuation.duration"],
        impacted_lineage_roles=["REPORT_FIELD", "SOURCE_FIELD"],
        impact_reason="修正久期发生INDICATOR_ADD，需要复核报送字段。",
        recommended_action="复核字段映射。",
        confidence_level="HIGH",
    )
    trigger = TicketTrigger(
        action_type=ActionTicketType.DATA_MAPPING,
        responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
        trigger_reasons=["REPORT_OR_SOURCE_FIELD_IMPACT"],
        related_impact_codes=[impact.reporting_item_code],
    )

    card = build_ticket_card(trigger, [impact], historical_cases=[])

    assert card.summary == "确认受影响报送项的数据映射和血缘口径。"
    assert card.responsible_system == ResponsibleSystem.DATA_GOVERNANCE_PLATFORM
    assert "G31.PART_I.1_0.C_DURATION" in card.affected_assets["reporting_item_codes"]
    assert "rpt_g31.duration" in card.affected_assets["reporting_fields"]
    assert "risk.duration" in card.affected_assets["source_fields"]
    assert len(card.must_do) <= 5
    assert "形成可复用的数据映射记录" in card.output_artifacts
```

- [ ] **Step 2: Write quality checker tests**

Create `监管报送项目/backend/tests/test_ticket_quality_checker.py`:

```python
from app.models.enums import ActionTicketType, ResponsibleRole, ResponsibleSystem
from app.services.ticket_card_builder import TicketTaskCard
from app.services.ticket_quality_checker import check_ticket_card_quality


def test_quality_checker_flags_missing_acceptance_and_assets():
    card = TicketTaskCard(
        action_type=ActionTicketType.DATA_MAPPING,
        owner_role=ResponsibleRole.DATA_GOVERNANCE,
        executor_role=ResponsibleRole.DATA_GOVERNANCE,
        responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
        summary="确认映射。",
        affected_assets={},
        must_do=["复核字段映射。"],
        must_confirm=[],
        output_artifacts=["形成可复用的数据映射记录"],
        acceptance_criteria=[],
        blockers=[],
        evidence_refs=[],
        historical_cases=[],
    )

    result = check_ticket_card_quality(card)

    assert result.score < 100
    assert "MISSING_AFFECTED_ASSETS" in result.flags
    assert "MISSING_ACCEPTANCE_CRITERIA" in result.flags
    assert "MISSING_EVIDENCE_REFS" in result.flags
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_ticket_card_builder.py tests/test_ticket_quality_checker.py -q
```

Expected: FAIL because the new services do not exist.

- [ ] **Step 4: Implement card builder**

Create `监管报送项目/backend/app/services/ticket_card_builder.py`:

```python
from pydantic import BaseModel

from app.models.enums import ActionTicketType, ResponsibleRole, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_trigger_engine import TicketTrigger


class TicketTaskCard(BaseModel):
    action_type: ActionTicketType
    owner_role: ResponsibleRole
    executor_role: ResponsibleRole
    responsible_system: ResponsibleSystem
    summary: str
    affected_assets: dict
    must_do: list[str]
    must_confirm: list[str]
    output_artifacts: list[str]
    acceptance_criteria: list[str]
    blockers: list[str]
    evidence_refs: list[dict]
    historical_cases: list[dict] = []


def build_ticket_card(
    trigger: TicketTrigger,
    impacts: list[ReportingImpactDraft],
    historical_cases: list[dict],
) -> TicketTaskCard:
    relevant_impacts = [
        impact for impact in impacts
        if not trigger.related_impact_codes or impact.reporting_item_code in trigger.related_impact_codes
    ]
    assets = _affected_assets(relevant_impacts)
    blockers = _blockers(relevant_impacts)
    return TicketTaskCard(
        action_type=trigger.action_type,
        owner_role=_owner_role(trigger.action_type),
        executor_role=_executor_role(trigger.action_type),
        responsible_system=trigger.responsible_system,
        summary=_summary(trigger.action_type),
        affected_assets=assets,
        must_do=_must_do(trigger.action_type, trigger.trigger_reasons),
        must_confirm=_must_confirm(trigger.action_type, blockers),
        output_artifacts=_output_artifacts(trigger.action_type),
        acceptance_criteria=_acceptance_criteria(trigger.action_type),
        blockers=blockers,
        evidence_refs=_evidence_refs(relevant_impacts, trigger.trigger_reasons),
        historical_cases=historical_cases[:3],
    )


def _affected_assets(impacts: list[ReportingImpactDraft]) -> dict:
    return {
        "reporting_item_codes": _unique([impact.reporting_item_code for impact in impacts if impact.reporting_item_code]),
        "reporting_fields": _unique([impact.impacted_reporting_field for impact in impacts if impact.impacted_reporting_field]),
        "source_fields": _unique([field for impact in impacts for field in impact.impacted_source_fields]),
        "lineage_roles": _unique([role for impact in impacts for role in impact.impacted_lineage_roles]),
    }


def _blockers(impacts: list[ReportingImpactDraft]) -> list[str]:
    blockers: list[str] = []
    for impact in impacts:
        if impact.reporting_item_code and not impact.impacted_source_fields:
            blockers.append(f"{impact.reporting_item_code} 未命中源字段，需要确认是否补充血缘或源系统字段。")
    return blockers


def _summary(action_type: ActionTicketType) -> str:
    return {
        ActionTicketType.SCOPE_CONFIRM: "确认监管变更涉及的报送口径、适用范围和生效要求。",
        ActionTicketType.DATA_MAPPING: "确认受影响报送项的数据映射和血缘口径。",
        ActionTicketType.LINEAGE_BUILD: "补齐受影响报送项的字段血缘和转换关系。",
        ActionTicketType.CATALOG_INIT: "维护新增或调整后的报送目录、报送项和版本信息。",
        ActionTicketType.SOURCE_SYSTEM_CHANGE: "确认源系统是否需要新增采集字段、码值或接口调整。",
        ActionTicketType.REPORT_PROCESSING: "调整报送加工逻辑、汇总逻辑和调度依赖。",
        ActionTicketType.VALIDATION_RULE: "新增或调整本次变更涉及的数据质量和跨表校验规则。",
        ActionTicketType.HISTORICAL_DATA: "确认追溯、补报、重算或差异说明处理方案。",
        ActionTicketType.TASK_INIT: "配置报送任务、机构范围、频度和权限。",
        ActionTicketType.TEST_ACCEPTANCE: "完成样例数据、回归测试、差异分析和验收确认。",
        ActionTicketType.ARCHIVE_REVIEW: "归档最终口径、处理结论、监管反馈和复用标签。",
        ActionTicketType.MERGED_LIGHTWEIGHT: "一次性处理轻量变更并完成确认归档。",
    }[action_type]


def _must_do(action_type: ActionTicketType, trigger_reasons: list[str]) -> list[str]:
    base = {
        ActionTicketType.SCOPE_CONFIRM: ["对照监管证据确认新旧口径差异。", "确认生效日期、追溯范围和特殊场景。", "形成业务或报送管理确认结论。"],
        ActionTicketType.DATA_MAPPING: ["核对报送字段到源字段的映射。", "确认维度字段、过滤字段和码值口径。", "形成可复用的数据映射记录。"],
        ActionTicketType.LINEAGE_BUILD: ["补齐报送字段、源字段和转换表达式。", "标注字段角色和置信度。", "提交数据治理复核。"],
        ActionTicketType.CATALOG_INIT: ["维护报送对象、报送项和版本信息。", "补充生效区间和来源证据。"],
        ActionTicketType.SOURCE_SYSTEM_CHANGE: ["确认源系统是否已有满足口径的数据字段。", "确认新增字段、码值或接口调整范围。", "对齐源系统发布节奏。"],
        ActionTicketType.REPORT_PROCESSING: ["定位 SQL/ETL 和汇总逻辑修改点。", "调整调度依赖和回滚方案。", "输出可审查的加工变更说明。"],
        ActionTicketType.VALIDATION_RULE: ["确认表内、表间或跨期校验规则变化。", "维护校验表达式、阈值和异常解释口径。"],
        ActionTicketType.HISTORICAL_DATA: ["确认追溯起点和重算范围。", "准备差异分析和监管解释材料。"],
        ActionTicketType.TASK_INIT: ["配置任务频度、机构范围和权限。", "确认报送时点不冲突。"],
        ActionTicketType.TEST_ACCEPTANCE: ["准备覆盖关键口径的样例数据。", "执行回归测试并输出差异分析。", "完成业务验收确认。"],
        ActionTicketType.ARCHIVE_REVIEW: ["记录最终口径和决策依据。", "沉淀规则卡片、概念和历史案例标签。"],
        ActionTicketType.MERGED_LIGHTWEIGHT: ["确认轻量变更范围。", "完成一次性处理和归档。"],
    }[action_type]
    if "CROSS_REPORT_CONSISTENCY" in trigger_reasons and action_type == ActionTicketType.VALIDATION_RULE:
        return ["维护跨报表一致性校验关系。"] + base[:4]
    return base[:5]


def _must_confirm(action_type: ActionTicketType, blockers: list[str]) -> list[str]:
    questions = {
        ActionTicketType.DATA_MAPPING: ["现有源字段语义是否覆盖新口径？", "是否需要新增维度字段、过滤字段或码值维表？"],
        ActionTicketType.SOURCE_SYSTEM_CHANGE: ["源系统是否已有该数据？", "新增字段是否能匹配监管时限？"],
        ActionTicketType.VALIDATION_RULE: ["阈值和差异解释口径是否需要业务确认？"],
        ActionTicketType.HISTORICAL_DATA: ["追溯至哪个数据日期？", "是否需要监管报备或专项说明？"],
    }.get(action_type, ["是否存在特殊场景或豁免？"])
    return (blockers + questions)[:5]


def _output_artifacts(action_type: ActionTicketType) -> list[str]:
    return {
        ActionTicketType.SCOPE_CONFIRM: ["口径确认记录", "生效日期和追溯范围"],
        ActionTicketType.DATA_MAPPING: ["形成可复用的数据映射记录", "字段角色和血缘置信度"],
        ActionTicketType.LINEAGE_BUILD: ["血缘边和转换表达式", "源字段责任系统"],
        ActionTicketType.CATALOG_INIT: ["报送目录版本", "报送项元数据"],
        ActionTicketType.SOURCE_SYSTEM_CHANGE: ["源字段定义", "码值或接口调整记录"],
        ActionTicketType.REPORT_PROCESSING: ["SQL/ETL 变更说明", "调度依赖和回滚方案"],
        ActionTicketType.VALIDATION_RULE: ["校验规则表达式", "阈值和异常解释口径"],
        ActionTicketType.HISTORICAL_DATA: ["重算范围", "差异分析材料"],
        ActionTicketType.TASK_INIT: ["任务配置", "机构范围和频度设置"],
        ActionTicketType.TEST_ACCEPTANCE: ["测试样例", "回归结果和验收结论"],
        ActionTicketType.ARCHIVE_REVIEW: ["最终口径归档", "历史案例标签"],
        ActionTicketType.MERGED_LIGHTWEIGHT: ["轻量处理结论", "归档记录"],
    }[action_type]


def _acceptance_criteria(action_type: ActionTicketType) -> list[str]:
    return {
        ActionTicketType.DATA_MAPPING: ["报送字段到源字段映射覆盖全部受影响资产。", "业务或报送管理确认字段语义。", "血缘可在字段定位页查询。"],
        ActionTicketType.SOURCE_SYSTEM_CHANGE: ["源系统字段、码值或接口方案已确认。", "上游发布时间满足监管报送时限。"],
        ActionTicketType.REPORT_PROCESSING: ["加工逻辑通过代码复核。", "测试环境跑数差异可解释。"],
        ActionTicketType.VALIDATION_RULE: ["新校验规则在测试环境通过。", "异常解释口径已确认。"],
        ActionTicketType.TEST_ACCEPTANCE: ["回归用例通过。", "业务验收结论完成记录。"],
    }.get(action_type, ["处理结论已确认。", "相关证据已归档。"])


def _evidence_refs(impacts: list[ReportingImpactDraft], trigger_reasons: list[str]) -> list[dict]:
    return [
        {
            "type": "IMPACT_ITEM",
            "code": impact.reporting_item_code,
            "text": impact.impact_reason,
            "trigger_reasons": trigger_reasons,
        }
        for impact in impacts
    ]


def _owner_role(action_type: ActionTicketType) -> ResponsibleRole:
    return {
        ActionTicketType.SCOPE_CONFIRM: ResponsibleRole.BUSINESS,
        ActionTicketType.DATA_MAPPING: ResponsibleRole.DATA_GOVERNANCE,
        ActionTicketType.LINEAGE_BUILD: ResponsibleRole.DATA_GOVERNANCE,
        ActionTicketType.CATALOG_INIT: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.SOURCE_SYSTEM_CHANGE: ResponsibleRole.SOURCE_SYSTEM,
        ActionTicketType.REPORT_PROCESSING: ResponsibleRole.DATA_DEV,
        ActionTicketType.VALIDATION_RULE: ResponsibleRole.DATA_QUALITY,
        ActionTicketType.HISTORICAL_DATA: ResponsibleRole.BUSINESS,
        ActionTicketType.TASK_INIT: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.TEST_ACCEPTANCE: ResponsibleRole.BUSINESS,
        ActionTicketType.ARCHIVE_REVIEW: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.MERGED_LIGHTWEIGHT: ResponsibleRole.REPORTING_MGMT,
    }[action_type]


def _executor_role(action_type: ActionTicketType) -> ResponsibleRole:
    return {
        ActionTicketType.SCOPE_CONFIRM: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.DATA_MAPPING: ResponsibleRole.DATA_GOVERNANCE,
        ActionTicketType.LINEAGE_BUILD: ResponsibleRole.DATA_GOVERNANCE,
        ActionTicketType.CATALOG_INIT: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.SOURCE_SYSTEM_CHANGE: ResponsibleRole.SOURCE_SYSTEM,
        ActionTicketType.REPORT_PROCESSING: ResponsibleRole.DATA_DEV,
        ActionTicketType.VALIDATION_RULE: ResponsibleRole.DATA_QUALITY,
        ActionTicketType.HISTORICAL_DATA: ResponsibleRole.DATA_DEV,
        ActionTicketType.TASK_INIT: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.TEST_ACCEPTANCE: ResponsibleRole.QA,
        ActionTicketType.ARCHIVE_REVIEW: ResponsibleRole.REPORTING_MGMT,
        ActionTicketType.MERGED_LIGHTWEIGHT: ResponsibleRole.DATA_DEV,
    }[action_type]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
```

- [ ] **Step 5: Implement quality checker**

Create `监管报送项目/backend/app/services/ticket_quality_checker.py`:

```python
from pydantic import BaseModel

from app.services.ticket_card_builder import TicketTaskCard


class TicketQualityResult(BaseModel):
    score: int
    flags: list[str]


def check_ticket_card_quality(card: TicketTaskCard) -> TicketQualityResult:
    score = 100
    flags: list[str] = []

    if not card.summary.strip():
        score -= 15
        flags.append("MISSING_SUMMARY")
    if not card.affected_assets:
        score -= 15
        flags.append("MISSING_AFFECTED_ASSETS")
    if not card.must_do:
        score -= 15
        flags.append("MISSING_MUST_DO")
    if not card.acceptance_criteria:
        score -= 15
        flags.append("MISSING_ACCEPTANCE_CRITERIA")
    if not card.output_artifacts:
        score -= 10
        flags.append("MISSING_OUTPUT_ARTIFACTS")
    if not card.evidence_refs:
        score -= 10
        flags.append("MISSING_EVIDENCE_REFS")
    if len(card.must_do) > 5:
        score -= 10
        flags.append("TOO_MANY_MUST_DO_ITEMS")
    if not card.responsible_system.value:
        score -= 10
        flags.append("MISSING_RESPONSIBLE_SYSTEM")

    return TicketQualityResult(score=max(score, 0), flags=flags)
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_ticket_card_builder.py tests/test_ticket_quality_checker.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/jiangqiuping/webproject
git add 监管报送项目/backend/app/services/ticket_card_builder.py \
        监管报送项目/backend/app/services/ticket_quality_checker.py \
        监管报送项目/backend/tests/test_ticket_card_builder.py \
        监管报送项目/backend/tests/test_ticket_quality_checker.py
git commit -m "feat: build structured ticket cards"
```

---

### Task 4: Refactor Ticket Generator Behind Existing Entrypoint

**Files:**
- Modify: `监管报送项目/backend/app/services/reporting_ticket_generator.py`
- Modify: `监管报送项目/backend/app/api/routes_tasks.py`
- Create: `监管报送项目/backend/app/services/decision_archive_service.py`
- Modify: `监管报送项目/backend/tests/test_reporting_services.py`
- Modify: `监管报送项目/backend/tests/test_api_workflow.py`

- [ ] **Step 1: Add reporting generator test for structured children**

Append to `监管报送项目/backend/tests/test_reporting_services.py`:

```python
from app.services.change_severity_classifier import ChangeClassification, SeverityScore
from app.models.enums import ChangeTicketType, SeverityLevel
from app.services.reporting_ticket_generator import build_ticket_plan


def test_build_ticket_plan_outputs_structured_ticket_cards():
    catalog = build_1104_seed_catalog()
    changes = extract_reporting_changes("调整G24同业融入余额统计口径，并同步调整内部数据加工逻辑与跨表一致性校验。")
    impacts = analyze_reporting_impacts(changes, catalog)
    classification = ChangeClassification(
        change_ticket_type=ChangeTicketType.SCOPE_ADJUSTMENT,
        severity=SeverityScore(level=SeverityLevel.L3_STANDARD, score=8, triggered_signals=["test"]),
    )

    plan = build_ticket_plan(classification, impacts, "G24 口径调整", document_text="同步调整内部数据加工逻辑与跨表一致性校验")

    assert plan.children
    assert any(child.card.responsible_system.value == "DATA_GOVERNANCE_PLATFORM" for child in plan.children)
    assert all(child.card.summary for child in plan.children)
    assert all(child.card.must_do for child in plan.children)
    assert all(child.quality.score > 0 for child in plan.children)
```

- [ ] **Step 2: Run targeted test and verify failure**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_reporting_services.py::test_build_ticket_plan_outputs_structured_ticket_cards -q
```

Expected: FAIL because `build_ticket_plan` does not accept `document_text` and `ChildTicketPlan` lacks `card` and `quality`.

- [ ] **Step 3: Add historical case service**

Create `监管报送项目/backend/app/services/decision_archive_service.py`:

```python
from app.services.reporting_impact_analyzer import ReportingImpactDraft


def search_similar_decisions(
    impacts: list[ReportingImpactDraft],
    top_k: int = 3,
) -> dict[str, list[dict]]:
    cases: dict[str, list[dict]] = {}
    for impact in impacts:
        if impact.reporting_item_code:
            cases[impact.reporting_item_code] = []
    return cases
```

This first implementation returns stable empty lists. It keeps the interface ready without adding DB coupling in the first refactor.

- [ ] **Step 4: Modify ticket plan dataclasses**

In `监管报送项目/backend/app/services/reporting_ticket_generator.py`, import:

```python
from app.services.ticket_card_builder import TicketTaskCard, build_ticket_card
from app.services.ticket_quality_checker import TicketQualityResult, check_ticket_card_quality
from app.services.ticket_trigger_engine import build_ticket_triggers
```

Update `ChildTicketPlan`:

```python
@dataclass
class ChildTicketPlan:
    action_type: ActionTicketType
    title: str
    spec: ActionTicketSpec
    content_markdown: str
    related_impact_codes: list[str] = field(default_factory=list)
    card: TicketTaskCard | None = None
    quality: TicketQualityResult | None = None
```

- [ ] **Step 5: Update `build_ticket_plan` signature and trigger path**

Change the function signature:

```python
def build_ticket_plan(
    classification: ChangeClassification,
    impacts: list[ReportingImpactDraft],
    task_title: str,
    rule_cards_by_key: dict[str, list[dict]] | None = None,
    historical_cases_by_key: dict[str, list[dict]] | None = None,
    document_text: str = "",
) -> TicketPlan:
```

In the non-L1 branch, replace matrix-only selection with trigger-driven children:

```python
        triggers = build_ticket_triggers(impacts, document_text=document_text)
        if triggers:
            children = [
                _build_child_plan_from_trigger(trigger, task_title, impacts, rule_cards_by_key, historical_cases_by_key or {})
                for trigger in triggers
            ]
        else:
            action_types = _select_action_types(
                classification.change_ticket_type, classification.severity.level
            )
            children = [
                _build_child_plan(action_type, task_title, impacts, rule_cards_by_key)
                for action_type in action_types
            ]
```

- [ ] **Step 6: Add trigger child builder and compatibility renderer**

Add to `reporting_ticket_generator.py`:

```python
def _build_child_plan_from_trigger(
    trigger,
    task_title: str,
    impacts: list[ReportingImpactDraft],
    rule_cards_by_key: dict[str, list[dict]] | None = None,
    historical_cases_by_key: dict[str, list[dict]] | None = None,
) -> ChildTicketPlan:
    spec = _ACTION_SPECS[trigger.action_type]
    related_impacts = [
        impact for impact in impacts
        if not trigger.related_impact_codes or impact.reporting_item_code in trigger.related_impact_codes
    ]
    historical_cases = _historical_cases_for_impacts(related_impacts, historical_cases_by_key or {})
    card = build_ticket_card(trigger, related_impacts, historical_cases=historical_cases)
    quality = check_ticket_card_quality(card)
    return ChildTicketPlan(
        action_type=trigger.action_type,
        title=f"{task_title}｜{spec.name_zh}",
        spec=spec,
        content_markdown=_render_card_markdown(card, rule_cards_by_key or {}),
        related_impact_codes=trigger.related_impact_codes,
        card=card,
        quality=quality,
    )


def _historical_cases_for_impacts(
    impacts: list[ReportingImpactDraft],
    historical_cases_by_key: dict[str, list[dict]],
) -> list[dict]:
    cases: list[dict] = []
    for impact in impacts:
        cases.extend(historical_cases_by_key.get(impact.reporting_item_code, []))
    return cases[:3]


def _render_card_markdown(
    card: TicketTaskCard,
    rule_cards_by_key: dict[str, list[dict]],
) -> str:
    lines = [
        "## 工单摘要",
        "",
        card.summary,
        "",
        "## 责任分配",
        "",
        f"- 责任系统：{card.responsible_system.value}",
        f"- 出口责任 (A)：{card.owner_role.value}",
        f"- 执行人 (R)：{card.executor_role.value}",
        "",
        "## 受影响资产",
        "",
    ]
    for key, values in card.affected_assets.items():
        if values:
            lines.append(f"- {key}：{', '.join(values[:5])}")
    lines.extend(["", "## 必须动作", ""])
    lines.extend(f"- {item}" for item in card.must_do)
    lines.extend(["", "## 待确认问题", ""])
    lines.extend(f"- {item}" for item in card.must_confirm)
    lines.extend(["", "## 验收标准", ""])
    lines.extend(f"- {item}" for item in card.acceptance_criteria)
    if card.blockers:
        lines.extend(["", "## 阻塞点", ""])
        lines.extend(f"- {item}" for item in card.blockers)
    if card.output_artifacts:
        lines.extend(["", "## 治理资产产出", ""])
        lines.extend(f"- {item}" for item in card.output_artifacts)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 7: Persist structured fields in `routes_tasks.py`**

In `_persist_child_ticket`, import `json` already exists. When `child.card` and `child.quality` are present, pass structured fields:

```python
        summary=child.card.summary if child.card else "",
        responsible_system=child.card.responsible_system.value if child.card else "",
        affected_systems=json.dumps([child.card.responsible_system.value], ensure_ascii=False) if child.card else "[]",
        affected_assets=json.dumps(child.card.affected_assets, ensure_ascii=False) if child.card else "{}",
        must_do=json.dumps(child.card.must_do, ensure_ascii=False) if child.card else "[]",
        must_confirm=json.dumps(child.card.must_confirm, ensure_ascii=False) if child.card else "[]",
        output_artifacts=json.dumps(child.card.output_artifacts, ensure_ascii=False) if child.card else "[]",
        acceptance_criteria_structured=json.dumps(child.card.acceptance_criteria, ensure_ascii=False) if child.card else "[]",
        blockers=json.dumps(child.card.blockers, ensure_ascii=False) if child.card else "[]",
        evidence_refs=json.dumps(child.card.evidence_refs, ensure_ascii=False) if child.card else "[]",
        historical_cases=json.dumps(child.card.historical_cases, ensure_ascii=False) if child.card else "[]",
        quality_score=child.quality.score if child.quality else 0,
        quality_flags=json.dumps(child.quality.flags, ensure_ascii=False) if child.quality else "[]",
```

In `generate_task_ticket`, pass `document_text` to `build_ticket_plan`:

```python
    plan = build_ticket_plan(
        classification,
        impact_drafts,
        task.title,
        rule_cards_by_key=rule_cards_by_key,
        historical_cases_by_key={},
        document_text=document_text,
    )
```

- [ ] **Step 8: Run backend test subset**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_reporting_services.py tests/test_api_workflow.py tests/test_ticket_trigger_engine.py tests/test_ticket_card_builder.py tests/test_ticket_quality_checker.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/jiangqiuping/webproject
git add 监管报送项目/backend/app/services/reporting_ticket_generator.py \
        监管报送项目/backend/app/services/decision_archive_service.py \
        监管报送项目/backend/app/api/routes_tasks.py \
        监管报送项目/backend/tests/test_reporting_services.py \
        监管报送项目/backend/tests/test_api_workflow.py
git commit -m "feat: generate structured governance tickets"
```

---

### Task 5: Render Structured Ticket Workbench In Frontend

**Files:**
- Modify: `监管报送项目/frontend/src/types/api.ts`
- Modify: `监管报送项目/frontend/src/views/ReviewTicketView.vue`
- Test: `监管报送项目/frontend/src/views/ReviewTicketView.test.ts`

- [ ] **Step 1: Add frontend test for structured card rendering**

Create `监管报送项目/frontend/src/views/ReviewTicketView.test.ts`:

```ts
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ReviewTicketView from "./ReviewTicketView.vue";
import type { TaskWorkflow, TicketDraft } from "@/types/api";

function ticket(overrides: Partial<TicketDraft>): TicketDraft {
  return {
    id: 1,
    task_id: 1,
    title: "G31 数据映射子单",
    content: "旧 Markdown 正文",
    parent_ticket_id: null,
    ticket_role: "CHILD",
    change_ticket_type: "",
    action_ticket_type: "DATA_MAPPING",
    severity_level: "",
    severity_score: 0,
    severity_signals: "[]",
    severity_forced_reason: "",
    severity_overridden_by: "",
    owner_role: "DATA_GOVERNANCE",
    executor_role: "DATA_GOVERNANCE",
    depends_on_lineage: true,
    business_signoff_required: true,
    closure_review_required: false,
    related_impact_codes: "[]",
    summary: "确认受影响报送项的数据映射和血缘口径。",
    responsible_system: "DATA_GOVERNANCE_PLATFORM",
    affected_systems: "[\"DATA_GOVERNANCE_PLATFORM\"]",
    affected_assets: "{\"reporting_item_codes\":[\"G31.PART_I.1_0.C_DURATION\"],\"reporting_fields\":[\"rpt_g31.duration\"],\"source_fields\":[\"risk.duration\"]}",
    must_do: "[\"核对报送字段到源字段的映射。\"]",
    must_confirm: "[\"现有源字段语义是否覆盖新口径？\"]",
    output_artifacts: "[\"形成可复用的数据映射记录\"]",
    acceptance_criteria_structured: "[\"血缘可在字段定位页查询。\"]",
    blockers: "[]",
    evidence_refs: "[]",
    historical_cases: "[]",
    quality_score: 92,
    quality_flags: "[]",
    status: "DRAFT",
    created_at: null,
    ...overrides,
  };
}

function workflow(tickets: TicketDraft[]): TaskWorkflow {
  return {
    task: { id: 1, document_id: 1, title: "任务", status: "TICKET_GENERATED", risk_level: "HIGH", created_at: "", updated_at: "" },
    document: { id: 1, filename: "doc.txt", content_type: "text/plain", storage_path: "", title: "doc", text_excerpt: "", parsed_text: "", status: "PARSED", parse_status: "PARSED", parser: "text", char_count: 0, paragraph_count: 0, table_count: 0, parse_quality: "GOOD", parse_error_message: "", created_at: "" },
    document_profile: null,
    steps: [],
    clauses: [],
    semantic_items: [],
    field_mappings: [],
    reporting_candidates: [],
    lineage_candidates: [],
    impact_items: [],
    rule_cards: [],
    ticket_drafts: tickets,
  };
}

describe("ReviewTicketView structured tickets", () => {
  it("renders structured card fields before markdown fallback", () => {
    const wrapper = mount(ReviewTicketView, {
      props: { workflow: workflow([ticket({})]), busy: false },
      global: { stubs: { transition: false } },
    });

    expect(wrapper.text()).toContain("数据治理平台");
    expect(wrapper.text()).toContain("确认受影响报送项的数据映射和血缘口径。");
    expect(wrapper.text()).toContain("核对报送字段到源字段的映射。");
    expect(wrapper.text()).toContain("工单质量");
    expect(wrapper.text()).not.toContain("可审查 SQL · 参考草稿");
  });

  it("falls back to markdown for old tickets", () => {
    const oldTicket = ticket({
      summary: "",
      responsible_system: "",
      affected_assets: "{}",
      must_do: "[]",
      acceptance_criteria_structured: "[]",
    });
    const wrapper = mount(ReviewTicketView, {
      props: { workflow: workflow([oldTicket]), busy: false },
    });

    expect(wrapper.text()).toContain("旧 Markdown 正文");
  });
});
```

- [ ] **Step 2: Run frontend test and verify failure**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run test -- ReviewTicketView.test.ts
```

Expected: FAIL because structured rendering is not implemented.

- [ ] **Step 3: Add parsing helpers in `ReviewTicketView.vue` script**

Add these helpers in the `<script setup>` section:

```ts
function parseJsonArray(value: string | undefined): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function parseJsonObject(value: string | undefined): Record<string, string[]> {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).map(([key, raw]) => [
        key,
        Array.isArray(raw) ? raw.map(String) : [],
      ]),
    );
  } catch {
    return {};
  }
}

function hasStructuredTicket(ticket: TicketDraft): boolean {
  return Boolean(ticket.summary || ticket.responsible_system || parseJsonArray(ticket.must_do).length);
}
```

Add system label mapping:

```ts
const SYSTEM_LABELS: Record<string, string> = {
  REG_REPORTING_SYSTEM: "监管报送系统",
  DATA_GOVERNANCE_PLATFORM: "数据治理平台",
  DATA_MART_ETL: "数据集市 / ETL",
  SOURCE_SYSTEM: "源系统",
  DATA_QUALITY_PLATFORM: "数据质量平台",
  TEST_ACCEPTANCE: "测试验收",
  KNOWLEDGE_ARCHIVE: "归档知识库",
};

function systemLabel(system: string): string {
  return SYSTEM_LABELS[system] || system || "未分组";
}
```

- [ ] **Step 4: Replace fixed detail sections with conditional structured rendering**

In the template detail body, render structured fields first:

```vue
<div class="doc-body" v-if="activeTicket && hasStructuredTicket(activeTicket)">
  <div class="doc-section">
    <h4>任务目标</h4>
    <p>{{ activeTicket.summary }}</p>
    <div class="checks-row" style="margin-top:10px;">
      <span class="check-pill ok">责任系统：{{ systemLabel(activeTicket.responsible_system) }}</span>
      <span class="check-pill ok">工单质量：{{ activeTicket.quality_score }}</span>
    </div>
  </div>

  <div class="doc-section">
    <h4>受影响资产</h4>
    <div v-for="(values, key) in parseJsonObject(activeTicket.affected_assets)" :key="key" style="margin-bottom:8px;">
      <strong>{{ key }}</strong>
      <div class="row" style="flex-wrap:wrap;gap:6px;margin-top:6px;">
        <span v-for="value in values.slice(0, 5)" :key="value" class="tag outline mono">{{ value }}</span>
      </div>
    </div>
  </div>

  <div class="doc-section">
    <h4>必须动作</h4>
    <ul class="ticket-bullets">
      <li v-for="item in parseJsonArray(activeTicket.must_do)" :key="item">{{ item }}</li>
    </ul>
  </div>

  <div class="doc-section">
    <h4>待确认问题</h4>
    <ul class="ticket-bullets">
      <li v-for="item in parseJsonArray(activeTicket.must_confirm)" :key="item">{{ item }}</li>
    </ul>
  </div>

  <div class="doc-section" v-if="parseJsonArray(activeTicket.blockers).length">
    <h4>阻塞点</h4>
    <ul class="ticket-bullets">
      <li v-for="item in parseJsonArray(activeTicket.blockers)" :key="item">{{ item }}</li>
    </ul>
  </div>

  <div class="doc-section">
    <h4>治理资产产出</h4>
    <ul class="ticket-bullets">
      <li v-for="item in parseJsonArray(activeTicket.output_artifacts)" :key="item">{{ item }}</li>
    </ul>
  </div>

  <details class="doc-section">
    <summary>兼容 Markdown 正文</summary>
    <pre class="ticket-content">{{ activeTicket.content || defaultTicketContent }}</pre>
  </details>
</div>
```

Keep the old Markdown body under `v-else`.

- [ ] **Step 5: Add minimal CSS**

Add in `<style scoped>`:

```css
.ticket-bullets {
  margin: 0;
  padding-left: 18px;
  color: var(--ink-700);
  line-height: 1.7;
}
.ticket-bullets li + li {
  margin-top: 4px;
}
```

- [ ] **Step 6: Run frontend tests and build**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run test -- ReviewTicketView.test.ts
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/jiangqiuping/webproject
git add 监管报送项目/frontend/src/types/api.ts \
        监管报送项目/frontend/src/views/ReviewTicketView.vue \
        监管报送项目/frontend/src/views/ReviewTicketView.test.ts
git commit -m "feat: render structured ticket workbench"
```

---

### Task 6: End-to-End Verification And Regression Safety

**Files:**
- Modify: `监管报送项目/backend/tests/test_api_workflow.py`
- Modify: `监管报送项目/frontend/src/views/ReviewTicketView.test.ts`
- Verify only: production files should already be covered by Tasks 1-5.

- [ ] **Step 1: Add API workflow assertion for structured tickets**

In `监管报送项目/backend/tests/test_api_workflow.py`, extend `test_document_to_ticket_workflow` by replacing the existing ticket assertion block:

```python
    ticket_response = client.post(f"/api/tasks/{task_id}/generate-ticket")
    assert ticket_response.status_code == 200
    parent_content = ticket_response.json()["parent"]["content"]
    assert "母单类型" in parent_content
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in parent_content
```

with:

```python
    ticket_response = client.post(f"/api/tasks/{task_id}/generate-ticket")
    assert ticket_response.status_code == 200
    ticket_body = ticket_response.json()
    parent_content = ticket_body["parent"]["content"]
    assert "母单类型" in parent_content
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in parent_content

    child = ticket_body["children"][0]
    assert child["content"]
    assert child["summary"]
    assert child["responsible_system"]
    assert child["must_do"] != "[]"
    assert child["acceptance_criteria_structured"] != "[]"
    assert child["quality_score"] > 0
```

- [ ] **Step 2: Run backend regression set**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_reporting_services.py tests/test_api_workflow.py tests/test_database_config.py tests/test_ticket_trigger_engine.py tests/test_ticket_card_builder.py tests/test_ticket_quality_checker.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend regression set**

Run:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run test
npm run build
```

Expected: PASS.

- [ ] **Step 4: Manual smoke through local app**

Start or reuse services:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run uvicorn app.main:app --reload
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173/?page=ticket
```

Expected:

- Existing generated tickets still display.
- New generated tickets show structured card sections.
- The fixed generic SQL block no longer appears for structured non-SQL tickets.
- Markdown content can still be opened through compatibility section.

- [ ] **Step 5: Commit verification-only fixes**

If Step 2 or Step 3 required small test or compatibility fixes:

```bash
cd /Users/jiangqiuping/webproject
git add 监管报送项目/backend/tests/test_api_workflow.py \
        监管报送项目/frontend/src/__tests__/App.test.ts \
        监管报送项目/frontend/src/views/ReviewTicketView.test.ts
git commit -m "test: verify structured ticket workflow"
```

If no files changed, do not create an empty commit.

---

## Self-Review

### Spec Coverage

- Structured ticket fields: Task 1.
- Trigger-driven splitting: Task 2.
- Structured task cards: Task 3.
- Quality scoring: Task 3.
- Ticket generator refactor behind existing endpoint: Task 4.
- Frontend system-owned workbench rendering: Task 5.
- Main-flow stability and compatibility checks: Task 6.
- Historical cases: Task 4 creates a stable empty service interface; DB-backed history can be a follow-up task after the first structured rollout.

### Implementation Boundaries

- Main flow endpoints remain stable.
- Ticket internals are refactored into focused service files.
- Old Markdown remains available.
- Old rows render through fallback logic.

### Commands

Backend focused verification:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_reporting_services.py tests/test_api_workflow.py tests/test_database_config.py tests/test_ticket_trigger_engine.py tests/test_ticket_card_builder.py tests/test_ticket_quality_checker.py -q
```

Frontend verification:

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/frontend
npm run test
npm run build
```
