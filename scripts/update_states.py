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


if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from backend.risk_radar.states import (
    build_state_snapshot,
)


# ============================================================
# PATHS
# ============================================================

SPOT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "spot"
    / "latest.parquet"
)

VOLATILITY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility"
    / "latest.parquet"
)

DERIVATIVES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
    / "latest.parquet"
)

FUNDING_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "funding"
    / "latest.parquet"
)

LIQUIDATIONS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "liquidations"
    / "latest.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "states"
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
# HELPERS
# ============================================================


def require_file(
    path: Path,
) -> pl.DataFrame:

    if not path.exists():

        raise FileNotFoundError(
            f"Required snapshot missing: {path}"
        )


    return pl.read_parquet(
        path
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
# LOAD INPUTS
# ============================================================

spot = require_file(
    SPOT_PATH
)

volatility = require_file(
    VOLATILITY_PATH
)

derivatives = require_file(
    DERIVATIVES_PATH
)

funding = require_file(
    FUNDING_PATH
)

liquidations = require_file(
    LIQUIDATIONS_PATH
)


print(
    "Spot:",
    spot.shape,
)

print(
    "Volatility:",
    volatility.shape,
)

print(
    "Derivatives:",
    derivatives.shape,
)

print(
    "Funding:",
    funding.shape,
)

print(
    "Liquidations:",
    liquidations.shape,
)


# ============================================================
# BUILD STATE SNAPSHOT
# ============================================================

snapshot = build_state_snapshot(
    spot=spot,
    volatility=volatility,
    derivatives=derivatives,
    funding=funding,
    liquidations=liquidations,
)


# ============================================================
# SAVE LATEST
# ============================================================

atomic_write(
    snapshot,
    LATEST_PATH,
)


# ============================================================
# APPEND HISTORY
# ============================================================

if HISTORY_PATH.exists():

    history = pl.read_parquet(
        HISTORY_PATH
    )


    history = (
        pl.concat(
            [
                history,
                snapshot,
            ],
            how="diagonal_relaxed",
        )

        .unique(
            subset=[
                "symbol",
                "state_source_at",
            ],
            keep="last",
        )

        .sort([
            "symbol",
            "state_source_at",
        ])
    )

else:

    history = (
        snapshot

        .sort([
            "symbol",
            "state_source_at",
        ])
    )


atomic_write(
    history,
    HISTORY_PATH,
)


# ============================================================
# MAIN STATE DIAGNOSTIC
# ============================================================

print(
    "\nSTATE SNAPSHOT"
)


print(
    snapshot.select([
        "symbol",

        "price_change_1h",

        "open_interest_change_common_1h",
        "oi_change_magnitude_percentile_1h",

        "median_funding_rate",

        "funding_cross_confirmed_tail_percentile",
        "funding_history_available",
        "funding_crowding_state",

        "liquidation_percentile_1h",
        "liquidations_to_oi_percentile_1h",
        "liquidation_confirmed_percentile_1h",

        "long_liquidation_share_1h",

        "vol_ratio_1h_vs_24h",

        "common_oi_overlap_min_share_1h",

        "price_state_1h",
        "oi_state_1h",

        "funding_state",
        "leverage_state",
        "liquidation_state",
        "volatility_state",

        "primary_state",

        "state_ready_1h",

        "oi_change_quality_1h",
        "state_quality",
    ])
)


# ============================================================
# PRIMARY STATE COUNTS
# ============================================================

print(
    "\nPRIMARY STATE COUNTS"
)


print(
    snapshot

    .group_by(
        "primary_state"
    )

    .len()

    .sort(
        "len",
        descending=True,
    )
)


# ============================================================
# FUNDING SIGNAL
# ============================================================

print(
    "\nFUNDING SIGNAL"
)


print(
    snapshot

    .select([
        "symbol",

        "median_funding_rate",

        "funding_cross_confirmed_tail_percentile",

        "funding_history_available",

        "funding_confirmed_tail_percentile",

        "funding_crowding_state",

        "primary_state",
    ])

    .sort(
        "funding_cross_confirmed_tail_percentile",
        descending=True,
    )
)


# ============================================================
# READINESS
# ============================================================

print(
    "\nFULLY READY:"
)


print(
    snapshot.select(

        pl.col(
            "state_ready_1h"
        )

        .sum()

        .alias(
            "assets_ready"
        )

    )
)


# ============================================================
# QUALITY COUNTS
# ============================================================

print(
    "\nSTATE QUALITY"
)


print(
    snapshot

    .group_by(
        "state_quality"
    )

    .len()

    .sort(
        "len",
        descending=True,
    )
)


# ============================================================
# TIMING
# ============================================================

print(
    "\nSOURCE SYNCHRONISATION"
)


print(
    snapshot.select([
        pl.col(
            "state_source_skew_seconds"
        )
        .min()
        .alias(
            "min_skew_seconds"
        ),

        pl.col(
            "state_source_skew_seconds"
        )
        .median()
        .alias(
            "median_skew_seconds"
        ),

        pl.col(
            "state_source_skew_seconds"
        )
        .max()
        .alias(
            "max_skew_seconds"
        ),

        pl.col(
            "inputs_synchronised"
        )
        .sum()
        .alias(
            "synchronised_assets"
        ),
    ])
)


# ============================================================
# COMMON OI OVERLAP
# ============================================================

print(
    "\nCOMMON OI OVERLAP"
)


print(
    snapshot.select([
        pl.col(
            "common_oi_overlap_min_share_1h"
        )
        .min()
        .alias(
            "min_overlap"
        ),

        pl.col(
            "common_oi_overlap_min_share_1h"
        )
        .median()
        .alias(
            "median_overlap"
        ),

        pl.col(
            "common_oi_overlap_min_share_1h"
        )
        .max()
        .alias(
            "max_overlap"
        ),
    ])
)


# ============================================================
# FUNDING HISTORY STATUS
# ============================================================

print(
    "\nFUNDING HISTORY STATUS"
)


print(
    snapshot.select([
        pl.col(
            "funding_history_available"
        )
        .sum()
        .alias(
            "assets_funding_ready"
        ),

        pl.col(
            "funding_history_observations"
        )
        .min()
        .alias(
            "min_observations"
        ),

        pl.col(
            "funding_history_observations"
        )
        .median()
        .alias(
            "median_observations"
        ),

        pl.col(
            "funding_history_span_hours"
        )
        .min()
        .alias(
            "min_span_hours"
        ),

        pl.col(
            "funding_history_span_hours"
        )
        .median()
        .alias(
            "median_span_hours"
        ),
    ])
)


# ============================================================
# EXAMPLES
# ============================================================

print(
    "\nEXAMPLES"
)


print(
    snapshot.select([
        "symbol",
        "primary_state",
        "state_quality",
        "state_evidence",
    ])
)


# ============================================================
# OUTPUT
# ============================================================

print(
    "\nSaved:",
    LATEST_PATH,
)

print(
    "Saved:",
    HISTORY_PATH,
)