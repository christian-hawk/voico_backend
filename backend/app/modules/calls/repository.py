import math
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import update
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.calls.schema import Call, CallLabel, CallStatus, SortDir, SortField

_LIKE_ESCAPE = "\\"
_PHONE_SEPARATORS = "+() -"
# SortField values are column names by construction
_NULLABLE_SORT_FIELDS = {SortField.caller_name, SortField.label, SortField.duration_seconds}


def _escape_like(term: str) -> str:
    escaped = term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE + _LIKE_ESCAPE)
    escaped = escaped.replace("%", _LIKE_ESCAPE + "%")
    return escaped.replace("_", _LIKE_ESCAPE + "_")


def _normalized_phone() -> Any:
    expr: Any = col(Call.phone_number)
    for separator in _PHONE_SEPARATORS:
        expr = func.replace(expr, separator, "")
    return expr


class CallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, call_id: uuid.UUID) -> Optional[Call]:
        result = await self.session.exec(select(Call).where(Call.id == call_id))
        return result.first()

    async def list_calls(
        self,
        status: Optional[CallStatus],
        page: int,
        page_size: int,
        caller_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        label: Optional[CallLabel] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        sort_by: Optional[SortField] = None,
        sort_dir: SortDir = SortDir.asc,
    ) -> tuple[list[Call], int, int, dict[str, int]]:
        conditions: list[Any] = []
        if status is not None:
            conditions.append(Call.status == status)
        if caller_name is not None:
            pattern = f"%{_escape_like(caller_name)}%"
            conditions.append(col(Call.caller_name).ilike(pattern, escape=_LIKE_ESCAPE))
        if phone_number is not None:
            digits = "".join(char for char in phone_number if char.isdigit())
            if digits:
                # digits-only term: compare digits against digits, ignoring formatting
                conditions.append(_normalized_phone().like(f"%{digits}%"))
            else:
                pattern = f"%{_escape_like(phone_number)}%"
                conditions.append(col(Call.phone_number).ilike(pattern, escape=_LIKE_ESCAPE))
        if label is not None:
            conditions.append(Call.label == label)
        if min_duration is not None:
            conditions.append(col(Call.duration_seconds) >= min_duration)
        if max_duration is not None:
            conditions.append(col(Call.duration_seconds) <= max_duration)

        query = select(Call)
        count_query = select(func.count()).select_from(Call)

        for condition in conditions:
            query = query.where(condition)
            count_query = count_query.where(condition)

        count_result = await self.session.exec(count_query)
        total = count_result.one()

        # counts are global by design (only total reflects the filters); one
        # GROUP BY replaces the per-status loop. Missing statuses default to 0.
        count_rows = await self.session.exec(
            select(col(Call.status), func.count()).group_by(col(Call.status))
        )
        counts: dict[str, int] = {status.value: c for status, c in count_rows}

        # created_at desc + id keep pagination stable across ties in any ordering
        tie_breakers = (col(Call.created_at).desc(), col(Call.id))
        if sort_by is not None:
            sort_column = col(getattr(Call, sort_by.value))
            ordering = sort_column.desc() if sort_dir is SortDir.desc else sort_column.asc()
            if sort_by in _NULLABLE_SORT_FIELDS:
                ordering = ordering.nulls_last()
            query = query.order_by(ordering, *tie_breakers)
        else:
            query = query.order_by(*tie_breakers)

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.session.exec(query)
        calls = list(result.all())

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return calls, total, total_pages, counts

    async def update(self, call: Call) -> Call:
        self.session.add(call)
        await self.session.flush()
        await self.session.refresh(call)
        return call

    async def expire_stale_calls(self, cutoff: datetime) -> int:
        stmt = (
            update(Call)
            .where(col(Call.status) == CallStatus.in_progress, col(Call.started_at) < cutoff)
            .values(status=CallStatus.failed, ended_at=datetime.utcnow())
        )
        result = await self.session.exec(stmt)
        return result.rowcount
