"""Game event analytics: retention, funnel, ad monetisation and A/B test of a mobile game."""
from .data import connect_events
from .queries import build_base_tables, run_sql

__all__ = ["connect_events", "build_base_tables", "run_sql"]
__version__ = "1.0.0"
