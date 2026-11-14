"""Claude API provayderi (rasmiy `anthropic` Python SDK).

- Model: settings.ai_model (default claude-opus-5-5). Effort aniq beriladi (Opus 5.5'da default medium).
- Thinking o'chirilmaydi (Opus 5.5'da `disabled` 400 qaytaradi) — parametr umuman yuborilmaydi.
- Majburiy tool_choice ishlatilmaydi (Opus 5.5'da 400) — `auto` + strict tool'lar + structured output.
- Server-side fallback: refusal bo'lsa Anthropic tavsiya qilgan modelda qayta urinadi.
- stop_reason == "refusal" — LLMRefused; chaqiruvchi deterministik shablonga o'tadi.
"""
import json
import logging

import anthropic

from app.core.config import get_settings
from app.integrations.llm.base import ChatResult, ExplainResult, LLMError, LLMRefused, ToolExecutor, Usage

log = logging.getLogger(__name__)

# 1M token narxi (kirish, chiqish), USD — 2026-09 holati; narxlarni rasmiy sahifadan tekshiring.
PRICING = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOOL_ROUNDS = 6

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "problem": {"type": "string"},
                    "cause": {"type": "string"},
                    "action": {"type": "string"},
                    "timing": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "risks": {"type": "string"},
                },
                "required": ["index", "problem", "cause", "action", "timing", "expected_outcome", "risks"],
                "additionalProperties": False,
            },
        },
        "summary_uz": {"type": "string"},
    },
    "required": ["items", "summary_uz"],
    "additionalProperties": False,
}

CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "on_topic": {"type": "boolean"},
        "answer": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["on_topic", "answer", "sources"],
    "additionalProperties": False,
}


def _usage(model: str, resp) -> Usage:
    u = getattr(resp, "usage", None)
    inp = (getattr(u, "input_tokens", 0) or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + (
        getattr(u, "cache_creation_input_tokens", 0) or 0)
    out = getattr(u, "output_tokens", 0) or 0
    price = PRICING.get(model)
    cost = (inp * price[0] + out * price[1]) / 1_000_000 if price else None
    return Usage(model=model, input_tokens=inp, output_tokens=out, cost_usd=cost)


def _merge(a: Usage, b: Usage) -> Usage:
    return Usage(a.model or b.model, a.input_tokens + b.input_tokens, a.output_tokens + b.output_tokens,
                 (a.cost_usd or 0) + (b.cost_usd or 0) if (a.cost_usd is not None or b.cost_usd is not None) else None)


def _first_text(resp) -> str:
    for block in resp.content:
        if block.type == "text":
            return block.text
    raise LLMError("Javobda matn bloki yo'q")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        s = get_settings()
        self.model = s.ai_model
        self.effort_analysis = s.ai_effort_analysis
        self.effort_chat = s.ai_effort_chat
        self.client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, timeout=120.0, max_retries=2)

    async def _create(self, **kwargs):
        try:
            try:
                resp = await self.client.beta.messages.create(
                    model=self.model,
                    betas=[FALLBACK_BETA],
                    extra_body={"fallbacks": "default"},
                    **kwargs,
                )
            except anthropic.BadRequestError as e:
                # Hisob/platforma server-side fallback'ni qo'llab-quvvatlamasa — oddiy so'rov bilan qayta urinamiz
                if "fallback" not in str(e).lower():
                    raise
                log.warning("server-side fallback qabul qilinmadi, oddiy so'rov yuborilmoqda")
                resp = await self.client.messages.create(model=self.model, **kwargs)
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API xatosi: {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Claude API'ga ulanib bo'lmadi") from e
        if resp.stop_reason == "refusal":
            raise LLMRefused("Model so'rovni rad etdi")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Javob max_tokens chegarasida kesildi")
        return resp

    async def explain(self, context: dict, drafts: list[dict]) -> ExplainResult | None:
        from app.agent.prompts import EXPLAIN_SYSTEM_V1

        payload = {"context": context, "recommendations": [{"index": i, **d} for i, d in enumerate(drafts)]}
        resp = await self._create(
            max_tokens=8000,
            system=[{"type": "text", "text": EXPLAIN_SYSTEM_V1, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": self.effort_analysis, "format": {"type": "json_schema", "schema": EXPLAIN_SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}],
        )
        data = json.loads(_first_text(resp))
        return ExplainResult(items=data["items"], summary_uz=data["summary_uz"], usage=_usage(self.model, resp))

    async def chat(self, system: str, history: list[dict], message: str, tools: list[dict],
                   execute: ToolExecutor) -> ChatResult:
        messages = [*history, {"role": "user", "content": message}]
        strict_tools = [{**t, "strict": True} for t in tools]
        usage = Usage(model=self.model)
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await self._create(
                max_tokens=6000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                tools=strict_tools,
                tool_choice={"type": "auto"},
                output_config={"effort": self.effort_chat, "format": {"type": "json_schema", "schema": CHAT_SCHEMA}},
                messages=messages,
            )
            usage = _merge(usage, _usage(self.model, resp))
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not tool_uses:
                data = json.loads(_first_text(resp))
                return ChatResult(bool(data["on_topic"]), data["answer"], list(data.get("sources", [])), usage)
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for tu in tool_uses:
                try:
                    out = await execute(tu.name, dict(tu.input))
                    results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
                except Exception as e:  # tool xatosi modelga is_error bilan qaytariladi
                    log.warning("tool %s failed: %s", tu.name, e)
                    results.append({"type": "tool_result", "tool_use_id": tu.id, "content": f"Xato: {e}", "is_error": True})
            messages.append({"role": "user", "content": results})
        raise LLMError("Tool chaqiruvlari limiti oshdi")
