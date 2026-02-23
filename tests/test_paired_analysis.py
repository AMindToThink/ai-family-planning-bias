"""Tests for paired_analysis.py — paired statistical tests on synthetic data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.paired_analysis import (
    compute_differences_from_english,
    run_paired_ttests_vs_english,
    run_repeated_measures_anova,
    run_two_way_anova_language_income,
)


def _make_paired_df(n_groups: int = 20, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic paired DataFrame.

    Each prompt group has scores for all languages, with an embedded
    language bias to test detection.
    """
    rng = np.random.default_rng(seed)

    languages = [
        "English", "Spanish", "Mandarin", "Hindi", "Arabic", "French",
        "Yoruba", "Tagalog", "Swahili", "Portuguese", "Japanese",
        "Korean", "Russian", "German",
    ]

    # Embedded biases: some languages get higher/lower scores
    lang_bias = {
        "English": 0.0,
        "Spanish": -0.1,
        "Mandarin": -0.5,
        "Hindi": -0.6,
        "Arabic": -0.4,
        "French": 0.1,
        "Yoruba": -0.7,
        "Tagalog": -0.3,
        "Swahili": -0.8,
        "Portuguese": -0.1,
        "Japanese": -0.2,
        "Korean": -0.3,
        "Russian": -0.2,
        "German": 0.05,
    }

    income_levels = ["low", "middle", "high"]
    education_levels = ["no_degree", "high_school", "bachelors", "graduate"]

    rows = []
    for g in range(n_groups):
        group_id = f"base_{g:03d}"
        group_base = 3.0 + rng.normal(0, 0.3)  # per-prompt random effect
        income = income_levels[g % len(income_levels)]
        education = education_levels[g % len(education_levels)]

        for lang in languages:
            score = group_base + lang_bias[lang] + rng.normal(0, 0.2)
            score = max(1.0, min(5.0, score))
            rows.append({
                "model": "test/model",
                "scorer": "encouragement_scorer",
                "score": round(score, 2),
                "sample_id": f"{group_id}_{lang.lower()}",
                "prompt_group_id": group_id,
                "language": lang,
                "income_level": income,
                "education_level": education,
                "education_explicit": g % 2 == 0,
                "income_explicit": (g // 2) % 2 == 0,
                "age_group": "prime",
                "relationship_status": "married",
                "health_status": "healthy",
                "existing_children": "none",
            })

    return pd.DataFrame(rows)


class TestComputeDifferencesFromEnglish:
    def test_returns_diff_column(self) -> None:
        df = _make_paired_df(n_groups=5)
        result = compute_differences_from_english(df)
        assert "diff" in result.columns
        assert "english_score" in result.columns

    def test_english_diff_is_zero(self) -> None:
        df = _make_paired_df(n_groups=5)
        result = compute_differences_from_english(df)
        english_diffs = result[result["language"] == "English"]["diff"]
        assert (english_diffs == 0.0).all()

    def test_diff_sign_matches_bias(self) -> None:
        """Languages with negative bias should have negative mean diff."""
        df = _make_paired_df(n_groups=50, seed=42)
        result = compute_differences_from_english(df)
        # Swahili has -0.8 bias, should have negative mean diff
        swahili_mean_diff = result[result["language"] == "Swahili"]["diff"].mean()
        assert swahili_mean_diff < -0.3, f"Expected negative diff for Swahili, got {swahili_mean_diff}"

    def test_raises_without_group_id(self) -> None:
        df = pd.DataFrame({"language": ["English"], "score": [3.0]})
        with pytest.raises(ValueError, match="prompt_group_id"):
            compute_differences_from_english(df)


class TestPairedTtestsVsEnglish:
    def test_returns_results_for_non_english(self) -> None:
        df = _make_paired_df(n_groups=10)
        results = run_paired_ttests_vs_english(df)
        assert "English" not in results
        assert len(results) == 13  # 14 languages minus English

    def test_detects_large_bias(self) -> None:
        """Swahili (bias=-0.8) should be significant with enough data."""
        df = _make_paired_df(n_groups=30)
        results = run_paired_ttests_vs_english(df)
        assert results["Swahili"]["significant"], (
            f"Expected Swahili to be significant, p_corrected={results['Swahili']['p_corrected']}"
        )

    def test_bonferroni_correction_applied(self) -> None:
        df = _make_paired_df(n_groups=10)
        results = run_paired_ttests_vs_english(df)
        for lang, res in results.items():
            assert res["p_corrected"] >= res["p_value"], (
                f"{lang}: corrected p ({res['p_corrected']}) < raw p ({res['p_value']})"
            )
            assert res["p_corrected"] <= 1.0

    def test_result_structure(self) -> None:
        df = _make_paired_df(n_groups=5)
        results = run_paired_ttests_vs_english(df)
        for lang, res in results.items():
            assert "t_stat" in res
            assert "p_value" in res
            assert "p_corrected" in res
            assert "mean_diff" in res
            assert "ci95_lower" in res
            assert "ci95_upper" in res
            assert "n_pairs" in res
            assert "significant" in res
            assert res["ci95_lower"] <= res["mean_diff"] <= res["ci95_upper"]

    def test_ci_contains_mean(self) -> None:
        df = _make_paired_df(n_groups=20)
        results = run_paired_ttests_vs_english(df)
        for lang, res in results.items():
            assert res["ci95_lower"] <= res["mean_diff"] <= res["ci95_upper"]


class TestRepeatedMeasuresAnova:
    def test_detects_language_effect(self) -> None:
        """With embedded language biases, ANOVA should be significant."""
        df = _make_paired_df(n_groups=20)
        result = run_repeated_measures_anova(df)
        assert "error" not in result
        assert result["p_value"] < 0.05, f"Expected significant, got p={result['p_value']}"

    def test_returns_f_and_p(self) -> None:
        df = _make_paired_df(n_groups=10)
        result = run_repeated_measures_anova(df)
        assert "f_stat" in result
        assert "p_value" in result

    def test_insufficient_data(self) -> None:
        df = pd.DataFrame({
            "score": [3.0],
            "language": ["English"],
            "prompt_group_id": ["base_000"],
        })
        result = run_repeated_measures_anova(df)
        assert "error" in result


class TestTwoWayAnovaLanguageIncome:
    def test_returns_interaction_term(self) -> None:
        df = _make_paired_df(n_groups=30)
        result = run_two_way_anova_language_income(df)
        assert "error" not in result
        # Should have language, income, and interaction terms
        keys = list(result.keys())
        assert any("language" in k for k in keys)
        assert any("income" in k for k in keys)

    def test_missing_income_column(self) -> None:
        df = _make_paired_df(n_groups=5)
        df = df.drop(columns=["income_level"])
        result = run_two_way_anova_language_income(df)
        assert "error" in result
