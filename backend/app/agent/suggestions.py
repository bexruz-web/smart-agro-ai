"""AI Agronom uchun dinamik savollar: dala holati va shu dalaning oldingi suhbatiga qarab (3–4 ta)."""
from app.core.i18n import QUESTIONS, pick
from app.db.models import Field
from app.domain import knowledge


def build(field: Field, facts: dict, last_user_message: str | None, lang: str) -> list[str]:
    status = field.status or {}
    crop_name = ""
    if field.crop:
        c = knowledge.crop(field.crop)
        crop_name = c.get(f"name_{lang}") or c["name_uz"]
    v = lambda k: (facts.get(k) or {}).get("value")  # noqa: E731
    keys: list[str] = []
    m_class = status.get("moisture_class")
    if m_class == "wet":
        keys.append("too_wet")
    elif (v("fc_precip_48h") or 0) >= 5 and (v("fc_precip_prob_max_48h") or 0) >= 50:
        keys.append("rain_vs_irrigation")
    else:
        keys.append("irrigate_today")
    if (v("fc_tmax_72h") or 0) >= 35:
        keys.append("heat")
    if v("fc_tmin_72h") is not None and v("fc_tmin_72h") <= 0 and field.crop:
        keys.append("frost")
    if (field.soil_ec_ds_m or 0) > 0 and field.crop and field.soil_ec_ds_m > knowledge.crop(field.crop)["ece_threshold_ds_m"]:
        keys.append("salinity")
    if (v("devices_offline") or 0) > 0 or (v("sensor_bad_last_hour") or 0) >= 3:
        keys.append("sensor")
    stage = facts.get("crop_stage", {}).get("value")
    days_to_harvest = v("days_to_harvest")
    if field.crop and (days_to_harvest is not None and days_to_harvest <= 14 or stage in (None,) and v("days_since_planting") is None):
        keys.append("next_crop")
    if field.crop:
        keys.append("fertilize")
    keys.append("pests")
    if last_user_message:
        keys.insert(1, "continue")
    if "salinity" not in keys and field.crop:
        keys.append("next_crop")
    seen, out = set(), []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        name = crop_name or {"uz": "ekin", "ru": "культура", "en": "crop"}.get(lang, "crop")
        if lang == "en":
            name = name[:1].lower() + name[1:]  # "my winter wheat", "after maize (grain)"
        out.append(pick(QUESTIONS[k], lang).format(crop=name))
    return out[:4]
