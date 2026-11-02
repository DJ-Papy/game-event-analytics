"""Helper shared by the notebooks: open DuckDB and create the `events` view over the Parquet files.

Files that cannot be read (truncated download or source defect) are skipped and returned,
so that the notebooks can report them instead of failing.
"""
import glob

import duckdb


def connect_events(pattern: str, memory_limit: str = "2GB"):
    files = sorted(glob.glob(pattern))
    readable, unreadable = [], []
    for f in files:
        probe = duckdb.connect()                       # one connection per file: an error must not poison the next probe
        try:
            probe.execute(f"SELECT COUNT(*) FROM read_parquet('{f}')").fetchone()
            readable.append(f)
        except duckdb.Error:
            unreadable.append(f)
        finally:
            probe.close()

    con = duckdb.connect()                             # in-memory: nothing is written to disk
    con.sql(f"SET memory_limit='{memory_limit}'")
    try:
        con.sql("SET enable_progress_bar = false")     # no progress widget saved in the notebooks
    except duckdb.Error:
        pass                                           # Jupyter without ipywidgets: no widget is drawn anyway
    con.sql(
        "CREATE VIEW events AS "
        "SELECT * EXCLUDE (event_timestamp), CAST(event_timestamp AS TIMESTAMP) AS ts "
        f"FROM read_parquet({readable})"
    )
    return con, readable, unreadable
