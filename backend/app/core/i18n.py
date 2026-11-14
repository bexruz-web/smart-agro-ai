"""Uch tilli matnlar (uz — lotin, ru, en): bot xabarnomalari, ma'lumotnomalar, AI agronom savollari."""
LANGS = ("uz", "ru", "en")
DEFAULT_LANG = "en"  # asosiy til — ingliz

REFUSAL = {
    "uz": "Men Smart Agro AI agronomik yordamchisiman. Faqat qishloq xo'jaligi, tuproq, ekinlar, sug'orish, ob-havo va "
          "hosildorlik bilan bog'liq savollarga javob bera olaman.",
    "ru": "Я агрономический помощник Smart Agro AI. Я отвечаю только на вопросы о сельском хозяйстве, почве, культурах, "
          "поливе, погоде и урожайности.",
    "en": "I am the Smart Agro AI agronomy assistant. I can only answer questions about agriculture, soil, crops, "
          "irrigation, weather and yields.",
}
LANG_NAME = {"uz": "o'zbek (lotin yozuvi)", "ru": "русский", "en": "English"}

IRRIGATION_TYPES = {
    "drip": {"uz": "Tomchilab sug'orish", "ru": "Капельное орошение", "en": "Drip irrigation"},
    "furrow": {"uz": "Egatlab sug'orish", "ru": "Бороздковый полив", "en": "Furrow irrigation"},
    "sprinkler": {"uz": "Yomg'irlatib sug'orish", "ru": "Дождевание", "en": "Sprinkler irrigation"},
    "flood": {"uz": "Bostirib sug'orish", "ru": "Затопление (напуском)", "en": "Flood irrigation"},
    "rainfed": {"uz": "Lalmi", "ru": "Богара (без полива)", "en": "Rainfed"},
}
WATER_SOURCES = {
    "canal": {"uz": "Kanal", "ru": "Канал", "en": "Canal"},
    "ariq": {"uz": "Ariq", "ru": "Арык", "en": "Irrigation ditch"},
    "well": {"uz": "Quduq", "ru": "Колодец", "en": "Well"},
    "river": {"uz": "Daryo", "ru": "Река", "en": "River"},
    "reservoir": {"uz": "Suv ombori", "ru": "Водохранилище", "en": "Reservoir"},
    "none": {"uz": "Yo'q", "ru": "Нет", "en": "None"},
}
MOISTURE_CLASS = {
    "very_dry": {"uz": "juda quruq", "ru": "очень сухо", "en": "very dry"},
    "dry": {"uz": "quruq", "ru": "сухо", "en": "dry"},
    "normal": {"uz": "me'yorida", "ru": "в норме", "en": "adequate"},
    "wet": {"uz": "ortiqcha nam", "ru": "переувлажнено", "en": "saturated"},
}
RISK = {
    "high": {"uz": "🔴 Yuqori", "ru": "🔴 Высокий", "en": "🔴 High"},
    "medium": {"uz": "🟡 O'rtacha", "ru": "🟡 Средний", "en": "🟡 Medium"},
    "low": {"uz": "🟢 Mo'tadil", "ru": "🟢 Умеренный", "en": "🟢 Low"},
}

T = {
    "report_title": {"uz": "Smart Agro AI · AI xabarnoma", "ru": "Smart Agro AI · AI-сводка", "en": "Smart Agro AI · AI update"},
    "today": {"uz": "Bugun", "ru": "Сегодня", "en": "Today"},
    "yesterday": {"uz": "Kecha", "ru": "Вчера", "en": "Yesterday"},
    "tomorrow": {"uz": "Ertaga", "ru": "Завтра", "en": "Tomorrow"},
    "greeting": {"uz": "Assalomu alaykum!", "ru": "Здравствуйте!", "en": "Hello!"},
    "field_line": {"uz": "{field} bo'yicha tahlil:", "ru": "Анализ по полю «{field}»:", "en": "Analysis for “{field}”:"},
    "irrigation": {"uz": "Suv ehtiyoji", "ru": "Потребность в воде", "en": "Water need"},
    "rain_at": {"uz": "{time} da yomg'ir", "ru": "дождь в {time}", "en": "rain at {time}"},
    "soil_moisture": {"uz": "Tuproq namligi", "ru": "Влажность почвы", "en": "Soil moisture"},
    "mm": {"uz": "mm", "ru": "мм", "en": "mm"},
    "no_data": {"uz": "ma'lumot yo'q", "ru": "нет данных", "en": "no data"},
    "sensor": {"uz": "datchik", "ru": "датчик", "en": "sensor"},
    "model": {"uz": "model", "ru": "модель", "en": "model"},
    "advice": {"uz": "Tavsiya", "ru": "Рекомендация", "en": "Advice"},
    "irrigate_now": {"uz": "Bugun sug'orish tavsiya etiladi: taxminan {mm} mm (≈ {m3} m³/ga).",
                     "ru": "Сегодня рекомендуется полив: около {mm} мм (≈ {m3} м³/га).",
                     "en": "Irrigation recommended today: about {mm} mm (≈ {m3} m³/ha)."},
    "split": {"uz": "Tanqislik katta — suvni bir necha marta bo'lib bering.", "ru": "Дефицит большой — давайте воду в несколько приёмов.",
              "en": "The deficit is large — apply water in several rounds."},
    "no_irrigation": {"uz": "Sug'orish hozircha talab qilinmaydi.", "ru": "Полив пока не требуется.", "en": "No irrigation needed for now."},
    "rain_expected": {"uz": "Yomg'ir kutilmoqda — sug'orishni kechiktiring.", "ru": "Ожидается дождь — полив можно отложить.",
                      "en": "Rain is expected — postpone irrigation."},
    "next_irrigation": {"uz": "Keyingi sug'orish taxminan {days} kundan keyin tavsiya etiladi.",
                        "ru": "Следующий полив — примерно через {days} дн.", "en": "Next irrigation in about {days} days."},
    "next_irrigation_unknown": {"uz": "Keyingi 7 kunda sug'orish kutilmayapti.", "ru": "В ближайшие 7 дней полив не ожидается.",
                                "en": "No irrigation expected in the next 7 days."},
    "watch": {"uz": "Ob-havo va tuproq holatini kuzatib boring.", "ru": "Следите за погодой и состоянием почвы.",
              "en": "Keep an eye on the weather and soil."},
    "footer": {"uz": "Smart Agro AI — aqlli dehqonchilik yordamchisi", "ru": "Smart Agro AI — умный помощник фермера",
               "en": "Smart Agro AI — your smart farming assistant"},
    "open_field": {"uz": "📊 Dalani ochish", "ru": "📊 Открыть поле", "en": "📊 Open field"},
    "alert": {"uz": "Ogohlantirish", "ru": "Предупреждение", "en": "Alert"},
    "field": {"uz": "Dala", "ru": "Поле", "en": "Field"},
    "resolved": {"uz": "✅ Bartaraf bo'ldi", "ru": "✅ Устранено", "en": "✅ Resolved"},
    "sensor_offline_body": {"uz": "{name} {since} dan beri ma'lumot yubormayapti.\nQuvvat va aloqani tekshiring.",
                            "ru": "{name} не передаёт данные с {since}.\nПроверьте питание и связь.",
                            "en": "{name} has not sent data since {since}.\nCheck power and connectivity."},
}

ALERTS = {
    "soil_moisture_critical": {
        "title": {"uz": "Tuproq namligi kritik", "ru": "Критическая влажность почвы", "en": "Critical soil moisture"},
        "action": {"uz": "Imkon qadar tez sug'oring.", "ru": "Проведите полив как можно скорее.", "en": "Irrigate as soon as possible."}},
    "irrigation_needed": {
        "title": {"uz": "Sug'orish vaqti keldi", "ru": "Пора поливать", "en": "Time to irrigate"},
        "action": {"uz": "Keyingi 24 soat ichida sug'oring (ertalab yoki kechqurun).", "ru": "Полейте в ближайшие 24 часа (утром или вечером).",
                   "en": "Irrigate within 24 hours (morning or evening)."}},
    "irrigation_delay": {
        "title": {"uz": "Sug'orishni kechiktiring", "ru": "Отложите полив", "en": "Postpone irrigation"},
        "action": {"uz": "Yaqin 48 soatda yomg'ir kutilmoqda.", "ru": "В ближайшие 48 часов ожидается дождь.", "en": "Rain is expected within 48 hours."}},
    "heavy_rain": {
        "title": {"uz": "Kuchli yog'ingarchilik kutilmoqda", "ru": "Ожидаются сильные осадки", "en": "Heavy rain expected"},
        "action": {"uz": "Sug'orishni to'xtating, zovur va ariqlarni tozalang.", "ru": "Остановите полив, прочистите арыки и дренаж.",
                   "en": "Stop irrigation, clear ditches and drains."}},
    "hail_risk": {
        "title": {"uz": "Do'l xavfi", "ru": "Риск града", "en": "Hail risk"},
        "action": {"uz": "Texnikani yopiq joyga oling.", "ru": "Уберите технику под навес.", "en": "Move equipment under cover."}},
    "frost_risk": {
        "title": {"uz": "Sovuq urishi xavfi", "ru": "Риск заморозков", "en": "Frost risk"},
        "action": {"uz": "Kechqurun yengil sug'oring, sezgir ishlarni kechiktiring.", "ru": "Слегка полейте вечером, отложите чувствительные работы.",
                   "en": "Water lightly in the evening and postpone sensitive work."}},
    "heat_stress": {
        "title": {"uz": "Issiq urishi xavfi", "ru": "Риск теплового стресса", "en": "Heat stress risk"},
        "action": {"uz": "Sug'orishni erta tongga suring, namlikni saqlang.", "ru": "Перенесите полив на раннее утро, поддерживайте влажность.",
                   "en": "Irrigate early in the morning and keep the soil moist."}},
    "extreme_heat": {
        "title": {"uz": "Haddan tashqari issiq", "ru": "Сильная жара", "en": "Extreme heat"},
        "action": {"uz": "Kunduzi ishlov bermang, namlikni tekshiring.", "ru": "Не проводите работы днём, проверьте влажность.",
                   "en": "Avoid fieldwork at midday and check soil moisture."}},
    "sharp_temp_change": {
        "title": {"uz": "Keskin harorat o'zgarishi", "ru": "Резкая смена температуры", "en": "Sharp temperature change"},
        "action": {"uz": "Ekish va kimyoviy ishlovni kechiktiring.", "ru": "Отложите посев и обработки.", "en": "Postpone sowing and spraying."}},
    "drought_risk": {
        "title": {"uz": "Qurg'oqchilik xavfi", "ru": "Риск засухи", "en": "Drought risk"},
        "action": {"uz": "Sug'orish navbatini oldindan rejalashtiring.", "ru": "Заранее спланируйте очередь полива.", "en": "Plan your irrigation turn in advance."}},
    "sensor_offline": {
        "title": {"uz": "Sensor oflayn", "ru": "Датчик офлайн", "en": "Sensor offline"},
        "action": {"uz": "Quvvat va aloqani tekshiring.", "ru": "Проверьте питание и связь.", "en": "Check power and connectivity."}},
    "sensor_fault": {
        "title": {"uz": "Sensor nosozligi", "ru": "Неисправность датчика", "en": "Sensor fault"},
        "action": {"uz": "Datchik ulanishi va o'rnatilishini tekshiring.", "ru": "Проверьте подключение и установку датчика.",
                   "en": "Check the sensor wiring and installation."}},
    "crop_condition_worse": {
        "title": {"uz": "Ekin holati yomonlashmoqda", "ru": "Состояние культуры ухудшается", "en": "Crop condition worsening"},
        "action": {"uz": "Dalani ko'zdan kechiring va sug'orishni tekshiring.", "ru": "Осмотрите поле и проверьте полив.",
                   "en": "Inspect the field and check irrigation."}},
    "agro_stage_change": {
        "title": {"uz": "Bajarilishi kerak bo'lgan ish", "ru": "Пора выполнить работы", "en": "Task due"},
        "action": {"uz": "Ekin keyingi bosqichga o'tmoqda — ishlarni rejalashtiring.", "ru": "Культура переходит в следующую фазу — запланируйте работы.",
                   "en": "The crop is entering its next stage — plan the work."}},
    "harvest_soon": {
        "title": {"uz": "Hosil yig'imi yaqin", "ru": "Скоро уборка", "en": "Harvest is near"},
        "action": {"uz": "Texnika va saqlash joyini tayyorlang.", "ru": "Подготовьте технику и хранилище.", "en": "Prepare equipment and storage."}},
    "soil_ph_unsuitable": {
        "title": {"uz": "Tuproq pH mos emas", "ru": "Неподходящий pH почвы", "en": "Unsuitable soil pH"},
        "action": {"uz": "Agrokimyo laboratoriyasi tavsiyasini oling.", "ru": "Получите рекомендацию агрохимлаборатории.",
                   "en": "Get advice from a soil lab."}},
    "soil_salinity_high": {
        "title": {"uz": "Tuproq sho'rlanishi yuqori", "ru": "Высокая засолённость почвы", "en": "High soil salinity"},
        "action": {"uz": "Sho'r yuvish va zovurlarni tekshiring.", "ru": "Проверьте промывку и дренаж.", "en": "Check leaching and drainage."}},
}

# AI Agronom: dinamik savollar banki (holatga qarab tanlanadi)
QUESTIONS = {
    "irrigate_today": {"uz": "Bugun sug'orish kerakmi?", "ru": "Нужно ли сегодня поливать?", "en": "Should I irrigate today?"},
    "too_wet": {"uz": "Tuproq namligi oshib ketdi, nima qilay?", "ru": "Почва переувлажнена, что делать?", "en": "The soil is too wet — what should I do?"},
    "rain_vs_irrigation": {"uz": "Yomg'ir kutilyapti — sug'orishni kechiktiraymi?", "ru": "Ожидается дождь — отложить полив?",
                           "en": "Rain is coming — should I delay irrigation?"},
    "salinity": {"uz": "Tuproq sho'rlanishiga qarshi nima qilay?", "ru": "Что делать с засолением почвы?", "en": "How do I deal with soil salinity?"},
    "fertilize": {"uz": "{crop}ga qachon va qanday o'g'it beraman?", "ru": "Когда и чем подкармливать культуру «{crop}»?",
                  "en": "When and how should I fertilize my {crop}?"},
    "pests": {"uz": "Kasallik yoki zararkunanda xavfi bo'lsa, nima qilay?", "ru": "Что делать при риске болезней или вредителей?",
              "en": "What if there is a disease or pest risk?"},
    "next_crop": {"uz": "{crop}dan keyin nima eksam bo'ladi?", "ru": "Что посадить после культуры «{crop}»?",
                  "en": "What should I plant after {crop}?"},
    "heat": {"uz": "Issiqda ekinni qanday himoya qilaman?", "ru": "Как защитить посевы от жары?", "en": "How do I protect the crop from heat?"},
    "frost": {"uz": "Sovuqdan ekinni qanday himoya qilaman?", "ru": "Как защитить посевы от заморозков?", "en": "How do I protect the crop from frost?"},
    "sensor": {"uz": "Datchik ishlamayapti — nimani tekshiray?", "ru": "Датчик не работает — что проверить?", "en": "The sensor isn't working — what should I check?"},
    "continue": {"uz": "Oldingi maslahatingiz bo'yicha keyingi qadam nima?", "ru": "Какой следующий шаг по вашему прошлому совету?",
                 "en": "What is the next step after your last advice?"},
}


def norm_lang(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    lang = lang.lower()[:2]
    return lang if lang in LANGS else DEFAULT_LANG


def t(key: str, lang: str, **kw) -> str:
    text = T[key].get(norm_lang(lang)) or T[key][DEFAULT_LANG]
    return text.format(**kw) if kw else text


def pick(mapping: dict, lang: str) -> str:
    return mapping.get(norm_lang(lang)) or mapping[DEFAULT_LANG]


CHAT_MSG = {
    "limit": {"uz": "Bugungi savollar limiti tugadi. Ertaga yana yozing.",
              "ru": "Лимит вопросов на сегодня исчерпан. Напишите завтра.",
              "en": "You have reached today's question limit. Please try again tomorrow."},
    "unavailable": {"uz": "AI agronom hozir javob bera olmayapti. Birozdan keyin qayta urinib ko'ring.",
                    "ru": "AI-агроном сейчас не может ответить. Попробуйте ещё раз чуть позже.",
                    "en": "The AI Agronomist can't answer right now. Please try again in a moment."},
}
