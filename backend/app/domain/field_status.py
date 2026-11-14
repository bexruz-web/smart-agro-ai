"""Dala kartochkasi holati: namlik holati (4 sinf) va qurish xavfi (3 daraja).

Namlik holati — ildiz zonasidagi mavjud suv ulushi (1 − tanqislik/TAW) bo'yicha:
  juda quruq < 40% · quruq 40–60% · me'yorida 60–100% · ortiqcha nam — sensor hajmiy namligi dala sig'imidan yuqori.
Chegaralar boshlang'ich qiymat, keyin sozlanadi.

Qurish xavfi:
  yuqori   — "juda quruq", yoki "quruq" + 48 soatda yomg'ir ehtimoli < 30% + harorat ≥ 35 °C
  o'rtacha — "quruq", yoki "me'yorida" + harorat ≥ 35 °C + yomg'ir kutilmayapti
  mo'tadil — qolgan holatlar
"""

HOT_C = 35.0
RAIN_PROB_LOW = 30


def moisture_class(depletion_mm: float | None, taw_mm: float | None, sensor_vwc: float | None,
                   theta_fc: float | None) -> str | None:
    if sensor_vwc is not None and theta_fc is not None and sensor_vwc / 100 > theta_fc:
        return "wet"
    if depletion_mm is None or not taw_mm:
        return None
    available = 1 - depletion_mm / taw_mm
    if available < 0.4:
        return "very_dry"
    if available < 0.6:
        return "dry"
    return "normal"


def drying_risk(m_class: str | None, rain_prob_48h: float | None, tmax_72h: float | None) -> str | None:
    if m_class is None:
        return None
    hot = tmax_72h is not None and tmax_72h >= HOT_C
    no_rain = rain_prob_48h is None or rain_prob_48h < RAIN_PROB_LOW
    if m_class == "very_dry" or (m_class == "dry" and no_rain and hot):
        return "high"
    if m_class == "dry" or (m_class == "normal" and hot and no_rain):
        return "medium"
    return "low"
