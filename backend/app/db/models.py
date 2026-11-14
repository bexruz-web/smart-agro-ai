"""Ma'lumotlar modeli. Har bir o'lchov/kuzatuvda manba va vaqt saqlanadi (qat'iy qoida #6)."""
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Farmer(TimestampMixin, Base):
    __tablename__ = "farmers"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="uz")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")
    report_interval_hours: Mapped[int] = mapped_column(Integer, default=4)
    quiet_hours_start: Mapped[int | None] = mapped_column(Integer)
    quiet_hours_end: Mapped[int | None] = mapped_column(Integer)
    farm_location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(16), default="farmer")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # bot bloklangan bo'lsa

    fields: Mapped[list["Field"]] = relationship(back_populates="farmer", cascade="all, delete-orphan")


class Field(TimestampMixin, Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    geom = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    drawing_method: Mapped[str] = mapped_column(String(16), default="polygon")
    crop: Mapped[str | None] = mapped_column(String(32))
    planting_date: Mapped[date | None] = mapped_column(Date)
    soil_texture: Mapped[str | None] = mapped_column(String(32))
    water_available_m3_ha: Mapped[float | None] = mapped_column(Float)
    soil_ph: Mapped[float | None] = mapped_column(Float)  # laboratoriya natijasi (fermer kiritadi)
    soil_ec_ds_m: Mapped[float | None] = mapped_column(Float)  # ECe, dS/m (laboratoriya)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    last_report_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    farmer: Mapped[Farmer] = relationship(back_populates="fields")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str] = mapped_column(String(64))
    firmware: Mapped[str | None] = mapped_column(String(32))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seq: Mapped[int | None] = mapped_column(BigInteger)
    rssi: Mapped[int | None] = mapped_column(Integer)
    battery_v: Mapped[float | None] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class IngestBatch(Base):
    """Qurilma paketlari jurnali: (device, seq) takrorlanmaydi — replay himoyasi."""

    __tablename__ = "ingest_batches"
    __table_args__ = (UniqueConstraint("device_pk", "seq", name="uq_ingest_device_seq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(BigInteger)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    n_readings: Mapped[int] = mapped_column(Integer, default=0)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        UniqueConstraint("device_pk", "ts", "metric", name="uq_reading_device_ts_metric"),
        Index("ix_reading_field_metric_ts", "field_id", "metric", "ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metric: Mapped[str] = mapped_column(String(32))
    value: Mapped[float] = mapped_column(Float)
    raw_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    quality_flag: Mapped[str] = mapped_column(String(8), default="ok")
    quality_reason: Mapped[str | None] = mapped_column(String(128))
    seq: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(16), default="sensor")  # sensor | simulator | demo
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WeatherForecast(Base):
    """Prognozlar kuzatuvlardan alohida saqlanadi (WX-3)."""

    __tablename__ = "weather_forecasts"
    __table_args__ = (
        UniqueConstraint("field_id", "source", "issued_at", "granularity", "valid_at", name="uq_forecast"),
        Index("ix_forecast_field_valid", "field_id", "valid_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32), default="open-meteo")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    granularity: Mapped[str] = mapped_column(String(8))  # hourly | daily
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    variables: Mapped[dict] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WeatherObservation(Base):
    """NASA POWER kunlik kuzatuvlari grid katagi bo'yicha keshlanadi (6.2-bo'lim, 4-qoida)."""

    __tablename__ = "weather_observations"
    __table_args__ = (UniqueConstraint("source", "grid_key", "date", name="uq_observation"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="nasa-power")
    grid_key: Mapped[str] = mapped_column(String(32), index=True)
    date: Mapped[date] = mapped_column(Date)
    variables: Mapped[dict] = mapped_column(JSONB)
    resolution: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClimateSeries(Base):
    """Iqlim siljishi uchun yillik agregatlar (NASA POWER, 1981-yildan)."""

    __tablename__ = "climate_series"
    __table_args__ = (UniqueConstraint("grid_key", "year", name="uq_climate_series"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grid_key: Mapped[str] = mapped_column(String(32), index=True)
    year: Mapped[int] = mapped_column(Integer)
    t_mean: Mapped[float | None] = mapped_column(Float)
    precip_total: Mapped[float | None] = mapped_column(Float)
    hot_days: Mapped[int | None] = mapped_column(Integer)
    frost_days: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32), default="nasa-power")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClimateBaseline(Base):
    __tablename__ = "climate_baselines"
    __table_args__ = (UniqueConstraint("grid_key", "variable", "month", name="uq_climate_baseline"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grid_key: Mapped[str] = mapped_column(String(32), index=True)
    variable: Mapped[str] = mapped_column(String(32))
    month: Mapped[int] = mapped_column(Integer)
    mean: Mapped[float] = mapped_column(Float)
    std: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32), default="nasa-power")


class CropSeason(TimestampMixin, Base):
    __tablename__ = "crop_seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    crop: Mapped[str] = mapped_column(String(32))
    planting_date: Mapped[date | None] = mapped_column(Date)
    harvest_date: Mapped[date | None] = mapped_column(Date)
    yield_t_ha: Mapped[float | None] = mapped_column(Float)
    predicted_yield_t_ha: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[str | None] = mapped_column(String(16))
    water_used_m3: Mapped[float | None] = mapped_column(Float)
    fertilizers: Mapped[str | None] = mapped_column(Text)
    problems: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active")


class FieldEvent(TimestampMixin, Base):
    __tablename__ = "field_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="farmer")


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(16))  # report | realtime | manual | demo
    snapshot: Mapped[dict] = mapped_column(JSONB)
    rules_fired: Mapped[list] = mapped_column(JSONB, default=list)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(16))
    llm_status: Mapped[str] = mapped_column(String(32), default="skipped")
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"))
    alert_type: Mapped[str] = mapped_column(String(48))
    category: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16))
    problem: Mapped[str] = mapped_column(Text)
    cause: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    action: Mapped[str] = mapped_column(Text)
    timing: Mapped[str] = mapped_column(Text)
    expected_outcome: Mapped[str] = mapped_column(Text)
    risks: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(8))
    confidence_reason: Mapped[str] = mapped_column(Text)
    facts: Mapped[list] = mapped_column(JSONB, default=list)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(16), default="new")
    ai_explained: Mapped[bool] = mapped_column(Boolean, default=False)
    amount_mm: Mapped[float | None] = mapped_column(Float)
    due_date: Mapped[date | None] = mapped_column(Date)


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"))
    season_id: Mapped[int | None] = mapped_column(ForeignKey("crop_seasons.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(16), default="miniapp")


class AlertState(Base):
    """Ogohlantirishlar uchun cooldown va "bartaraf bo'ldi" xabarlari holati."""

    __tablename__ = "alert_states"
    __table_args__ = (UniqueConstraint("field_id", "alert_type", name="uq_alert_state"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"))
    alert_type: Mapped[str] = mapped_column(String(48))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    severity: Mapped[str] = mapped_column(String(16))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_severity: Mapped[str | None] = mapped_column(String(16))
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"))


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # report | alert | resolved
    dedupe_key: Mapped[str | None] = mapped_column(String(96))
    severity: Mapped[str | None] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24))  # sent | failed | skipped_no_token | skipped_quiet
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id", ondelete="SET NULL"))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(32))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
