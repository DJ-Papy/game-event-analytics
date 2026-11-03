"""Build small Parquet event files with the same schema as the Kaggle dataset."""
import json
import random
from datetime import datetime, timedelta

import duckdb
import pandas as pd

COLUMNS = ["event_id", "event_name", "props", "event_receive_time", "user_id", "user_session_id",
           "user_session_issued_at", "user_session_count", "uprops", "client_platform", "country_code",
           "processing_time", "event_timestamp"]


def event(user, name, ts, session="", platform="Android", country="FR", props=None, uprops=None):
    """One raw event. `ts` is a datetime or an ISO string."""
    ts = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
    return dict(event_name=name, props=json.dumps(props or {}), event_receive_time=ts.isoformat(),
                user_id=user, user_session_id=session, user_session_issued_at="", user_session_count=1,
                uprops=json.dumps(uprops or {"appVersion": "0.21.21"}), client_platform=platform,
                country_code=country, processing_time=ts, event_timestamp=ts.strftime("%Y-%m-%d %H:%M:%S.%f"))


def write_parquet(rows, path):
    """Write events to one Parquet file, with the maps typed as MAP(VARCHAR, VARCHAR)."""
    df = pd.DataFrame(rows)
    df.insert(0, "event_id", [f"e{i}" for i in range(len(df))])
    con = duckdb.connect()
    con.register("df", df[COLUMNS])
    con.execute(f"""
        COPY (
            SELECT event_id, event_name, CAST(json(props) AS MAP(VARCHAR, VARCHAR)) AS event_properties,
                   event_receive_time, user_id, user_session_id, user_session_issued_at, user_session_count,
                   CAST(json(uprops) AS MAP(VARCHAR, VARCHAR)) AS user_properties_custom,
                   client_platform, country_code, processing_time, event_timestamp
            FROM df
        ) TO '{path}' (FORMAT parquet)
    """)
    con.close()


def random_events(n_players=400, seed=7):
    """A random but reproducible event stream over the real window, with a gap on 2025-03-27."""
    rng = random.Random(seed)
    start, end = datetime(2025, 2, 28, 6, 0), datetime(2025, 4, 10, 20, 30)
    rows = []
    for u in range(n_players):
        user = f"u{u}"
        platform = rng.choice(["Android", "Android", "IPhonePlayer", ""])
        country = rng.choice(["US", "GB", "FR", "TH"])
        install = start + timedelta(days=rng.randint(-5, 40), hours=rng.randint(0, 12))
        variant = rng.choice(["Control-Variant", "Variant-A", "Variant-B"]) \
            if platform == "IPhonePlayer" and rng.random() < 0.5 else None
        p_return = rng.uniform(0.2, 0.7)
        day, first = max(install, start), True
        while day <= end:
            if day.date().isoformat() == "2025-03-27" and rng.random() < 0.6:
                day += timedelta(days=1)
                continue
            sess = f"s{u}_{day.date()}"
            if first and install >= start:
                rows.append(event(user, "firstOpen", day, sess, platform, country))
            if first and variant:
                rows.append(event(user, "_experimentJoin", day, "", platform, country,
                                  {"experiment_name": "AdsConfig_iOS", "experiment_variant_name": variant}))
            rows.append(event(user, "_sessionStart", day, sess, platform, country))
            for k, name in enumerate(["gameOpened", "tokenCashout", "deviceUnlocked", "zoneUnlocked"]):
                if rng.random() < 0.95:
                    rows.append(event(user, name, day + timedelta(minutes=k + 1), sess, platform, country))
            for k in range(rng.randint(0, 8)):
                value = f"{rng.uniform(0.005, 0.04):.4f}"
                if rng.random() < 0.1:
                    value = value.replace(".", ",")
                key = "value" if day < datetime(2025, 3, 29) else "amount"
                rows.append(event(user, "adImpression", day + timedelta(minutes=10 + k), sess, platform, country,
                                  {"adFormat": rng.choice(["INTER", "REWARDED"]), key: value}))
            if platform == "Android" and rng.random() < 0.03:
                rows.append(event(user, "purchaseCompleted", day + timedelta(minutes=30), sess, platform, country,
                                  {"productName": "gem1"}))
            rows.append(event(user, "achievementUpdated", day + timedelta(minutes=40), "", platform, country,
                              {"achievement_id": "a1"}))
            first = False
            if rng.random() > p_return:
                break
            day = (day + timedelta(days=rng.choice([1, 1, 1, 2, 3]))).replace(hour=rng.randint(6, 20))
    return rows
