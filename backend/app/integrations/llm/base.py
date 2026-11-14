"""LLM provayder interfeysi. Claude — default; boshqa provayder (masalan Gemini) shu interfeys orqali qo'shiladi."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

REFUSAL_TEXT = (
    "Men Smart Agro AI agronomik yordamchisiman. Faqat qishloq xo'jaligi, tuproq, ekinlar, sug'orish, "
    "ob-havo va hosildorlik bilan bog'liq savollarga javob bera olaman."
)

ToolExecutor = Callable[[str, dict], Awaitable[str]]


class LLMError(RuntimeError):
    pass


class LLMRefused(LLMError):
    pass


@dataclass
class Usage:
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


@dataclass
class ExplainResult:
    items: list[dict]
    summary_uz: str
    usage: Usage = field(default_factory=Usage)


@dataclass
class ChatResult:
    on_topic: bool
    answer: str
    sources: list[str]
    usage: Usage = field(default_factory=Usage)


class LLMProvider(Protocol):
    name: str

    async def explain(self, context: dict, drafts: list[dict]) -> ExplainResult | None: ...

    async def chat(self, system: str, history: list[dict], message: str, tools: list[dict],
                   execute: ToolExecutor) -> ChatResult: ...
