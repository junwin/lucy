"""Tests for GenerateSvgHandler — validation and sanitization."""

from __future__ import annotations

import json
import pytest

from src.handlers.generate_svg_handler import (
    GenerateSvgHandler,
    GenerateSvgInput,
    SvgSanitizer,
    ALLOWED_ELEMENTS,
    MAX_SVG_CHARS,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def handler():
    """Create a handler instance with a minimal mock config."""
    from unittest.mock import MagicMock
    mock_config = MagicMock()
    return GenerateSvgHandler(mock_config)


@pytest.fixture
def sanitizer():
    return SvgSanitizer()


# ── Input validation ─────────────────────────────────────────────────────

class TestInputValidation:
    def test_valid_minimal_input(self):
        """Minimal valid input should validate."""
        inp = GenerateSvgInput.model_validate({
            "svg_code": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        })
        assert inp.svg_code == "<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        assert inp.width == 400  # default
        assert inp.height == 200  # default

    def test_missing_svg_code_rejected(self):
        """svg_code is required."""
        with pytest.raises(Exception):
            GenerateSvgInput.model_validate({})

    def test_width_below_min_rejected(self):
        with pytest.raises(Exception):
            GenerateSvgInput.model_validate({
                "svg_code": "<svg></svg>",
                "width": 10,
            })

    def test_width_above_max_rejected(self):
        with pytest.raises(Exception):
            GenerateSvgInput.model_validate({
                "svg_code": "<svg></svg>",
                "width": 2000,
            })

    def test_height_below_min_rejected(self):
        with pytest.raises(Exception):
            GenerateSvgInput.model_validate({
                "svg_code": "<svg></svg>",
                "height": 10,
            })

    def test_height_above_max_rejected(self):
        with pytest.raises(Exception):
            GenerateSvgInput.model_validate({
                "svg_code": "<svg></svg>",
                "height": 2000,
            })


# ── Sanitization ─────────────────────────────────────────────────────────

class TestSanitization:
    def test_valid_svg_passes_through(self, sanitizer):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="red"/>
</svg>"""
        result = sanitizer.sanitize(svg)
        assert "circle" in result
        assert 'fill="red"' in result

    def test_script_element_stripped(self, sanitizer):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert('xss')</script>
  <rect x="0" y="0" width="10" height="10"/>
</svg>"""
        result = sanitizer.sanitize(svg)
        assert "script" not in result
        assert "alert" not in result
        assert "rect" in result

    def test_onclick_handler_stripped(self, sanitizer):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" onclick="evil()" fill="blue"/>
</svg>"""
        result = sanitizer.sanitize(svg)
        assert "onclick" not in result
        assert "fill" in result  # allowed attr preserved

    def test_foreignObject_stripped(self, sanitizer):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
  <foreignObject><body>bad</body></foreignObject>
  <rect x="0" y="0" width="10" height="10"/>
</svg>"""
        result = sanitizer.sanitize(svg)
        assert "foreignObject" not in result
        assert "bad" not in result
        assert "rect" in result

    def test_onerror_stripped(self, sanitizer):
        svg = """<svg xmlns="http://www.w3.org/2000/svg">
  <image href="x" onerror="alert(1)"/>
</svg>"""
        result = sanitizer.sanitize(svg)
        assert "onerror" not in result

    def test_namespace_preserved(self, sanitizer):
        svg = """<svg viewBox="0 0 100 100">
  <rect width="100" height="100"/>
</svg>"""
        result = sanitizer.sanitize(svg)
        # Should be valid SVG output
        assert "svg" in result
        assert "rect" in result

    def test_all_whitelisted_elements_preserved(self, sanitizer):
        """All allowed elements should survive sanitization."""
        for elem in sorted(ALLOWED_ELEMENTS):
            if elem == "svg":
                continue  # root handled separately
            svg = f'<svg xmlns="http://www.w3.org/2000/svg"><{elem}/></svg>'
            result = sanitizer.sanitize(svg)
            assert elem in result, f"Allowed element '{elem}' was stripped"

    def test_disallowed_elements_stripped(self, sanitizer):
        """Known-dangerous elements should be removed."""
        disallowed = ["script", "foreignObject", "iframe", "embed", "object"]
        for elem in disallowed:
            svg = f'<svg xmlns="http://www.w3.org/2000/svg"><{elem}>bad</{elem}><rect/></svg>'
            result = sanitizer.sanitize(svg)
            assert elem not in result, f"Disallowed element '{elem}' was not stripped"


# ── Error cases ──────────────────────────────────────────────────────────

class TestParseErrors:
    def test_malformed_xml_rejected(self):
        import xml.etree.ElementTree as ET
        with pytest.raises(ET.ParseError):
            ET.fromstring("not xml <<<")

    def test_non_svg_root_rejected(self, sanitizer):
        with pytest.raises(ValueError, match="Root element must be <svg>"):
            sanitizer.sanitize("<html><body>not svg</body></html>")


# ── Handler execute ──────────────────────────────────────────────────────

class TestHandlerExecute:
    def test_successful_generation(self, handler):
        result = handler.execute({
            "svg_code": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="red"/>
</svg>""",
            "description": "A red circle",
            "width": 400,
            "height": 200,
        })
        assert result["ok"] is True
        assert "svg" in result
        assert result["svg"]["markup"]  # non-empty
        assert result["svg"]["alt"] == "A red circle"
        assert result["svg"]["width"] == 400
        assert result["svg"]["height"] == 200
        # Should also have image key for non-streaming fallback
        assert "image" in result
        assert result["image"]["url"].startswith("data:image/svg+xml;base64,")

    def test_empty_svg_code_rejected(self, handler):
        result = handler.execute({"svg_code": "   "})
        assert result["ok"] is False
        assert "empty" in result["error"].lower()

    def test_oversized_svg_rejected(self, handler):
        huge = "<svg>" + (" " * (MAX_SVG_CHARS + 10)) + "</svg>"
        result = handler.execute({"svg_code": huge})
        assert result["ok"] is False
        assert "too large" in result["error"].lower()

    def test_invalid_svg_xml_rejected(self, handler):
        result = handler.execute({"svg_code": "not xml <<<"})
        assert result["ok"] is False
        assert "Invalid SVG" in result["error"] or "well-formed" in result["error"].lower()

    def test_xss_sanitized_in_handler(self, handler):
        result = handler.execute({
            "svg_code": """<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert('xss')</script>
  <circle cx="50" cy="50" r="40" fill="green"/>
</svg>""",
        })
        assert result["ok"] is True
        assert "script" not in result["svg"]["markup"]
        assert "alert" not in result["svg"]["markup"]
        assert "circle" in result["svg"]["markup"]

    def test_result_is_valid_json(self, handler):
        result = handler.execute({
            "svg_code": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        })
        # Handler result must be JSON-serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["ok"] is True
