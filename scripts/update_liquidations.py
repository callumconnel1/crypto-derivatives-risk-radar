from __future__ import annotations

import os
import sys
from pathlib import Path

import polars as pl


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(
    PROJECT_ROOT
) not in sys.path:
    sys.path.insert(
        0,
        str(
            PROJECT_ROOT
        ),
    )


from backend.risk_radar.liquidations import (
    build_liquidation_snapshots,
)


# ============================================================
# PATHS
# ============================================================

CRYPTO_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "crypto_liquidations"
)

GLOBAL_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "global_liquidations"
)

EXCHANGE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "exchange_liquidations"
)

DERIVATIVES_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
    / "latest.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "liquidations"
)

ASSET_LATEST_PATH = (
    OUTPUT_DIR
    / "latest.parquet"
)

GLOBAL_LATEST_PATH = (
    OUTPUT_DIR
    / "global_latest.parquet"
)

EXCHANGE_LATEST_PATH = (
    OUTPUT_DIR
    / "exchanges_latest.parquet"
)


# ============================================================
# HELPERS
# ============================================================


def read_all_parquet(
    directory: Path,
) -> pl.DataFrame:
    files = sorted(
        directory.rglob(
            "*.parquet"
        )
    )

    if not files:
        raise FileNotFoundError(
            f"No Parquet files found in {directory}"
        )

    return pl.concat(
        [
            pl.read_parquet(
                path
            )
            for path in files
        ],
        how="diagonal_relaxed",
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
# LOAD RAW HISTORY
# ============================================================

print(
    "Loading crypto liquidation history..."
)

crypto_history = read_all_parquet(
    CRYPTO_DIR
)


print(
    "Loading global liquidation history..."
)

global_history = read_all_parquet(
    GLOBAL_DIR
)


print(
    "Loading exchange liquidation history..."
)

exchange_history = read_all_parquet(
    EXCHANGE_DIR
)


print(
    "Crypto rows:",
    crypto_history.height,
)

print(
    "Global rows:",
    global_history.height,
)

print(
    "Exchange rows:",
    exchange_history.height,
)


# ============================================================
# OPTIONAL OI SNAPSHOT
# ============================================================

if DERIVATIVES_LATEST_PATH.exists():
    derivatives_latest = (
        pl.read_parquet(
            DERIVATIVES_LATEST_PATH
        )
    )

else:
    derivatives_latest = None


# ============================================================
# BUILD SNAPSHOTS
# ============================================================

(
    asset_snapshot,
    global_snapshot,
    exchange_snapshot,
) = build_liquidation_snapshots(
    crypto_history=crypto_history,
    global_history=global_history,
    exchange_history=exchange_history,
    derivatives_latest=derivatives_latest,
)


# ============================================================
# SAVE
# ============================================================

atomic_write(
    asset_snapshot,
    ASSET_LATEST_PATH,
)

atomic_write(
    global_snapshot,
    GLOBAL_LATEST_PATH,
)

atomic_write(
    exchange_snapshot,
    EXCHANGE_LATEST_PATH,
)


# ============================================================
# ASSET DIAGNOSTICS
# ============================================================

print(
    "\nASSET LIQUIDATION SNAPSHOT"
)

print(
    asset_snapshot.select([
        "symbol",

        "total_liquidations_1h",

        "long_liquidation_share_1h",
        "liquidation_direction_1h",
        "liquidation_directional_imbalance_1h",

        "liquidation_percentile_1h",

        "liquidation_baseline_observations",
        "liquidation_baseline_span_hours",
        "liquidation_baseline_coverage_24h",
        "liquidation_history_24h_complete",

        "liquidation_baseline_equal_count_1h",

        "liquidation_ratio_to_median_1h",

        "liquidations_to_oi_1h",
    ])
)


# ============================================================
# TEMPORAL CALIBRATION SUMMARY
# ============================================================

print(
    "\nLIQUIDATION TEMPORAL CALIBRATION"
)

print(
    asset_snapshot.select([
        pl.col(
            "liquidation_baseline_observations"
        )
        .min()
        .alias(
            "min_observations"
        ),

        pl.col(
            "liquidation_baseline_observations"
        )
        .median()
        .alias(
            "median_observations"
        ),

        pl.col(
            "liquidation_baseline_observations"
        )
        .max()
        .alias(
            "max_observations"
        ),

        pl.col(
            "liquidation_baseline_span_hours"
        )
        .min()
        .alias(
            "min_span_hours"
        ),

        pl.col(
            "liquidation_baseline_span_hours"
        )
        .median()
        .alias(
            "median_span_hours"
        ),

        pl.col(
            "liquidation_baseline_span_hours"
        )
        .max()
        .alias(
            "max_span_hours"
        ),

        pl.col(
            "liquidation_history_24h_complete"
        )
        .sum()
        .alias(
            "assets_full_24h"
        ),
    ])
)


# ============================================================
# TIE DIAGNOSTICS
# ============================================================

print(
    "\n1H PERCENTILE TIE DIAGNOSTICS"
)

print(
    asset_snapshot
    .sort(
        "liquidation_baseline_equal_count_1h",
        descending=True,
    )
    .select([
        "symbol",
        "total_liquidations_1h",
        "liquidation_baseline_equal_count_1h",
        "liquidation_percentile_1h",
    ])
)


# ============================================================
# GLOBAL LIQUIDATION SNAPSHOT
# ============================================================

print(
    "\nGLOBAL LIQUIDATION SNAPSHOT"
)

global_display_columns = [
    "total_liquidations_1h",
    "long_liquidations_1h",
    "short_liquidations_1h",
    "total_liquidations_24h",
    "long_liquidation_share_1h",

    "global_liquidation_percentile_1h",

    "global_baseline_observations",
    "global_baseline_span_hours",
    "global_baseline_coverage_24h",
    "global_history_24h_complete",
    "global_baseline_equal_count_1h",
]


for optional_column in [
    "top_liquidation_exchange_1h",
    "top_liquidation_exchange_share_1h",
    "top_liquidation_exchange_provider_share_1h",
    "exchange_liquidation_hhi_1h",
    "exchange_liquidation_normalized_share_sum_1h",
    "exchange_liquidation_provider_share_sum_1h",
    "exchange_liquidation_total_1h",
]:
    if optional_column in global_snapshot.columns:
        global_display_columns.append(
            optional_column
        )


print(
    global_snapshot.select(
        global_display_columns
    )
)


# ============================================================
# TOP LIQUIDATION EXCHANGES
# ============================================================

print(
    "\nTOP LIQUIDATION EXCHANGES"
)

exchange_display_columns = [
    "exchange",
    "total_liquidations_1h",
    "long_liquidations_1h",
    "short_liquidations_1h",
]

if (
    "global_liquidation_share_1h"
    in exchange_snapshot.columns
):
    exchange_display_columns.append(
        "global_liquidation_share_1h"
    )

if (
    "normalized_liquidation_share_1h"
    in exchange_snapshot.columns
):
    exchange_display_columns.append(
        "normalized_liquidation_share_1h"
    )


print(
    exchange_snapshot.select(
        exchange_display_columns
    )
)


# ============================================================
# NORMALISATION CHECK
# ============================================================

if (
    "normalized_liquidation_share_1h"
    in exchange_snapshot.columns
):
    normalized_sum = (
        exchange_snapshot[
            "normalized_liquidation_share_1h"
        ]
        .drop_nulls()
        .sum()
    )

    print(
        "\nNORMALISED EXCHANGE SHARE SUM"
    )

    print(
        normalized_sum
    )


# ============================================================
# OUTPUT
# ============================================================

print(
    "\nSaved:",
    ASSET_LATEST_PATH,
)

print(
    "Saved:",
    GLOBAL_LATEST_PATH,
)

print(
    "Saved:",
    EXCHANGE_LATEST_PATH,
)
