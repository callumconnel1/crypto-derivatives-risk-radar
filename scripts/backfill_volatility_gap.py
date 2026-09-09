import sys
import time
from pathlib import Path

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from get_data import get_historical_quotes


ASSETS = {
    1: "BTC",
    1027: "ETH",
    5426: "SOL",
    52: "XRP",
    1839: "BNB",
    74: "DOGE",
    2010: "ADA",
    1975: "LINK",
    5805: "AVAX",
    20947: "SUI",
    1958: "TRX",
    6636: "DOT",
    2: "LTC",
    1831: "BCH",
    7083: "UNI",
    21794: "APT",
    6535: "NEAR",
    1321: "ETC",
    8916: "ICP",
    2280: "FIL",
}


DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility_5m"
)


for i, (id, symbol) in enumerate(
    ASSETS.items(),
    start=1,
):

    print(
        f"[{i:02d}/{len(ASSETS)}] "
        f"Backfilling {symbol}..."
    )

    frame = get_historical_quotes(
        ids=[id],
        time_start="2026-09-09T00:00:00Z",
        time_end="2026-09-09T14:25:00Z",
        interval="5m",
        convert="USD",
    )

    path = (
        DATA_DIR
        / f"{symbol}.parquet"
    )

    existing = pl.read_parquet(
        path
    )

    combined = (
        pl.concat(
            [
                existing,
                frame,
            ],
            how="diagonal_relaxed",
        )
        .sort("timestamp")
        .unique(
            subset=[
                "symbol",
                "timestamp",
            ],
            keep="last",
            maintain_order=True,
        )
    )

    combined.write_parquet(
        path,
        compression="zstd",
    )

    print(
        f"    {combined.height:,} total rows"
    )

    time.sleep(0.25)


print("\nBackfill complete.")