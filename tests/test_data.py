import pytest

from game_events.data import connect_events

from .factory import event, write_parquet


def test_truncated_file_is_skipped_not_fatal(tmp_path):
    write_parquet([event("A", "firstOpen", "2025-03-01 10:00:00")], tmp_path / "part-00000.parquet")
    raw = (tmp_path / "part-00000.parquet").read_bytes()
    (tmp_path / "part-00049.parquet").write_bytes(raw[: len(raw) // 2])

    con, readable, unreadable = connect_events(tmp_path / "*.parquet")

    assert [p.endswith("part-00000.parquet") for p in readable] == [True]
    assert [p.endswith("part-00049.parquet") for p in unreadable] == [True]
    assert con.execute("SELECT COUNT(*) FROM events").fetchall()[0][0] == 1


def test_timestamp_is_cast(tmp_path):
    write_parquet([event("A", "firstOpen", "2025-03-01 10:00:00")], tmp_path / "p.parquet")
    con, _, _ = connect_events(tmp_path / "*.parquet")
    assert str(con.execute("SELECT ts FROM events").fetchall()[0][0]) == "2025-03-01 10:00:00"


def test_missing_data_gives_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="data/README.md"):
        connect_events(tmp_path / "*.parquet")
