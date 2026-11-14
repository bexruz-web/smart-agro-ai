"""Deterministik 7 qismli tavsiyalar (DSS-2). LLM ishlamasa ham tizim shu matnlar bilan ishlaydi.

Matndagi har bir raqam faktlardan olinadi — o'ylab topilgan raqam yo'q.
"""
from app.domain.alerts import AlertCandidate
from app.domain.water_balance import irrigation_mm_to_m3_ha

TITLE_UZ = {
    "soil_moisture_critical": "Tuproq namligi kritik darajada",
    "irrigation_needed": "Sug'orish vaqti keldi",
    "irrigation_delay": "Sug'orishni kechiktirish mumkin",
    "heavy_rain": "Kuchli yog'ingarchilik kutilmoqda",
    "hail_risk": "Do'l xavfi",
    "frost_risk": "Sovuq urishi xavfi",
    "heat_stress": "Issiq urishi xavfi",
    "extreme_heat": "Haddan tashqari issiq",
    "sharp_temp_change": "Keskin harorat o'zgarishi",
    "drought_risk": "Qurg'oqchilik xavfi",
    "sensor_offline": "Sensor bilan aloqa yo'q",
    "sensor_fault": "Sensor shubhali qiymatlar bermoqda",
    "crop_condition_worse": "Ekin holati yomonlashmoqda",
    "agro_stage_change": "Rivojlanish bosqichi o'zgarmoqda",
    "harvest_soon": "Hosil yig'imi yaqinlashmoqda",
    "soil_ph_unsuitable": "Tuproq pH ekin uchun mos emas",
    "soil_salinity_high": "Tuproq sho'rlanishi yuqori",
}


def fmt(facts: dict, fid: str, digits: int = 1) -> str:
    f = facts.get(fid)
    if not f or f["value"] is None:
        return "ma'lumot yo'q"
    v = f["value"]
    if isinstance(v, bool):
        return "ha" if v else "yo'q"
    if isinstance(v, float):
        v = f"{v:.{digits}f}"
    unit = f" {f['unit']}" if f["unit"] else ""
    return f"{v}{unit}"


def evidence_list(facts: dict, ids: list[str]) -> list[dict]:
    out = []
    for fid in ids:
        f = facts.get(fid)
        if f:
            out.append({k: f[k] for k in ("fact_id", "label_uz", "value", "unit", "source_label", "observed_at")})
    return out


def _confidence(facts: dict, ids: list[str]) -> tuple[str, str]:
    sources = {facts[i]["source"] for i in ids if i in facts}
    suspect = any(facts[i].get("quality") == "suspect" for i in ids if i in facts)
    if "sensor" in sources and not suspect:
        return "high", "Dala sensori o'lchovi va model hisobi bir-birini tasdiqlaydi"
    if "forecast" in sources and "sensor" not in sources and "model" not in sources:
        return "medium", "Ob-havo prognoziga asoslangan — prognozlar xato qilishi mumkin"
    if "sensor" in sources and suspect:
        return "low", "Sensor qiymatlari shubhali deb belgilangan"
    return "medium", "Dala sensori yo'q — NASA POWER/Open-Meteo va FAO-56 modeli asosida"


def build(alert: AlertCandidate, facts: dict, assumptions: list[str], crop_name: str | None) -> dict:
    t = alert.type
    p = alert.params
    crop = crop_name or "ekin"
    rec = {"problem": "", "cause": "", "action": "", "timing": "", "expected_outcome": "", "risks": ""}
    amount_mm = None

    if t in ("soil_moisture_critical", "irrigation_needed", "irrigation_delay"):
        amount_mm = p.get("amount_mm")
        m3 = irrigation_mm_to_m3_ha(amount_mm) if amount_mm else None
        sm = f"sensor bo'yicha tuproq namligi {fmt(facts, 'soil_moisture')}, " if "soil_moisture" in facts else ""
        rec["cause"] = (
            f"{sm}ildiz zonasi suv tanqisligi {fmt(facts, 'depletion_mm')}; oson o'zlashtiriladigan suv chegarasi (RAW) "
            f"{fmt(facts, 'raw_mm')}, umumiy mavjud suv (TAW) {fmt(facts, 'taw_mm')}. "
            f"Keyingi 48 soatda kutilayotgan yog'in: {fmt(facts, 'fc_precip_48h')} (ehtimol {fmt(facts, 'fc_precip_prob_max_48h', 0)})."
        )
        if t == "irrigation_delay":
            rec["problem"] = f"Tuproq namligi pasaygan, lekin yaqin kunlarda yomg'ir kutilmoqda"
            rec["action"] = "Sug'orishni vaqtincha kechiktiring va yomg'irdan keyin namlikni qayta tekshiring."
            rec["timing"] = "Keyingi 48 soat; yomg'ir yog'masa — darhol sug'orishni rejalashtiring"
            rec["expected_outcome"] = "Suv tejaladi, yomg'ir tanqislikning bir qismini qoplaydi"
            rec["risks"] = "Prognoz xato bo'lsa, ekin suv stressiga uchrashi mumkin; sensorni kuzatib boring"
        else:
            rec["problem"] = ("Tuproq namligi kritik darajaga tushgan" if t == "soil_moisture_critical"
                              else f"{crop} uchun sug'orish vaqti keldi")
            rec["action"] = (f"Sug'orishni rejalashtiring: taxminan {amount_mm:.0f} mm (≈ {m3:.0f} m³/ga) suv bering."
                             if amount_mm else "Sug'orishni rejalashtiring.")
            rec["timing"] = ("Darhol, keyingi 12 soat ichida" if t == "soil_moisture_critical" else "Keyingi 24 soat ichida") + \
                ", iloji boricha ertalab yoki kechqurun (bug'lanish kam)"
            rec["expected_outcome"] = "Ildiz zonasi namligi tiklanadi, suv stressi va hosil yo'qotilishining oldi olinadi"
            rec["risks"] = ("Miqdor tuproq turi va sensor chuqurligiga bog'liq taxmin; sug'orishdan keyin namlikni tekshiring. "
                            "Ortiqcha sug'orish suv isrofi va sho'rlanishga olib kelishi mumkin.")
    elif t == "heavy_rain":
        rec["problem"] = "Kuchli yog'ingarchilik kutilmoqda"
        rec["cause"] = f"Keyingi 24 soatda prognoz: {fmt(facts, 'fc_precip_24h')}" + (
            f"; hozirgi tuproq namligi {fmt(facts, 'soil_moisture')}" if "soil_moisture" in facts else "")
        rec["action"] = "Sug'orishni to'xtating, ariq va zovurlarni tozalang, suv to'planadigan joylarni tekshiring."
        rec["timing"] = "Yog'ingarchilikdan oldin, bugun"
        rec["expected_outcome"] = "Suv to'planishi va ildiz chirishi xavfi kamayadi, suv tejaladi"
        rec["risks"] = "Prognoz miqdori o'zgarishi mumkin; past joylarda suv to'planishi ehtimoli bor"
    elif t == "hail_risk":
        rec["problem"] = "Momaqaldiroq va do'l ehtimoli"
        rec["cause"] = "Prognozda momaqaldiroq bilan do'l kodi (WMO 96/99) bor"
        rec["action"] = "Texnikani yopiq joyga oling, ko'chat va yosh ekinlarni iloji bo'lsa himoyalang."
        rec["timing"] = "Keyingi 48 soat"
        rec["expected_outcome"] = "Mexanik shikastlanish xavfi kamayadi"
        rec["risks"] = "Do'l prognozi ishonchliligi past — bu faqat ehtiyot chorasi"
    elif t == "frost_risk":
        rec["problem"] = f"Sovuq urishi xavfi ({crop})"
        rec["cause"] = f"72 soat ichida minimal harorat {fmt(facts, 'fc_tmin_72h')}; ekin bosqichi: {fmt(facts, 'crop_stage')}"
        rec["action"] = "Kechqurun yengil sug'orish, tutun/qoplama bilan himoya, sovuqqa sezgir ishlarni (o'g'itlash, kimyoviy ishlov) kechiktiring."
        rec["timing"] = "Sovuq kutilgan kechadan oldin"
        rec["expected_outcome"] = "Sovuqdan zararlanish kamayadi"
        rec["risks"] = "Prognoz haroratidan dala harorati 1–3°C farq qilishi mumkin (pastqam joylar sovuqroq)"
    elif t in ("heat_stress", "extreme_heat"):
        rec["problem"] = "Haddan tashqari issiq" if t == "extreme_heat" else f"Issiq urishi xavfi ({crop})"
        rec["cause"] = (f"Sensor: havo harorati {fmt(facts, 'air_temp')}" if t == "extreme_heat"
                        else f"72 soat ichida maksimal harorat {fmt(facts, 'fc_tmax_72h')}, issiq kunlar soni {fmt(facts, 'fc_hot_days_72h', 0)}")
        rec["action"] = "Sug'orishni salqin vaqtga (erta tong) suring, tuproq namligini me'yorda saqlang, kunduzi ishlov bermang."
        rec["timing"] = "Issiq kunlardan oldin va davomida"
        rec["expected_outcome"] = "Gullash/hosil tugish davrida issiqdan zararlanish kamayadi"
        rec["risks"] = "Suv yetishmasa issiq stressi kuchayadi"
    elif t == "sharp_temp_change":
        rec["problem"] = "Keskin harorat o'zgarishi kutilmoqda"
        rec["cause"] = f"Kunlararo harorat farqi {fmt(facts, 'fc_max_temp_jump_72h')} gacha"
        rec["action"] = "Sezgir ishlarni (ekish, kimyoviy ishlov) harorat barqarorlashguncha kechiktiring."
        rec["timing"] = "Keyingi 72 soat"
        rec["expected_outcome"] = "Stressdan va ishlov samarasizligidan saqlanish"
        rec["risks"] = "Prognoz noaniqligi"
    elif t == "drought_risk":
        rec["problem"] = "Qurg'oqchilik xavfi oshmoqda"
        rec["cause"] = (f"So'nggi 30 kunda yog'in {fmt(facts, 'nasa_precip_30d')}, iqlim me'yori "
                        f"{fmt(facts, 'nasa_precip_30d_baseline')} (NASA POWER, hudud foni)")
        rec["action"] = "Suv rejasini qayta ko'ring: sug'orish navbatini oldindan kelishing, mulchalash va kechki sug'orishdan foydalaning."
        rec["timing"] = "Shu hafta"
        rec["expected_outcome"] = "Suv tanqisligiga tayyorgarlik, hosil yo'qotilishi kamayadi"
        rec["risks"] = "NASA POWER ~50 km hududni ifodalaydi — dalangiz holati farq qilishi mumkin"
    elif t == "sensor_offline":
        rec["problem"] = "Sensor bilan aloqa uzilgan"
        rec["cause"] = f"Aloqasiz qurilmalar soni: {fmt(facts, 'devices_offline', 0)}"
        rec["action"] = "Qurilma ta'minoti (batareya/quyosh paneli), Wi-Fi yoki SIM aloqasini tekshiring."
        rec["timing"] = "Bugun"
        rec["expected_outcome"] = "Dala o'lchovlari tiklanadi, tavsiyalar aniqligi oshadi"
        rec["risks"] = "Aloqa tiklanguncha tavsiyalar faqat model va prognozga tayanadi"
    elif t == "sensor_fault":
        rec["problem"] = "Sensor shubhali qiymatlar bermoqda"
        rec["cause"] = f"So'nggi 1 soatda {fmt(facts, 'sensor_bad_last_hour', 0)} ta o'lchov sifat nazoratidan o'tmadi"
        rec["action"] = "Sensor ulanishini, tuproqqa to'g'ri o'rnatilganini va kalibrlashni tekshiring."
        rec["timing"] = "Bugun"
        rec["expected_outcome"] = "Ishonchli o'lchovlar tiklanadi"
        rec["risks"] = "Shubhali qiymatlar tahlilga kiritilmaydi"
    elif t == "crop_condition_worse":
        rec["problem"] = f"{crop} suv stressida — holati yomonlashmoqda"
        rec["cause"] = f"Suv stressi koeffitsienti Ks = {fmt(facts, 'ks', 2)}, so'nggi 7 kunda stress kunlari: {fmt(facts, 'stress_days_7d', 0)}"
        rec["action"] = "Sug'orish rejasini tekshiring va dalani ko'zdan kechiring (so'lish, barglar rangi)."
        rec["timing"] = "Keyingi 1–2 kun"
        rec["expected_outcome"] = "Stress uzoq davom etishining oldi olinadi"
        rec["risks"] = "Model taxmini; sun'iy yo'ldosh NDVI (HLS) ulanganda aniqlik oshadi"
    elif t == "agro_stage_change":
        rec["problem"] = f"{crop} keyingi bosqichga o'tmoqda: {p.get('next_stage')}"
        rec["cause"] = f"Joriy bosqich: {fmt(facts, 'crop_stage')}; keyingi bosqichgacha {fmt(facts, 'days_to_next_stage', 0)}"
        rec["action"] = "Bosqichga mos ishlarni rejalashtiring: o'g'itlash, kultivatsiya, zararkunanda monitoringi (mahalliy agronom tavsiyasi bilan)."
        rec["timing"] = "Keyingi 3 kun"
        rec["expected_outcome"] = "Ishlar o'z vaqtida bajariladi"
        rec["risks"] = "Bosqich sanalari FAO-56 indikativ jadvallaridan — haqiqiy holat farq qilishi mumkin"
    elif t == "harvest_soon":
        rec["problem"] = "Hosil yig'imi yaqinlashmoqda"
        rec["cause"] = f"Mavsum oxirigacha taxminan {fmt(facts, 'days_to_harvest', 0)}"
        rec["action"] = "Yig'im texnikasi va saqlash joyini tayyorlang. Yig'imdan keyin botda /hosil buyrug'i bilan natijani kiriting."
        rec["timing"] = "Keyingi 7 kun"
        rec["expected_outcome"] = "Hosil natijasi keyingi mavsum tavsiyalarini aniqlashtiradi"
        rec["risks"] = "Sana taxminiy"
    elif t == "soil_ph_unsuitable":
        rec["problem"] = f"Tuproq pH {crop} uchun mos emas"
        rec["cause"] = f"Laboratoriya pH {fmt(facts, 'soil_ph')}, ekin uchun odatiy oraliq {p.get('lo')}–{p.get('hi')} (tekshirilmagan umumiy qiymat)"
        rec["action"] = "Mahalliy agrokimyo laboratoriyasi tavsiyasi bilan tuproqni tuzatish (organik o'g'it, gips yoki ohak) rejasini tuzing."
        rec["timing"] = "Keyingi ekishdan oldin"
        rec["expected_outcome"] = "Oziq moddalar o'zlashtirilishi yaxshilanadi"
        rec["risks"] = "Doza faqat laboratoriya tavsiyasi bilan belgilanadi"
    elif t == "soil_salinity_high":
        rec["problem"] = f"Tuproq sho'rlanishi {crop} uchun yuqori"
        rec["cause"] = f"ECe {fmt(facts, 'soil_ec')}, ekin chegarasi {p.get('threshold')} dS/m (FAO-29)"
        rec["action"] = "Sho'r yuvish, zovurlarni tozalash va sho'rga chidamli ekinlarni (almashlab ekish rejasi) ko'rib chiqing."
        rec["timing"] = "Mavsumlararo davrda"
        rec["expected_outcome"] = "Hosil yo'qotilishi kamayadi"
        rec["risks"] = "Sho'r yuvish ko'p suv talab qiladi"

    confidence, reason = _confidence(facts, alert.evidence)
    if t in ("hail_risk",):
        confidence, reason = "low", "Do'l prognozining ishonchliligi past"
    facts_text = [
        f"{facts[i]['label_uz']}: {fmt(facts, i)} ({facts[i]['source_label']})" for i in alert.evidence if i in facts
    ]
    return {
        "alert_type": t,
        "category": alert.category,
        "severity": alert.severity,
        "title_uz": TITLE_UZ.get(t, t),
        **rec,
        "evidence": evidence_list(facts, alert.evidence),
        "confidence": confidence,
        "confidence_reason": reason,
        "facts": facts_text,
        "assumptions": list(assumptions),
        "amount_mm": amount_mm,
    }
