from pathlib import Path

from ebooklib import epub

from narrate.extract import extract_epub
from narrate.pipeline import preview_book


def _write_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("test-book")
    book.set_title("River Book")
    book.set_language("en")
    book.add_author("Edith Wren")
    one = epub.EpubHtml(title="One", file_name="one.xhtml", lang="en")
    one.content = "<html><body><h1>One</h1><p>" + ("Hello there. " * 40) + "</p></body></html>"
    two = epub.EpubHtml(title="Two", file_name="two.xhtml", lang="en")
    two.content = "<html><body><h1>Two</h1><p>" + ("Second chapter text. " * 40) + "</p></body></html>"
    nav = epub.EpubNav()
    ncx = epub.EpubNcx()
    book.add_item(one)
    book.add_item(two)
    book.add_item(nav)
    book.add_item(ncx)
    book.toc = (one, two)
    book.spine = ["nav", one, two]
    epub.write_epub(str(path), book)


def test_extract_epub_chapters(tmp_path: Path):
    path = tmp_path / "river.epub"
    _write_epub(path)
    book = extract_epub(path)
    assert book.title == "River Book"
    assert book.author == "Edith Wren"
    assert len(book.chapters) == 2
    assert book.chapters[0].title == "One"
    assert "Hello there" in book.chapters[0].text
    assert book.chars > 400


def test_preview_includes_cost(tmp_path: Path):
    path = tmp_path / "river.epub"
    _write_epub(path)
    preview = preview_book(path, "openai/gpt-4o-mini-tts-2025-12-15")
    assert preview["chapter_count"] == 2
    assert preview["estimated_usd"] >= 0
    assert preview["chunk_total"] >= 2
