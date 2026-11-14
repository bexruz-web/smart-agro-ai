"""Almashlab ekish skoringi (ROT-2…4): shaffof qoidalar + FAO-33 hosil oralig'i + suv unumdorligi."""
from dataclasses import dataclass, field

from app.domain import knowledge
from app.domain.yield_model import Scenario, YieldEstimate, estimate_yield

CEREALS = {"Poaceae"}
LEGUMES = {"Fabaceae"}


@dataclass
class Candidate:
    crop: str
    crop_name_uz: str
    score: float
    score_breakdown: list[dict] = field(default_factory=list)
    yield_estimate: YieldEstimate | None = None
    water_need_m3_ha: float | None = None
    water_productivity_kg_m3: float | None = None
    confidence: str = "low"
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    rationale_uz: str = ""
    excluded: bool = False
    exclusion_reason: str | None = None


def _add(c: Candidate, points: float, factor: str, reason: str) -> None:
    c.score += points
    c.score_breakdown.append({"factor_uz": factor, "points": points, "reason_uz": reason})


def plan_rotation(
    previous_crops: list[str],
    scenarios_by_crop: dict[str, list[Scenario]],
    water_available_m3_ha: float | None,
    soil_ph: float | None,
    soil_ece: float | None,
    farmer_history: dict[str, dict],
) -> list[Candidate]:
    """previous_crops — eng yangisidan eskisiga. farmer_history[crop] = {"pairs": [(real, prognoz)], "yields": [..]}"""
    rules = knowledge.rotation_rules()
    last = previous_crops[0] if previous_crops else None
    last_family = knowledge.crop(last)["family"] if last else None
    out: list[Candidate] = []

    for key in knowledge.crop_keys():
        c = knowledge.crop(key)
        cand = Candidate(crop=key, crop_name_uz=c["name_uz"], score=50.0)
        cand.score_breakdown.append({"factor_uz": "Boshlang'ich ball", "points": 50, "reason_uz": "Har bir ekin 50 balldan boshlaydi"})

        # --- qat'iy cheklovlar
        consecutive = 0
        for prev in previous_crops:
            if prev == key:
                consecutive += 1
            else:
                break
        if consecutive >= rules["same_crop_max_consecutive"]:
            cand.excluded = True
            cand.exclusion_reason = f"{c['name_uz']} ketma-ket {consecutive} mavsum ekilgan — kasallik va tuproq charchashi xavfi"
        if soil_ece is not None and soil_ece > c["ece_threshold_ds_m"] * rules["salinity_exclusion_factor"]:
            cand.excluded = True
            cand.exclusion_reason = (
                f"Tuproq sho'rlanishi (ECe {soil_ece} dS/m) ekin chegarasidan ({c['ece_threshold_ds_m']} dS/m, FAO-29) ancha yuqori"
            )

        # --- ballar
        if last == key:
            _add(cand, rules["same_crop_penalty"], "Bir xil ekin takrori", "Oldingi mavsumda ham shu ekin ekilgan")
        elif last_family and last_family == c["family"]:
            _add(cand, rules["same_family_penalty"], "Bir oiladagi ekin", f"Oldingi ekin ham {c['family_uz']} oilasidan — umumiy kasallik/zararkunandalar")
        if last_family in CEREALS and c["family"] in LEGUMES:
            _add(cand, rules["legume_after_cereal_bonus"], "Dukkakli — azot to'playdi", "Boshoqdoshlardan keyin dukkakli ekin tuproqqa azot qaytaradi")
        if last_family in LEGUMES and c["family"] not in LEGUMES:
            _add(cand, rules["after_legume_bonus"], "Dukkaklidan keyin", "Oldingi dukkakli ekin qoldirgan azotdan foydalanadi")
        if last == "alfalfa" and key == "cotton":
            _add(cand, rules["cotton_after_alfalfa_bonus"], "Beda → g'o'za", "O'zbekistonda an'anaviy g'o'za–beda almashlab ekishi (tuproq strukturasi)")
        if soil_ph is not None:
            lo, hi = c["ph_range"]
            if not (lo <= soil_ph <= hi):
                _add(cand, rules["ph_outside_penalty"], "pH mos emas", f"Tuproq pH {soil_ph}, ekin uchun {lo}–{hi} (tekshirilmagan umumiy oraliq)")
                cand.risks.append("Tuproq pH ekin uchun qulay oraliqdan tashqarida")
        else:
            cand.assumptions.append("Tuproq pH noma'lum — pH mosligi baholanmadi")

        # --- hosil va suv
        hist = farmer_history.get(key, {})
        est = estimate_yield(
            c,
            scenarios_by_crop.get(key, []),
            water_available_m3_ha,
            soil_ece,
            hist.get("pairs", []),
            hist.get("yields", []),
        )
        cand.yield_estimate = est
        cand.assumptions.extend(est.assumptions)
        cand.confidence = est.confidence
        ym_mid = c["potential_yield_t_ha"][1]
        rel = est.likely_t_ha / ym_mid if ym_mid else 0
        _add(cand, round(20 * min(rel, 1.0), 1), "Kutilayotgan hosil", f"Ehtimoliy hosil potensialning {rel * 100:.0f}% i")

        if est.water_need_mm is not None:
            cand.water_need_m3_ha = round(est.water_need_mm * 10, -1)
        else:
            lo_mm, hi_mm = c["water_need_mm"]
            cand.water_need_m3_ha = round((lo_mm + hi_mm) / 2 * 10, -1)
            cand.assumptions.append("Suv talabi FAO o'rtacha qiymatidan olingan (mahalliy iqlim ssenariysi yo'q)")
        total_water_m3 = (est.etc_normal_mm or sum(c["water_need_mm"]) / 2) * 10
        if total_water_m3:
            cand.water_productivity_kg_m3 = round(est.likely_t_ha * 1000 / total_water_m3, 2)

        if water_available_m3_ha is not None and cand.water_need_m3_ha:
            fit = min(1.0, water_available_m3_ha / cand.water_need_m3_ha) if cand.water_need_m3_ha > 0 else 1.0
            _add(cand, round(15 * fit, 1), "Suvga moslik", f"Mavjud suv talabning {fit * 100:.0f}% ini qoplaydi")
            if fit < 0.6:
                cand.risks.append("Suv yetishmasligi — hosil sezilarli kamayishi mumkin")
        else:
            _add(cand, 7.5, "Suvga moslik", "Suv limiti noma'lum — neytral ball")

        if c.get("proxy_note"):
            cand.assumptions.append(c["proxy_note"])
        if c["ky"] > 1.0:
            cand.risks.append(f"Suv tanqisligiga sezgir (Ky={c['ky']}, FAO-33)")
        cand.rationale_uz = _rationale(cand, c)
        cand.score = round(cand.score, 1)
        out.append(cand)

    out.sort(key=lambda x: (x.excluded, -x.score))
    return out


def _rationale(cand: Candidate, c: dict) -> str:
    plus = [b["factor_uz"] for b in cand.score_breakdown if b["points"] > 0 and b["factor_uz"] != "Boshlang'ich ball"]
    minus = [b["factor_uz"] for b in cand.score_breakdown if b["points"] < 0]
    text = f"{c['name_uz']}: "
    if plus:
        text += "afzalliklari — " + ", ".join(plus).lower() + ". "
    if minus:
        text += "kamchiliklari — " + ", ".join(minus).lower() + ". "
    return text.strip()
