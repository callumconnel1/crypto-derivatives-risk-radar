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


from backend.risk_radar.funding import (
    build_funding_snapshot,
)


# ============================================================
# PATHS
# ============================================================

DERIVATIVES_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
    / "latest.parquet"
)

DERIVATIVES_HISTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
    / "history.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "funding"
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
            f"Required file missing: {path}"
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

latest_derivatives = require_file(
    DERIVATIVES_LATEST_PATH
)

derivatives_history = require_file(
    DERIVATIVES_HISTORY_PATH
)


print(
    "Derivatives latest:",
    latest_derivatives.shape,
)

print(
    "Derivatives history:",
    derivatives_history.shape,
)


# ============================================================
# BUILD FUNDING SNAPSHOT
# ============================================================

snapshot = build_funding_snapshot(
    derivatives_latest=(
        latest_derivatives
    ),
    derivatives_history=(
        derivatives_history
    ),
)


# ============================================================
# SAVE LATEST
# ============================================================

atomic_write(
    snapshot,
    LATEST_PATH,
)


# ============================================================
# APPEND DERIVED HISTORY
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
                "funding_calculated_at",
            ],
            keep="last",
        )

        .sort([
            "symbol",
            "funding_calculated_at",
        ])
    )

else:

    history = (
        snapshot

        .sort([
            "symbol",
            "funding_calculated_at",
        ])
    )


atomic_write(
    history,
    HISTORY_PATH,
)


# ============================================================
# CROSS-SECTIONAL FUNDING
# ============================================================

print(
    "\nCROSS-SECTIONAL FUNDING"
)


print(
    snapshot.select([
        "symbol",
        "median_funding_rate",

        "funding_cross_percentile",

        "funding_cross_directional_tail_percentile",

        "funding_cross_magnitude_percentile",

        "funding_cross_confirmed_tail_percentile",

        "funding_history_available",
    ])

    .sort(
        "funding_cross_confirmed_tail_percentile",
        descending=True,
    )
)


# ============================================================
# HISTORICAL CALIBRATION
# ============================================================

print(
    "\nHISTORICAL FUNDING CALIBRATION"
)


print(
    snapshot.select([
        "symbol",

        "funding_history_percentile",

        "funding_history_directional_tail_percentile",

        "funding_history_magnitude_percentile",

        "funding_history_confirmed_tail_percentile",

        "funding_confirmed_tail_percentile",

        "funding_robust_z",

        "funding_crowding_state",
    ])
)


# ============================================================
# HISTORICAL READINESS
# ============================================================

print(
    "\nHISTORICAL READINESS"
)


print(
    snapshot.select([

        pl.col(
            "funding_history_available"
        )
        .sum()
        .alias(
            "assets_ready"
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
            "funding_history_observations"
        )
        .max()
        .alias(
            "max_observations"
        ),

        pl.col(
            "funding_history_distinct_values"
        )
        .min()
        .alias(
            "min_distinct"
        ),

        pl.col(
            "funding_history_distinct_values"
        )
        .median()
        .alias(
            "median_distinct"
        ),

        pl.col(
            "funding_history_distinct_values"
        )
        .max()
        .alias(
            "max_distinct"
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

        pl.col(
            "funding_history_span_hours"
        )
        .max()
        .alias(
            "max_span_hours"
        ),
    ])
)


# ============================================================
# FUNDING CROWDING STATES
# ============================================================

print(
    "\nFUNDING CROWDING STATES"
)


print(
    snapshot

    .group_by(
        "funding_crowding_state"
    )

    .len()

    .sort(
        "len",
        descending=True,
    )
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