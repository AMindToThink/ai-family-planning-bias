"""Statistical analysis and visualization pipeline for family planning bias evaluation.

Loads Inspect eval logs, builds a DataFrame of scores × demographics, and runs:
- Mean encouragement by language (bar chart with 95% CI)
- One-way ANOVA per demographic dimension
- OLS regression
- Explicit vs. implicit t-tests
- Language × income interaction heatmap
- Summary markdown report
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log
from scipy import stats
from statsmodels.formula.api import ols as ols_formula


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_eval_logs(log_dir: str) -> list[EvalLog]:
    """Read all successful eval logs from a directory."""
    log_files = list_eval_logs(log_dir)
    logs = []
    for log_file in log_files:
        log = read_eval_log(log_file)
        if log.status == "success":
            logs.append(log)
    return logs


def logs_to_dataframe(logs: list[EvalLog]) -> pd.DataFrame:
    """Convert eval logs to a flat DataFrame with scores and metadata."""
    rows: list[dict] = []
    for log in logs:
        model = log.eval.model
        if log.samples is None:
            continue
        for sample in log.samples:
            if sample.scores is None:
                continue
            # Get the encouragement score
            for scorer_name, score_obj in sample.scores.items():
                row: dict = {
                    "model": model,
                    "scorer": scorer_name,
                    "score": float(score_obj.value) if score_obj.value is not None else None,
                    "explanation": score_obj.explanation or "",
                    "sample_id": sample.id,
                }
                # Add all metadata fields
                if sample.metadata:
                    row.update(sample.metadata)
                rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Ensure score is numeric
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------


def plot_mean_by_language(df: pd.DataFrame, output_dir: Path) -> None:
    """Horizontal bar chart of mean encouragement score by language with 95% CI."""
    lang_stats = df.groupby("language")["score"].agg(["mean", "sem", "count"]).reset_index()
    lang_stats["ci95"] = lang_stats["sem"] * 1.96
    lang_stats = lang_stats.sort_values("mean")

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(
        lang_stats["language"],
        lang_stats["mean"],
        xerr=lang_stats["ci95"],
        color=sns.color_palette("coolwarm", len(lang_stats)),
        capsize=3,
    )
    ax.axvline(x=3.0, color="black", linestyle="--", linewidth=1, label="Neutral (3.0)")
    ax.set_xlabel("Mean Encouragement Score (1=Discourage, 5=Encourage)")
    ax.set_title("Mean Encouragement Score by Language")
    ax.set_xlim(1, 5)
    ax.legend()
    plt.tight_layout()
    fig.savefig(output_dir / "mean_by_language.png", dpi=150)
    plt.close(fig)


def plot_language_income_heatmap(df: pd.DataFrame, output_dir: Path) -> None:
    """Heatmap of mean score by language × income level."""
    pivot = df.pivot_table(values="score", index="language", columns="income_level", aggfunc="mean")

    # Reorder columns
    col_order = ["low", "middle", "high"]
    pivot = pivot.reindex(columns=[c for c in col_order if c in pivot.columns])

    fig, ax = plt.subplots(figsize=(8, 10))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=3.0,
        vmin=1,
        vmax=5,
        ax=ax,
    )
    ax.set_title("Mean Encouragement Score: Language × Income")
    ax.set_ylabel("Language")
    ax.set_xlabel("Income Level")
    plt.tight_layout()
    fig.savefig(output_dir / "language_income_heatmap.png", dpi=150)
    plt.close(fig)


def plot_explicit_vs_implicit(df: pd.DataFrame, output_dir: Path) -> None:
    """Grouped bar chart comparing explicit vs implicit scores per dimension."""
    dimensions = ["income", "education", "age", "relationship", "health", "children"]
    explicit_cols = [f"{d}_explicit" for d in dimensions]

    records = []
    for dim, col in zip(dimensions, explicit_cols):
        if col not in df.columns:
            continue
        for explicit_val in [True, False]:
            subset = df[df[col] == explicit_val]["score"]
            records.append(
                {
                    "dimension": dim,
                    "encoding": "Explicit" if explicit_val else "Implicit",
                    "mean_score": subset.mean(),
                    "sem": subset.sem(),
                }
            )

    plot_df = pd.DataFrame(records)
    if plot_df.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(dimensions))
    width = 0.35

    explicit_data = plot_df[plot_df["encoding"] == "Explicit"]
    implicit_data = plot_df[plot_df["encoding"] == "Implicit"]

    ax.bar(x - width / 2, explicit_data["mean_score"], width, label="Explicit", color="#4C72B0")
    ax.bar(x + width / 2, implicit_data["mean_score"], width, label="Implicit", color="#DD8452")

    ax.set_ylabel("Mean Encouragement Score")
    ax.set_title("Explicit vs Implicit Demographic Encoding")
    ax.set_xticks(x)
    ax.set_xticklabels(dimensions, rotation=45)
    ax.axhline(y=3.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_ylim(1, 5)
    ax.legend()
    plt.tight_layout()
    fig.savefig(output_dir / "explicit_vs_implicit.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------


def run_anova_per_dimension(df: pd.DataFrame) -> dict[str, dict]:
    """Run one-way ANOVA for each demographic dimension.

    Returns dict mapping dimension name to {f_stat, p_value, groups}.
    """
    dimension_columns = {
        "language": "language",
        "income": "income_level",
        "education": "education_level",
        "age": "age_group",
        "relationship": "relationship_status",
        "health": "health_status",
        "children": "existing_children",
    }

    results = {}
    for dim_name, col in dimension_columns.items():
        if col not in df.columns:
            continue
        groups = [group["score"].dropna().values for _, group in df.groupby(col)]
        groups = [g for g in groups if len(g) >= 2]
        if len(groups) < 2:
            continue
        f_stat, p_value = stats.f_oneway(*groups)
        results[dim_name] = {
            "f_stat": float(f_stat),
            "p_value": float(p_value),
            "n_groups": len(groups),
        }

    return results


def run_ols_regression(df: pd.DataFrame) -> str:
    """Run OLS regression of score on all demographic dimensions.

    Returns the summary as a string.
    """
    # Build formula — treat categoricals with C()
    formula = (
        "score ~ C(language) + C(income_level) + C(education_level) + "
        "C(age_group) + C(existing_children) + C(relationship_status) + "
        "C(health_status) + income_explicit + education_explicit"
    )
    # Drop rows with missing scores
    clean_df = df.dropna(subset=["score"])
    if len(clean_df) < 10:
        return "Insufficient data for regression."

    model = ols_formula(formula, data=clean_df).fit()
    return str(model.summary())


def run_explicit_implicit_ttests(df: pd.DataFrame) -> dict[str, dict]:
    """Run independent t-tests comparing explicit vs implicit for each dimension.

    Returns dict mapping dimension to {t_stat, p_value, mean_explicit, mean_implicit}.
    """
    dimensions = ["income", "education", "age", "relationship", "health", "children"]
    results = {}
    for dim in dimensions:
        col = f"{dim}_explicit"
        if col not in df.columns:
            continue
        explicit_scores = df[df[col] == True]["score"].dropna()  # noqa: E712
        implicit_scores = df[df[col] == False]["score"].dropna()  # noqa: E712
        if len(explicit_scores) < 2 or len(implicit_scores) < 2:
            continue
        t_stat, p_value = stats.ttest_ind(explicit_scores, implicit_scores)
        results[dim] = {
            "t_stat": float(t_stat),
            "p_value": float(p_value),
            "mean_explicit": float(explicit_scores.mean()),
            "mean_implicit": float(implicit_scores.mean()),
            "n_explicit": len(explicit_scores),
            "n_implicit": len(implicit_scores),
        }
    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    df: pd.DataFrame,
    anova_results: dict[str, dict],
    ols_summary: str,
    ttest_results: dict[str, dict],
    output_dir: Path,
) -> None:
    """Generate a markdown summary report."""
    lines = [
        "# Family Planning Bias Evaluation Report\n",
        f"**Total samples analyzed:** {len(df)}\n",
        f"**Languages:** {df['language'].nunique() if 'language' in df.columns else 'N/A'}\n",
        f"**Models evaluated:** {', '.join(df['model'].unique()) if 'model' in df.columns else 'N/A'}\n",
        f"**Overall mean score:** {df['score'].mean():.3f} (SD={df['score'].std():.3f})\n",
        "",
        "## Mean Score by Language\n",
        "![Mean by Language](mean_by_language.png)\n",
    ]

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

    # ANOVA results
    lines.append("## One-Way ANOVA by Demographic Dimension\n")
    lines.append("| Dimension | F-statistic | p-value | Significant (p<0.05) |")
    lines.append("|-----------|-------------|---------|---------------------|")
    for dim, res in sorted(anova_results.items()):
        sig = "Yes" if res["p_value"] < 0.05 else "No"
        lines.append(f"| {dim} | {res['f_stat']:.3f} | {res['p_value']:.4f} | {sig} |")
    lines.append("")

    # Explicit vs implicit t-tests
    lines.append("## Explicit vs Implicit Encoding t-tests\n")
    lines.append("![Explicit vs Implicit](explicit_vs_implicit.png)\n")
    lines.append(
        "| Dimension | Mean (Explicit) | Mean (Implicit) | t-stat | p-value | Significant |"
    )
    lines.append("|-----------|----------------|-----------------|--------|---------|-------------|")
    for dim, res in sorted(ttest_results.items()):
        sig = "Yes" if res["p_value"] < 0.05 else "No"
        lines.append(
            f"| {dim} | {res['mean_explicit']:.3f} | {res['mean_implicit']:.3f} | "
            f"{res['t_stat']:.3f} | {res['p_value']:.4f} | {sig} |"
        )
    lines.append("")

    # Language × income heatmap
    lines.append("## Language × Income Interaction\n")
    lines.append("![Language × Income Heatmap](language_income_heatmap.png)\n")

    # OLS regression
    lines.append("## OLS Regression Summary\n")
    lines.append("```")
    lines.append(ols_summary)
    lines.append("```\n")

    report_path = output_dir / "report.md"
    report_path.write_text("\n".join(lines))
    print(f"Report written to {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_analysis(log_dir: str, output_dir: str) -> None:
    """Full analysis pipeline."""
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

    # Save raw data
    df.to_csv(output_path / "scores.csv", index=False)

    # Visualizations
    print("Generating visualizations...")
    if "language" in df.columns:
        plot_mean_by_language(df, output_path)
        if "income_level" in df.columns:
            plot_language_income_heatmap(df, output_path)
    plot_explicit_vs_implicit(df, output_path)

    # Statistical tests
    print("Running statistical tests...")
    anova_results = run_anova_per_dimension(df)
    ols_summary = run_ols_regression(df)
    ttest_results = run_explicit_implicit_ttests(df)

    # Report
    print("Generating report...")
    generate_report(df, anova_results, ols_summary, ttest_results, output_path)

    print("Analysis complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze family planning bias eval results")
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
    run_analysis(args.log_dir, args.output_dir)


if __name__ == "__main__":
    main()
