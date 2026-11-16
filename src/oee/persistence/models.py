"""SQLAlchemy modely (ARCHITECTURE §5, TASK §9).

Konvencie (ARCHITECTURE §10.2–10.3):
- množstvá `Integer`, minúty a podiely `Float` (žiadne `Numeric`);
- časy zmeny a udalostí = naivný lokálny čas linky;
- auditné timestampy (`*_at` okrem `start_at`, `slot_*`) = naivný UTC;
- kategória je atribút kódu, samostatná tabuľka kategórií nie je (D5);
- model zmeny sa neseeduje — zadáva ho manažér (D8);
- vzťahy sú iba many-to-one s `lazy="raise"`: nenačítavajú sa, slúžia na to, aby unit of work vkladal
  rodiča pred deťmi (bez nich SQLAlchemy INSERT podľa FK neradí). Dáta sa čítajú explicitnými dotazmi.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SHIFT_STATUSES = ("open", "in_progress", "completed", "incomplete")
HOUR_STATUSES = ("submitted", "needs_attention")
SOURCES = ("manual", "import")
AI_STATUSES = ("pending", "ok", "fallback", "error")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[int]: JSON}


class ShiftModelRow(Base):
    """Konfigurácia modelu zmeny (verzionovaná). Snapshot sa kopíruje do `shift.model_snapshot`."""

    __tablename__ = "shift_model"
    __table_args__ = (
        Index("uq_shift_model_active_line", "line_id", unique=True, sqlite_where=text("active = 1")),
        CheckConstraint("line_rate_pcs_per_hour > 0", name="ck_shift_model_rate"),
        CheckConstraint("shift_length_min > 0 AND shift_length_min % 60 = 0", name="ck_shift_model_length"),
        CheckConstraint("target_oee > 0 AND target_oee <= 1", name="ck_shift_model_goal"),
        CheckConstraint("break_min >= 0 AND am_min >= 0", name="ck_shift_model_allowance_min"),
        CheckConstraint("break_hour_no >= 1 AND am_hour_no >= 1", name="ck_shift_model_allowance_hour"),
        CheckConstraint(
            "break_offset_min >= 0 AND am_offset_min >= 0", name="ck_shift_model_allowance_offset"
        ),
        CheckConstraint("grace_min >= 0", name="ck_shift_model_grace"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer)
    line_id: Mapped[str] = mapped_column(String(16))
    product_id: Mapped[str] = mapped_column(String(16))
    line_rate_pcs_per_hour: Mapped[float] = mapped_column(Float)
    shift_start: Mapped[str] = mapped_column(String(5))
    """„HH:MM" lokálny čas linky."""
    shift_length_min: Mapped[int] = mapped_column(Integer)
    break_min: Mapped[int] = mapped_column(Integer)
    break_hour_no: Mapped[int] = mapped_column(Integer)
    break_offset_min: Mapped[int] = mapped_column(Integer, default=0)
    am_min: Mapped[int] = mapped_column(Integer)
    am_hour_no: Mapped[int] = mapped_column(Integer)
    am_offset_min: Mapped[int] = mapped_column(Integer, default=0)
    target_oee: Mapped[float] = mapped_column(Float)
    working_days: Mapped[list[int]] = mapped_column(JSON)
    grace_min: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Shift(Base):
    __tablename__ = "shift"
    __table_args__ = (
        UniqueConstraint("line_id", "date", "shift_code", name="uq_shift_line_date_code"),
        CheckConstraint(_in("status", SHIFT_STATUSES), name="ck_shift_status"),
        CheckConstraint("revision >= 0", name="ck_shift_revision"),
    )

    shift_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    line_id: Mapped[str] = mapped_column(String(16))
    product_id: Mapped[str] = mapped_column(String(16))
    date: Mapped[date] = mapped_column(Date)
    shift_code: Mapped[str] = mapped_column(String(8))
    model_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class HourlyReportRow(Base):
    __tablename__ = "hourly_report"
    __table_args__ = (
        UniqueConstraint("shift_id", "hour_no", name="uq_hour_shift_no"),
        CheckConstraint("hour_no >= 1", name="ck_hour_no"),
        CheckConstraint("planned_min > 0", name="ck_hour_planned"),
        CheckConstraint(_in("status", HOUR_STATUSES), name="ck_hour_status"),
    )

    hour_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shift.shift_id", ondelete="CASCADE"), index=True)
    shift: Mapped[Shift] = relationship(lazy="raise")
    hour_no: Mapped[int] = mapped_column(Integer)
    slot_start: Mapped[datetime] = mapped_column(DateTime)
    slot_end: Mapped[datetime] = mapped_column(DateTime)
    planned_min: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    """`submitted` alebo `needs_attention` (uložené s varovaniami validácie)."""
    submitted_by: Mapped[str | None] = mapped_column(String(64), default=None)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    comment: Mapped[str | None] = mapped_column(Text, default=None)


class ProductionRecord(Base):
    __tablename__ = "production_record"
    __table_args__ = (
        CheckConstraint("produced_qty >= 0", name="ck_prod_produced"),
        CheckConstraint("rejects_qty >= 0 AND rejects_qty <= produced_qty", name="ck_prod_rejects"),
        CheckConstraint("retests IS NULL OR retests >= 0", name="ck_prod_retests"),
        CheckConstraint(_in("source", SOURCES), name="ck_prod_source"),
    )

    hour_id: Mapped[str] = mapped_column(
        ForeignKey("hourly_report.hour_id", ondelete="CASCADE"), primary_key=True
    )
    hour: Mapped[HourlyReportRow] = relationship(lazy="raise")
    produced_qty: Mapped[int] = mapped_column(Integer)
    rejects_qty: Mapped[int] = mapped_column(Integer)
    retests: Mapped[int | None] = mapped_column(Integer, default=None)
    microstop_s: Mapped[float | None] = mapped_column(Float, default=None)
    slowdown_s: Mapped[float | None] = mapped_column(Float, default=None)
    source: Mapped[str] = mapped_column(String(8))


class IssueType(Base):
    """Kód prestoja (ST-xxx). `category` = efektívna kategória (Top-10 má prednosť, D9)."""

    __tablename__ = "issue_type"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(200))
    name_sk: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    station_id: Mapped[str | None] = mapped_column(String(16), default=None)
    active_top10: Mapped[bool] = mapped_column(Boolean, default=False)
    is_other: Mapped[bool] = mapped_column(Boolean, default=False)


class DefectType(Base):
    """Kód zmätku (Q-xxx)."""

    __tablename__ = "defect_type"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(200))
    name_sk: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    active_top10: Mapped[bool] = mapped_column(Boolean, default=False)
    is_other: Mapped[bool] = mapped_column(Boolean, default=False)


class IssueEvent(Base):
    """Udalosť (segment) prestoja. Soft delete cez `deleted_at`."""

    __tablename__ = "issue_event"
    __table_args__ = (
        CheckConstraint("duration_min > 0", name="ck_issue_duration"),
        CheckConstraint(_in("source", SOURCES), name="ck_issue_source"),
    )

    issue_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    client_key: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    """Kľúč idempotencie ručného hlásenia (V9); import ho nemá (NULL viackrát)."""
    hour_id: Mapped[str] = mapped_column(ForeignKey("hourly_report.hour_id", ondelete="CASCADE"), index=True)
    hour: Mapped[HourlyReportRow] = relationship(lazy="raise")
    issue_type_code: Mapped[str] = mapped_column(ForeignKey("issue_type.code"))
    issue_type: Mapped[IssueType] = relationship(lazy="raise")
    free_text_name: Mapped[str | None] = mapped_column(String(200), default=None)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    """Začiatok (lokálny čas linky, celý dátum kvôli nočnej zmene); None = bez času."""
    duration_min: Mapped[float] = mapped_column(Float)
    continues_issue_id: Mapped[str | None] = mapped_column(
        ForeignKey("issue_event.issue_id", ondelete="SET NULL"), default=None
    )
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(String(8))
    external_ref: Mapped[str | None] = mapped_column(String(128), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class QualityRecord(Base):
    """Rozpis zmätkov hodiny. `defect_type_code` NULL = „Unspecified defect".

    Invariant Σ qty = `rejects_qty` kontroluje repozitár (`replace_hour_quality`).
    """

    __tablename__ = "quality_record"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_quality_qty"),
        CheckConstraint(_in("source", SOURCES), name="ck_quality_source"),
    )

    quality_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hour_id: Mapped[str] = mapped_column(ForeignKey("hourly_report.hour_id", ondelete="CASCADE"), index=True)
    hour: Mapped[HourlyReportRow] = relationship(lazy="raise")
    defect_type_code: Mapped[str | None] = mapped_column(ForeignKey("defect_type.code"), default=None)
    defect_type: Mapped[DefectType | None] = relationship(lazy="raise")
    qty: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(8))
    external_ref: Mapped[str | None] = mapped_column(String(128), unique=True, default=None)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AiOutput(Base):
    """Cache výstupu AI podľa faktov (`facts_hash` = SHA-256 kanonického JSON)."""

    __tablename__ = "ai_output"
    __table_args__ = (
        UniqueConstraint(
            "kind", "subject_key", "facts_hash", "model", "lang", "prompt_version", name="uq_ai_output_key"
        ),
        CheckConstraint(_in("status", AI_STATUSES), name="ck_ai_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))
    subject_key: Mapped[str] = mapped_column(String(64))
    facts_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(8))
    prompt_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
