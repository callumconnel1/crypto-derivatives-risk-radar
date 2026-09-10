from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

import polars as pl


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from backend.risk_radar.derivatives import (
    add_common_universe_oi_features,
    add_oi_change_features,
    build_latest_derivatives_snapshot,
    prepare_common_oi_market_snapshot,
)


# ============================================================
# PATHS
# ============================================================

MARKET_PAIR_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "market_pairs"
)

EXCHANGE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "exchange_summary"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
)

LATEST_PATH = (
    OUTPUT_DIR
    / "latest.parquet"
)

MARKETS_PATH = (
    OUTPUT_DIR
    / "markets_latest.parquet"
)

HISTORY_PATH = (
    OUTPUT_DIR
    / "history.parquet"
)

MARKETS_HISTORY_PATH = (
    OUTPUT_DIR
    / "markets_history.parquet"
)


MARKET_HISTORY_RETENTION_HOURS = 26


# ============================================================
# HELPERS
# ============================================================


def latest_partition(
    directory: Path,
) -> Path:

    files = list(
        directory.rglob(
            "*.parquet"
        )
    )

    if not files:

        raise FileNotFoundError(
            f"No Parquet files found in {directory}"
        )

    return max(
        files,
        key=lambda path:
            path.stat().st_mtime,
    )


def atomic_write(
    dataframe: pl.DataFrame,
    path: Path,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = (
        path.parent
        / f".{path.name}.tmp"
    )

    dataframe.write_parquet(
        temporary
    )

    os.replace(
        temporary,
        path,
    )


# ============================================================
# LOAD LATEST RAW PARTITIONS
# ============================================================

market_file = latest_partition(
    MARKET_PAIR_DIR
)

exchange_file = latest_partition(
    EXCHANGE_DIR
)


print(
    "Market-pair partition:",
    market_file,
)

print(
    "Exchange partition:",
    exchange_file,
)


market_pairs = pl.read_parquet(
    market_file
)

exchange_summary = pl.read_parquet(
    exchange_file
)


# ============================================================
# BUILD CURRENT CLEAN SNAPSHOT
# ============================================================

(
    base_snapshot,
    cleaned_markets,
) = build_latest_derivatives_snapshot(
    market_pairs,
    exchange_summary,
)


# ============================================================
# ASSET-LEVEL HISTORY
# ============================================================

if HISTORY_PATH.exists():

    history = pl.read_parquet(
        HISTORY_PATH
    )


    history_columns = [
        column
        for column in base_snapshot.columns
        if column in history.columns
    ]


    history = history.select(
        history_columns
    )


    history = (
        pl.concat(
            [
                history,
                base_snapshot,
            ],
            how="diagonal_relaxed",
        )

        .unique(
            subset=[
                "symbol",
                "calculated_at",
            ],
            keep="last",
        )

        .sort([
            "symbol",
            "calculated_at",
        ])
    )

else:

    history = (
        base_snapshot
        .sort([
            "symbol",
            "calculated_at",
        ])
    )


# ============================================================
# MARKET-LEVEL COMMON-UNIVERSE HISTORY
# ============================================================

current_market_history = (
    prepare_common_oi_market_snapshot(
        cleaned_markets
    )
)


history_frames = []


if MARKETS_HISTORY_PATH.exists():

    history_frames.append(
        pl.read_parquet(
            MARKETS_HISTORY_PATH
        )
    )


# Bootstrap using the previous latest file if available.
if MARKETS_PATH.exists():

    previous_markets = (
        pl.read_parquet(
            MARKETS_PATH
        )
    )

    if not previous_markets.is_empty():

        history_frames.append(
            prepare_common_oi_market_snapshot(
                previous_markets
            )
        )


history_frames.append(
    current_market_history
)


markets_history = (
    pl.concat(
        history_frames,
        how="diagonal_relaxed",
    )

    .unique(
        subset=[
            "symbol",
            "market_id",
            "exchange_id",
            "collected_at",
        ],
        keep="last",
    )

    .sort([
        "collected_at",
        "symbol",
        "exchange_id",
        "market_id",
    ])
)


# ============================================================
# ROLLING RETENTION
# ============================================================

latest_market_time = (
    markets_history[
        "collected_at"
    ].max()
)


if latest_market_time is not None:

    cutoff = (
        latest_market_time
        - timedelta(
            hours=MARKET_HISTORY_RETENTION_HOURS
        )
    )

    markets_history = (
        markets_history
        .filter(
            pl.col(
                "collected_at"
            )
            >= cutoff
        )
    )


# ============================================================
# DERIVED OI FEATURES
# ============================================================

# Old aggregate comparison retained for diagnostics.
snapshot = (
    add_oi_change_features(
        history=history,
        latest_snapshot=base_snapshot,
    )
)


# New production-quality common-universe comparison.
snapshot = (
    add_common_universe_oi_features(
        market_history=markets_history,
        latest_snapshot=snapshot,
    )
)


# ============================================================
# SAVE
# ============================================================

atomic_write(
    snapshot,
    LATEST_PATH,
)

atomic_write(
    cleaned_markets,
    MARKETS_PATH,
)

atomic_write(
    history,
    HISTORY_PATH,
)

atomic_write(
    markets_history,
    MARKETS_HISTORY_PATH,
)


# ============================================================
# DIAGNOSTICS
# ============================================================

history_start = (
    history["calculated_at"].min()
)

history_end = (
    history["calculated_at"].max()
)


if (
    history_start is not None
    and history_end is not None
):

    history_span_hours = (
        (
            history_end
            - history_start
        ).total_seconds()
        / 3600.0
    )

else:

    history_span_hours = 0.0


print("\nASSET HISTORY")

print(
    "Start:",
    history_start,
)

print(
    "End:",
    history_end,
)

print(
    "Span:",
    f"{history_span_hours:.2f} hours",
)


market_history_start = (
    markets_history[
        "collected_at"
    ].min()
)

market_history_end = (
    markets_history[
        "collected_at"
    ].max()
)


if (
    market_history_start is not None
    and market_history_end is not None
):

    market_span_hours = (
        (
            market_history_end
            - market_history_start
        ).total_seconds()
        / 3600.0
    )

else:

    market_span_hours = 0.0


print(
    "\nCOMMON MARKET HISTORY"
)

print(
    "Rows:",
    markets_history.height,
)

print(
    "Start:",
    market_history_start,
)

print(
    "End:",
    market_history_end,
)

print(
    "Span:",
    f"{market_span_hours:.2f} hours",
)

print(
    "Snapshots:",
    markets_history[
        "collected_at"
    ].n_unique(),
)


print(
    "\nDERIVATIVES SNAPSHOT"
)


print(
    snapshot.select([
        "symbol",

        "total_open_interest",

        "open_interest_change_1h",
        "open_interest_change_common_1h",

        "common_market_count_1h",
        "common_venue_count_1h",

        "common_oi_share_current_1h",
        "common_oi_share_reference_1h",
        "common_oi_overlap_min_share_1h",

        "common_oi_change_available_1h",
    ])
    .sort(
        "total_open_interest",
        descending=True,
    )
)


print(
    "\nCOMMON OI AVAILABILITY"
)


print(
    snapshot.select([

        pl.col(
            "common_oi_change_available_1h"
        )
        .sum()
        .alias(
            "assets_1h"
        ),

        pl.col(
            "common_oi_change_available_4h"
        )
        .sum()
        .alias(
            "assets_4h"
        ),

        pl.col(
            "common_oi_change_available_24h"
        )
        .sum()
        .alias(
            "assets_24h"
        ),
    ])
)


print(
    "\nSaved:",
    LATEST_PATH,
)

print(
    "Saved:",
    MARKETS_PATH,
)

print(
    "Saved:",
    HISTORY_PATH,
)

print(
    "Saved:",
    MARKETS_HISTORY_PATH,
)