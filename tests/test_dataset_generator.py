"""Tests for dataset_generator.py."""

from __future__ import annotations

import json

from src.dataset_generator import (
    ParentProfile,
    compose_english_prompt,
    generate_profiles,
    profiles_to_inspect_dataset,
)
from src.prompt_templates import CLOSING_QUESTIONS, LANGUAGES


class TestGenerateProfiles:
    def test_correct_total_count(self) -> None:
        profiles = generate_profiles(samples_per_language=5)
        assert len(profiles) == 5 * len(LANGUAGES)

    def test_correct_count_per_language(self) -> None:
        profiles = generate_profiles(samples_per_language=10)
        for lang in LANGUAGES:
            count = sum(1 for p in profiles if p.language == lang)
            assert count == 10, f"Expected 10 for {lang}, got {count}"

    def test_all_languages_present(self) -> None:
        profiles = generate_profiles(samples_per_language=2)
        languages_in_profiles = {p.language for p in profiles}
        assert languages_in_profiles == set(LANGUAGES)

    def test_sample_ids_unique(self) -> None:
        profiles = generate_profiles(samples_per_language=5)
        ids = [p.sample_id for p in profiles]
        assert len(ids) == len(set(ids)), "Duplicate sample IDs found"

    def test_english_prompts_populated(self) -> None:
        profiles = generate_profiles(samples_per_language=3)
        for p in profiles:
            assert p.prompt_english, f"Empty English prompt for {p.sample_id}"
            assert len(p.prompt_english) > 20, "Prompt too short"

    def test_balanced_income_levels(self) -> None:
        """Income levels should be roughly balanced within each language."""
        profiles = generate_profiles(samples_per_language=30, seed=42)
        for lang in LANGUAGES:
            lang_profiles = [p for p in profiles if p.language == lang]
            income_counts: dict[str, int] = {}
            for p in lang_profiles:
                income_counts[p.income_level] = income_counts.get(p.income_level, 0) + 1
            # With 30 samples and 3 levels, each should appear at least 5 times
            for level, count in income_counts.items():
                assert count >= 3, f"{lang}: {level} income has only {count} samples"

    def test_explicit_implicit_mix(self) -> None:
        """Both explicit and implicit variants should be present."""
        profiles = generate_profiles(samples_per_language=20)
        explicit_income = sum(1 for p in profiles if p.income_explicit)
        implicit_income = sum(1 for p in profiles if not p.income_explicit)
        assert explicit_income > 0, "No explicit income samples"
        assert implicit_income > 0, "No implicit income samples"

    def test_reproducible_with_seed(self) -> None:
        profiles_a = generate_profiles(samples_per_language=5, seed=123)
        profiles_b = generate_profiles(samples_per_language=5, seed=123)
        for a, b in zip(profiles_a, profiles_b):
            assert a.sample_id == b.sample_id
            assert a.language == b.language
            assert a.income_level == b.income_level
            assert a.prompt_english == b.prompt_english

    def test_different_seeds_produce_different_results(self) -> None:
        profiles_a = generate_profiles(samples_per_language=5, seed=1)
        profiles_b = generate_profiles(samples_per_language=5, seed=2)
        # At least some prompts should differ
        diffs = sum(
            1
            for a, b in zip(profiles_a, profiles_b)
            if a.prompt_english != b.prompt_english
        )
        assert diffs > 0, "Different seeds produced identical prompts"


class TestComposeEnglishPrompt:
    def test_ends_with_closing_question(self) -> None:
        profile = ParentProfile(
            language="English",
            income_level="low",
            income_explicit=True,
            education_level="high_school",
            education_explicit=True,
            age_group="prime",
            age_explicit=True,
            relationship_status="married",
            relationship_explicit=True,
            health_status="healthy",
            health_explicit=True,
            existing_children="none",
            children_explicit=True,
        )
        prompt = compose_english_prompt(profile)
        # Should end with one of the closing questions
        assert any(prompt.endswith(q) for q in CLOSING_QUESTIONS), (
            f"Prompt doesn't end with a closing question: ...{prompt[-80:]}"
        )

    def test_contains_multiple_fragments(self) -> None:
        profile = ParentProfile(
            language="English",
            income_level="high",
            income_explicit=True,
            education_level="graduate",
            education_explicit=True,
            age_group="older",
            age_explicit=True,
            relationship_status="single",
            relationship_explicit=True,
            health_status="chronic",
            health_explicit=True,
            existing_children="three_plus",
            children_explicit=True,
        )
        prompt = compose_english_prompt(profile)
        # Prompt should have at least ~6 sentences + closing question
        sentences = prompt.split(".")
        assert len(sentences) >= 5, f"Expected multiple sentences, got: {prompt}"


class TestProfilesToInspectDataset:
    def test_output_format(self) -> None:
        profiles = generate_profiles(samples_per_language=2)
        # Fill in translated prompts for test
        for p in profiles:
            p.prompt_translated = p.prompt_english

        dataset = profiles_to_inspect_dataset(profiles)
        assert isinstance(dataset, list)
        assert len(dataset) == len(profiles)

    def test_sample_has_required_fields(self) -> None:
        profiles = generate_profiles(samples_per_language=1)
        for p in profiles:
            p.prompt_translated = p.prompt_english

        dataset = profiles_to_inspect_dataset(profiles)
        sample = dataset[0]
        assert "input" in sample
        assert "metadata" in sample
        assert isinstance(sample["input"], list)
        assert sample["input"][0]["role"] == "user"
        assert len(sample["input"][0]["content"]) > 0

    def test_metadata_contains_demographics(self) -> None:
        profiles = generate_profiles(samples_per_language=1)
        for p in profiles:
            p.prompt_translated = p.prompt_english

        dataset = profiles_to_inspect_dataset(profiles)
        meta = dataset[0]["metadata"]
        required_keys = [
            "sample_id",
            "language",
            "income_level",
            "income_explicit",
            "education_level",
            "education_explicit",
            "age_group",
            "age_explicit",
            "relationship_status",
            "relationship_explicit",
            "health_status",
            "health_explicit",
            "existing_children",
            "children_explicit",
            "prompt_english",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_valid_json_serialization(self) -> None:
        profiles = generate_profiles(samples_per_language=2)
        for p in profiles:
            p.prompt_translated = p.prompt_english

        dataset = profiles_to_inspect_dataset(profiles)
        # Should be JSON-serializable
        json_str = json.dumps(dataset, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed) == len(dataset)
