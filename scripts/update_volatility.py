import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

BACKEND_DIR = (
    PROJECT_ROOT / "backend"
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.append(
        str(BACKEND_DIR)
    )


from risk_radar.volatility import (
    build_latest_volatility_snapshot,
)


# ============================================================
# PATHS
# ============================================================

SEED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility_5m"
)

LIVE_SPOT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "spot"
    / "quotes"
)

MODEL_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility"
    / "model_params.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LATEST_PATH = (
    OUTPUT_DIR
    / "latest.parquet"
)

HISTORY_PATH = (
    OUTPUT_DIR
    / "history.parquet"
)


# ============================================================
# LOAD SEED HISTORY
# ============================================================

seed_files = sorted(
    SEED_DIR.glob(
        "*.parquet"
    )
)

if not seed_files:

    raise RuntimeError(
        "No historical 5m volatility seed data found"
    )


seed_frames = [
    pl.read_parquet(file)
    for file in seed_files
]

seed = pl.concat(
    seed_frames,
    how="diagonal_relaxed",
)


# ============================================================
# LOAD LIVE SPOT COLLECTOR DATA
# ============================================================

live_files = sorted(
    LIVE_SPOT_DIR.glob(
        "date=*/hour=*.parquet"
    )
)


if live_files:

    live_frames = []

    # Only recent partitions are needed.
    # Avoid reading the entire collector history forever.
    for file in live_files[-72:]:

        try:

            frame = pl.read_parquet(
                file
            )

            if (
                "timestamp"
                not in frame.columns
                or "price"
                not in frame.columns
            ):
                continue

            live_frames.append(
                frame.select([
                    column
                    for column
                    in [
                        "timestamp",
                        "asset",
                        "symbol",
                        "price",
                    ]
                    if column
                    in frame.columns
                ])
            )

        except Exception as error:

            print(
                f"Could not read {file}: {error}"
            )


    if live_frames:

        live = pl.concat(
            live_frames,
            how="diagonal_relaxed",
        )

        # ----------------------------------------------------
        # Convert collector snapshots into 5-minute closes
        # ----------------------------------------------------

        live = (
            live
            .sort([
                "symbol",
                "timestamp",
            ])
            .group_by_dynamic(
                "timestamp",
                every="5m",
                group_by=[
                    "symbol",
                    "asset",
                ],
            )
            .agg(
                pl.col(
                    "price"
                ).last()
            )
        )

    else:

        live = pl.DataFrame()

else:

    live = pl.DataFrame()


# ============================================================
# MERGE SEED + LIVE
# ============================================================

if live.is_empty():

    prices = seed

else:

    prices = pl.concat(
        [
            seed,
            live,
        ],
        how="diagonal_relaxed",
    )


prices = (
    prices
    .sort([
        "symbol",
        "timestamp",
    ])
    .unique(
        subset=[
            "symbol",
            "timestamp",
        ],
        keep="last",
        maintain_order=True,
    )
)

gap_check = (
    prices
    .sort(["symbol", "timestamp"])
    .with_columns(
        pl.col("timestamp")
        .diff()
        .over("symbol")
        .alias("time_gap")
    )
    .filter(
        pl.col("time_gap")
        > pl.duration(minutes=10)
    )
    .select([
        "symbol",
        "timestamp",
        "time_gap",
    ])
)

print("\nPRICE GAP CHECK")
print(gap_check)


# Keep enough history for percentile + model memory.
cutoff = (
    datetime.now(UTC)
    - timedelta(
        days=10
    )
)

prices = prices.filter(
    pl.col("timestamp")
    >= cutoff
)


# ============================================================
# LOAD MODEL PARAMETERS
# ============================================================

if not MODEL_PATH.exists():

    raise RuntimeError(
        "Model parameter file not found. "
        "Run scripts/fit_volatility_models.py first."
    )


model_params = pl.read_parquet(
    MODEL_PATH
)


# ============================================================
# BUILD SNAPSHOT
# ============================================================

snapshot = (
    build_latest_volatility_snapshot(
        prices=prices,
        model_params=model_params,
        percentile_lookback_days=7,
    )
)


if snapshot.is_empty():

    raise RuntimeError(
        "Volatility engine returned no rows"
    )


snapshot = snapshot.with_columns(
    pl.lit(
        datetime.now(
            UTC
        )
    )
    .alias(
        "calculated_at"
    )
)


# ============================================================
# SAVE LATEST
# ============================================================

snapshot.write_parquet(
    LATEST_PATH,
    compression="zstd",
)


# ============================================================
# APPEND HISTORY
# ============================================================

if HISTORY_PATH.exists():

    history = pl.read_parquet(
        HISTORY_PATH
    )

    history = pl.concat(
        [
            history,
            snapshot,
        ],
        how="diagonal_relaxed",
    )

    history = history.unique(
        subset=[
            "symbol",
            "timestamp",
        ],
        keep="last",
        maintain_order=True,
    )

else:

    history = snapshot


history.write_parquet(
    HISTORY_PATH,
    compression="zstd",
)


# ============================================================
# DISPLAY
# ============================================================

print(
    snapshot.select([
        "symbol",
        "price",

        "realized_vol_1h",
        "realized_vol_4h",
        "realized_vol_24h",

        "vol_percentile_24h",

        "power_law_vol_forecast",
        "ewma_vol_forecast",

        "model_disagreement",
    ])
)