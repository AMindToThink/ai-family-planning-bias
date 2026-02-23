"""Analysis pipeline for the language-focused paired experiment.

Leverages the paired design (same prompt translated into all languages) to
run within-subjects statistical tests that isolate language as the causal
variable. Demographics (income, education, etc.) serve as covariates.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from statsmodels.formula.api import ols as ols_formula
from statsmodels.stats.anova import anova_lm

from src.analysis import (
    load_eval_logs,
    logs_to_dataframe,
    plot_language_income_heatmap,
    plot_mean_by_language,
)


# ---------------------------------------------------------------------------
# Paired statistical tests
# ---------------------------------------------------------------------------


def compute_differences_from_english(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-prompt-group score differences relative to English.

    Returns a DataFrame with columns: prompt_group_id, language, score,
    english_score, diff (= score - english_score).
    """
    if "prompt_group_id" not in df.columns:
        raise ValueError("DataFrame must contain 'prompt_group_id' column")

    english = df[df["language"] == "English"][["prompt_group_id", "score"]].rename(
        columns={"score": "english_score"}
    )
    merged = df.merge(english, on="prompt_group_id", how="inner")
    merged["diff"] = merged["score"] - merged["english_score"]
    return merged


def run_paired_ttests_vs_english(df: pd.DataFrame) -> dict[str, dict]:
    """Run paired t-tests comparing each language to English.

    Uses prompt_group_id to match pairs. Applies Bonferroni correction
    for 13 comparisons (14 languages minus English).

    Returns dict mapping language to {t_stat, p_value, p_corrected,
    mean_diff, ci95_lower, ci95_upper, n_pairs, significant}.
    """
    merged = compute_differences_from_english(df)
    non_english = [lang for lang in merged["language"].unique() if lang != "English"]
    n_comparisons = len(non_english)

    results = {}
    for lang in sorted(non_english):
        lang_diffs = merged[merged["language"] == lang]["diff"].dropna()
        if len(lang_diffs) < 2:
            continue

        t_stat, p_value = stats.ttest_1samp(lang_diffs, 0)
        p_corrected = min(p_value * n_comparisons, 1.0)  # Bonferroni
        mean_diff = float(lang_diffs.mean())
        sem = float(lang_diffs.sem())
        ci95 = sem * 1.96

        results[lang] = {
            "t_stat": float(t_stat),
            "p_value": float(p_value),
            "p_corrected": float(p_corrected),
            "mean_diff": mean_diff,
            "ci95_lower": mean_diff - ci95,
            "ci95_upper": mean_diff + ci95,
            "n_pairs": len(lang_diffs),
            "significant": p_corrected < 0.05,
        }

    return results


def run_repeated_measures_anova(df: pd.DataFrame) -> dict:
    """Run repeated-measures-style ANOVA on language with prompt_group as block.

    Uses a two-way ANOVA with prompt_group_id as a blocking factor:
    score ~ C(language) + C(prompt_group_id)

    Returns dict with {f_stat, p_value, df_language, df_residual}.
    """
    clean = df.dropna(subset=["score"])
    if clean["language"].nunique() < 2 or clean["prompt_group_id"].nunique() < 2:
        return {"f_stat": float("nan"), "p_value": float("nan"), "error": "Insufficient data"}

    model = ols_formula("score ~ C(language) + C(prompt_group_id)", data=clean).fit()
    anova_table = anova_lm(model, typ=2)

    # Extract language row
    lang_row = None
    for idx in anova_table.index:
        if "language" in str(idx).lower():
            lang_row = anova_table.loc[idx]
            break

    if lang_row is None:
        return {"f_stat": float("nan"), "p_value": float("nan"), "error": "Language not in model"}

    return {
        "f_stat": float(lang_row["F"]),
        "p_value": float(lang_row["PR(>F)"]),
        "df_language": float(lang_row["df"]),
        "sum_sq_language": float(lang_row["sum_sq"]),
    }


def run_two_way_anova_language_income(df: pd.DataFrame) -> dict:
    """Run two-way ANOVA: score ~ C(language) * C(income_level).

    Returns dict with F and p for language, income, and their interaction.
    """
    clean = df.dropna(subset=["score"])
    if "income_level" not in clean.columns:
        return {"error": "No income_level column"}

    model = ols_formula("score ~ C(language) * C(income_level)", data=clean).fit()
    anova_table = anova_lm(model, typ=2)

    results = {}
    for idx in anova_table.index:
        idx_str = str(idx)
        if idx_str == "Residual":
            continue
        key = idx_str.replace("C(", "").replace(")", "").replace(":", "_x_")
        results[key] = {
            "f_stat": float(anova_table.loc[idx, "F"]),
            "p_value": float(anova_table.loc[idx, "PR(>F)"]),
        }

    return results


def run_paired_ols_regression(df: pd.DataFrame) -> str:
    """OLS regression with demographics as covariates.

    score ~ C(language) + C(income_level) + C(education_level) + C(age_group)
            + C(existing_children) + C(relationship_status) + C(health_status)
    """
    formula = (
        "score ~ C(language) + C(income_level) + C(education_level) + "
        "C(age_group) + C(existing_children) + C(relationship_status) + "
        "C(health_status)"
    )
    clean = df.dropna(subset=["score"])
    if len(clean) < 10:
        return "Insufficient data for regression."

    model = ols_formula(formula, data=clean).fit()
    return str(model.summary())


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------


def plot_paired_differences(
    ttest_results: dict[str, dict], output_dir: Path
) -> None:
    """Plot mean score difference from English for each language with 95% CI.

    This is the key chart: positive = more encouraging than English,
    negative = more discouraging.
    """
    if not ttest_results:
        return

    languages = sorted(ttest_results.keys(), key=lambda k: ttest_results[k]["mean_diff"])
    means = [ttest_results[lang]["mean_diff"] for lang in languages]
    ci_lower = [ttest_results[lang]["ci95_lower"] for lang in languages]
    ci_upper = [ttest_results[lang]["ci95_upper"] for lang in languages]
    significant = [ttest_results[lang]["significant"] for lang in languages]

    errors_lower = [m - lo for m, lo in zip(means, ci_lower)]
    errors_upper = [hi - m for m, hi in zip(means, ci_upper)]

    colors = ["#c0392b" if sig else "#95a5a6" for sig in significant]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(
        languages,
        means,
        xerr=[errors_lower, errors_upper],
        color=colors,
        capsize=3,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.axvline(x=0, color="black", linestyle="-", linewidth=1)
    ax.set_xlabel("Mean Score Difference from English (Bonferroni-corrected)")
    ax.set_title("Language Bias: Score Difference vs English Baseline")

    # Add legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="#c0392b", label="Significant (p < 0.05)"),
        Patch(facecolor="#95a5a6", label="Not significant"),
    ]
    ax.legend(handles=legend_elements, loc="lower right")

    plt.tight_layout()
    fig.savefig(output_dir / "paired_differences.png", dpi=150)
    plt.close(fig)


def plot_spaghetti(df: pd.DataFrame, output_dir: Path) -> None:
    """Spaghetti plot: each prompt_group_id as a line across languages.

    Shows within-prompt variation to visualize how consistent the
    language effect is across different demographic profiles.
    """
    if "prompt_group_id" not in df.columns:
        return

    pivot = df.pivot_table(
        values="score", index="prompt_group_id", columns="language", aggfunc="mean"
    )
    if pivot.empty:
        return

    # Order languages by mean score
    lang_order = pivot.mean().sort_values().index.tolist()
    pivot = pivot[lang_order]

    fig, ax = plt.subplots(figsize=(14, 7))

    # Plot individual lines with low alpha
    for group_id in pivot.index:
        ax.plot(
            range(len(lang_order)),
            pivot.loc[group_id],
            color="#2c3e50",
            alpha=0.15,
            linewidth=0.8,
        )

    # Plot mean line
    mean_scores = pivot.mean()
    ax.plot(
        range(len(lang_order)),
        mean_scores,
        color="#e74c3c",
        linewidth=2.5,
        label="Mean across prompts",
        zorder=5,
    )

    ax.set_xticks(range(len(lang_order)))
    ax.set_xticklabels(lang_order, rotation=45, ha="right")
    ax.set_ylabel("Encouragement Score (1-5)")
    ax.set_title("Per-Prompt Score Across Languages (Spaghetti Plot)")
    ax.axhline(y=3.0, color="gray", linestyle="--", linewidth=0.8, label="Neutral (3.0)")
    ax.set_ylim(0.5, 5.5)
    ax.legend()
    plt.tight_layout()
    fig.savefig(output_dir / "spaghetti_plot.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_paired_report(
    df: pd.DataFrame,
    ttest_results: dict[str, dict],
    rm_anova: dict,
    two_way_anova: dict,
    ols_summary: str,
    output_dir: Path,
) -> None:
    """Generate markdown report for the paired experiment."""
    lines = [
        "# Language-Focused Family Planning Bias Report (Paired Design)\n",
        "## Experiment Design\n",
        "Each base prompt was translated into all 14 languages, creating matched",
        "pairs. Score differences within each prompt group are attributable to",
        "language alone.\n",
        f"**Total samples analyzed:** {len(df)}",
        f"**Unique prompt groups:** {df['prompt_group_id'].nunique() if 'prompt_group_id' in df.columns else 'N/A'}",
        f"**Languages:** {df['language'].nunique() if 'language' in df.columns else 'N/A'}",
        f"**Model(s) evaluated:** {', '.join(df['model'].unique()) if 'model' in df.columns else 'N/A'}",
        f"**Overall mean score:** {df['score'].mean():.3f} (SD={df['score'].std():.3f})\n",
    ]

    # Mean by language table
    lines.append("## Mean Score by Language\n")
    lines.append("![Mean by Language](mean_by_language.png)\n")
    if "language" in df.columns:
        lang_stats = (
            df.groupby("language")["score"]
            .agg(["mean", "std", "count"])
            .sort_values("mean")
            .reset_index()
        )
        lines.append("| Language | Mean | SD | N |")
        lines.append("|----------|------|----|---|")
        for _, row in lang_stats.iterrows():
            lines.append(
                f"| {row['language']} | {row['mean']:.3f} | {row['std']:.3f} | {int(row['count'])} |"
            )
        lines.append("")

    # Repeated-measures ANOVA
    lines.append("## Repeated-Measures ANOVA (Language Effect)\n")
    if "error" in rm_anova:
        lines.append(f"Error: {rm_anova['error']}\n")
    else:
        sig = "Yes" if rm_anova["p_value"] < 0.05 else "No"
        lines.append(f"- **F-statistic:** {rm_anova['f_stat']:.3f}")
        lines.append(f"- **p-value:** {rm_anova['p_value']:.6f}")
        lines.append(f"- **Significant (p < 0.05):** {sig}\n")

    # Paired differences
    lines.append("## Paired Differences from English (KEY RESULT)\n")
    lines.append("![Paired Differences](paired_differences.png)\n")
    lines.append(
        "| Language | Mean Diff | 95% CI | t-stat | p (raw) | p (Bonferroni) | Sig? |"
    )
    lines.append(
        "|----------|-----------|--------|--------|---------|----------------|------|"
    )
    for lang, res in sorted(ttest_results.items(), key=lambda x: x[1]["mean_diff"]):
        sig = "Yes" if res["significant"] else "No"
        lines.append(
            f"| {lang} | {res['mean_diff']:+.3f} | "
            f"[{res['ci95_lower']:+.3f}, {res['ci95_upper']:+.3f}] | "
            f"{res['t_stat']:.3f} | {res['p_value']:.4f} | "
            f"{res['p_corrected']:.4f} | {sig} |"
        )
    lines.append("")

    # Spaghetti plot
    lines.append("## Per-Prompt Variation Across Languages\n")
    lines.append("![Spaghetti Plot](spaghetti_plot.png)\n")

    # Two-way ANOVA
    lines.append("## Two-Way ANOVA: Language × Income\n")
    lines.append("![Language × Income Heatmap](language_income_heatmap.png)\n")
    if "error" in two_way_anova:
        lines.append(f"Error: {two_way_anova['error']}\n")
    else:
        lines.append("| Factor | F-statistic | p-value | Significant |")
        lines.append("|--------|-------------|---------|-------------|")
        for factor, res in sorted(two_way_anova.items()):
            sig = "Yes" if res["p_value"] < 0.05 else "No"
            lines.append(f"| {factor} | {res['f_stat']:.3f} | {res['p_value']:.4f} | {sig} |")
        lines.append("")

    # OLS
    lines.append("## OLS Regression Summary\n")
    lines.append("```")
    lines.append(ols_summary)
    lines.append("```\n")

    report_path = output_dir / "paired_report.md"
    report_path.write_text("\n".join(lines))
    print(f"Report written to {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_paired_analysis(log_dir: str, output_dir: str) -> None:
    """Full paired analysis pipeline."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("Loading eval logs...")
    logs = load_eval_logs(log_dir)
    if not logs:
        print(f"No successful eval logs found in {log_dir}")
        return

    print(f"Loaded {len(logs)} log(s).")
    df = logs_to_dataframe(logs)
    if df.empty:
        print("No scored samples found.")
        return

    print(f"DataFrame has {len(df)} rows.")

    # Check for paired design
    if "prompt_group_id" not in df.columns:
        print("WARNING: No prompt_group_id in data. Is this a paired dataset?")
        print("Falling back to unpaired analysis.")

    # Save raw data
    df.to_csv(output_path / "scores.csv", index=False)

    # Visualizations (reused)
    print("Generating visualizations...")
    if "language" in df.columns:
        plot_mean_by_language(df, output_path)
        if "income_level" in df.columns:
            plot_language_income_heatmap(df, output_path)

    # Paired statistical tests
    print("Running paired statistical tests...")
    ttest_results = run_paired_ttests_vs_english(df)
    rm_anova = run_repeated_measures_anova(df)
    two_way_anova = run_two_way_anova_language_income(df)
    ols_summary = run_paired_ols_regression(df)

    # Paired visualizations
    plot_paired_differences(ttest_results, output_path)
    if "prompt_group_id" in df.columns:
        plot_spaghetti(df, output_path)

    # Report
    print("Generating paired report...")
    generate_paired_report(df, ttest_results, rm_anova, two_way_anova, ols_summary, output_path)

    print("Paired analysis complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze paired family planning bias eval results"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs/",
        help="Directory containing Inspect eval logs",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/",
        help="Directory for output charts and report",
    )
    args = parser.parse_args()
    run_paired_analysis(args.log_dir, args.output_dir)


if __name__ == "__main__":
    main()
