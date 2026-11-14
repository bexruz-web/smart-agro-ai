"""Gemini API provayderi (REST, `httpx`). `GEMINI_API_KEY` va `AI_MODEL=gemini-…` bo'lsa ishlatiladi.

- Strukturalangan javob: generationConfig.responseMimeType=application/json + responseSchema.
- Chat: tool chaqiruvlari o'rniga dala konteksti (faktlar, prognoz, tavsiyalar, mavsumlar) oldindan yig'ilib beriladi —
  model faqat shu fermerning ma'lumotini ko'radi (ChatTools.execute farmer_id'ni sessiyadan oladi).
- Model band bo'lsa (429/503) yoki topilmasa (404) — zaxira modellarga o'tadi.
"""
import json
import logging
import re

import httpx

from app.core.config import get_settings
from app.integrations.llm.base import ChatResult, ExplainResult, LLMError, LLMRefused, ToolExecutor, Usage

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]

EXPLAIN_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "index": {"type": "INTEGER"},
                    "problem": {"type": "STRING"},
                    "cause": {"type": "STRING"},
                    "action": {"type": "STRING"},
                    "timing": {"type": "STRING"},
                    "expected_outcome": {"type": "STRING"},
                    "risks": {"type": "STRING"},
                },
                "required": ["index", "problem", "cause", "action", "timing", "expected_outcome", "risks"],
            },
        },
        "summary_uz": {"type": "STRING"},
    },
    "required": ["items", "summary_uz"],
}

CHAT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "on_topic": {"type": "BOOLEAN"},
        "answer": {"type": "STRING"},
        "sources": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["on_topic", "answer", "sources"],
}


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        s = get_settings()
        self.model = s.ai_model
        self.key = s.gemini_api_key
        self.timeout = 120.0

    async def _generate(self, system: str, user_text: str, schema: dict) -> tuple[dict, Usage]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.3},
        }
        models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        last_error = "noma'lum xato"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for model in models:
                try:
                    resp = await client.post(API.format(model=model), json=body, headers={"x-goog-api-key": self.key})
                except httpx.HTTPError as e:
                    last_error = f"{model}: tarmoq xatosi {e.__class__.__name__}"
                    continue
                if resp.status_code in (404, 429, 500, 503):
                    last_error = f"{model}: {resp.status_code}"
                    log.warning("Gemini %s javob bermadi (%s), keyingi model sinaladi", model, resp.status_code)
                    continue
                if resp.status_code >= 400:
                    raise LLMError(f"Gemini API xatosi: {resp.status_code}")
                data = resp.json()
                if data.get("promptFeedback", {}).get("blockReason"):
                    raise LLMRefused("Gemini so'rovni blokladi")
                cands = data.get("candidates") or []
                if not cands:
                    raise LLMError("Gemini bo'sh javob qaytardi")
                if cands[0].get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
                    raise LLMRefused("Gemini javobni xavfsizlik sababli to'xtatdi")
                parts = cands[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    m = re.search(r"\{.*\}", text, re.S)
                    if not m:
                        raise LLMError("Gemini JSON qaytarmadi")
                    parsed = json.loads(m.group(0))
                um = data.get("usageMetadata", {})
                usage = Usage(model=data.get("modelVersion", model), input_tokens=um.get("promptTokenCount", 0),
                              output_tokens=um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0), cost_usd=None)
                return parsed, usage
        raise LLMError(f"Gemini modellari javob bermadi ({last_error})")

    async def explain(self, context: dict, drafts: list[dict]) -> ExplainResult | None:
        from app.agent.prompts import EXPLAIN_SYSTEM_V1

        payload = {"context": context, "recommendations": [{"index": i, **d} for i, d in enumerate(drafts)]}
        data, usage = await self._generate(EXPLAIN_SYSTEM_V1, json.dumps(payload, ensure_ascii=False, default=str), EXPLAIN_SCHEMA)
        return ExplainResult(items=data.get("items", []), summary_uz=data.get("summary_uz", ""), usage=usage)

    async def chat(self, system: str, history: list[dict], message: str, tools: list[dict],
                   execute: ToolExecutor) -> ChatResult:
        hint = re.search(r"\(Fermer tanlagan dala ID: (\d+)\)", message)
        question = message[: hint.start()].strip() if hint else message
        fields = json.loads(await execute("get_my_fields", {}))
        context: dict = {"fields": fields}
        field_id = None
        if hint and any(f["id"] == int(hint.group(1)) for f in fields):
            field_id = int(hint.group(1))
        elif len(fields) == 1:
            field_id = fields[0]["id"]
        if field_id is not None:
            for name in ("get_field_snapshot", "get_forecast", "get_recommendations", "get_season_history"):
                try:
                    context[name.removeprefix("get_")] = json.loads(await execute(name, {"field_id": field_id}))
                except Exception as e:  # noqa: BLE001 — bitta manba xatosi javobni to'xtatmasin
                    context[name.removeprefix("get_")] = f"ma'lumot olinmadi: {e}"
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        user_text = (
            "Faqat quyidagi KONTEKST'dagi ma'lumotlardan foydalan (bu fermerning o'z dalalari). "
            "Kontekstda yo'q raqamni o'ylab topma.\n\n"
            f"KONTEKST (JSON):\n{json.dumps(context, ensure_ascii=False, default=str)[:60000]}\n\n"
            f"OLDINGI SUHBAT:\n{convo or '—'}\n\nSAVOL: {question}"
        )
        data, usage = await self._generate(system, user_text, CHAT_SCHEMA)
        return ChatResult(bool(data.get("on_topic")), str(data.get("answer", "")), list(data.get("sources") or []), usage)
