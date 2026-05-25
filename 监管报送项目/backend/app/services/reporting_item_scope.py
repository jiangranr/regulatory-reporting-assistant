from collections.abc import Iterable
from typing import TypeVar


T = TypeVar("T")


def is_analysis_item(item: object) -> bool:
    """
    Whether a reporting item should participate in business impact analysis.

    Template headers, report date cells, blank/layout cells, and other structural
    cells are still preserved in template tables, but they should not drive
    lineage, source-field impact, or business ticket generation.
    """
    status = str(getattr(item, "status", "ACTIVE") or "ACTIVE").upper()
    if status != "ACTIVE":
        return False
    return bool(getattr(item, "is_fillable", False) or getattr(item, "is_derived", False))


def filter_analysis_items(items: Iterable[T]) -> list[T]:
    return [item for item in items if is_analysis_item(item)]
