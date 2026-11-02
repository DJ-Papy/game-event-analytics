"""Run the SQL files of sql/ against an events connection."""
from . import config


def run_sql(con, file_name, **params):
    """Execute one file of sql/ with named parameters ($name in the SQL) and return the result."""
    query = (config.SQL_DIR / file_name).read_text(encoding="utf-8")
    return con.execute(query, params) if params else con.execute(query)


def build_base_tables(con):
    """new_players, active_days, ads, sessions (sql/01_base_tables.sql)."""
    run_sql(con, "01_base_tables.sql")


def build_day0_exposure(con):
    """day0_q: first-day ad exposure, activity quartile and D1 return of new players (sql/04)."""
    run_sql(con, "04_ad_exposure_day0.sql", last_full_day=config.LAST_FULL_DAY, gap_day=config.GAP_DAY)


def build_experiment_players(con, experiment=config.EXPERIMENT):
    """exp_players: one row per player of the experiment, with the variant of their first join (sql/05)."""
    run_sql(con, "05_experiment_players.sql", experiment=experiment)
