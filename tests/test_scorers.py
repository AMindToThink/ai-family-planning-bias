"""Tests for scorers.py — judge response parsing and score validation."""

from __future__ import annotations

import pytest

from src.scorers import parse_judge_response


class TestParseJudgeResponse:
    def test_valid_json(self) -> None:
        text = '{"score": 4, "reasoning": "The response was mildly encouraging."}'
        score, reasoning = parse_judge_response(text)
        assert score == 4
        assert "encouraging" in reasoning

    def test_json_with_markdown_code_block(self) -> None:
        text = '```json\n{"score": 2, "reasoning": "Discouraged the user."}\n```'
        score, reasoning = parse_judge_response(text)
        assert score == 2

    def test_json_with_code_block_no_lang(self) -> None:
        text = '```\n{"score": 5, "reasoning": "Very positive."}\n```'
        score, reasoning = parse_judge_response(text)
        assert score == 5

    def test_score_boundary_low(self) -> None:
        text = '{"score": 1, "reasoning": "Strongly discourages."}'
        score, _ = parse_judge_response(text)
        assert score == 1

    def test_score_boundary_high(self) -> None:
        text = '{"score": 5, "reasoning": "Strongly encourages."}'
        score, _ = parse_judge_response(text)
        assert score == 5

    def test_out_of_range_score_fallback(self) -> None:
        """Score of 0 or 6 should trigger fallback parsing."""
        text = '{"score": 0, "reasoning": "Invalid."}'
        score, reasoning = parse_judge_response(text)
        # Falls through to regex fallback, which looks for single digit
        # 0 is not in range 1-5, so should default to 3
        assert score == 3
        assert "PARSE FAILURE" in reasoning

    def test_malformed_json_with_extractable_score(self) -> None:
        text = 'I think the score should be {"score": 3, "reasoning": truncated'
        score, reasoning = parse_judge_response(text)
        assert score == 3
        assert "Parsed from malformed JSON" in reasoning

    def test_completely_unparseable(self) -> None:
        text = "I cannot evaluate this response. It seems fine overall."
        score, reasoning = parse_judge_response(text)
        assert score == 3  # default neutral
        assert "PARSE FAILURE" in reasoning

    def test_empty_string(self) -> None:
        score, reasoning = parse_judge_response("")
        assert score == 3
        assert "PARSE FAILURE" in reasoning

    def test_missing_reasoning_key(self) -> None:
        text = '{"score": 4}'
        score, reasoning = parse_judge_response(text)
        assert score == 4
        assert reasoning == ""  # empty but valid

    def test_string_score_value(self) -> None:
        """Score as string should still parse."""
        text = '{"score": "2", "reasoning": "Somewhat discouraging."}'
        score, reasoning = parse_judge_response(text)
        assert score == 2

    @pytest.mark.parametrize("score_val", [1, 2, 3, 4, 5])
    def test_all_valid_scores(self, score_val: int) -> None:
        text = f'{{"score": {score_val}, "reasoning": "test"}}'
        score, _ = parse_judge_response(text)
        assert score == score_val

    def test_extra_whitespace(self) -> None:
        text = '  \n  {"score": 3, "reasoning": "Balanced"}  \n  '
        score, _ = parse_judge_response(text)
        assert score == 3

    def test_score_with_extra_fields(self) -> None:
        text = '{"score": 4, "reasoning": "Good", "confidence": 0.9}'
        score, reasoning = parse_judge_response(text)
        assert score == 4
        assert reasoning == "Good"
