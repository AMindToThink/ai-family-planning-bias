"""Synthetic dataset generation for family planning bias evaluation.

Generates stratified ParentProfile samples across 14 languages, translating
English-composed prompts via LLM with cultural localization instructions.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from openai import OpenAI

from src.prompt_templates import (
    ALL_TEMPLATES,
    CLOSING_QUESTIONS,
    LANGUAGES,
    AgeGroup,
    EducationLevel,
    ExistingChildren,
    HealthStatus,
    IncomeLevel,
    RelationshipStatus,
)


@dataclass
class ParentProfile:
    """Demographic profile for a synthetic family-planning prompt."""

    language: str
    income_level: str
    income_explicit: bool
    education_level: str
    education_explicit: bool
    age_group: str
    age_explicit: bool
    relationship_status: str
    relationship_explicit: bool
    health_status: str
    health_explicit: bool
    existing_children: str
    children_explicit: bool
    prompt_english: str = ""
    prompt_translated: str = ""
    sample_id: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def _pick_template(dimension: str, level: str, explicit: bool) -> str:
    """Randomly choose a phrasing variant for the given dimension/level/explicitness."""
    key = (dimension, level, explicit)
    variants = ALL_TEMPLATES[key]
    return random.choice(variants)


def compose_english_prompt(profile: ParentProfile) -> str:
    """Assemble an English prompt from template fragments and a closing question."""
    fragments = [
        _pick_template("income", profile.income_level, profile.income_explicit),
        _pick_template("education", profile.education_level, profile.education_explicit),
        _pick_template("age", profile.age_group, profile.age_explicit),
        _pick_template("relationship", profile.relationship_status, profile.relationship_explicit),
        _pick_template("health", profile.health_status, profile.health_explicit),
        _pick_template("children", profile.existing_children, profile.children_explicit),
    ]
    random.shuffle(fragments)
    closing = random.choice(CLOSING_QUESTIONS)
    return " ".join(fragments) + " " + closing


def _build_stratification_pool() -> list[dict[str, str | bool]]:
    """Build a pool of demographic combinations for stratified sampling.

    Returns a list of dicts with dimension levels and explicit/implicit flags.
    We cycle through combinations to ensure balanced coverage.
    """
    income_levels = [e.value for e in IncomeLevel]
    education_levels = [e.value for e in EducationLevel]
    age_groups = [e.value for e in AgeGroup]
    relationship_statuses = [e.value for e in RelationshipStatus]
    health_statuses = [e.value for e in HealthStatus]
    children_counts = [e.value for e in ExistingChildren]

    pool: list[dict[str, str | bool]] = []

    # Create balanced combinations by cycling through levels
    # We need at least 30 per language, so generate enough combos
    combo_idx = 0
    while len(pool) < 100:  # generate plenty, we'll sample from this
        combo: dict[str, str | bool] = {
            "income_level": income_levels[combo_idx % len(income_levels)],
            "income_explicit": combo_idx % 2 == 0,
            "education_level": education_levels[combo_idx % len(education_levels)],
            "education_explicit": (combo_idx // 2) % 2 == 0,
            "age_group": age_groups[combo_idx % len(age_groups)],
            "age_explicit": (combo_idx // 3) % 2 == 0,
            "relationship_status": relationship_statuses[combo_idx % len(relationship_statuses)],
            "relationship_explicit": (combo_idx // 4) % 2 == 0,
            "health_status": health_statuses[combo_idx % len(health_statuses)],
            "health_explicit": (combo_idx // 5) % 2 == 0,
            "existing_children": children_counts[combo_idx % len(children_counts)],
            "children_explicit": (combo_idx // 6) % 2 == 0,
        }
        pool.append(combo)
        combo_idx += 1

    return pool


def generate_profiles(
    samples_per_language: int = 30,
    languages: list[str] | None = None,
    seed: int = 42,
) -> list[ParentProfile]:
    """Generate stratified ParentProfile instances across languages.

    Args:
        samples_per_language: Number of samples per language.
        languages: Override the default 14 languages.
        seed: Random seed for reproducibility.

    Returns:
        List of ParentProfile with English prompts composed (not yet translated).
    """
    random.seed(seed)
    if languages is None:
        languages = LANGUAGES

    pool = _build_stratification_pool()
    profiles: list[ParentProfile] = []

    for lang in languages:
        # Sample from stratification pool with replacement if needed
        sampled = random.choices(pool, k=samples_per_language)
        for i, combo in enumerate(sampled):
            profile = ParentProfile(
                language=lang,
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
                sample_id=f"{lang.lower()}_{i:03d}",
            )
            profile.prompt_english = compose_english_prompt(profile)
            profiles.append(profile)

    return profiles


TRANSLATION_SYSTEM_PROMPT = """You are a professional translator and cultural consultant. \
Translate the following English text into {language}.

IMPORTANT INSTRUCTIONS:
- Do NOT produce a literal word-for-word translation.
- Adapt cultural references: convert currencies to local equivalents, \
education systems to local norms, and place names to local analogues.
- Preserve the emotional tone and level of formality.
- The translated text should read as if it were originally written by \
a native {language} speaker in their cultural context.
- Return ONLY the translated text, nothing else."""


def translate_prompt(
    english_text: str,
    language: str,
    client: OpenAI,
    model: str = "gpt-4o",
) -> str:
    """Translate an English prompt via LLM with cultural localization.

    Args:
        english_text: The English prompt to translate.
        language: Target language name (e.g., "Spanish", "Mandarin").
        client: OpenAI client instance.
        model: Model to use for translation.

    Returns:
        Translated and culturally localized prompt text.
    """
    if language == "English":
        return english_text

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": TRANSLATION_SYSTEM_PROMPT.format(language=language),
            },
            {"role": "user", "content": english_text},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    return response.choices[0].message.content or english_text


def translate_all_profiles(
    profiles: list[ParentProfile],
    client: OpenAI,
    model: str = "gpt-4o",
) -> list[ParentProfile]:
    """Translate all profile prompts, skipping English ones.

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


def profiles_to_inspect_dataset(profiles: list[ParentProfile]) -> list[dict]:
    """Convert profiles to Inspect AI JSON dataset format.

    Each sample has an 'input' (the prompt text) and 'metadata' with
    all demographic fields for analysis.
    """
    samples = []
    for profile in profiles:
        metadata = {
            "sample_id": profile.sample_id,
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
    parser = argparse.ArgumentParser(description="Generate family planning bias dataset")
    parser.add_argument(
        "--samples-per-language",
        type=int,
        default=30,
        help="Number of samples per language (default: 30)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/family_planning_dataset.json",
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

    print(f"Generating {args.samples_per_language} samples per language...", file=sys.stderr)
    profiles = generate_profiles(
        samples_per_language=args.samples_per_language,
        seed=args.seed,
    )
    print(f"Generated {len(profiles)} profiles.", file=sys.stderr)

    if args.skip_translation:
        print("Skipping translation — using English prompts for all.", file=sys.stderr)
        for p in profiles:
            p.prompt_translated = p.prompt_english
    else:
        print("Translating prompts...", file=sys.stderr)
        client = OpenAI()
        profiles = translate_all_profiles(profiles, client, model=args.translation_model)

    dataset = profiles_to_inspect_dataset(profiles)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(dataset)} samples to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
