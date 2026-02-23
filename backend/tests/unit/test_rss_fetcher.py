"""
Unit tests for RSS fetcher utilities.
These test pure functions that require no database or API access.
"""
import pytest
from app.ingestion.rss_fetcher import _clean_html, _url_hash


class TestUrlHash:
    def test_is_deterministic(self):
        url = "https://example.com/article/123"
        assert _url_hash(url) == _url_hash(url)

    def test_different_urls_produce_different_hashes(self):
        assert _url_hash("https://example.com/1") != _url_hash("https://example.com/2")

    def test_returns_64_char_hex_string(self):
        result = _url_hash("https://example.com")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


class TestCleanHtml:
    def test_strips_basic_tags(self):
        assert _clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_empty_string_returns_empty(self):
        assert _clean_html("") == ""

    def test_removes_script_tags(self):
        html = "<p>Content</p><script>alert('xss')</script>"
        result = _clean_html(html)
        assert "alert" not in result
        assert "Content" in result

    def test_removes_style_tags(self):
        html = "<style>body { color: red; }</style><p>Text</p>"
        result = _clean_html(html)
        assert "color" not in result
        assert "Text" in result

    def test_collapses_whitespace(self):
        html = "<p>Hello   World</p>"
        result = _clean_html(html)
        assert "  " not in result

    def test_plain_text_passthrough(self):
        result = _clean_html("No HTML here")
        assert result == "No HTML here"
