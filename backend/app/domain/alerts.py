"""Decision Support qoidalari. Kirish — Field Snapshot faktlari, chiqish — ogohlantirish nomzodlari.

Har bir qoida o'zi ishlatgan faktlar ro'yxatini (evidence) qaytaradi — tavsiyadagi "dalillar" shu yerdan.
"""
from dataclasses import dataclass, field

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}

RAIN_SIGNIFICANT_48H_MM = 5.0
RAIN_DELAY_48H_MM = 10.0
RAIN_DELAY_PROB = 60
HEAVY_RAIN_24H_MM = 20.0
VERY_HEAVY_RAIN_24H_MM = 40.0
EXTREME_HEAT_C = 40.0
SHARP_CHANGE_C = 10.0


@dataclass
class AlertCandidate:
    type: str
    category: str
    severity: str
    evidence: list[str]  # fact_id'lar
    params: dict = field(default_factory=dict)


def _f(facts: dict, key: str):
    fact = facts.get(key)
    return None if fact is None else fact.get("value")


def evaluate(facts: dict, crop: dict | None, stage: str | None) -> list[AlertCandidate]:
    out: list[AlertCandidate] = []
    depletion = _f(facts, "depletion_mm")
    raw = _f(facts, "raw_mm")
    taw = _f(facts, "taw_mm")
    rain48 = _f(facts, "fc_precip_48h")
    prob48 = _f(facts, "fc_precip_prob_max_48h")
    sm = _f(facts, "soil_moisture")

    # --- Sug'orish va tuproq namligi
    if depletion is not None and raw is not None and taw is not None:
        rain_coming = rain48 is not None and rain48 >= RAIN_DELAY_48H_MM and (prob48 or 0) >= RAIN_DELAY_PROB
        ev = ["depletion_mm", "raw_mm", "taw_mm"] + (["soil_moisture"] if sm is not None else []) + (
            ["fc_precip_48h", "fc_precip_prob_max_48h"] if rain48 is not None else [])
        if depletion >= 0.8 * taw:
            out.append(AlertCandidate("soil_moisture_critical", "irrigation", "critical", ev,
                                      {"amount_mm": round(depletion, 1), "rain_coming": rain_coming}))
        elif depletion >= raw:
            if rain_coming:
                out.append(AlertCandidate("irrigation_delay", "irrigation", "info", ev,
                                          {"amount_mm": round(depletion, 1)}))
            elif rain48 is None or rain48 < RAIN_SIGNIFICANT_48H_MM:
                out.append(AlertCandidate("irrigation_needed", "irrigation", "warning", ev,
                                          {"amount_mm": round(depletion, 1)}))

    # --- Kuchli yomg'ir / do'l / qor
    rain24 = _f(facts, "fc_precip_24h")
    if rain24 is not None and rain24 >= HEAVY_RAIN_24H_MM:
        sev = "critical" if rain24 >= VERY_HEAVY_RAIN_24H_MM else "warning"
        ev = ["fc_precip_24h"] + (["soil_moisture"] if sm is not None else [])
        out.append(AlertCandidate("heavy_rain", "weather", sev, ev, {"rain_mm": rain24}))
    if _f(facts, "fc_hail_48h"):
        out.append(AlertCandidate("hail_risk", "weather", "warning", ["fc_hail_48h"]))

    # --- Sovuq urishi
    tmin72 = _f(facts, "fc_tmin_72h")
    if tmin72 is not None:
        threshold = crop["frost_kill_c"] if crop else 0.0
        sensitive = bool(crop) and stage in crop.get("frost_sensitive_stages", [])
        if crop:
            # mavsumdan tashqari (ekin yo'q) dalada sovuq ekinga xavf solmaydi
            if stage not in ("off", None) and (tmin72 <= threshold or (sensitive and tmin72 <= 0.0)):
                sev = "critical" if sensitive else "warning"
                out.append(AlertCandidate("frost_risk", "weather", sev, ["fc_tmin_72h", "crop_stage"],
                                          {"tmin": tmin72, "threshold": threshold}))
        elif tmin72 <= 0.0:
            out.append(AlertCandidate("frost_risk", "weather", "info", ["fc_tmin_72h"],
                                      {"tmin": tmin72, "threshold": 0.0}))

    # --- Issiq urishi
    tmax72 = _f(facts, "fc_tmax_72h")
    hot_days = _f(facts, "fc_hot_days_72h")
    air = _f(facts, "air_temp")
    heat_thr = crop["heat_stress_c"] if crop else 35.0
    if air is not None and air >= EXTREME_HEAT_C:
        out.append(AlertCandidate("extreme_heat", "weather", "critical", ["air_temp"], {"t": air}))
    elif tmax72 is not None and tmax72 >= heat_thr and (not crop or stage not in ("off", None)):
        sev = "critical" if (hot_days or 0) >= 3 else "warning"
        out.append(AlertCandidate("heat_stress", "weather", sev, ["fc_tmax_72h", "fc_hot_days_72h"],
                                  {"tmax": tmax72, "threshold": heat_thr}))

    # --- Keskin harorat o'zgarishi
    jump = _f(facts, "fc_max_temp_jump_72h")
    if jump is not None and jump >= SHARP_CHANGE_C:
        out.append(AlertCandidate("sharp_temp_change", "weather", "warning", ["fc_max_temp_jump_72h"], {"jump": jump}))

    # --- Qurg'oqchilik xavfi: yog'in bazadan ancha kam + bug'lanish + namlik pasaymoqda
    p30 = _f(facts, "nasa_precip_30d")
    p30_base = _f(facts, "nasa_precip_30d_baseline")
    trend = _f(facts, "soil_moisture_trend_24h")
    if p30 is not None and p30_base and p30_base >= 10 and p30 <= 0.3 * p30_base:
        if (trend is not None and trend < 0) or (depletion is not None and raw and depletion >= 0.7 * raw):
            ev = ["nasa_precip_30d", "nasa_precip_30d_baseline"] + (["soil_moisture_trend_24h"] if trend is not None else ["depletion_mm"])
            out.append(AlertCandidate("drought_risk", "weather", "warning", ev, {}))

    # --- Sensor holati
    if _f(facts, "devices_offline"):
        out.append(AlertCandidate("sensor_offline", "sensor", "warning", ["devices_offline"]))
    if (_f(facts, "sensor_bad_last_hour") or 0) >= 3:
        out.append(AlertCandidate("sensor_fault", "sensor", "warning", ["sensor_bad_last_hour"]))

    # --- Ekin holati yomonlashmoqda (suv stressi davom etmoqda)
    ks = _f(facts, "ks")
    stress_days = _f(facts, "stress_days_7d")
    if ks is not None and ks < 0.7 and (stress_days or 0) >= 3:
        out.append(AlertCandidate("crop_condition_worse", "crop", "warning", ["ks", "stress_days_7d", "crop_stage"], {}))

    # --- Agrotexnik ishlar vaqti
    to_next = _f(facts, "days_to_next_stage")
    next_stage = _f(facts, "next_stage")
    if crop and to_next is not None and 0 <= to_next <= 3 and next_stage:
        out.append(AlertCandidate("agro_stage_change", "crop", "info", ["crop_stage", "days_to_next_stage"],
                                  {"next_stage": next_stage}))
    to_harvest = _f(facts, "days_to_harvest")
    if crop and to_harvest is not None and 0 <= to_harvest <= 7:
        out.append(AlertCandidate("harvest_soon", "crop", "info", ["days_to_harvest"], {}))

    # --- Tuproq: pH va sho'rlanish (laboratoriya yoki sensor)
    ph = _f(facts, "soil_ph")
    if crop and ph is not None:
        lo, hi = crop["ph_range"]
        if not (lo - 0.3 <= ph <= hi + 0.3):
            out.append(AlertCandidate("soil_ph_unsuitable", "soil", "warning", ["soil_ph"], {"lo": lo, "hi": hi}))
    ece = _f(facts, "soil_ec")
    if crop and ece is not None and ece > crop["ece_threshold_ds_m"]:
        out.append(AlertCandidate("soil_salinity_high", "soil", "warning", ["soil_ec"],
                                  {"threshold": crop["ece_threshold_ds_m"]}))
    return out
