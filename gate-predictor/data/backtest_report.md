# GATE Topic Predictor - Backtest Evaluation Report
**Subject ID**: operating_systems
**Evaluation Window**: 2020 - 2024
**Generated**: 2026-09-29 15:43:48 UTC

> **Disclaimer**: All outputs are trend-based guidance. GATE question selection is non-deterministic.

## Summary Metrics Across All Folds (Mean +/- Std)

| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div | ECE | EMD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Predictor** | 28.6% +/- 26.4% | -0.012 +/- 0.617 | 26.7% +/- 27.9% | 56.0% +/- 26.1% | 6.6027 | 0.0153 | 0.7784 |
| **NaiveFrequency** | 54.0% +/- 19.0% | 0.041 +/- 0.565 | 26.7% +/- 43.5% | 56.0% +/- 16.7% | 6.8696 | 0.0306 | 0.8377 |
| **Uniform** | 54.3% +/- 10.8% | 0.548 +/- 0.024 | 26.7% +/- 14.9% | 60.0% +/- 14.1% | 6.4085 | 0.0000 | 0.6892 |

## Detailed Folds

### Fold Year: 2020
- **Train Years**: 2015 - 2019
- **Total Test Marks**: 14.0

| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div |
| --- | --- | --- | --- | --- | --- |
| Predictor | 42.9% | 0.529 | 66.7% | 80.0% | 3.9307 |
| NaiveFrequency | 64.3% | 0.658 | 100.0% | 60.0% | 3.6822 |
| Uniform | 57.1% | 0.537 | 0.0% | 60.0% | 5.2943 |

### Fold Year: 2021
- **Train Years**: 2015 - 2020
- **Total Test Marks**: 18.0

| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div |
| --- | --- | --- | --- | --- | --- |
| Predictor | 0.0% | -0.750 | 0.0% | 40.0% | 7.0673 |
| NaiveFrequency | 38.9% | -0.775 | 0.0% | 40.0% | 8.3061 |
| Uniform | 61.1% | 0.525 | 33.3% | 80.0% | 3.6138 |

### Fold Year: 2022
- **Train Years**: 2015 - 2021
- **Total Test Marks**: 15.0

| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div |
| --- | --- | --- | --- | --- | --- |
| Predictor | 46.7% | 0.350 | 33.3% | 80.0% | 5.4021 |
| NaiveFrequency | 80.0% | 0.375 | 0.0% | 80.0% | 5.4091 |
| Uniform | 46.7% | 0.542 | 33.3% | 40.0% | 7.1425 |

### Fold Year: 2023
- **Train Years**: 2015 - 2022
- **Total Test Marks**: 15.0

| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div |
| --- | --- | --- | --- | --- | --- |
| Predictor | 53.3% | 0.425 | 33.3% | 60.0% | 5.0267 |
| NaiveFrequency | 53.3% | 0.204 | 33.3% | 60.0% | 5.6508 |
| Uniform | 66.7% | 0.550 | 33.3% | 60.0% | 7.0903 |

### Fold Year: 2024
- **Train Years**: 2015 - 2023
- **Total Test Marks**: 15.0

| Model | Must-Do Coverage | Spearman rho | Precision@3 | Precision@5 | KL Div |
| --- | --- | --- | --- | --- | --- |
| Predictor | 0.0% | -0.613 | 0.0% | 20.0% | 11.5865 |
| NaiveFrequency | 33.3% | -0.258 | 0.0% | 40.0% | 11.2996 |
| Uniform | 40.0% | 0.588 | 33.3% | 60.0% | 8.9014 |
