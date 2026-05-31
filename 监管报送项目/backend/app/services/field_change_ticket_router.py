"""field_change_ticket_router.py

六路由工单生成服务。

根据字段变更类型（ADDED/DELETED/MODIFIED）× 是否命中知识库，
按六路由矩阵生成对应的 TicketDraft，并更新 RegFieldChangeRecord 状态。
"""
from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.db_models import (
    DataFieldCatalog,
    RegFieldChangeRecord,
    RegReportingItem,
    ReportingItemLineage,
    TicketDraft,
)
from app.services.field_change_detector import FieldChange


# ──────────────────────────────────────────────────────────────────────────────
# 路由矩阵
# ──────────────────────────────────────────────────────────────────────────────

def route_change_to_ticket(
    change_record: RegFieldChangeRecord,
    session: Session,
) -> TicketDraft | None:
    """按六路由矩阵为一条变更记录生成 TicketDraft，或返回 None（不生成）。

    路由矩阵：
      ADDED   + 命中   → DATA_MAPPING，预填候选血缘
      ADDED   + 未命中 → LINEAGE_BUILD 高优，调推荐引擎
      DELETED + 命中   → REPORT_DECOMMISSION，附影响分析
      DELETED + 未命中 → 不生成工单，status=IGNORED
      MODIFIED+ 命中   → DATA_MAPPING，附口径 diff
      MODIFIED+ 未命中 → LINEAGE_BUILD 高优，告警型
    """
    ct = change_record.change_type
    hit = change_record.library_hit

    if ct == "DELETED" and not hit:
        change_record.status = "IGNORED"
        session.add(change_record)
        session.commit()
        return None

    ticket = _build_ticket(change_record, session)
    session.add(ticket)
    session.flush()

    change_record.ticket_id = ticket.id
    change_record.status = "TICKET_GENERATED" if ct != "MODIFIED" or hit else "ALERT"
    session.add(change_record)
    session.commit()
    session.refresh(ticket)
    return ticket


def route_all_pending(task_id: int, session: Session) -> list[TicketDraft]:
    """对 task 下所有 PENDING 状态的变更记录执行路由，返回生成的工单列表。"""
    records = session.exec(
        select(RegFieldChangeRecord).where(
            RegFieldChangeRecord.task_id == task_id,
            RegFieldChangeRecord.status == "PENDING",
        )
    ).all()

    tickets: list[TicketDraft] = []
    for record in records:
        ticket = route_change_to_ticket(record, session)
        if ticket:
            tickets.append(ticket)
    return tickets


# ──────────────────────────────────────────────────────────────────────────────
# 工单构造
# ──────────────────────────────────────────────────────────────────────────────

def _build_ticket(record: RegFieldChangeRecord, session: Session) -> TicketDraft:
    ct = record.change_type
    hit = record.library_hit

    if ct == "ADDED" and hit:
        return _ticket_added_hit(record, session)
    elif ct == "ADDED" and not hit:
        return _ticket_added_miss(record, session)
    elif ct == "DELETED" and hit:
        return _ticket_deleted_hit(record, session)
    elif ct == "MODIFIED" and hit:
        return _ticket_modified_hit(record)
    else:  # MODIFIED + 未命中
        return _ticket_modified_miss(record)


def _ticket_added_hit(record: RegFieldChangeRecord, session: Session) -> TicketDraft:
    """新增指标 + 命中知识库 → DATA_MAPPING，预填候选血缘。"""
    candidates = _get_lineage_candidates(record.reporting_item_code, session)
    after = _load_snapshot(record.after_snapshot)

    must_do = [
        f"确认以下候选血缘是否适用于新指标「{record.item_name}」：",
        *[f"  · {c['field_name']}（{c['field_code']}）" for c in candidates],
        "如有变化，在工单中更新血缘映射后确认。",
    ]
    must_confirm = [
        "候选血缘字段已核实，口径与新指标定义一致。",
        "若现有字段需加过滤条件，已在备注中说明。",
    ]

    return TicketDraft(
        task_id=record.task_id,
        title=f"【新增指标·血缘确认】{record.reporting_object_code} - {record.item_name}",
        content=_render_added_hit_content(record, after, candidates),
        action_ticket_type="DATA_MAPPING",
        severity_level="L2",
        severity_score=60,
        summary=f"监管新增指标「{record.item_name}」，系统已找到候选血缘，请确认映射关系。",
        must_do=json.dumps(must_do, ensure_ascii=False),
        must_confirm=json.dumps(must_confirm, ensure_ascii=False),
        related_impact_codes=json.dumps([record.reporting_item_code], ensure_ascii=False),
        status="OPEN",
    )


def _ticket_added_miss(record: RegFieldChangeRecord, session: Session) -> TicketDraft:
    """新增指标 + 未命中知识库 → LINEAGE_BUILD 高优，附推荐来源。"""
    after = _load_snapshot(record.after_snapshot)
    recommendations = _get_source_recommendations(record, session)

    must_do = [
        f"新监管指标「{record.item_name}」尚无血缘记录，请确认数据来源：",
        *[f"  · {r}" for r in recommendations],
        "确认来源后，在知识库中补录血缘关系。",
    ]
    must_confirm = [
        "已确认数据来源系统和源字段。",
        "已在知识库补录血缘，或已标注【确认无需血缘】并说明原因。",
    ]

    return TicketDraft(
        task_id=record.task_id,
        title=f"【新增指标·来源待确认】{record.reporting_object_code} - {record.item_name}",
        content=_render_added_miss_content(record, after, recommendations),
        action_ticket_type="LINEAGE_BUILD",
        severity_level="L1",
        severity_score=90,
        summary=f"监管新增指标「{record.item_name}」，知识库中无血缘记录，需排查数据来源。",
        must_do=json.dumps(must_do, ensure_ascii=False),
        must_confirm=json.dumps(must_confirm, ensure_ascii=False),
        related_impact_codes=json.dumps([record.reporting_item_code], ensure_ascii=False),
        status="OPEN",
    )


def _ticket_deleted_hit(record: RegFieldChangeRecord, session: Session) -> TicketDraft:
    """删除指标 + 命中知识库 → REPORT_DECOMMISSION，附影响分析。"""
    impact = _get_deletion_impact(record.reporting_item_code, session)

    must_do = [
        f"指标「{record.item_name}」已从监管报表中删除，请处理以下影响：",
        *impact,
        "确认所有下游依赖已妥善处理后关闭工单。",
    ]
    must_confirm = [
        "已确认相关血缘记录是否需要同步下线。",
        "已确认引用此指标的规则和校验是否需要修改或退役。",
    ]

    return TicketDraft(
        task_id=record.task_id,
        title=f"【删除指标·退役确认】{record.reporting_object_code} - {record.item_name}",
        content=_render_deleted_hit_content(record, impact),
        action_ticket_type="REPORT_DECOMMISSION",
        severity_level="L2",
        severity_score=70,
        summary=f"监管删除指标「{record.item_name}」，需确认知识库中相关血缘和规则的退役处理。",
        must_do=json.dumps(must_do, ensure_ascii=False),
        must_confirm=json.dumps(must_confirm, ensure_ascii=False),
        related_impact_codes=json.dumps([record.reporting_item_code], ensure_ascii=False),
        status="OPEN",
    )


def _ticket_modified_hit(record: RegFieldChangeRecord) -> TicketDraft:
    """变更指标 + 命中知识库 → DATA_MAPPING，附口径 diff。"""
    before = _load_snapshot(record.before_snapshot)
    after = _load_snapshot(record.after_snapshot)
    diff_lines = _compute_diff(before, after)

    must_do = [
        f"指标「{record.item_name}」口径发生变化，请核实现有血缘是否仍适用：",
        *diff_lines,
        "根据口径变化判断源字段取数逻辑是否需要调整。",
    ]
    must_confirm = [
        "已核实口径变化对现有数据取数的影响。",
        "血缘关系已按新口径更新，或已确认无需调整。",
    ]

    return TicketDraft(
        task_id=record.task_id,
        title=f"【口径变更·血缘复核】{record.reporting_object_code} - {record.item_name}",
        content=_render_modified_hit_content(record, before, after, diff_lines),
        action_ticket_type="DATA_MAPPING",
        severity_level="L2",
        severity_score=65,
        summary=f"监管变更指标「{record.item_name}」口径，需确认现有血缘是否仍适用。",
        must_do=json.dumps(must_do, ensure_ascii=False),
        must_confirm=json.dumps(must_confirm, ensure_ascii=False),
        related_impact_codes=json.dumps([record.reporting_item_code], ensure_ascii=False),
        status="OPEN",
    )


def _ticket_modified_miss(record: RegFieldChangeRecord) -> TicketDraft:
    """变更指标 + 未命中知识库 → LINEAGE_BUILD 高优，告警型。"""
    before = _load_snapshot(record.before_snapshot)
    after = _load_snapshot(record.after_snapshot)

    must_do = [
        f"⚠️ 告警：指标「{record.item_name}」在监管文件中发生变更，但知识库中无血缘记录。",
        "请排查是否存在漏录的隐藏血缘关系：",
        "  ① 若确实有血缘 → 补录后关闭此工单",
        "  ② 若确认无需维护 → 标记忽略并说明原因",
    ]
    must_confirm = [
        "已排查是否存在未录入的血缘关系。",
        "已处理：补录血缘 或 标注【确认无需维护】并说明原因。",
    ]

    return TicketDraft(
        task_id=record.task_id,
        title=f"【隐藏血缘告警】{record.reporting_object_code} - {record.item_name}",
        content=_render_modified_miss_content(record, before, after),
        action_ticket_type="LINEAGE_BUILD",
        severity_level="L1",
        severity_score=85,
        summary=f"指标「{record.item_name}」有监管变更但无血缘记录，可能存在漏录，需人工排查。",
        must_do=json.dumps(must_do, ensure_ascii=False),
        must_confirm=json.dumps(must_confirm, ensure_ascii=False),
        related_impact_codes=json.dumps([record.reporting_item_code], ensure_ascii=False),
        status="OPEN",
    )


# ──────────────────────────────────────────────────────────────────────────────
# 辅助：数据查询
# ──────────────────────────────────────────────────────────────────────────────

def _get_lineage_candidates(item_code: str, session: Session) -> list[dict]:
    """获取该指标已有的血缘候选字段列表。"""
    item = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code == item_code)
    ).first()
    if not item or not item.id:
        return []

    lineages = session.exec(
        select(ReportingItemLineage).where(
            ReportingItemLineage.reporting_item_id == item.id
        )
    ).all()

    candidates = []
    for lin in lineages:
        field = session.get(DataFieldCatalog, lin.data_field_id)
        if field:
            candidates.append({
                "field_code": field.field_code,
                "field_name": field.field_name,
                "table_name": field.table_name,
                "lineage_role": lin.lineage_role,
                "mapping_status": lin.mapping_status,
            })
    return candidates


def _get_source_recommendations(
    record: RegFieldChangeRecord,
    session: Session,
) -> list[str]:
    """为未命中知识库的新增指标生成来源推荐文案。

    使用关键词匹配在 DataFieldCatalog 中查找相似字段。
    完整的语义推荐引擎在 Step E2+F2 实现，此处为轻量版本。
    """
    item_name = record.item_name
    after = _load_snapshot(record.after_snapshot)
    definition = after.get("definition", "")

    # 提取关键词（名称 + 定义中的名词片段）
    keywords = _extract_keywords(item_name + " " + definition)

    results: list[dict] = []
    all_fields = session.exec(select(DataFieldCatalog)).all()
    for field in all_fields:
        score = sum(1 for kw in keywords if kw in (field.business_meaning or "") or kw in field.field_name)
        if score > 0:
            results.append({"field": field, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:3]

    if not top:
        return [
            "未找到匹配候选字段，建议：",
            "  · 检查投资业务数据集市（DM_INVESTMENT）是否有相关字段",
            "  · 检查投资持仓源系统（ODS_INVEST）是否有相关字段",
            "  · 若需接入新数据源，请升级为系统集成需求",
        ]

    lines = []
    for item in top:
        f = item["field"]
        lines.append(f"{f.field_name}（{f.field_code}）— {f.business_meaning}")
    return lines


def _get_deletion_impact(item_code: str, session: Session) -> list[str]:
    """分析删除指标的影响范围。"""
    item = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code == item_code)
    ).first()
    if not item or not item.id:
        return ["未在知识库中找到相关记录，影响范围待确认。"]

    lineages = session.exec(
        select(ReportingItemLineage).where(
            ReportingItemLineage.reporting_item_id == item.id
        )
    ).all()

    lines = []
    if lineages:
        lines.append(f"当前知识库中有 {len(lineages)} 条血缘记录：")
        for lin in lineages:
            field = session.get(DataFieldCatalog, lin.data_field_id)
            if field:
                lines.append(f"  · {field.field_name}（{field.field_code}）")
    else:
        lines.append("当前知识库中无血缘记录。")

    return lines


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取简单关键词（中文词组，长度 2-6 字）。"""
    import re
    # 提取 2-6 个汉字的词组
    words = re.findall(r'[一-鿿]{2,6}', text)
    # 去重，过滤过于通用的词
    stop = {"余额", "金额", "填报", "机构", "数据", "管理", "情况", "投资", "按照", "期末"}
    return list({w for w in words if w not in stop})


# ──────────────────────────────────────────────────────────────────────────────
# 辅助：内容渲染
# ──────────────────────────────────────────────────────────────────────────────

def _load_snapshot(s: str | dict) -> dict:
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s)
    except Exception:
        return {}


def _compute_diff(before: dict, after: dict) -> list[str]:
    lines = []
    b_def = before.get("definition", "")
    a_def = after.get("definition", "")
    if b_def != a_def:
        lines.append(f"  变更前：{b_def}")
        lines.append(f"  变更后：{a_def}")
    return lines or ["  （定义无可显示差异）"]


def _render_added_hit_content(record: RegFieldChangeRecord, after: dict, candidates: list[dict]) -> str:
    cand_text = "\n".join(f"  · {c['field_name']}（{c['field_code']}）" for c in candidates) or "  （无候选）"
    return (
        f"## 新增指标：{record.item_name}\n\n"
        f"**指标编码**：{record.reporting_item_code}\n"
        f"**所属报表**：{record.reporting_object_code}\n\n"
        f"**指标定义**：\n{after.get('definition', '（无）')}\n\n"
        f"**候选血缘字段**（来自现有知识库）：\n{cand_text}\n\n"
        f"请确认上述字段是否适用于新指标，并更新血缘映射。"
    )


def _render_added_miss_content(record: RegFieldChangeRecord, after: dict, recommendations: list[str]) -> str:
    rec_text = "\n".join(f"  · {r}" for r in recommendations)
    return (
        f"## 新增指标（来源待确认）：{record.item_name}\n\n"
        f"**指标编码**：{record.reporting_item_code}\n"
        f"**所属报表**：{record.reporting_object_code}\n\n"
        f"**指标定义**：\n{after.get('definition', '（无）')}\n\n"
        f"**AI 推荐候选来源**（关键词匹配，仅供参考）：\n{rec_text}\n\n"
        f"⚠️ 知识库中无此指标的血缘记录，请排查数据来源并补录。"
    )


def _render_deleted_hit_content(record: RegFieldChangeRecord, impact: list[str]) -> str:
    impact_text = "\n".join(f"  {line}" for line in impact)
    return (
        f"## 删除指标：{record.item_name}\n\n"
        f"**指标编码**：{record.reporting_item_code}\n"
        f"**所属报表**：{record.reporting_object_code}\n\n"
        f"**影响范围分析**：\n{impact_text}\n\n"
        f"请确认以上血缘记录是否需要同步退役。"
    )


def _render_modified_hit_content(
    record: RegFieldChangeRecord,
    before: dict,
    after: dict,
    diff_lines: list[str],
) -> str:
    diff_text = "\n".join(diff_lines)
    return (
        f"## 口径变更：{record.item_name}\n\n"
        f"**指标编码**：{record.reporting_item_code}\n"
        f"**所属报表**：{record.reporting_object_code}\n\n"
        f"**口径变化**：\n{diff_text}\n\n"
        f"请核实现有血缘字段的取数逻辑是否需要调整。"
    )


def _render_modified_miss_content(record: RegFieldChangeRecord, before: dict, after: dict) -> str:
    return (
        f"## ⚠️ 隐藏血缘告警：{record.item_name}\n\n"
        f"**指标编码**：{record.reporting_item_code}\n"
        f"**所属报表**：{record.reporting_object_code}\n\n"
        f"**变更前定义**：\n{before.get('definition', '（无）')}\n\n"
        f"**变更后定义**：\n{after.get('definition', '（无）')}\n\n"
        f"该指标在监管文件中发生变更，但知识库中无血缘记录。\n"
        f"可能存在未录入的隐藏血缘，请人工排查。"
    )
