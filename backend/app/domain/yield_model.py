"""Hosildorlik prognozi: FAO-33 suvga javob modeli + FAO-29 sho'rlanish + fermer tarixi bo'yicha kalibrlash.

1 − Ya/Ym = Ky·(1 − ETa/ETc)        (FAO-33)
Ya/Ym (sho'rlanish) = 1 − b·(ECe − ECe_threshold)/100   (FAO-29, Maas-Hoffman)
"""
import math
import statistics
from dataclasses import dataclass, field


def water_yield_ratio(eta_over_etc: float, ky: float) -> float:
    return max(0.0, min(1.0, 1 - ky * (1 - max(0.0, min(1.0, eta_over_etc)))))


def salinity_yield_ratio(ece: float | None, threshold: float, slope_pct: float) -> float:
    if ece is None or ece <= threshold:
        return 1.0
    return max(0.0, 1 - slope_pct * (ece - threshold) / 100)


def hargreaves_et0(t_min: float, t_max: float, ra: float) -> float:
    """FAO-56 52-tenglama — faqat harorat ma'lum bo'lganda (iqlim ssenariylari uchun)."""
    t_mean = (t_min + t_max) / 2
    return max(0.0, 0.0023 * (t_mean + 17.8) * math.sqrt(max(t_max - t_min, 0)) * 0.408 * ra)


def calibration_factor(pairs: list[tuple[float, float]]) -> tuple[float, int]:
    """pairs: (real, prognoz). k = median(real/prognoz), kam mavsumda 1 ga tortiladi (shrinkage)."""
    ratios = [r / p for r, p in pairs if p and p > 0 and r is not None]
    if not ratios:
        return 1.0, 0
    n = len(ratios)
    k_raw = statistics.median(ratios)
    weight = n / (n + 2)  # 1 mavsum → 33%, 3 mavsum → 60%, 8 mavsum → 80%
    return 1 + weight * (k_raw - 1), n


@dataclass
class Scenario:
    name: str  # dry | normal | wet
    etc_mm: float
    peff_mm: float


@dataclass
class YieldEstimate:
    min_t_ha: float
    likely_t_ha: float
    max_t_ha: float
    confidence: str
    assumptions: list[str] = field(default_factory=list)
    water_need_mm: float | None = None  # o'rtacha yildagi sug'orish ehtiyoji
    etc_normal_mm: float | None = None
    method_uz: str = (
        "FAO-33 suvga javob modeli (Ky) + FAO-29 sho'rlanish tuzatmasi; "
        "iqlim ssenariylari NASA POWER tarixidan (quruq/o'rtacha/nam yillar)"
    )


def estimate_yield(
    crop: dict,
    scenarios: list[Scenario],
    water_available_m3_ha: float | None,
    ece: float | None,
    farmer_pairs: list[tuple[float, float]],
    farmer_yields: list[float],
) -> YieldEstimate:
    assumptions: list[str] = []
    ym_min, ym_mid, ym_max = crop["potential_yield_t_ha"]
    if farmer_yields:
        best = max(farmer_yields)
        # fermerning eng yaxshi natijasi potensialning pastki chegarasi sifatida
        ym_mid = max(ym_mid, best)
        ym_max = max(ym_max, best * 1.1)
        ym_min = min(ym_min, min(farmer_yields))
    else:
        assumptions.append(
            f"Potensial hosil ({ym_min}–{ym_max} t/ga) mintaqaviy taxmindan olingan — fermer tarixi yo'q"
        )

    if water_available_m3_ha is None:
        assumptions.append("Sug'orish suvi ekin talabini to'liq qoplaydi deb taxmin qilindi (suv limiti kiritilmagan)")
    if ece is None:
        assumptions.append("Tuproq sho'rlanishi (EC) noma'lum — sho'rlanish ta'siri hisobga olinmadi")

    by_name = {s.name: s for s in scenarios}

    def ratio(s: Scenario) -> float:
        need = max(s.etc_mm, 1.0)
        if water_available_m3_ha is None:
            return 1.0
        return min(1.0, (s.peff_mm + water_available_m3_ha / 10) / need)

    sal = salinity_yield_ratio(ece, crop["ece_threshold_ds_m"], crop["ece_slope_pct_per_ds_m"])
    k, n_seasons = calibration_factor(farmer_pairs)
    if n_seasons:
        assumptions.append(f"Fermerning {n_seasons} ta mavsumi bo'yicha kalibrlash koeffitsienti: {k:.2f}")

    def ya(ym: float, s: Scenario | None) -> float:
        r = water_yield_ratio(ratio(s), crop["ky"]) if s else 1.0
        return round(ym * r * sal * k, 2)

    dry, normal, wet = by_name.get("dry"), by_name.get("normal"), by_name.get("wet")
    if not scenarios:
        assumptions.append("Iqlim ssenariylari hali hisoblanmagan — suv stressi hisobga olinmadi")
    values = sorted([ya(ym_min, dry), ya(ym_mid, normal), ya(ym_max, wet)])

    if n_seasons >= 3 and water_available_m3_ha is not None:
        confidence = "high"
    elif n_seasons >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    need = None
    if normal:
        need = round(max(0.0, normal.etc_mm - normal.peff_mm), 0)
    return YieldEstimate(
        min_t_ha=values[0],
        likely_t_ha=values[1],
        max_t_ha=values[2],
        confidence=confidence,
        assumptions=assumptions,
        water_need_mm=need,
        etc_normal_mm=round(normal.etc_mm, 0) if normal else None,
    )
