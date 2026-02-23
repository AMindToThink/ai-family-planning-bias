"""Tests for paired_dataset_generator.py."""

from __future__ import annotations

import json

from src.paired_dataset_generator import (
    generate_paired_profiles,
    paired_profiles_to_inspect_dataset,
)
from src.prompt_templates import LANGUAGES


class TestGeneratePairedProfiles:
    def test_correct_total_count(self) -> None:
        profiles = generate_paired_profiles(n_base=5)
        assert len(profiles) == 5 * len(LANGUAGES)

    def test_correct_total_count_large(self) -> None:
        profiles = generate_paired_profiles(n_base=30)
        assert len(profiles) == 30 * len(LANGUAGES)

    def test_all_languages_per_group(self) -> None:
        profiles = generate_paired_profiles(n_base=3)
        # Group by prompt_group_id
        groups: dict[str, set[str]] = {}
        for p in profiles:
            gid = p.metadata["prompt_group_id"]
            groups.setdefault(gid, set()).add(p.language)

        assert len(groups) == 3
        for gid, langs in groups.items():
            assert langs == set(LANGUAGES), f"Group {gid} missing languages: {set(LANGUAGES) - langs}"

    def test_english_prompt_identical_within_group(self) -> None:
        """All profiles in a group should share the same English prompt."""
        profiles = generate_paired_profiles(n_base=5)
        groups: dict[str, list[str]] = {}
        for p in profiles:
            gid = p.metadata["prompt_group_id"]
            groups.setdefault(gid, []).append(p.prompt_english)

        for gid, prompts in groups.items():
            assert len(set(prompts)) == 1, (
                f"Group {gid} has {len(set(prompts))} distinct English prompts"
            )

    def test_unique_sample_ids(self) -> None:
        profiles = generate_paired_profiles(n_base=5)
        ids = [p.sample_id for p in profiles]
        assert len(ids) == len(set(ids))

    def test_prompt_group_ids_correct_format(self) -> None:
        profiles = generate_paired_profiles(n_base=3)
        expected_groups = {"base_000", "base_001", "base_002"}
        actual_groups = {p.metadata["prompt_group_id"] for p in profiles}
        assert actual_groups == expected_groups

    def test_demographics_vary_across_groups(self) -> None:
        """Different groups should have different demographic combos."""
        profiles = generate_paired_profiles(n_base=10)
        # Check income levels across groups (only look at English to avoid duplication)
        english = [p for p in profiles if p.language == "English"]
        income_levels = {p.income_level for p in english}
        # With 10 groups, we should see multiple income levels
        assert len(income_levels) >= 2, f"Only one income level across 10 groups: {income_levels}"

    def test_reproducible_with_seed(self) -> None:
        a = generate_paired_profiles(n_base=5, seed=99)
        b = generate_paired_profiles(n_base=5, seed=99)
        for pa, pb in zip(a, b):
            assert pa.sample_id == pb.sample_id
            assert pa.prompt_english == pb.prompt_english
            assert pa.language == pb.language

    def test_different_seeds_produce_different_results(self) -> None:
        a = generate_paired_profiles(n_base=5, seed=1)
        b = generate_paired_profiles(n_base=5, seed=2)
        english_a = [p.prompt_english for p in a if p.language == "English"]
        english_b = [p.prompt_english for p in b if p.language == "English"]
        assert english_a != english_b


class TestPairedProfilesToInspectDataset:
    def test_output_count(self) -> None:
        profiles = generate_paired_profiles(n_base=2)
        for p in profiles:
            p.prompt_translated = p.prompt_english
        dataset = paired_profiles_to_inspect_dataset(profiles)
        assert len(dataset) == 2 * len(LANGUAGES)

    def test_metadata_contains_prompt_group_id(self) -> None:
        profiles = generate_paired_profiles(n_base=2)
        for p in profiles:
            p.prompt_translated = p.prompt_english
        dataset = paired_profiles_to_inspect_dataset(profiles)
        for sample in dataset:
            assert "prompt_group_id" in sample["metadata"]
            assert sample["metadata"]["prompt_group_id"].startswith("base_")

    def test_metadata_contains_all_demographics(self) -> None:
        profiles = generate_paired_profiles(n_base=1)
        for p in profiles:
            p.prompt_translated = p.prompt_english
        dataset = paired_profiles_to_inspect_dataset(profiles)
        required_keys = [
            "prompt_group_id",
            "language",
            "income_level",
            "education_level",
            "age_group",
            "relationship_status",
            "health_status",
            "existing_children",
        ]
        for sample in dataset:
            for key in required_keys:
                assert key in sample["metadata"], f"Missing: {key}"

    def test_valid_json(self) -> None:
        profiles = generate_paired_profiles(n_base=2)
        for p in profiles:
            p.prompt_translated = p.prompt_english
        dataset = paired_profiles_to_inspect_dataset(profiles)
        json_str = json.dumps(dataset, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed) == len(dataset)
