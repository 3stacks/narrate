from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_COVER, ITEM_DOCUMENT, ITEM_IMAGE, epub
from pypdf import PdfReader

from narrate.textutil import clean_text, is_skippable_title, looks_like_chapter_heading

MIN_CHAPTER_CHARS = 250


@dataclass
class Chapter:
    title: str
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)


@dataclass
class Book:
    title: str
    author: str
    chapters: list[Chapter] = field(default_factory=list)
    cover_bytes: bytes | None = None
    cover_mime: str = "image/jpeg"
    source_kind: str = "epub"
    warning: str = ""

    @property
    def chars(self) -> int:
        return sum(chapter.chars for chapter in self.chapters)


def extract_book(path: Path) -> Book:
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return extract_epub(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use EPUB or PDF.")


def extract_epub(path: Path) -> Book:
    book = epub.read_epub(str(path), options={"ignore_ncx": False})
    title = _dc(book, "title") or path.stem
    author = _dc(book, "creator") or "Unknown"
    cover, mime = _epub_cover(book)

    by_href = _toc_titles(book)
    chapters: list[Chapter] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        name = item.get_name()
        html = item.get_content().decode("utf-8", errors="ignore")
        text = _html_text(html)
        if len(text) < MIN_CHAPTER_CHARS:
            continue
        title_guess = by_href.get(_norm_href(name)) or _heading_title(html) or Path(name).stem
        if is_skippable_title(title_guess) and len(text) < 2000:
            continue
        chapters.append(Chapter(title=_unique_title(title_guess, chapters), text=text))

    if not chapters:
        raise ValueError("No readable chapters found in this EPUB.")
    return Book(
        title=title,
        author=author,
        chapters=chapters,
        cover_bytes=cover,
        cover_mime=mime,
        source_kind="epub",
    )


def extract_pdf(path: Path) -> Book:
    reader = PdfReader(str(path))
    info = reader.metadata or {}
    title = str(getattr(info, "title", None) or path.stem)
    author = str(getattr(info, "author", None) or "Unknown")
    pages = [clean_text(page.extract_text() or "") for page in reader.pages]
    joined = "\n\n".join(page for page in pages if page)
    if len(joined) < 400:
        raise ValueError(
            "This PDF has almost no extractable text. It is probably a scan. OCR is not in v1."
        )

    chapters = _pdf_chapters(pages)
    cover = _pdf_cover(reader)
    warning = ""
    if len(joined) < 80 * max(len(reader.pages), 1):
        warning = "Text layer looks thin. Page furniture may get spoken."
    return Book(
        title=title,
        author=author,
        chapters=chapters,
        cover_bytes=cover,
        cover_mime="image/jpeg",
        source_kind="pdf",
        warning=warning,
    )


def _dc(book: epub.EpubBook, field: str) -> str:
    values = book.get_metadata("DC", field)
    if not values:
        return ""
    return str(values[0][0]).strip()


def _html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return clean_text(soup.get_text("\n"))


def _heading_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(["h1", "h2", "h3"])
    if heading:
        return clean_text(heading.get_text(" "))
    return ""


def _toc_titles(book: epub.EpubBook) -> dict[str, str]:
    titles: dict[str, str] = {}

    def walk(entries) -> None:
        for entry in entries or []:
            if isinstance(entry, tuple) and len(entry) == 2:
                walk(entry[1])
                entry = entry[0]
            href = getattr(entry, "href", None) or getattr(entry, "file_name", None)
            title = getattr(entry, "title", None)
            if href and title:
                titles[_norm_href(str(href))] = str(title).strip()

    walk(book.toc)
    return titles


def _norm_href(href: str) -> str:
    href = href.split("#", 1)[0]
    return href.lstrip("./")


def _epub_cover(book: epub.EpubBook) -> tuple[bytes | None, str]:
    for item in book.get_items_of_type(ITEM_COVER):
        return item.get_content(), _mime_from_name(item.get_name())
    for item in book.get_items_of_type(ITEM_IMAGE):
        name = item.get_name().lower()
        if "cover" in name:
            return item.get_content(), _mime_from_name(item.get_name())
    return None, "image/jpeg"


def _mime_from_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def _pdf_cover(reader: PdfReader) -> bytes | None:
    if not reader.pages:
        return None
    try:
        page = reader.pages[0]
        if not page.images:
            return None
        image = page.images[0]
        data = image.data
        return bytes(data) if data else None
    except Exception:
        return None


def _pdf_chapters(pages: list[str]) -> list[Chapter]:
    current_title = "Chapter 1"
    buf: list[str] = []
    chapters: list[Chapter] = []

    def flush() -> None:
        nonlocal buf, current_title
        text = clean_text("\n".join(buf))
        buf = []
        if len(text) < MIN_CHAPTER_CHARS:
            return
        chapters.append(Chapter(title=_unique_title(current_title, chapters), text=text))

    for page in pages:
        if not page:
            continue
        lines = page.splitlines()
        if lines and looks_like_chapter_heading(lines[0]) and buf:
            flush()
            current_title = lines[0].strip()
            buf.append("\n".join(lines[1:]))
        else:
            buf.append(page)
    flush()

    if chapters:
        return chapters

    blob = clean_text("\n\n".join(pages))
    size = 9000
    pieces = [blob[i : i + size] for i in range(0, len(blob), size)]
    return [
        Chapter(title=f"Part {index + 1}", text=piece)
        for index, piece in enumerate(pieces)
        if len(piece) >= MIN_CHAPTER_CHARS
    ]


def _unique_title(title: str, existing: list[Chapter]) -> str:
    base = re.sub(r"\s+", " ", title).strip() or "Chapter"
    used = {chapter.title for chapter in existing}
    if base not in used:
        return base
    n = 2
    while f"{base} ({n})" in used:
        n += 1
    return f"{base} ({n})"
