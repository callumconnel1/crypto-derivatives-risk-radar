from __future__ import annotations

import math
import os
import sys
from datetime import UTC, datetime
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


from backend.risk_radar.market_structure_research import (
    build_market_structure_research,
)


# ============================================================
# PATHS
# ============================================================

RISK_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "risk"
    / "latest.parquet"
)

BASIS_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "basis"
    / "latest.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "market_structure"
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


def correlation(
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


def format_corr(
    value: float | None,
) -> str:
    if value is None:
        return "NA"

    return f"{value:+.4f}"


# ============================================================
# LOAD
# ============================================================

risk_latest = require_file(
    RISK_LATEST_PATH
)

basis_latest = require_file(
    BASIS_LATEST_PATH
)


print(
    "Risk:",
    risk_latest.shape,
)

print(
    "Basis:",
    basis_latest.shape,
)


# ============================================================
# BUILD RESEARCH SNAPSHOT
# ============================================================

research = (
    build_market_structure_research(
        risk_latest=risk_latest,
        basis_latest=basis_latest,
    )
)


# ============================================================
# ATTACH PRODUCTION SNAPSHOT TIMING
# ============================================================

timing_columns = [
    column
    for column in [
        "risk_source_at",
        "risk_calculated_at",
        "risk_generated_at",
        "risk_version",
    ]
    if column in risk_latest.columns
]


if timing_columns:

    timing = (
        risk_latest
        .select(
            [
                "symbol",
                *timing_columns,
            ]
        )
        .unique(
            subset=[
                "symbol"
            ],
            keep="last",
        )
    )

    research = (
        research
        .join(
            timing,
            on="symbol",
            how="left",
        )
    )


snapshot_time_column = next(
    (
        column
        for column in [
            "risk_source_at",
            "risk_calculated_at",
            "risk_generated_at",
        ]
        if column in research.columns
    ),
    None,
)


if snapshot_time_column is not None:

    research = research.with_columns(
        pl.col(
            snapshot_time_column
        ).alias(
            "research_snapshot_at"
        )
    )

else:

    research = research.with_columns(
        pl.lit(
            datetime.now(
                UTC
            )
        ).alias(
            "research_snapshot_at"
        )
    )


research = research.with_columns(
    pl.lit(
        datetime.now(
            UTC
        )
    ).alias(
        "research_generated_at"
    )
)


if (
    "risk_version"
    in research.columns
):

    research = research.rename({
        "risk_version":
            "production_risk_version"
    })


# ============================================================
# SAVE LATEST + APPEND LONGITUDINAL HISTORY
# ============================================================

atomic_write(
    research,
    LATEST_PATH,
)


if HISTORY_PATH.exists():

    history = (
        pl.concat(
            [
                pl.read_parquet(
                    HISTORY_PATH
                ),
                research,
            ],
            how="diagonal_relaxed",
        )
        .unique(
            subset=[
                "symbol",
                "research_snapshot_at",
            ],
            keep="last",
        )
        .sort([
            "research_snapshot_at",
            "symbol",
        ])
    )

else:

    history = (
        research
        .sort([
            "research_snapshot_at",
            "symbol",
        ])
    )


atomic_write(
    history,
    HISTORY_PATH,
)


# ============================================================
# SOURCE STATUS
# ============================================================

print(
    "\nBASIS RESEARCH SOURCE STATUS"
)


print(
    research
    .group_by([
        "basis_level_source",
        "basis_dispersion_source",
    ])
    .len()
    .sort(
        "len",
        descending=True,
    )
)


print(
    "\nBASIS CALIBRATION READINESS"
)


print(
    research.select([
        pl.col(
            "basis_calibration_ready"
        )
        .fill_null(
            False
        )
        .sum()
        .alias(
            "assets_basis_ready"
        ),

        pl.len().alias(
            "assets_total"
        ),
    ])
)


# ============================================================
# STRUCTURE-CHANNEL CORRELATIONS
# ============================================================

print(
    "\nSTRUCTURE CHANNEL CORRELATIONS"
)


structure_pairs = [
    (
        "oi_concentration_component",
        "basis_level_component",
    ),
    (
        "oi_concentration_component",
        "basis_dispersion_component",
    ),
    (
        "basis_level_component",
        "basis_dispersion_component",
    ),
]


for first, second in structure_pairs:
    print(
        f"{first:<34} vs "
        f"{second:<34} "
        f"{format_corr(correlation(research, first, second))}"
    )


# ============================================================
# STRUCTURE CHANNELS VS EXISTING FACTORS
# ============================================================

print(
    "\nSTRUCTURE CHANNELS VS EXISTING FACTORS"
)


structure_channels = [
    "oi_concentration_component",
    "basis_level_component",
    "basis_dispersion_component",
]

existing_factors = [
    "volatility_component",
    "leverage_component",
    "funding_component",
    "liquidation_component",
]


for structure_channel in structure_channels:
    for factor in existing_factors:
        print(
            f"{structure_channel:<34} vs "
            f"{factor:<24} "
            f"{format_corr(correlation(research, structure_channel, factor))}"
        )


# ============================================================
# CANDIDATE STRUCTURE DISTRIBUTIONS
# ============================================================

print(
    "\nSTRUCTURE COMPONENT DISTRIBUTIONS"
)


print(
    research.select([
        pl.col(
            "production_market_structure_component"
        )
        .min()
        .alias(
            "production_min"
        ),

        pl.col(
            "production_market_structure_component"
        )
        .median()
        .alias(
            "production_median"
        ),

        pl.col(
            "production_market_structure_component"
        )
        .mean()
        .alias(
            "production_mean"
        ),

        pl.col(
            "production_market_structure_component"
        )
        .max()
        .alias(
            "production_max"
        ),

        pl.col(
            "candidate_structure_equal_three"
        )
        .min()
        .alias(
            "equal3_min"
        ),

        pl.col(
            "candidate_structure_equal_three"
        )
        .median()
        .alias(
            "equal3_median"
        ),

        pl.col(
            "candidate_structure_equal_three"
        )
        .mean()
        .alias(
            "equal3_mean"
        ),

        pl.col(
            "candidate_structure_equal_three"
        )
        .max()
        .alias(
            "equal3_max"
        ),

        pl.col(
            "candidate_structure_concentration_half"
        )
        .min()
        .alias(
            "halfconc_min"
        ),

        pl.col(
            "candidate_structure_concentration_half"
        )
        .median()
        .alias(
            "halfconc_median"
        ),

        pl.col(
            "candidate_structure_concentration_half"
        )
        .mean()
        .alias(
            "halfconc_mean"
        ),

        pl.col(
            "candidate_structure_concentration_half"
        )
        .max()
        .alias(
            "halfconc_max"
        ),
    ])
)


# ============================================================
# SCORE IMPACT
# ============================================================

print(
    "\nCOUNTERFACTUAL SCORE IMPACT"
)


print(
    research.select([
        pl.col(
            "candidate_score_delta_equal_three"
        )
        .min()
        .alias(
            "equal3_delta_min"
        ),

        pl.col(
            "candidate_score_delta_equal_three"
        )
        .median()
        .alias(
            "equal3_delta_median"
        ),

        pl.col(
            "candidate_score_delta_equal_three"
        )
        .mean()
        .alias(
            "equal3_delta_mean"
        ),

        pl.col(
            "candidate_score_delta_equal_three"
        )
        .max()
        .alias(
            "equal3_delta_max"
        ),

        pl.col(
            "candidate_score_delta_concentration_half"
        )
        .min()
        .alias(
            "halfconc_delta_min"
        ),

        pl.col(
            "candidate_score_delta_concentration_half"
        )
        .median()
        .alias(
            "halfconc_delta_median"
        ),

        pl.col(
            "candidate_score_delta_concentration_half"
        )
        .mean()
        .alias(
            "halfconc_delta_mean"
        ),

        pl.col(
            "candidate_score_delta_concentration_half"
        )
        .max()
        .alias(
            "halfconc_delta_max"
        ),
    ])
)


print(
    "\nPRODUCTION VS CANDIDATE SCORE CORRELATIONS"
)


print(
    "production vs equal-three:",
    format_corr(
        correlation(
            research,
            "production_risk_score",
            "candidate_risk_score_equal_three",
        )
    ),
)

print(
    "production vs concentration-half:",
    format_corr(
        correlation(
            research,
            "production_risk_score",
            "candidate_risk_score_concentration_half",
        )
    ),
)


# ============================================================
# RANK CHANGES
# ============================================================

print(
    "\nLARGEST ABSOLUTE RANK CHANGES — EQUAL THREE"
)


print(
    research
    .with_columns(
        pl.col(
            "rank_change_equal_three"
        )
        .abs()
        .alias(
            "_abs_rank_change"
        )
    )
    .sort(
        "_abs_rank_change",
        descending=True,
        nulls_last=True,
    )
    .head(
        10
    )
    .select([
        "symbol",
        "production_risk_rank",
        "candidate_risk_rank_equal_three",
        "rank_change_equal_three",
        "production_risk_score",
        "candidate_risk_score_equal_three",
        "oi_concentration_component",
        "basis_level_component",
        "basis_dispersion_component",
    ])
)


print(
    "\nLARGEST ABSOLUTE RANK CHANGES — 50/25/25"
)


print(
    research
    .with_columns(
        pl.col(
            "rank_change_concentration_half"
        )
        .abs()
        .alias(
            "_abs_rank_change"
        )
    )
    .sort(
        "_abs_rank_change",
        descending=True,
        nulls_last=True,
    )
    .head(
        10
    )
    .select([
        "symbol",
        "production_risk_rank",
        "candidate_risk_rank_concentration_half",
        "rank_change_concentration_half",
        "production_risk_score",
        "candidate_risk_score_concentration_half",
        "oi_concentration_component",
        "basis_level_component",
        "basis_dispersion_component",
    ])
)


# ============================================================
# CANDIDATE TOP 10
# ============================================================

print(
    "\nTOP 10 — EQUAL THREE STRUCTURE"
)


print(
    research
    .sort(
        "candidate_risk_rank_equal_three"
    )
    .head(
        10
    )
    .select([
        "candidate_risk_rank_equal_three",
        "symbol",
        "candidate_risk_score_equal_three",
        "production_risk_rank",
        "production_risk_score",
        "candidate_structure_equal_three",
        "primary_state",
    ])
)


print(
    "\nTOP 10 — 50/25/25 STRUCTURE"
)


print(
    research
    .sort(
        "candidate_risk_rank_concentration_half"
    )
    .head(
        10
    )
    .select([
        "candidate_risk_rank_concentration_half",
        "symbol",
        "candidate_risk_score_concentration_half",
        "production_risk_rank",
        "production_risk_score",
        "candidate_structure_concentration_half",
        "primary_state",
    ])
)


# ============================================================
# OUTPUT
# ============================================================

# ============================================================
# LONGITUDINAL HISTORY STATUS
# ============================================================

history_times = (
    history[
        "research_snapshot_at"
    ]
    .drop_nulls()
    .to_list()
)


if history_times:

    history_span_hours = (
        max(
            history_times
        )
        - min(
            history_times
        )
    ).total_seconds() / 3600.0

else:

    history_span_hours = 0.0


snapshot_count = (
    history.select(
        pl.col(
            "research_snapshot_at"
        )
        .n_unique()
        .alias(
            "snapshot_count"
        )
    )[
        "snapshot_count"
    ][0]
)


print(
    "\nRESEARCH HISTORY STATUS"
)


print(
    pl.DataFrame({
        "history_rows": [
            history.height
        ],
        "snapshot_count": [
            snapshot_count
        ],
        "history_span_hours": [
            history_span_hours
        ],
    })
)


print(
    "\nSaved research snapshot:",
    LATEST_PATH,
)

print(
    "Saved research history:",
    HISTORY_PATH,
)

print(
    "\nProduction risk/latest.parquet was not modified."
)
