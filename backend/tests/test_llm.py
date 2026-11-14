"""Claude provayderi va chat mavzu filtri — tarmoqsiz (soxta mijoz bilan) testlar."""
import json
from types import SimpleNamespace

import pytest

from app.integrations.llm import anthropic_provider as ap
from app.integrations.llm.base import LLMRefused
from app.integrations.llm.mock_provider import MockProvider, is_agri


def _resp(stop_reason="end_turn", content=None):
    usage = SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(stop_reason=stop_reason, content=content or [], usage=usage)


def _text(t):
    return SimpleNamespace(type="text", text=t)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    p = ap.AnthropicProvider()
    yield p
    get_settings.cache_clear()


async def test_explain_parses_json_and_sets_params(provider):
    fake = FakeMessages([_resp(content=[_text(json.dumps({"items": [{"index": 0, "problem": "p", "cause": "c", "action": "a",
                                                                       "timing": "t", "expected_outcome": "e", "risks": "r"}],
                                                            "summary_uz": "Xulosa"}))])])
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    res = await provider.explain({"facts": {}}, [{"problem": "x"}])
    assert res.items[0]["action"] == "a" and res.summary_uz == "Xulosa"
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["effort"] == "medium"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in call and "tool_choice" not in call
    assert call["extra_body"] == {"fallbacks": "default"}
    assert res.usage.cost_usd == pytest.approx((1000 * 4 + 200 * 20) / 1e6)


async def test_refusal_raises(provider):
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages([_resp(stop_reason="refusal")])))
    with pytest.raises(LLMRefused):
        await provider.explain({}, [])


async def test_chat_tool_loop(provider):
    tool_use = SimpleNamespace(type="tool_use", id="tu1", name="get_my_fields", input={})
    final = json.dumps({"on_topic": True, "answer": "Javob", "sources": ["🛰 NASA POWER"]})
    fake = FakeMessages([_resp("tool_use", [tool_use]), _resp(content=[_text(final)])])
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    executed = []

    async def execute(name, args):
        executed.append(name)
        return "[]"

    res = await provider.chat("sys", [], "savol", [{"name": "get_my_fields", "description": "d",
                                                   "input_schema": {"type": "object", "properties": {}, "required": [],
                                                                    "additionalProperties": False}}], execute)
    assert executed == ["get_my_fields"] and res.answer == "Javob" and res.on_topic
    assert fake.calls[0]["tool_choice"] == {"type": "auto"} and fake.calls[0]["tools"][0]["strict"] is True
    assert fake.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


async def test_mock_topic_guard():
    assert is_agri("Bug'doyni qachon sug'oray?") and not is_agri("Futbol kim yutadi?")
    res = await MockProvider().chat("", [], "Kino tavsiya qil", [], None)
    assert res.on_topic is False


async def test_mock_field_hint_does_not_bypass_guard():
    res = await MockProvider().chat("", [], "Futbol kim yutadi?\n\n(Fermer tanlagan dala ID: 3)", [], None)
    assert res.on_topic is False
