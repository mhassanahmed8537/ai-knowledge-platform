from core.providers.llm import StubLLMProvider, UsageAccumulator, to_gemini_contents

SYSTEM = """You answer from sources.

[1] (Doc A) The sky is blue.
[2] (Doc B) Water boils at 100C.
"""


async def _collect(stream) -> str:  # type: ignore[no-untyped-def]
    return "".join([chunk async for chunk in stream])


async def test_stub_streams_and_cites_every_source() -> None:
    provider = StubLLMProvider()
    text = await _collect(
        provider.astream(system=SYSTEM, messages=[{"role": "user", "content": "Why?"}])
    )
    assert "[1]" in text
    assert "[2]" in text
    assert "Why?" in text


async def test_stub_is_deterministic() -> None:
    provider = StubLLMProvider()
    msgs = [{"role": "user", "content": "same question"}]
    first = await _collect(provider.astream(system=SYSTEM, messages=msgs))
    second = await _collect(provider.astream(system=SYSTEM, messages=msgs))
    assert first == second


async def test_stub_handles_no_sources() -> None:
    provider = StubLLMProvider()
    text = await _collect(
        provider.astream(system="no sources here", messages=[{"role": "user", "content": "Q"}])
    )
    assert "no sources retrieved" in text


def test_gemini_maps_assistant_role_to_model() -> None:
    # Gemini calls the assistant turn "model" and wraps content in parts[].
    contents = to_gemini_contents(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "follow up"},
        ]
    )
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[1]["parts"] == [{"text": "hello"}]


def test_gemini_contents_empty() -> None:
    assert to_gemini_contents([]) == []


async def test_stub_emits_multiple_chunks() -> None:
    provider = StubLLMProvider()
    chunks = [
        c
        async for c in StubLLMProvider().astream(
            system=SYSTEM, messages=[{"role": "user", "content": "Q"}]
        )
    ]
    assert len(chunks) > 3  # genuinely streamed, not one blob
    assert provider.name == "stub"


async def test_stub_fills_usage_accumulator_when_given_one() -> None:
    provider = StubLLMProvider()
    usage = UsageAccumulator()
    await _collect(
        provider.astream(system=SYSTEM, messages=[{"role": "user", "content": "Why?"}], usage=usage)
    )
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0


async def test_stub_leaves_usage_accumulator_untouched_when_not_given() -> None:
    provider = StubLLMProvider()
    # Should not raise when usage is omitted (the default).
    text = await _collect(
        provider.astream(system=SYSTEM, messages=[{"role": "user", "content": "Why?"}])
    )
    assert text
