"""Paired dataset generation for language-focused bias evaluation.

Generates N base English prompts with stratified demographics, then translates
each identical prompt into all 14 languages. This paired/within-subjects design
isolates language as the causal variable — any score difference between languages
for the same prompt_group_id is attributable to language alone.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

from src.dataset_generator import (
    ParentProfile,
    _build_stratification_pool,
    compose_english_prompt,
    translate_prompt,
)
from src.prompt_templates import LANGUAGES


def generate_paired_profiles(
    n_base: int = 30,
    languages: list[str] | None = None,
    seed: int = 42,
) -> list[ParentProfile]:
    """Generate paired profiles: N base prompts × all languages.

    Each base prompt is composed once in English, then replicated across all
    languages with the same prompt_group_id. Demographics are stratified
    across the base prompts.

    Args:
        n_base: Number of base English prompts to generate.
        languages: Override the default 14 languages.
        seed: Random seed for reproducibility.

    Returns:
        List of ParentProfile with English prompts composed (not yet translated).
        Length = n_base × len(languages).
    """
    random.seed(seed)
    if languages is None:
        languages = LANGUAGES

    pool = _build_stratification_pool()
    sampled_combos = random.sample(pool, min(n_base, len(pool)))
    # If n_base > pool size, extend with random choices
    while len(sampled_combos) < n_base:
        sampled_combos.append(random.choice(pool))

    profiles: list[ParentProfile] = []

    for base_idx, combo in enumerate(sampled_combos):
        group_id = f"base_{base_idx:03d}"

        # Compose ONE English prompt for this demographic combo
        base_profile = ParentProfile(
            language="English",
            income_level=str(combo["income_level"]),
            income_explicit=bool(combo["income_explicit"]),
            education_level=str(combo["education_level"]),
            education_explicit=bool(combo["education_explicit"]),
            age_group=str(combo["age_group"]),
            age_explicit=bool(combo["age_explicit"]),
            relationship_status=str(combo["relationship_status"]),
            relationship_explicit=bool(combo["relationship_explicit"]),
            health_status=str(combo["health_status"]),
            health_explicit=bool(combo["health_explicit"]),
            existing_children=str(combo["existing_children"]),
            children_explicit=bool(combo["children_explicit"]),
        )
        english_prompt = compose_english_prompt(base_profile)

        # Clone into all languages
        for lang in languages:
            profile = ParentProfile(
                language=lang,
                income_level=base_profile.income_level,
                income_explicit=base_profile.income_explicit,
                education_level=base_profile.education_level,
                education_explicit=base_profile.education_explicit,
                age_group=base_profile.age_group,
                age_explicit=base_profile.age_explicit,
                relationship_status=base_profile.relationship_status,
                relationship_explicit=base_profile.relationship_explicit,
                health_status=base_profile.health_status,
                health_explicit=base_profile.health_explicit,
                existing_children=base_profile.existing_children,
                children_explicit=base_profile.children_explicit,
                prompt_english=english_prompt,
                sample_id=f"{group_id}_{lang.lower()}",
                metadata={"prompt_group_id": group_id},
            )
            profiles.append(profile)

    return profiles


def translate_paired_profiles(
    profiles: list[ParentProfile],
    client: OpenAI,
    model: str = "gpt-4o",
) -> list[ParentProfile]:
    """Translate all paired profiles, skipping English ones.

    Args:
        profiles: List of profiles with English prompts composed.
        client: OpenAI client instance.
        model: Model for translation.

    Returns:
        Same list with prompt_translated filled in.
    """
    total = len(profiles)
    for i, profile in enumerate(profiles):
        if profile.language == "English":
            profile.prompt_translated = profile.prompt_english
        else:
            profile.prompt_translated = translate_prompt(
                profile.prompt_english, profile.language, client, model
            )
        if (i + 1) % 10 == 0 or i + 1 == total:
            print(f"  Translated {i + 1}/{total} profiles...", file=sys.stderr)

    return profiles


def paired_profiles_to_inspect_dataset(profiles: list[ParentProfile]) -> list[dict]:
    """Convert paired profiles to Inspect AI JSON dataset format.

    Each sample includes prompt_group_id in metadata for paired analysis.
    """
    samples = []
    for profile in profiles:
        metadata = {
            "sample_id": profile.sample_id,
            "prompt_group_id": profile.metadata.get("prompt_group_id", ""),
            "language": profile.language,
            "income_level": profile.income_level,
            "income_explicit": profile.income_explicit,
            "education_level": profile.education_level,
            "education_explicit": profile.education_explicit,
            "age_group": profile.age_group,
            "age_explicit": profile.age_explicit,
            "relationship_status": profile.relationship_status,
            "relationship_explicit": profile.relationship_explicit,
            "health_status": profile.health_status,
            "health_explicit": profile.health_explicit,
            "existing_children": profile.existing_children,
            "children_explicit": profile.children_explicit,
            "prompt_english": profile.prompt_english,
        }
        samples.append(
            {
                "input": [{"role": "user", "content": profile.prompt_translated}],
                "metadata": metadata,
            }
        )
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate paired family planning bias dataset (language-focused)"
    )
    parser.add_argument(
        "--n-base",
        type=int,
        default=30,
        help="Number of base English prompts (default: 30, total = n_base × 14 languages)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/paired_dataset.json",
        help="Output file path",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--translation-model",
        type=str,
        default="gpt-4o",
        help="Model for translation (default: gpt-4o)",
    )
    parser.add_argument(
        "--skip-translation",
        action="store_true",
        help="Skip LLM translation (use English for all)",
    )
    args = parser.parse_args()

    print(
        f"Generating {args.n_base} base prompts × {len(LANGUAGES)} languages "
        f"= {args.n_base * len(LANGUAGES)} total samples...",
        file=sys.stderr,
    )
    profiles = generate_paired_profiles(n_base=args.n_base, seed=args.seed)
    print(f"Generated {len(profiles)} paired profiles.", file=sys.stderr)

    if args.skip_translation:
        print("Skipping translation — using English prompts for all.", file=sys.stderr)
        for p in profiles:
            p.prompt_translated = p.prompt_english
    else:
        print("Translating prompts...", file=sys.stderr)
        client = OpenAI()
        profiles = translate_paired_profiles(profiles, client, model=args.translation_model)

    dataset = paired_profiles_to_inspect_dataset(profiles)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(dataset)} samples to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
