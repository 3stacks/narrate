from narrate.textutil import chunk_text, clean_text, looks_like_chapter_heading
from narrate.voices import estimate_usd


def test_chunk_respects_max_chars():
    text = " ".join(f"Sentence number {i}." for i in range(200))
    chunks = chunk_text(text, 400)
    assert chunks
    assert all(len(chunk) <= 400 for chunk in chunks)
    assert "".join(chunk.replace(" ", "") for chunk in chunks).startswith("Sentencenumber0")


def test_short_text_is_one_chunk():
    assert chunk_text("Hello.", 3500) == ["Hello."]


def test_cost_for_typical_novel():
    # 500k characters at $0.60 / million
    assert estimate_usd("openai/gpt-4o-mini-tts-2025-12-15", 500_000) == 0.3


def test_clean_drops_page_numbers():
    text = clean_text("Hello\n12\nWorld")
    assert "12" not in text.splitlines()
    assert "Hello" in text


def test_chapter_heading():
    assert looks_like_chapter_heading("Chapter 12")
    assert looks_like_chapter_heading("THE LONG ROAD")
    assert not looks_like_chapter_heading("He walked down the long road toward town.")
