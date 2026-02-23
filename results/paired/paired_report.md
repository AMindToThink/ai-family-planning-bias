# Language-Focused Family Planning Bias Report (Paired Design)

## Experiment Design

Each base prompt was translated into all 14 languages, creating matched
pairs. Score differences within each prompt group are attributable to
language alone.

**Total samples analyzed:** 420
**Unique prompt groups:** 30
**Languages:** 14
**Model(s) evaluated:** openai/gpt-4o
**Overall mean score:** 2.624 (SD=0.500)

## Mean Score by Language

![Mean by Language](mean_by_language.png)

| Language | Mean | SD | N |
|----------|------|----|---|
| Swahili | 2.467 | 0.507 | 30 |
| French | 2.567 | 0.504 | 30 |
| Hindi | 2.567 | 0.568 | 30 |
| English | 2.600 | 0.498 | 30 |
| German | 2.600 | 0.498 | 30 |
| Japanese | 2.600 | 0.498 | 30 |
| Korean | 2.600 | 0.498 | 30 |
| Tagalog | 2.600 | 0.498 | 30 |
| Mandarin | 2.633 | 0.490 | 30 |
| Spanish | 2.633 | 0.490 | 30 |
| Russian | 2.700 | 0.466 | 30 |
| Yoruba | 2.700 | 0.466 | 30 |
| Arabic | 2.733 | 0.583 | 30 |
| Portuguese | 2.733 | 0.450 | 30 |

## Repeated-Measures ANOVA (Language Effect)

- **F-statistic:** 1.994
- **p-value:** 0.020261
- **Significant (p < 0.05):** Yes

## Paired Differences from English (KEY RESULT)

![Paired Differences](paired_differences.png)

| Language | Mean Diff | 95% CI | t-stat | p (raw) | p (Bonferroni) | Sig? |
|----------|-----------|--------|--------|---------|----------------|------|
| Swahili | -0.133 | [-0.289, +0.022] | -1.682 | 0.1033 | 1.0000 | No |
| French | -0.033 | [-0.181, +0.115] | -0.441 | 0.6624 | 1.0000 | No |
| Hindi | -0.033 | [-0.209, +0.142] | -0.372 | 0.7122 | 1.0000 | No |
| German | +0.000 | [-0.094, +0.094] | 0.000 | 1.0000 | 1.0000 | No |
| Japanese | +0.000 | [-0.094, +0.094] | 0.000 | 1.0000 | 1.0000 | No |
| Korean | +0.000 | [-0.133, +0.133] | 0.000 | 1.0000 | 1.0000 | No |
| Tagalog | +0.000 | [-0.094, +0.094] | 0.000 | 1.0000 | 1.0000 | No |
| Mandarin | +0.033 | [-0.081, +0.148] | 0.571 | 0.5725 | 1.0000 | No |
| Spanish | +0.033 | [-0.081, +0.148] | 0.571 | 0.5725 | 1.0000 | No |
| Russian | +0.100 | [-0.009, +0.209] | 1.795 | 0.0831 | 1.0000 | No |
| Yoruba | +0.100 | [-0.072, +0.272] | 1.140 | 0.2638 | 1.0000 | No |
| Arabic | +0.133 | [+0.010, +0.257] | 2.112 | 0.0434 | 0.5642 | No |
| Portuguese | +0.133 | [+0.010, +0.257] | 2.112 | 0.0434 | 0.5642 | No |

## Per-Prompt Variation Across Languages

![Spaghetti Plot](spaghetti_plot.png)

## Two-Way ANOVA: Language × Income

![Language × Income Heatmap](language_income_heatmap.png)

| Factor | F-statistic | p-value | Significant |
|--------|-------------|---------|-------------|
| income_level | 295.316 | 0.0000 | Yes |
| language | 1.565 | 0.0928 | No |
| language_x_income_level | 1.006 | 0.4585 | No |

## OLS Regression Summary

```
                            OLS Regression Results                            
==============================================================================
Dep. Variable:                  score   R-squared:                       0.622
Model:                            OLS   Adj. R-squared:                  0.603
Method:                 Least Squares   F-statistic:                     32.82
Date:                Mon, 23 Feb 2026   Prob (F-statistic):           1.31e-71
Time:                        20:39:57   Log-Likelihood:                -99.693
No. Observations:                 420   AIC:                             241.4
Df Residuals:                     399   BIC:                             326.2
Df Model:                          20                                         
Covariance Type:            nonrobust                                         
=======================================================================================================
                                          coef    std err          t      P>|t|      [0.025      0.975]
-------------------------------------------------------------------------------------------------------
Intercept                               1.6947      0.048     34.967      0.000       1.599       1.790
C(language)[T.English]                 -0.1333      0.081     -1.641      0.102      -0.293       0.026
C(language)[T.French]                  -0.1667      0.081     -2.051      0.041      -0.326      -0.007
C(language)[T.German]                  -0.1333      0.081     -1.641      0.102      -0.293       0.026
C(language)[T.Hindi]                   -0.1667      0.081     -2.051      0.041      -0.326      -0.007
C(language)[T.Japanese]                -0.1333      0.081     -1.641      0.102      -0.293       0.026
C(language)[T.Korean]                  -0.1333      0.081     -1.641      0.102      -0.293       0.026
C(language)[T.Mandarin]                -0.1000      0.081     -1.230      0.219      -0.260       0.060
C(language)[T.Portuguese]            -2.22e-15      0.081  -2.73e-14      1.000      -0.160       0.160
C(language)[T.Russian]                 -0.0333      0.081     -0.410      0.682      -0.193       0.126
C(language)[T.Spanish]                 -0.1000      0.081     -1.230      0.219      -0.260       0.060
C(language)[T.Swahili]                 -0.2667      0.081     -3.281      0.001      -0.426      -0.107
C(language)[T.Tagalog]                 -0.1333      0.081     -1.641      0.102      -0.293       0.026
C(language)[T.Yoruba]                  -0.0333      0.081     -0.410      0.682      -0.193       0.126
C(income_level)[T.low]                  0.1460      0.013     11.396      0.000       0.121       0.171
C(income_level)[T.middle]               0.3064      0.010     31.126      0.000       0.287       0.326
C(education_level)[T.bachelors]         0.1410      0.053      2.661      0.008       0.037       0.245
C(education_level)[T.graduate]          0.1454      0.053      2.720      0.007       0.040       0.250
C(education_level)[T.high_school]       0.1387      0.054      2.547      0.011       0.032       0.246
C(education_level)[T.no_degree]         0.1424      0.054      2.646      0.008       0.037       0.248
C(age_group)[T.prime]                   0.3064      0.010     31.126      0.000       0.287       0.326
C(age_group)[T.young]                   0.1460      0.013     11.396      0.000       0.121       0.171
C(existing_children)[T.one_two]         0.3064      0.010     31.126      0.000       0.287       0.326
C(existing_children)[T.three_plus]      1.2422      0.036     34.944      0.000       1.172       1.312
C(relationship_status)[T.partnered]     0.3064      0.010     31.126      0.000       0.287       0.326
C(relationship_status)[T.single]        0.1460      0.013     11.396      0.000       0.121       0.171
C(health_status)[T.healthy]            -0.0738      0.040     -1.850      0.065      -0.152       0.005
==============================================================================
Omnibus:                       69.804   Durbin-Watson:                   1.737
Prob(Omnibus):                  0.000   Jarque-Bera (JB):              265.605
Skew:                          -0.684   Prob(JB):                     2.11e-58
Kurtosis:                       6.648   Cond. No.                     9.20e+17
==============================================================================

Notes:
[1] Standard Errors assume that the covariance matrix of the errors is correctly specified.
[2] The smallest eigenvalue is 1.29e-33. This might indicate that there are
strong multicollinearity problems or that the design matrix is singular.
```
