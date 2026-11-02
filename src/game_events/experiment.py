"""A/B test analysis of an in-game experiment (exp_players, sql/05)."""
import numpy as np
import pandas as pd

from . import config, stats


def experiment_retention(con, days=(1, 7), control=config.CONTROL_VARIANT):
    """Retention counted from the join day, by variant, with the difference to control
    (percentage points, 95% Newcombe interval). Needs exp_players and active_days."""
    rows = []
    for n in days:
        d = con.execute(f"""
            SELECT p.variant, COUNT(*) AS players, COUNT(a.user_id) AS retained
            FROM exp_players p
            LEFT JOIN active_days a ON a.user_id = p.user_id AND a.day = p.join_day + {int(n)}
            WHERE p.join_day + {int(n)} <= DATE '{config.LAST_FULL_DAY}'
              AND p.join_day + {int(n)} <> DATE '{config.GAP_DAY}'
            GROUP BY 1 ORDER BY 1
        """).df()
        c = d[d["variant"] == control].iloc[0]
        for _, r in d.iterrows():
            row = dict(day_n=n, variant=r.variant, players=int(r.players),
                       pct=round(100 * r.retained / r.players, 1), diff_pts=None, ci_low=None, ci_high=None)
            if r.variant != control:
                diff, lo, hi = stats.diff_vs_control(int(r.retained), int(r.players), int(c.retained), int(c.players))
                row.update(diff_pts=round(diff, 1), ci_low=round(lo, 1), ci_high=round(hi, 1))
            rows.append(row)
    return pd.DataFrame(rows)


def ads_per_player(con, days_after_join, max_join_day):
    """Ads seen and estimated ad revenue per experiment player, from the join day to
    join day + days_after_join. Revenue is also given capped at 1 USD per impression
    (a few impressions have extreme values). Needs exp_players and ads."""
    return con.execute(f"""
        SELECT p.user_id, p.variant,
               COUNT(*) FILTER (WHERE a.ad_format = 'INTER')    AS interstitials,
               COUNT(*) FILTER (WHERE a.ad_format = 'REWARDED') AS rewarded,
               COALESCE(SUM(a.amount_usd), 0)                   AS revenue_usd,
               COALESCE(SUM(LEAST(a.amount_usd, 1)), 0)         AS revenue_capped_usd
        FROM exp_players p
        LEFT JOIN ads a ON a.user_id = p.user_id AND a.day BETWEEN p.join_day AND p.join_day + {int(days_after_join)}
        WHERE p.join_day <= DATE '{max_join_day}' AND p.join_day <> DATE '{config.GAP_DAY}'
        GROUP BY 1, 2
    """).df()


def compare_to_control(df, metrics, control=config.CONTROL_VARIANT, n_boot=3000, seed=1):
    """Mean per player of each metric by variant, difference to control and its 95% bootstrap interval."""
    rng = np.random.default_rng(seed)
    out = []
    ctrl = df[df["variant"] == control]
    for m in metrics:
        c = ctrl[m].values
        out.append(dict(metric=m, variant=control, players=len(c), mean=round(c.mean(), 3),
                        diff=None, pct_change=None, ci_low=None, ci_high=None))
        for v in sorted(set(df["variant"]) - {control}):
            x = df[df["variant"] == v][m].values
            lo, hi = stats.bootstrap_mean_diff(x, c, rng, n_boot)
            out.append(dict(metric=m, variant=v, players=len(x), mean=round(x.mean(), 3),
                            diff=round(x.mean() - c.mean(), 3), pct_change=round(100 * (x.mean() / c.mean() - 1), 1),
                            ci_low=round(lo, 3), ci_high=round(hi, 3)))
    return pd.DataFrame(out)
