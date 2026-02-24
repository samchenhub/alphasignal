"""
Unit tests for the LLM analysis pipeline (Gemini Flash).
All external API calls are mocked — no real API key needed.
"""
import pytest
from unittest.mock import patch
from app.analysis.claude_analyzer import _analyze, _is_relevant


class TestIsRelevant:
    """Tests for Stage 1: relevance filter."""

    def test_returns_true_when_relevant(self):
        with patch("app.analysis.claude_analyzer._call_groq_filter", return_value='{"relevant": true}'):
            result = _is_relevant("Apple Q4 earnings beat estimates", "content", ["AAPL"])
        assert result is True

    def test_returns_false_when_not_relevant(self):
        with patch("app.analysis.claude_analyzer._call_groq_filter", return_value='{"relevant": false}'):
            result = _is_relevant("Local sports news", "content", ["AAPL"])
        assert result is False

    def test_defaults_to_true_on_invalid_json(self):
        """When parse fails, default to relevant (conservative — don't miss signals)."""
        with patch("app.analysis.claude_analyzer._call_groq_filter", return_value="not json"):
            result = _is_relevant("title", "content", ["AAPL"])
        assert result is True

    def test_defaults_to_true_on_api_error(self):
        with patch("app.analysis.claude_analyzer._call_groq_filter", side_effect=Exception("API error")):
            result = _is_relevant("title", "content", ["AAPL"])
        assert result is True


class TestAnalyze:
    """Tests for Stage 2: structured extraction."""

    VALID_RESPONSE = """{
        "relevant_tickers": ["AAPL"],
        "sentiment_score": -0.82,
        "confidence": 0.91,
        "entities": {"companies": ["Apple"], "tickers": ["AAPL"], "people": []},
        "summary": "Apple cut Q4 guidance.",
        "key_events": [{"type": "revenue_guidance_down", "description": "Q4 cut 8%"}]
    }"""

    def test_parses_valid_json(self):
        with patch("app.analysis.claude_analyzer._call_groq_analysis", return_value=self.VALID_RESPONSE):
            result = _analyze("Apple guidance cut", "content", ["AAPL"], "US")
        assert result is not None
        assert result["sentiment_score"] == pytest.approx(-0.82)
        assert result["confidence"] == pytest.approx(0.91)
        assert "AAPL" in result["relevant_tickers"]

    def test_strips_markdown_code_fences(self):
        """LLMs often wrap JSON in ```json ... ``` blocks."""
        fenced = f"```json\n{self.VALID_RESPONSE}\n```"
        with patch("app.analysis.claude_analyzer._call_groq_analysis", return_value=fenced):
            result = _analyze("Apple guidance cut", "content", ["AAPL"], "US")
        assert result is not None
        assert result["sentiment_score"] == pytest.approx(-0.82)

    def test_strips_plain_code_fences(self):
        """Also handle ``` without language tag."""
        fenced = f"```\n{self.VALID_RESPONSE}\n```"
        with patch("app.analysis.claude_analyzer._call_groq_analysis", return_value=fenced):
            result = _analyze("title", "content", ["AAPL"], "US")
        assert result is not None

    def test_returns_none_on_invalid_json(self):
        with patch("app.analysis.claude_analyzer._call_groq_analysis", return_value="Here is my analysis: blah blah"):
            result = _analyze("title", "content", ["AAPL"], "US")
        assert result is None

    def test_returns_none_on_empty_response(self):
        with patch("app.analysis.claude_analyzer._call_groq_analysis", return_value=""):
            result = _analyze("title", "content", ["AAPL"], "US")
        assert result is None

    def test_returns_none_on_api_error(self):
        with patch("app.analysis.claude_analyzer._call_groq_analysis", side_effect=Exception("rate limit")):
            result = _analyze("title", "content", ["AAPL"], "US")
        assert result is None

    def test_handles_positive_sentiment(self):
        positive = self.VALID_RESPONSE.replace("-0.82", "0.95")
        with patch("app.analysis.claude_analyzer._call_groq_analysis", return_value=positive):
            result = _analyze("title", "content", ["AAPL"], "US")
        assert result["sentiment_score"] == pytest.approx(0.95)
