"""
tests/test_llm_client.py
Unit tests for agents/llm_client.py — specifically the JSON extractor.
No real API calls are made.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from agents.llm_client import extract_json


class TestExtractJson:
    def test_clean_json_object(self):
        raw = '{"code": "def f(): pass", "function_name": "f"}'
        data = extract_json(raw)
        assert data["function_name"] == "f"

    def test_json_wrapped_in_markdown_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        data = extract_json(raw)
        assert data["key"] == "value"

    def test_json_wrapped_in_plain_fence(self):
        raw = '```\n{"key": 42}\n```'
        data = extract_json(raw)
        assert data["key"] == 42

    def test_json_embedded_in_prose(self):
        raw = 'Here is the result: {"answer": true} done.'
        data = extract_json(raw)
        assert data["answer"] is True

    def test_raises_on_no_json(self):
        with pytest.raises(ValueError):
            extract_json("This is just plain text with no JSON.")

    def test_raises_on_malformed_json(self):
        with pytest.raises(ValueError):
            extract_json("{broken json: }")

    def test_nested_objects(self):
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        data = extract_json(raw)
        assert data["outer"]["inner"] == [1, 2, 3]

    def test_escaped_newlines_in_string(self):
        raw = '{"code": "def f():\\n    pass"}'
        data = extract_json(raw)
        assert "\\n" in data["code"] or "\n" in data["code"]

    def test_whitespace_stripped(self):
        raw = '   \n{"x": 1}\n   '
        data = extract_json(raw)
        assert data["x"] == 1
