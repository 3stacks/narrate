from __future__ import annotations

import re

_SKIP_TITLES = {
    "copyright",
    "contents",
    "table of contents",
    "title page",
    "cover",
    "dedication",
    "also by",
    "also by this author",
    "books by",
    "praise",
    "front matter",
}

_CHAPTER_HEAD = re.compile(
    r"^(chapter|part|book)\s+([0-9ivxlcdm]+|[a-z][a-z\s]{0,40})$",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    blank = False
    for raw in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if re.fullmatch(r"\d{1,4}", line):
            continue
        if not line:
            if not blank and lines:
                lines.append("")
                blank = True
            continue
        blank = False
        lines.append(line)
    return "\n".join(lines).strip()


def is_skippable_title(title: str) -> bool:
    key = re.sub(r"[^a-z ]", "", title.lower()).strip()
    return key in _SKIP_TITLES


def looks_like_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    if _CHAPTER_HEAD.match(stripped):
        return True
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    return bool(letters) and stripped == stripped.upper() and len(letters) >= 8


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars < 200:
        raise ValueError("max_chars is too small")
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    buf = ""
    for sentence in split_sentences(text):
        candidate = f"{buf} {sentence}".strip() if buf else sentence
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(sentence) <= max_chars:
            buf = sentence
            continue
        for piece in _hard_wrap(sentence, max_chars):
            if buf and len(buf) + 1 + len(piece) <= max_chars:
                buf = f"{buf} {piece}"
            else:
                if buf:
                    chunks.append(buf)
                buf = piece
    if buf:
        chunks.append(buf)
    return chunks


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    buf = ""
    for word in words:
        candidate = f"{buf} {word}".strip() if buf else word
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            out.append(buf)
        if len(word) <= max_chars:
            buf = word
            continue
        for i in range(0, len(word), max_chars):
            out.append(word[i : i + max_chars])
        buf = ""
    if buf:
        out.append(buf)
    return out
