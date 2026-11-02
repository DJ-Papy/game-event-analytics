"""Access to the raw event files."""
import glob

import duckdb

from . import config


def connect_events(pattern=config.RAW_EVENTS, memory_limit=config.DUCKDB_MEMORY_LIMIT):
    """Open an in-memory DuckDB connection with an `events` view over the readable Parquet files.

    Files that cannot be read (part-00049 is truncated in the source dataset) are skipped and
    returned, so that callers can report them instead of failing.
    Returns (connection, readable_files, unreadable_files).
    """
    files = sorted(glob.glob(str(pattern)))
    if not files:
        raise FileNotFoundError(f"No Parquet file matches {pattern}. See data/README.md to download the data.")
    readable, unreadable = [], []
    for f in files:
        probe = duckdb.connect()       # one connection per file: an error must not affect the next probe
        try:
            probe.execute(f"SELECT COUNT(*) FROM read_parquet('{f}')").fetchall()[0]
            readable.append(f)
        except duckdb.Error:
            unreadable.append(f)
        finally:
            probe.close()

    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{memory_limit}'")
    try:
        con.execute("SET enable_progress_bar = false")   # keeps progress widgets out of saved notebooks
    except duckdb.Error:
        pass                                             # Jupyter without ipywidgets: no widget is drawn anyway
    con.execute(
        "CREATE VIEW events AS "
        "SELECT * EXCLUDE (event_timestamp), CAST(event_timestamp AS TIMESTAMP) AS ts "
        f"FROM read_parquet({readable})"
    )
    return con, readable, unreadable
