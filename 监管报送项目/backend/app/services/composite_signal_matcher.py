from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from collections import defaultdict

from sqlmodel import Session, select

from app.models.db_models import (
    BusinessConceptValueMapping,
    DataFieldCatalog,
    DataFieldCodeValue,
    MeasureFieldMapping,
    RegConcept,
    RegConceptAlias,
    RegConceptReportingItemMap,
    RegReportingItem,
    RegReportingObject,
    ReportingItemLineage,
)


COMPOSITE_SEMANTIC_MATCH = "COMPOSITE_SEMANTIC_MATCH"
SEMANTIC_FIELD_MATCH = "SEMANTIC_FIELD_MATCH"


@dataclass(frozen=True)
class ConceptHit:
    concept_code: str
    concept_name: str
    concept_type: str
    matched_alias: str
    confidence_score: float


@dataclass
class CompositeSemanticMatch:
    match_type: str
    pattern_code: str
    indicator_hint: str
    measure_phrase: str
    condition_phrase: str
    reporting_item_codes: list[str]
    measure_field_codes: list[str]
    condition_field_codes: list[str]
    matched_concepts: list[dict]
    measure_fields: list[dict]
    conditions: list[dict]
    confidence: float
    review_status: str = "PENDING"
    needs_review: bool = True
    evidence_text: str = ""

    def to_dict(self) -> dict:
        return {
            "match_type": self.match_type,
            "pattern_code": self.pattern_code,
            "indicator_hint": self.indicator_hint,
            "measure_phrase": self.measure_phrase,
            "condition_phrase": self.condition_phrase,
            "reporting_item_codes": self.reporting_item_codes,
            "measure_field_codes": self.measure_field_codes,
            "condition_field_codes": self.condition_field_codes,
            "matched_concepts": self.matched_concepts,
            "measure_fields": self.measure_fields,
            "filter_conditions": self.conditions,
            "conditions": self.conditions,
            "confidence": self.confidence,
            "review_status": self.review_status,
            "needs_review": self.needs_review,
            "evidence_text": self.evidence_text,
        }


@dataclass(frozen=True)
class _ConditionMatch:
    hit: ConceptHit
    mapping: BusinessConceptValueMapping


@dataclass(frozen=True)
class _MeasureMatch:
    hit: ConceptHit
    mappings: tuple[MeasureFieldMapping, ...] = field(default_factory=tuple)


def build_composite_match(
    session: Session,
    table_code: str,
    indicator_hint: str,
    evidence_text: str = "",
) -> CompositeSemanticMatch | None:
    """Build a generic concept + measure composite candidate.

    This is deliberately deterministic. It resolves classification concepts from
    confirmed value mappings and measure concepts from active measure-field
    mappings. Missing either side means no composite match.
    """

    text = normalize_text(indicator_hint)
    if not text:
        return None

    condition = _match_condition(session, text)
    if condition is None:
        return None

    measure_text = text.replace(condition.hit.matched_alias, "", 1)
    measure = _match_measure(session, table_code, measure_text)
    if measure is None:
        measure = _match_measure(session, table_code, text)
    if measure is None:
        return None

    all_condition_mappings = session.exec(
        select(BusinessConceptValueMapping).where(
            BusinessConceptValueMapping.concept_code == condition.hit.concept_code,
            BusinessConceptValueMapping.mapping_status == "CONFIRMED",
        )
    ).all()
    if not all_condition_mappings:
        return None

    conditions = _build_filter_conditions(session, all_condition_mappings)
    if not conditions:
        return None

    measure_fields = _build_measure_fields(session, measure.mappings)
    if not measure_fields:
        return None

    reporting_item_codes = _reporting_item_codes_for_measure(session, measure.hit.concept_code, table_code)
    condition_field_codes = sorted({item["field_code"] for item in conditions})
    confidence = min(
        0.95,
        round(
            0.66
            + min(condition.hit.confidence_score, 1.0) * 0.14
            + min(measure.hit.confidence_score, 1.0) * 0.12
            + 0.04,
            2,
        ),
    )

    return CompositeSemanticMatch(
        match_type=COMPOSITE_SEMANTIC_MATCH,
        pattern_code=f"{table_code}_CLASSIFICATION_MEASURE",
        indicator_hint=indicator_hint,
        measure_phrase=measure.hit.concept_name,
        condition_phrase=condition.hit.concept_name,
        reporting_item_codes=reporting_item_codes,
        measure_field_codes=[item["field_code"] for item in measure_fields],
        condition_field_codes=condition_field_codes,
        matched_concepts=[
            {
                "concept_code": condition.hit.concept_code,
                "concept_name": condition.hit.concept_name,
                "concept_type": condition.hit.concept_type,
                "matched_alias": condition.hit.matched_alias,
            },
            {
                "concept_code": measure.hit.concept_code,
                "concept_name": measure.hit.concept_name,
                "concept_type": measure.hit.concept_type,
                "matched_alias": measure.hit.matched_alias,
            },
        ],
        measure_fields=measure_fields,
        conditions=conditions,
        confidence=confidence,
        review_status="PENDING",
        needs_review=True,
        evidence_text=evidence_text,
    )


def build_semantic_field_match(
    session: Session,
    table_code: str,
    indicator_hint: str,
    evidence_text: str = "",
) -> CompositeSemanticMatch | None:
    """Build a deterministic field-level semantic candidate.

    This handles cases like "发行人类型": the revision target is a dimension
    field itself, not a "classification + measure" phrase.
    """

    text = normalize_text(indicator_hint)
    if not text:
        return None

    hit = _match_field_concept(session, text)
    if hit is None:
        return None

    field_rows = _find_scoped_lineage_fields(session, table_code, hit)
    if not field_rows:
        return None

    measure_fields = [
        {
            "field_code": field.field_code,
            "field_name": field.field_name,
            "table_name": field.table_name,
            "column_name": field.column_name,
            "field_role": lineage.lineage_role,
            "confidence_score": 0.8,
        }
        for field, lineage, _item in field_rows
    ]
    reporting_item_codes = sorted({item.item_code for _field, _lineage, item in field_rows})

    return CompositeSemanticMatch(
        match_type=SEMANTIC_FIELD_MATCH,
        pattern_code=f"{table_code}_SEMANTIC_FIELD",
        indicator_hint=indicator_hint,
        measure_phrase="",
        condition_phrase=hit.concept_name,
        reporting_item_codes=reporting_item_codes,
        measure_field_codes=[field["field_code"] for field in measure_fields],
        condition_field_codes=[],
        matched_concepts=[
            {
                "concept_code": hit.concept_code,
                "concept_name": hit.concept_name,
                "concept_type": hit.concept_type,
                "matched_alias": hit.matched_alias,
            }
        ],
        measure_fields=measure_fields,
        conditions=[],
        confidence=0.8,
        review_status="PENDING",
        needs_review=True,
        evidence_text=evidence_text,
    )


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text or "")
    cleaned = cleaned.replace("\u3000", "").replace("×", "").replace("*", "")
    cleaned = re.sub(r"^\d+(?:\.\d+)*[、.．]?", "", cleaned)
    cleaned = re.sub(r"^[一二三四五六七八九十]+[、.．]", "", cleaned)
    cleaned = re.sub(r"^[（(][一二三四五六七八九十]+[）)]", "", cleaned)
    return cleaned


def _match_condition(session: Session, text: str) -> _ConditionMatch | None:
    mappings = session.exec(
        select(BusinessConceptValueMapping).where(
            BusinessConceptValueMapping.mapping_status == "CONFIRMED"
        )
    ).all()
    candidates: list[_ConditionMatch] = []
    for mapping in mappings:
        aliases = _concept_aliases(session, mapping.concept_code)
        aliases.extend(_json_list(mapping.match_aliases))
        code_value = session.exec(
            select(DataFieldCodeValue).where(
                DataFieldCodeValue.field_code == mapping.field_code,
                DataFieldCodeValue.value_code == mapping.value_code,
                DataFieldCodeValue.status == "ACTIVE",
            )
        ).first()
        if code_value is not None:
            aliases.append(code_value.value_name)
            aliases.extend(_json_list(code_value.value_aliases))
        aliases.append(mapping.concept_name)
        aliases.append(mapping.value_name)
        for alias in _sorted_aliases(aliases):
            if alias in text:
                candidates.append(
                    _ConditionMatch(
                        hit=ConceptHit(
                            concept_code=mapping.concept_code,
                            concept_name=mapping.concept_name,
                            concept_type="CLASSIFICATION",
                            matched_alias=alias,
                            confidence_score=mapping.confidence_score,
                        ),
                        mapping=mapping,
                    )
                )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (len(item.hit.matched_alias), item.hit.confidence_score))


def _match_field_concept(session: Session, text: str) -> ConceptHit | None:
    concepts = session.exec(
        select(RegConcept)
        .where(RegConcept.status == "ACTIVE")
        .where(RegConcept.concept_type.in_(["DIMENSION", "CLASSIFICATION"]))
    ).all()
    candidates: list[ConceptHit] = []
    for concept in concepts:
        aliases = _concept_aliases(session, concept.concept_code)
        aliases.append(concept.canonical_name)
        for alias in _sorted_aliases(aliases):
            if alias in text:
                candidates.append(
                    ConceptHit(
                        concept_code=concept.concept_code,
                        concept_name=concept.canonical_name,
                        concept_type=concept.concept_type,
                        matched_alias=alias,
                        confidence_score=0.8,
                    )
                )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (len(item.matched_alias), item.confidence_score))


def _match_measure(session: Session, table_code: str, text: str) -> _MeasureMatch | None:
    mappings = session.exec(
        select(MeasureFieldMapping)
        .where(MeasureFieldMapping.reporting_object_code == table_code)
        .where(MeasureFieldMapping.status == "ACTIVE")
        .order_by(MeasureFieldMapping.priority)
    ).all()
    by_concept: dict[str, list[MeasureFieldMapping]] = defaultdict(list)
    for mapping in mappings:
        by_concept[mapping.measure_concept_code].append(mapping)

    candidates: list[_MeasureMatch] = []
    for concept_code, concept_mappings in by_concept.items():
        aliases = _concept_aliases(session, concept_code)
        aliases.append(concept_mappings[0].measure_concept_name)
        for alias in _sorted_aliases(aliases):
            if alias in text:
                candidates.append(
                    _MeasureMatch(
                        hit=ConceptHit(
                            concept_code=concept_code,
                            concept_name=concept_mappings[0].measure_concept_name,
                            concept_type="MEASURE",
                            matched_alias=alias,
                            confidence_score=max(m.confidence_score for m in concept_mappings),
                        ),
                        mappings=tuple(concept_mappings),
                    )
                )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (len(item.hit.matched_alias), item.hit.confidence_score))


def _concept_aliases(session: Session, concept_code: str) -> list[str]:
    concept = session.exec(select(RegConcept).where(RegConcept.concept_code == concept_code)).first()
    if concept is None or concept.id is None:
        return []
    aliases = [concept.canonical_name]
    rows = session.exec(select(RegConceptAlias).where(RegConceptAlias.concept_id == concept.id)).all()
    aliases.extend(row.alias_text for row in rows)
    return aliases


def _build_filter_conditions(
    session: Session,
    mappings: list[BusinessConceptValueMapping],
) -> list[dict]:
    conditions = []
    for mapping in mappings:
        code_value = session.exec(
            select(DataFieldCodeValue).where(
                DataFieldCodeValue.field_code == mapping.field_code,
                DataFieldCodeValue.value_code == mapping.value_code,
                DataFieldCodeValue.status == "ACTIVE",
            )
        ).first()
        if code_value is None:
            continue
        field = session.exec(
            select(DataFieldCatalog).where(DataFieldCatalog.field_code == mapping.field_code)
        ).first()
        conditions.append(
            {
                "field_code": mapping.field_code,
                "field_name": field.field_name if field else mapping.field_code,
                "operator": "=",
                "value_code": mapping.value_code,
                "value_name": code_value.value_name,
                "confidence_level": code_value.confidence_level,
            }
        )
    return conditions


def _build_measure_fields(session: Session, mappings: tuple[MeasureFieldMapping, ...]) -> list[dict]:
    rows = []
    for mapping in sorted(mappings, key=lambda item: item.priority):
        field = session.exec(
            select(DataFieldCatalog).where(DataFieldCatalog.field_code == mapping.field_code)
        ).first()
        if field is None:
            continue
        rows.append(
            {
                "field_code": field.field_code,
                "field_name": field.field_name,
                "table_name": field.table_name,
                "column_name": field.column_name,
                "field_role": mapping.field_role,
                "confidence_score": mapping.confidence_score,
            }
        )
    return rows


def _find_scoped_lineage_fields(
    session: Session,
    table_code: str,
    hit: ConceptHit,
) -> list[tuple[DataFieldCatalog, ReportingItemLineage, RegReportingItem]]:
    aliases = _sorted_aliases(_concept_aliases(session, hit.concept_code) + [hit.concept_name])
    rows = session.exec(
        select(DataFieldCatalog, ReportingItemLineage, RegReportingItem)
        .join(ReportingItemLineage, ReportingItemLineage.data_field_id == DataFieldCatalog.id)
        .join(RegReportingItem, RegReportingItem.id == ReportingItemLineage.reporting_item_id)
        .join(RegReportingObject, RegReportingObject.id == RegReportingItem.reporting_object_id)
        .where(RegReportingObject.object_code == table_code)
        .where(ReportingItemLineage.lineage_role.in_(["DIMENSION_FIELD", "FILTER_FIELD"]))
    ).all()
    matched = []
    for field, lineage, item in rows:
        haystacks = [
            normalize_text(field.field_name),
            normalize_text(field.business_meaning),
            normalize_text(field.field_code),
            normalize_text(field.column_name),
        ]
        if any(alias and any(alias in haystack for haystack in haystacks) for alias in aliases):
            matched.append((field, lineage, item))
    return matched


def _reporting_item_codes_for_measure(
    session: Session,
    measure_concept_code: str,
    table_code: str,
) -> list[str]:
    concept = session.exec(
        select(RegConcept).where(RegConcept.concept_code == measure_concept_code)
    ).first()
    if concept is None or concept.id is None:
        return []
    rows = session.exec(
        select(RegConceptReportingItemMap)
        .where(RegConceptReportingItemMap.concept_id == concept.id)
        .where(RegConceptReportingItemMap.reporting_item_code.startswith(f"{table_code}."))
    ).all()
    return [row.reporting_item_code for row in rows]


def _json_list(value: str) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded if str(item).strip()]


def _sorted_aliases(values: list[str]) -> list[str]:
    aliases = {normalize_text(value) for value in values if normalize_text(value)}
    return sorted(aliases, key=len, reverse=True)
