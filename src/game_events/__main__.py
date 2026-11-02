"""Command line entry point.

    python -m game_events build       data checks, base tables, dashboard CSV files
    python -m game_events checks      data checks only
    python -m game_events inventory   tracking inventory (docs/*.csv)
"""
import argparse
import sys
from pathlib import Path

from . import config
from .checks import run_checks
from .data import connect_events
from .export import export_dashboard
from .inventory import build_inventory
from .queries import build_base_tables


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m game_events", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["build", "checks", "inventory"])
    parser.add_argument("--data", default=str(config.RAW_EVENTS), help="glob of the raw Parquet files")
    parser.add_argument("--out", type=Path, default=None, help="output folder (default: dashboard/data or docs)")
    args = parser.parse_args(argv)

    con, readable, unreadable = connect_events(args.data)
    print(f"{len(readable)} readable files, {len(unreadable)} unreadable")

    if args.command == "inventory":
        build_inventory(con, args.out or config.DOCS)
        print("Inventory written to", (args.out or config.DOCS).resolve())
        return 0

    build_base_tables(con)
    report = run_checks(con, readable, unreadable)
    print(report.to_string(index=False))
    if (report["status"] == "error").any():
        print("Data checks failed: nothing exported.", file=sys.stderr)
        return 1
    if args.command == "build":
        out = args.out or config.DASHBOARD_DATA
        print("Exporting dashboard tables:")
        export_dashboard(con, out)
        print("Done:", out.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
