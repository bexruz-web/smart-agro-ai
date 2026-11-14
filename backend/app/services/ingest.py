"""IoT o'lchovlarini qabul qilish: replay himoyasi, vaqt oynasi, sifat nazorati, saqlash."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, IngestBatch, SensorReading, WeatherForecast
from app.domain.qc import PAYLOAD_METRICS, TELEMETRY_METRICS, check_reading

MAX_FUTURE = timedelta(minutes=10)
MAX_PAST = timedelta(days=7)  # internet uzilganda buferlangan ma'lumotlar uchun


async def _model_air_temp(session: AsyncSession, field_id: int | None, ts: datetime) -> float | None:
    if field_id is None:
        return None
    row = await session.scalar(
        select(WeatherForecast.variables).where(
            WeatherForecast.field_id == field_id, WeatherForecast.granularity == "hourly",
            WeatherForecast.valid_at <= ts, WeatherForecast.valid_at > ts - timedelta(hours=1),
        ).order_by(WeatherForecast.issued_at.desc()).limit(1)
    )
    return row.get("temperature_2m") if row else None


async def _history(session: AsyncSession, device: Device, metric: str, before: datetime) -> list[tuple[datetime, float]]:
    res = await session.execute(
        select(SensorReading.ts, SensorReading.value).where(
            SensorReading.device_pk == device.id, SensorReading.metric == metric, SensorReading.ts < before
        ).order_by(SensorReading.ts.desc()).limit(12)
    )
    return list(reversed(res.all()))


async def ingest(session: AsyncSession, device: Device, payload: dict, source: str = "sensor") -> dict:
    now = datetime.now(timezone.utc)
    try:
        async with session.begin_nested():
            session.add(IngestBatch(device_pk=device.id, seq=payload["seq"], n_readings=len(payload["readings"])))
    except IntegrityError:
        return {"accepted": 0, "duplicate_batch": True, "flagged": 0}

    accepted = flagged = 0
    for r in sorted(payload["readings"], key=lambda x: x["ts"]):
        ts: datetime = r["ts"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts > now + MAX_FUTURE or ts < now - MAX_PAST:
            flagged += 1
            continue
        model_t = await _model_air_temp(session, device.field_id, ts)
        for key, (metric, unit) in PAYLOAD_METRICS.items():
            if r.get(key) is None:
                continue
            value = float(r[key])
            history = await _history(session, device, metric, ts)
            qc = check_reading(metric, value, ts, history, model_t if metric == "air_temp" else None)
            raw = r.get("soil_moisture_raw") if metric == "soil_moisture" else None
            stmt = insert(SensorReading).values(
                device_pk=device.id, field_id=device.field_id, ts=ts, metric=metric, value=value,
                raw_value=raw, unit=unit, quality_flag=qc.flag, quality_reason=qc.reason, seq=payload["seq"], source=source,
            ).on_conflict_do_nothing(constraint="uq_reading_device_ts_metric")
            res = await session.execute(stmt)
            if res.rowcount:
                accepted += 1
                if qc.flag != "ok":
                    flagged += 1
    device.last_seen_at = now
    device.last_seq = max(device.last_seq or 0, payload["seq"])
    device.firmware = payload.get("fw") or device.firmware
    device.rssi = payload.get("rssi")
    device.battery_v = payload.get("battery_v")
    await session.commit()
    return {"accepted": accepted, "duplicate_batch": False, "flagged": flagged}


async def ingest_telemetry(session: AsyncSession, device: Device, payload: dict, source: str = "sensor") -> dict:
    """Sxema telemetriyasi: bitta vaqt belgisi, bir nechta o'lchov. (device, timestamp) takrorlanmaydi."""
    now = datetime.now(timezone.utc)
    ts: datetime = payload["timestamp"]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if ts > now + MAX_FUTURE or ts < now - MAX_PAST:
        return {"accepted": 0, "duplicate": False, "flagged": len(payload["measurements"])}
    try:
        async with session.begin_nested():
            session.add(IngestBatch(device_pk=device.id, seq=int(ts.timestamp()), n_readings=len(payload["measurements"])))
    except IntegrityError:
        return {"accepted": 0, "duplicate": True, "flagged": 0}
    model_t = await _model_air_temp(session, device.field_id, ts)
    accepted = flagged = 0
    for name, m in payload["measurements"].items():
        if name not in TELEMETRY_METRICS or m.get("value") is None:
            continue
        metric, unit = TELEMETRY_METRICS[name]
        value = float(m["value"])
        history = await _history(session, device, metric, ts)
        qc = check_reading(metric, value, ts, history, model_t if metric == "air_temp" else None)
        res = await session.execute(insert(SensorReading).values(
            device_pk=device.id, field_id=device.field_id, ts=ts, metric=metric, value=value, raw_value=None, unit=unit,
            quality_flag=qc.flag, quality_reason=qc.reason, seq=int(ts.timestamp()), source=source,
        ).on_conflict_do_nothing(constraint="uq_reading_device_ts_metric"))
        if res.rowcount:
            accepted += 1
            flagged += qc.flag != "ok"
    status = payload.get("status") or {}
    csq = status.get("signal_quality")
    device.last_seen_at = now
    device.rssi = (-113 + 2 * int(csq)) if isinstance(csq, (int, float)) and 0 <= csq <= 31 else device.rssi
    await session.commit()
    return {"accepted": accepted, "duplicate": False, "flagged": flagged}
