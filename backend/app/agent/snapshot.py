"""Field Snapshot: dala bo'yicha barcha faktlar manbasi, vaqti va aniqligi bilan (DATA ANALYSIS bosqichi).

Har bir fakt: {fact_id, label_uz, value, unit, source, source_label, observed_at, resolution, quality, is_demo}.
LLM faqat shu faktlarni ko'radi va ularga havola qiladi — raqamlarni kod hisoblaydi.
"""
import calendar
import hashlib
import json
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CropSeason, Device, Field, FieldEvent, SensorReading
from app.domain import knowledge
from app.domain.et0 import actual_vapour_pressure_from_rh, et0_penman_monteith
from app.domain.gdd import gdd_day
from app.domain.geo import grid_key
from app.domain.qc import METRIC_LABEL_UZ, device_offline
from app.domain.water_balance import SoilWater, depletion_from_vwc, run_balance
from app.integrations import nasa_power, open_meteo
from app.services import weather

SENSOR_FRESH = timedelta(hours=3)
SENSOR_UNITS = {"soil_moisture": "%", "soil_temp": "°C", "air_temp": "°C", "air_humidity": "%", "light": "lx", "rain": ""}


@dataclass
class Snapshot:
    field_id: int
    generated_at: datetime
    facts: dict = field(default_factory=dict)
    crop_key: str | None = None
    stage: str | None = None
    assumptions: list[str] = field(default_factory=list)
    forecast_daily: list[dict] = field(default_factory=list)
    forecast_hourly: list[dict] = field(default_factory=list)
    forecast_issued_at: datetime | None = None
    balance_days: list[dict] = field(default_factory=list)
    is_demo: bool = False

    def add(self, fact_id: str, label: str, value, unit: str, source: str, source_label: str,
            observed_at: datetime | date | None, resolution: str, quality: str | None = None, is_demo: bool = False):
        if isinstance(value, float):
            value = round(value, 2)
        self.facts[fact_id] = {
            "fact_id": fact_id, "label_uz": label, "value": value, "unit": unit, "source": source,
            "source_label": source_label,
            "observed_at": observed_at.isoformat() if observed_at else None,
            "resolution": resolution, "quality": quality, "is_demo": is_demo,
        }

    def value(self, fact_id: str):
        f = self.facts.get(fact_id)
        return None if f is None else f["value"]

    def hash(self) -> str:
        """Muhim qiymatlar xeshi: LLM faqat holat sezilarli o'zgarganda chaqiriladi."""
        coarse = {k: (round(v["value"]) if isinstance(v["value"], float) else v["value"]) for k, v in sorted(self.facts.items())
                  if k not in ("devices_offline",)}
        return hashlib.sha256(json.dumps(coarse, sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "field_id": self.field_id, "generated_at": self.generated_at.isoformat(), "facts": self.facts,
            "crop": self.crop_key, "stage": self.stage, "assumptions": self.assumptions,
        }


def _planting(field_: Field, crop: dict, today: date) -> tuple[date, bool]:
    if field_.planting_date:
        return field_.planting_date, False
    p = knowledge.default_planting_date(crop, today.year)
    if p > today:
        p = knowledge.default_planting_date(crop, today.year - 1)
    return p, True


async def build_snapshot(session: AsyncSession, field_: Field, now: datetime | None = None) -> Snapshot:
    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    today = now.date()
    snap = Snapshot(field_id=field_.id, generated_at=now, is_demo=field_.is_demo)
    gkey = grid_key(field_.centroid_lat, field_.centroid_lon)

    # ---------- Sensorlar (dala nuqtasi)
    readings = (await session.execute(
        select(SensorReading).where(SensorReading.field_id == field_.id, SensorReading.ts >= now - timedelta(hours=24))
        .order_by(SensorReading.ts)
    )).scalars().all()
    latest: dict[str, SensorReading] = {}
    for r in readings:
        if r.quality_flag != "bad":
            latest[r.metric] = r
    for metric, r in latest.items():
        if now - r.ts > SENSOR_FRESH:
            continue
        demo = r.source in ("simulator", "demo")
        label = "📡 Sensor" + (" (DEMO/simulator)" if demo else "")
        value = bool(r.value) if metric == "rain" else r.value
        snap.add(metric, METRIC_LABEL_UZ.get(metric, metric), value, SENSOR_UNITS.get(metric, r.unit), "sensor",
                 label, r.ts, "field point (sensor location)", r.quality_flag, demo)
    sm = [(r.ts, r.value) for r in readings if r.metric == "soil_moisture" and r.quality_flag == "ok"]
    if len(sm) >= 4 and (sm[-1][0] - sm[0][0]) >= timedelta(hours=3):
        xs = [(t - sm[0][0]).total_seconds() / 86400 for t, _ in sm]
        ys = [v for _, v in sm]
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        den = sum((x - mx) ** 2 for x in xs)
        if den > 0:
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
            snap.add("soil_moisture_trend_24h", "Soil moisture trend (24 h)", slope, "%/kun", "model",
                     "🧮 Sensor trend", sm[-1][0], "field point")
    bad_last_hour = sum(1 for r in readings if r.quality_flag in ("bad", "suspect") and r.ts >= now - timedelta(hours=1))
    if readings:
        snap.add("sensor_bad_last_hour", "Shubhali/noto'g'ri o'lchovlar (1 soat)", bad_last_hour, "ta", "model",
                 "🧮 Quality control", now, "field point")
    devices = (await session.execute(select(Device).where(Device.field_id == field_.id))).scalars().all()
    if devices:
        offline = [d.device_id for d in devices if device_offline(
            d.last_seen_at, now, settings.expected_sensor_interval_min, settings.sensor_offline_factor)]
        snap.add("devices_offline", "Aloqasiz qurilmalar", len(offline), "ta", "model", "🧮 Device monitoring", now,
                 ", ".join(offline) or "—")

    # ---------- Prognoz (Open-Meteo)
    issued, hourly, daily = await weather.latest_forecast(session, field_.id)
    snap.forecast_issued_at = issued
    snap.forecast_hourly = hourly
    snap.forecast_daily = daily
    if issued:
        fl = open_meteo.SOURCE_LABEL
        res = "model grid (~2–11 km)"
        fut = [h for h in hourly if h["time"] >= now - timedelta(minutes=59)]
        cur = fut[0] if fut else None
        h24 = [h for h in fut if h["time"] < now + timedelta(hours=24)]
        h48 = [h for h in fut if h["time"] < now + timedelta(hours=48)]
        h72 = [h for h in fut if h["time"] < now + timedelta(hours=72)]

        def ssum(rows, k):
            vals = [r.get(k) for r in rows if r.get(k) is not None]
            return round(sum(vals), 1) if vals else None

        def smax(rows, k):
            vals = [r.get(k) for r in rows if r.get(k) is not None]
            return max(vals) if vals else None

        def smin(rows, k):
            vals = [r.get(k) for r in rows if r.get(k) is not None]
            return min(vals) if vals else None

        if cur:
            snap.add("fc_air_temp_now", "Havo harorati (model, hozir)", cur.get("temperature_2m"), "°C", "forecast", fl, cur["time"], res)
            snap.add("fc_humidity_now", "Havo namligi (model)", cur.get("relative_humidity_2m"), "%", "forecast", fl, cur["time"], res)
            snap.add("fc_wind_now", "Shamol tezligi", cur.get("wind_speed_10m"), "m/s", "forecast", fl, cur["time"], res)
            snap.add("fc_wind_dir_now", "Shamol yo'nalishi", cur.get("wind_direction_10m"), "°", "forecast", fl, cur["time"], res)
            snap.add("fc_soil_temp_now", "Tuproq yuzasi harorati (model)", cur.get("soil_temperature_0cm"), "°C", "forecast", fl, cur["time"], res)
            snap.add("fc_solar_now", "Quyosh radiatsiyasi (model)", cur.get("shortwave_radiation"), "W/m²", "forecast", fl, cur["time"], res)
        snap.add("fc_precip_24h", "Yog'in (keyingi 24 soat)", ssum(h24, "precipitation"), "mm", "forecast", fl, issued, res)
        snap.add("fc_precip_48h", "Yog'in (keyingi 48 soat)", ssum(h48, "precipitation"), "mm", "forecast", fl, issued, res)
        snap.add("fc_precip_prob_max_48h", "Yog'in ehtimoli (48 soat, maks.)", smax(h48, "precipitation_probability"), "%", "forecast", fl, issued, res)
        snap.add("fc_snow_48h", "Qor (48 soat)", ssum(h48, "snowfall"), "sm", "forecast", fl, issued, res)
        snap.add("fc_tmin_72h", "Minimal harorat (72 soat)", smin(h72, "temperature_2m"), "°C", "forecast", fl, issued, res)
        snap.add("fc_tmax_72h", "Maksimal harorat (72 soat)", smax(h72, "temperature_2m"), "°C", "forecast", fl, issued, res)
        snap.add("fc_wind_max_48h", "Maksimal shamol (48 soat)", smax(h48, "wind_speed_10m"), "m/s", "forecast", fl, issued, res)
        snap.add("fc_hail_48h", "Do'l ehtimoli (momaqaldiroq kodi 96/99)",
                 any(h.get("weather_code") in open_meteo.HAIL_CODES for h in h48), "", "forecast", fl, issued,
                 res + "; hail data is limited — low confidence")
        next_days = [d for d in daily if d["time"].date() >= today][:4]
        if next_days:
            d0 = next_days[0]
            snap.add("fc_precip_prob_today", "Bugun yog'in ehtimoli", d0.get("precipitation_probability_max"), "%", "forecast", fl, issued, res)
            snap.add("fc_precip_today", "Bugun yog'in", d0.get("precipitation_sum"), "mm", "forecast", fl, issued, res)
            snap.add("fc_snow_today", "Bugun qor", d0.get("snowfall_sum"), "sm", "forecast", fl, issued, res)
            snap.add("fc_et0_today", "ET0 bugun (FAO Penman-Monteith)", d0.get("et0_fao_evapotranspiration"), "mm", "forecast", fl, issued, res)
            snap.add("fc_solar_today", "Quyosh radiatsiyasi (bugun)", d0.get("shortwave_radiation_sum"), "MJ/m²", "forecast", fl, issued, res)
            jumps = []
            for a, b in zip(next_days, next_days[1:]):
                for k in ("temperature_2m_max", "temperature_2m_min"):
                    if a.get(k) is not None and b.get(k) is not None:
                        jumps.append(abs(b[k] - a[k]))
            if jumps:
                snap.add("fc_max_temp_jump_72h", "Keskin harorat o'zgarishi (kunlararo)", max(jumps), "°C", "forecast", fl, issued, res)

    # ---------- NASA POWER (hudud foni)
    power = await weather.load_power_daily(session, gkey, today - timedelta(days=400), today)
    if power:
        pl = nasa_power.SOURCE_LABEL
        res = "~50 km grid cell (regional background)"

        def last_with(key):
            for d in sorted(power, reverse=True):
                if power[d].get(key) is not None:
                    return d, power[d][key]
            return None, None

        for fid, key, label, unit in [
            ("nasa_t2m", "T2M", "Havo harorati (NASA, kunlik)", "°C"),
            ("nasa_solar", "ALLSKY_SFC_SW_DWN", "Quyosh radiatsiyasi (NASA)", "MJ/m²/kun"),
            ("nasa_soil_wetness_top", "GWETTOP", "Yuza tuproq namlik darajasi (MERRA-2, 0–1)", ""),
            ("nasa_soil_wetness_root", "GWETROOT", "Ildiz zonasi namlik darajasi (MERRA-2, 0–1)", ""),
            ("nasa_rh", "RH2M", "Havo namligi (NASA)", "%"),
        ]:
            d, v = last_with(key)
            if d:
                snap.add(fid, label, v, unit, "nasa", pl, d, res)
        last_p, _ = last_with("PRECTOTCORR")
        if last_p:
            p7 = sum(power[d].get("PRECTOTCORR") or 0 for d in power if last_p - timedelta(days=6) <= d <= last_p)
            p30 = sum(power[d].get("PRECTOTCORR") or 0 for d in power if last_p - timedelta(days=29) <= d <= last_p)
            snap.add("nasa_precip_7d", "Yog'in, so'nggi 7 kun (NASA)", p7, "mm", "nasa", pl, last_p, res)
            snap.add("nasa_precip_30d", "Yog'in, so'nggi 30 kun (NASA)", p30, "mm", "nasa", pl, last_p, res)
            base = await weather.monthly_precip_baseline(session, gkey)
            if base:
                b30 = 0.0
                for i in range(30):
                    d = last_p - timedelta(days=i)
                    b30 += base.get(d.month, 0) / calendar.monthrange(d.year, d.month)[1]
                snap.add("nasa_precip_30d_baseline", "Yog'in me'yori, 30 kun (1991–2020)", b30, "mm", "nasa",
                         pl + " · climate baseline", last_p, res)

    # ---------- Fermer ma'lumotlari va ekin holati
    if field_.soil_ph is not None:
        snap.add("soil_ph", "Tuproq pH (laboratoriya)", field_.soil_ph, "", "farmer", "✍️ Farmer input", None, "field")
    if field_.soil_ec_ds_m is not None:
        snap.add("soil_ec", "Sho'rlanish ECe (laboratoriya)", field_.soil_ec_ds_m, "dS/m", "farmer", "✍️ Farmer input", None, "field")

    crop = None
    planting = None
    if field_.crop:
        crop = knowledge.crop(field_.crop)
        snap.crop_key = field_.crop
        planting, assumed = _planting(field_, crop, today)
        if assumed:
            snap.assumptions.append(f"Ekish sanasi kiritilmagan — odatiy sana ({planting.isoformat()}) olindi")
        st = knowledge.stage_on(crop, planting, today)
        snap.stage = st.stage
        snap.add("crop_stage", "Rivojlanish bosqichi", st.stage_uz, "", "model", "🧮 FAO-56 crop stages", today, "field")
        snap.add("days_since_planting", "Ekilgandan beri", st.day, "kun", "farmer", "✍️ Farmer input / estimate", planting, "field")
        stages = crop["stages_days"]
        acc = 0
        for name in ("ini", "dev", "mid", "late"):
            acc += stages[name]
            if st.day < acc:
                order = ["ini", "dev", "mid", "late"]
                nxt = order.index(name) + 1
                if nxt < len(order):
                    snap.add("days_to_next_stage", "Keyingi bosqichgacha", acc - st.day, "kun", "model", "🧮 FAO-56", today, "field")
                    snap.add("next_stage", "Keyingi bosqich", knowledge.STAGE_UZ[order[nxt]], "", "model", "🧮 FAO-56", today, "field")
                break
        if 0 <= st.day <= knowledge.season_length(crop):
            snap.add("days_to_harvest", "Hosil yig'imigacha (taxmin)", knowledge.season_length(crop) - st.day, "kun", "model",
                     "🧮 FAO-56 season length", today, "field")
    else:
        snap.assumptions.append("Dalaga ekin kiritilmagan — suv balansi etalon o't (Kc=1.0) bo'yicha hisoblandi")
    if daily:
        heat_thr = crop["heat_stress_c"] if crop else 35.0
        next3 = [d for d in daily if d["time"].date() >= today][:3]
        hot = sum(1 for d in next3 if (d.get("temperature_2m_max") or -99) >= heat_thr)
        snap.add("fc_hot_days_72h", f"Issiq kunlar (≥{heat_thr:.0f}°C, 3 kun)", hot, "kun", "forecast",
                 open_meteo.SOURCE_LABEL, issued, "model grid (~2–11 km)")

    # ---------- Suv balansi (FAO-56) va GDD
    soil_key, soil, soil_assumed = knowledge.soil(field_.soil_texture)
    if soil_assumed:
        snap.assumptions.append(f"Tuproq turi kiritilmagan — '{soil['name_uz']}' deb taxmin qilindi (FAO-56 19-jadval)")
    sw = SoilWater(soil["theta_fc"], soil["theta_wp"], crop["root_depth_m"] if crop else 0.5, crop["depletion_p"] if crop else 0.5)
    start = today - timedelta(days=30)
    if planting and planting > start:
        start = planting
    om_daily = {d["time"].date(): d for d in daily}
    irrigation = await _irrigation_by_day(session, field_, start, today)
    elevation = field_.elevation_m or 0.0
    days, gdd_total, sources_used = [], 0.0, set()
    d = start
    while d <= today:
        p = power.get(d, {}) if power else {}
        et0, rain, tmin, tmax = None, None, p.get("T2M_MIN"), p.get("T2M_MAX")
        if all(p.get(k) is not None for k in ("T2M_MIN", "T2M_MAX", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN")):
            ea = actual_vapour_pressure_from_rh(p["T2M_MIN"], p["T2M_MAX"], p["RH2M"])
            et0 = et0_penman_monteith(p["T2M_MIN"], p["T2M_MAX"], ea, p["ALLSKY_SFC_SW_DWN"], p["WS2M"],
                                      field_.centroid_lat, d.timetuple().tm_yday, elevation)
            sources_used.add("NASA POWER")
        elif d in om_daily and om_daily[d].get("et0_fao_evapotranspiration") is not None:
            et0 = om_daily[d]["et0_fao_evapotranspiration"]
            sources_used.add("Open-Meteo")
        if p.get("PRECTOTCORR") is not None:
            rain = p["PRECTOTCORR"]
        elif d in om_daily:
            rain = om_daily[d].get("precipitation_sum")
        if tmin is None and d in om_daily:
            tmin, tmax = om_daily[d].get("temperature_2m_min"), om_daily[d].get("temperature_2m_max")
        if et0 is not None:
            kc = knowledge.stage_on(crop, planting, d).kc if crop else 1.0
            days.append({"day": d.isoformat(), "etc": kc * et0, "et0": et0, "rain": rain or 0.0, "irrigation": irrigation.get(d, 0.0)})
        if crop and tmin is not None and tmax is not None and d >= planting:
            gdd_total += gdd_day(tmin, tmax, crop["t_base_c"])
        d += timedelta(days=1)

    if days:
        sensor_sm = snap.facts.get("soil_moisture")
        result = run_balance(days, sw, start_depletion=0.5 * sw.raw_mm)
        depletion = result.depletion
        label = "🧮 FAO-56 water balance (" + " + ".join(sorted(sources_used)) + ")"
        if sensor_sm and sensor_sm["quality"] == "ok":
            depletion = depletion_from_vwc(sensor_sm["value"], sw)
            label = "🧮 FAO-56 water balance (sensor-corrected)"
            snap.assumptions.append("Sensor bitta chuqurlikda o'lchaydi — butun ildiz zonasi namligi bir xil deb olindi")
        else:
            snap.assumptions.append("Balans boshida tanqislik RAW ning 50% i deb olindi (sensor ma'lumoti yo'q)")
        snap.balance_days = [vars(x) for x in result.days]
        ks = 1.0 if depletion <= sw.raw_mm else max(0.0, (sw.taw_mm - depletion) / ((1 - sw.p) * sw.taw_mm))
        snap.add("depletion_mm", "Ildiz zonasi suv tanqisligi", depletion, "mm", "model", label, now, "field (model)")
        snap.add("raw_mm", "Oson o'zlashtiriladigan suv (RAW)", sw.raw_mm, "mm", "model", "🧮 FAO-56 (soil + crop)", now, "field (model)")
        snap.add("taw_mm", "Umumiy mavjud suv (TAW)", sw.taw_mm, "mm", "model", "🧮 FAO-56 (soil + crop)", now, "field (model)")
        snap.add("ks", "Suv stressi koeffitsienti (Ks)", ks, "", "model", label, now, "field (model)")
        snap.add("stress_days_7d", "Suv stressi kunlari (7 kun)", sum(1 for x in result.days[-7:] if x.ks < 1), "kun",
                 "model", label, now, "field (model)")
        last7 = days[-7:]
        snap.add("et0_7d_mean", "ET0 o'rtacha (7 kun)", statistics.fmean(x["et0"] for x in last7), "mm/kun", "model",
                 label, now, "field (model)")
        snap.add("etc_today", "Ekin suv sarfi ETc (bugun)", days[-1]["etc"], "mm", "model", label, now, "field (model)")
    if crop:
        snap.add("gdd", "Faol harorat yig'indisi (GDD)", gdd_total, "°C·kun", "model", "🧮 NASA POWER + Open-Meteo", now, "field (model)")
    return snap


async def _irrigation_by_day(session: AsyncSession, field_: Field, start: date, end: date) -> dict[date, float]:
    res = await session.execute(
        select(FieldEvent).where(FieldEvent.field_id == field_.id, FieldEvent.type == "irrigation",
                                 FieldEvent.date >= start, FieldEvent.date <= end)
    )
    out: dict[date, float] = {}
    for ev in res.scalars():
        mm = ev.amount or 0.0
        unit = (ev.unit or "mm").lower()
        if unit in ("m3", "m³"):
            mm = (ev.amount or 0) / max(field_.area_ha, 0.01) / 10
        elif unit in ("m3/ha", "m³/ga", "m3/ga"):
            mm = (ev.amount or 0) / 10
        out[ev.date] = out.get(ev.date, 0.0) + mm
    return out


async def previous_crops(session: AsyncSession, field_: Field) -> list[str]:
    res = await session.execute(
        select(CropSeason.crop).where(CropSeason.field_id == field_.id)
        .order_by(func.coalesce(CropSeason.planting_date, CropSeason.harvest_date).desc().nullslast(), CropSeason.id.desc())
    )
    crops = [c for c in res.scalars()]
    if field_.crop and (not crops or crops[0] != field_.crop):
        crops.insert(0, field_.crop)
    return crops
