"""AI kaliti yo'q bo'lganda (DEMO/test) ishlaydigan deterministik provayder.

Raqam o'ylab topmaydi: chat javobi tool'lardan olingan faktlar va tavsiyalardan yig'iladi.
"""
import json
import re

from app.integrations.llm.base import ChatResult, ExplainResult, ToolExecutor, Usage

AGRI_KEYWORDS = [
    # o'zbekcha
    "ekin", "dala", "tuproq", "sug'or", "sugor", "suv", "hosil", "ob-havo", "obhavo", "havo", "yomg'ir", "yomgir",
    "qor", "sovuq", "issiq", "harorat", "namlik", "o'g'it", "ogit", "azot", "fosfor", "kaliy", "bug'doy", "bugdoy",
    "paxta", "g'o'za", "goza", "makkajo'xori", "makkajoxori", "beda", "mosh", "kartoshka", "zararkunanda", "kasallik",
    "almashlab", "ekish", "urug'", "urug", "sho'r", "shor", "ph", "sensor", "nasa", "fermer", "dehqon", "agro",
    "gektar", "bosqich", "vegetatsiya", "barg", "ildiz", "prognoz", "quyosh", "shamol", "qurg'oqchilik", "do'l",
    # ruscha / inglizcha
    "почв", "полив", "урож", "погод", "удобр", "пшениц", "хлоп", "soil", "crop", "irrigat", "yield", "weather",
    "fertiliz", "wheat", "cotton", "farm", "harvest", "rain", "drought",
]


def is_agri(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in AGRI_KEYWORDS)


class MockProvider:
    name = "mock"

    async def explain(self, context: dict, drafts: list[dict]) -> ExplainResult | None:
        return None  # AI izohi yo'q — deterministik tavsiyalar ishlatiladi

    async def advice(self, facts: dict, lang_name: str) -> list[str] | None:
        return None  # deterministik matn ishlatiladi

    async def chat(self, system: str, history: list[dict], message: str, tools: list[dict],
                   execute: ToolExecutor) -> ChatResult:
        hint = re.search(r"\(Fermer tanlagan dala ID: (\d+)\)", message)
        question = message[: hint.start()].strip() if hint else message
        if not is_agri(question):  # tizim qo'shgan dala izohi mavzu tekshiruviga ta'sir qilmasligi kerak
            return ChatResult(False, "", [], Usage(model="mock"))
        fields = json.loads(await execute("get_my_fields", {}))
        if not fields:
            return ChatResult(True, "Hali dala qo'shilmagan. Mini App'da 'Dala qo'shish' orqali dalangizni xaritada belgilang.",
                              [], Usage(model="mock"))
        field_id = fields[0]["id"]
        if hint and any(f["id"] == int(hint.group(1)) for f in fields):
            field_id = int(hint.group(1))
        snap = json.loads(await execute("get_field_snapshot", {"field_id": field_id}))
        recs = json.loads(await execute("get_recommendations", {"field_id": field_id}))
        facts = snap.get("facts", {})
        lines = [f"Dala: {snap.get('field_name', field_id)}. Hozirgi asosiy ko'rsatkichlar:"]
        for fid in ("soil_moisture", "depletion_mm", "fc_precip_48h", "fc_tmin_72h", "fc_tmax_72h", "nasa_precip_30d"):
            f = facts.get(fid)
            if f and f.get("value") is not None:
                lines.append(f"• {f['label_uz']}: {f['value']} {f['unit']} ({f['source_label']})")
        if recs:
            lines.append("Faol tavsiyalar:")
            for r in recs[:3]:
                lines.append(f"• {r['problem']} — {r['action']}")
        lines.append("(AI kaliti ulanmagan: javob qoidalar asosida faktlardan tuzildi.)")
        sources = sorted({f["source_label"] for f in facts.values() if f.get("value") is not None})[:5]
        return ChatResult(True, "\n".join(lines), sources, Usage(model="mock"))


def get_provider():
    from app.core.config import get_settings

    provider = get_settings().llm_provider
    if provider == "gemini":
        from app.integrations.llm.gemini_provider import GeminiProvider

        return GeminiProvider()
    if provider == "anthropic":
        from app.integrations.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    return MockProvider()
