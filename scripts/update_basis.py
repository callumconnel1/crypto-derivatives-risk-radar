from __future__ import annotations

import math
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


from backend.risk_radar.basis import (
    build_basis_snapshot,
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
    / "basis"
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
            f"Required input missing: {path}"
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


def finite(
    value,
) -> bool:
    return (
        isinstance(
            value,
            (int, float),
        )
        and math.isfinite(
            float(value)
        )
    )


def pairwise_correlation(
    dataframe: pl.DataFrame,
    first: str,
    second: str,
) -> float | None:
    if (
        first not in dataframe.columns
        or
        second not in dataframe.columns
    ):
        return None

    clean = (
        dataframe
        .select([
            first,
            second,
        ])
        .drop_nulls()
    )

    if clean.height < 3:
        return None

    result = (
        clean
        .select(
            pl.corr(
                first,
                second,
            ).alias(
                "correlation"
            )
        )[
            "correlation"
        ][0]
    )

    if not finite(
        result
    ):
        return None

    return float(
        result
    )


# ============================================================
# LOAD INPUTS
# ============================================================

derivatives_latest = require_file(
    DERIVATIVES_LATEST_PATH
)

derivatives_history = require_file(
    DERIVATIVES_HISTORY_PATH
)


print(
    "Derivatives latest:",
    derivatives_latest.shape,
)

print(
    "Derivatives history:",
    derivatives_history.shape,
)


# ============================================================
# BUILD BASIS CALIBRATION
# ============================================================

snapshot = build_basis_snapshot(
    derivatives_latest=derivatives_latest,
    derivatives_history=derivatives_history,
)


print(
    "Basis snapshot:",
    snapshot.shape,
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
                "basis_calculated_at",
            ],
            keep="last",
        )
        .sort([
            "symbol",
            "basis_calculated_at",
        ])
    )

else:
    history = (
        snapshot
        .sort([
            "symbol",
            "basis_calculated_at",
        ])
    )


atomic_write(
    history,
    HISTORY_PATH,
)


# ============================================================
# CROSS-SECTIONAL SNAPSHOT
# ============================================================

print(
    "\nBASIS CROSS-SECTION"
)


print(
    snapshot
    .sort(
        "basis_cross_magnitude_percentile",
        descending=True,
        nulls_last=True,
    )
    .select([
        "symbol",

        "median_index_basis",
        "basis_direction",

        "basis_cross_percentile",
        "basis_cross_magnitude_percentile",

        "basis_iqr",
        "basis_dispersion_cross_percentile",
    ])
)


# ============================================================
# HISTORICAL CALIBRATION
# ============================================================

print(
    "\nBASIS HISTORICAL CALIBRATION"
)


print(
    snapshot
    .select([
        "symbol",

        "basis_history_observations",
        "basis_history_distinct_values",
        "basis_history_span_hours",
        "basis_history_available",

        "basis_history_magnitude_percentile",
        "basis_confirmed_magnitude_percentile",

        "basis_dispersion_history_observations",
        "basis_dispersion_history_distinct_values",
        "basis_dispersion_history_span_hours",
        "basis_dispersion_history_available",

        "basis_dispersion_history_percentile",
        "basis_dispersion_confirmed_percentile",
    ])
    .sort(
        "symbol"
    )
)


# ============================================================
# READINESS
# ============================================================

print(
    "\nBASIS READINESS"
)


print(
    snapshot.select([
        pl.col(
            "basis_history_available"
        )
        .sum()
        .alias(
            "basis_level_ready"
        ),

        pl.col(
            "basis_dispersion_history_available"
        )
        .sum()
        .alias(
            "basis_dispersion_ready"
        ),

        pl.col(
            "basis_calibration_ready"
        )
        .sum()
        .alias(
            "assets_fully_ready"
        ),

        pl.col(
            "basis_history_observations"
        )
        .median()
        .alias(
            "median_level_observations"
        ),

        pl.col(
            "basis_history_span_hours"
        )
        .median()
        .alias(
            "median_level_span_hours"
        ),
    ])
)


# ============================================================
# DISTRIBUTIONS
# ============================================================

print(
    "\nCURRENT BASIS DISTRIBUTIONS"
)


print(
    snapshot.select([
        pl.col(
            "median_index_basis"
        )
        .min()
        .alias(
            "basis_min"
        ),

        pl.col(
            "median_index_basis"
        )
        .median()
        .alias(
            "basis_median"
        ),

        pl.col(
            "median_index_basis"
        )
        .max()
        .alias(
            "basis_max"
        ),

        pl.col(
            "basis_iqr"
        )
        .min()
        .alias(
            "dispersion_min"
        ),

        pl.col(
            "basis_iqr"
        )
        .median()
        .alias(
            "dispersion_median"
        ),

        pl.col(
            "basis_iqr"
        )
        .max()
        .alias(
            "dispersion_max"
        ),
    ])
)


# ============================================================
# CENTRAL BASIS VS DISPERSION
# ============================================================

print(
    "\nBASIS MAGNITUDE VS DISPERSION"
)


correlation = pairwise_correlation(
    snapshot.with_columns(
        pl.col(
            "median_index_basis"
        )
        .abs()
        .alias(
            "basis_abs"
        )
    ),
    "basis_abs",
    "basis_iqr",
)


if correlation is None:
    correlation_text = "NA"
else:
    correlation_text = (
        f"{correlation:+.4f}"
    )


print(
    "abs(median_index_basis) vs basis_iqr:",
    correlation_text,
)


# ============================================================
# WARM-UP LEADERS
# ============================================================

print(
    "\nTOP BASIS MAGNITUDE — CROSS-SECTIONAL WARM-UP"
)


print(
    snapshot
    .sort(
        "basis_warmup_magnitude_percentile",
        descending=True,
        nulls_last=True,
    )
    .head(
        5
    )
    .select([
        "symbol",
        "median_index_basis",
        "basis_direction",
        "basis_warmup_magnitude_percentile",
    ])
)


print(
    "\nTOP BASIS DISPERSION — CROSS-SECTIONAL WARM-UP"
)


print(
    snapshot
    .sort(
        "basis_dispersion_warmup_percentile",
        descending=True,
        nulls_last=True,
    )
    .head(
        5
    )
    .select([
        "symbol",
        "basis_iqr",
        "basis_dispersion_warmup_percentile",
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
