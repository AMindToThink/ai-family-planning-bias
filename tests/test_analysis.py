"""Tests for analysis.py — statistical functions on synthetic DataFrames."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis import (
    run_anova_per_dimension,
    run_explicit_implicit_ttests,
    run_ols_regression,
)


def _make_synthetic_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic DataFrame resembling real eval output."""
    rng = np.random.default_rng(seed)

    languages = ["English", "Spanish", "Mandarin", "Hindi", "Arabic", "French"]
    income_levels = ["low", "middle", "high"]
    education_levels = ["no_degree", "high_school", "associates", "bachelors", "graduate"]
    age_groups = ["young", "prime", "older"]
    relationship_statuses = ["single", "partnered", "married"]
    health_statuses = ["chronic", "healthy"]
    children_counts = ["none", "one_two", "three_plus"]

    rows = []
    for i in range(n):
        lang = languages[i % len(languages)]
        # Add slight bias by language to test detection
        lang_bias = {"English": 0.3, "Spanish": -0.2, "Mandarin": -0.1}.get(lang, 0.0)
        income = income_levels[i % len(income_levels)]
        income_bias = {"low": -0.4, "middle": 0.0, "high": 0.3}[income]

        base_score = 3.0 + lang_bias + income_bias + rng.normal(0, 0.5)
        score = max(1.0, min(5.0, base_score))

        rows.append(
            {
                "model": "test/model",
                "scorer": "encouragement_scorer",
                "score": round(score, 2),
                "sample_id": f"sample_{i:03d}",
                "language": lang,
                "income_level": income,
                "income_explicit": i % 2 == 0,
                "education_level": education_levels[i % len(education_levels)],
                "education_explicit": (i // 2) % 2 == 0,
                "age_group": age_groups[i % len(age_groups)],
                "age_explicit": (i // 3) % 2 == 0,
                "relationship_status": relationship_statuses[i % len(relationship_statuses)],
                "relationship_explicit": (i // 4) % 2 == 0,
                "health_status": health_statuses[i % len(health_statuses)],
                "health_explicit": (i // 5) % 2 == 0,
                "existing_children": children_counts[i % len(children_counts)],
                "children_explicit": (i // 6) % 2 == 0,
                "explanation": "Test explanation.",
            }
        )

    return pd.DataFrame(rows)


class TestAnovaPerDimension:
    def test_returns_results_for_all_dimensions(self) -> None:
        df = _make_synthetic_df()
        results = run_anova_per_dimension(df)
        expected_dims = {"language", "income", "education", "age", "relationship", "health", "children"}
        assert set(results.keys()) == expected_dims

    def test_income_is_significant(self) -> None:
        """With embedded income bias, ANOVA should detect it."""
        df = _make_synthetic_df(n=300)
        results = run_anova_per_dimension(df)
        assert results["income"]["p_value"] < 0.05, (
            f"Expected significant income effect, got p={results['income']['p_value']}"
        )

    def test_result_structure(self) -> None:
        df = _make_synthetic_df()
        results = run_anova_per_dimension(df)
        for dim, res in results.items():
            assert "f_stat" in res
            assert "p_value" in res
            assert "n_groups" in res
            assert isinstance(res["f_stat"], float)
            assert isinstance(res["p_value"], float)
            assert 0 <= res["p_value"] <= 1

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["score", "language"])
        results = run_anova_per_dimension(df)
        assert len(results) == 0

    def test_single_group_skipped(self) -> None:
        df = _make_synthetic_df(n=50)
        df["language"] = "English"  # collapse to single group
        results = run_anova_per_dimension(df)
        assert "language" not in results


class TestExplicitImplicitTtests:
    def test_returns_all_dimensions(self) -> None:
        df = _make_synthetic_df()
        results = run_explicit_implicit_ttests(df)
        expected = {"income", "education", "age", "relationship", "health", "children"}
        assert set(results.keys()) == expected

    def test_result_structure(self) -> None:
        df = _make_synthetic_df()
        results = run_explicit_implicit_ttests(df)
        for dim, res in results.items():
            assert "t_stat" in res
            assert "p_value" in res
            assert "mean_explicit" in res
            assert "mean_implicit" in res
            assert "n_explicit" in res
            assert "n_implicit" in res
            assert res["n_explicit"] > 0
            assert res["n_implicit"] > 0

    def test_means_are_reasonable(self) -> None:
        df = _make_synthetic_df()
        results = run_explicit_implicit_ttests(df)
        for dim, res in results.items():
            assert 1 <= res["mean_explicit"] <= 5
            assert 1 <= res["mean_implicit"] <= 5


class TestOlsRegression:
    def test_returns_summary_string(self) -> None:
        df = _make_synthetic_df(n=200)
        summary = run_ols_regression(df)
        assert isinstance(summary, str)
        assert "OLS" in summary or "Regression" in summary or "coef" in summary

    def test_insufficient_data_message(self) -> None:
        df = pd.DataFrame({"score": [3.0]})
        result = run_ols_regression(df)
        assert "Insufficient" in result

    def test_includes_language_coefficients(self) -> None:
        df = _make_synthetic_df(n=200)
        summary = run_ols_regression(df)
        # Should include language as a predictor
        assert "language" in summary.lower() or "C(language)" in summary
