from core.providers.llm import StubLLMProvider

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
