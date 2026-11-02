"""Statistical helpers for A/B tests."""
import math

import numpy as np
from scipy.stats import chisquare
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_effectsize


def srm_pvalue(group_sizes):
    """Sample ratio mismatch: p-value of a chi-square test against an equal split.
    A small value means the assignment is suspect."""
    return float(chisquare(list(group_sizes)).pvalue)


def diff_vs_control(successes, trials, control_successes, control_trials):
    """Difference of two proportions (variant - control) in points, with its 95% Newcombe interval."""
    diff = 100 * (successes / trials - control_successes / control_trials)
    lo, hi = confint_proportions_2indep(successes, trials, control_successes, control_trials, method="newcomb")
    return diff, 100 * lo, 100 * hi


def bootstrap_mean_diff(x, control, rng, n_boot=3000):
    """95% percentile bootstrap interval of mean(x) - mean(control), resampling players."""
    diffs = [rng.choice(x, len(x)).mean() - rng.choice(control, len(control)).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return lo, hi


def sample_size_per_variant(baseline, uplift, alpha=0.05, power=0.8):
    """Players per variant needed to detect baseline -> baseline + uplift (two-sided z-test)."""
    effect = proportion_effectsize(baseline + uplift, baseline)
    return math.ceil(NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power))


def minimum_detectable_effect(baseline, players_per_variant, alpha=0.05, power=0.8):
    """Smallest increase of a proportion detectable with the given sample size (as a proportion)."""
    h = NormalIndPower().solve_power(nobs1=players_per_variant, alpha=alpha, power=power)
    return math.sin(math.asin(math.sqrt(baseline)) + h / 2) ** 2 - baseline
