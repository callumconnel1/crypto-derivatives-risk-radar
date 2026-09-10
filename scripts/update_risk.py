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


if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from backend.risk_radar.risk import (
    build_risk_snapshot,
)


# ============================================================
# PATHS
# ============================================================

STATES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "states"
    / "latest.parquet"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "risk"
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


def _finite(
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
    """
    Calculate Pearson correlation between two component
    columns using rows where both values are available.
    """

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


    if not _finite(result):

        return None


    return float(
        result
    )


# ============================================================
# LOAD STATE SNAPSHOT
# ============================================================

states = require_file(
    STATES_PATH
)


print(
    "States:",
    states.shape,
)


# ============================================================
# BUILD RISK SNAPSHOT
# ============================================================

snapshot = build_risk_snapshot(
    states
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
                "risk_source_at",
                "risk_version",
            ],
            keep="last",
        )

        .sort([
            "symbol",
            "risk_source_at",
        ])
    )

else:

    history = (
        snapshot

        .sort([
            "symbol",
            "risk_source_at",
        ])
    )


atomic_write(
    history,
    HISTORY_PATH,
)


# ============================================================
# PROVISIONAL CDRR RANKING
# ============================================================

print(
    "\nPROVISIONAL CDRR RANKING"
)


print(
    snapshot

    .select([
        "risk_rank",
        "symbol",

        "provisional_risk_score",
        "risk_cross_percentile",

        "volatility_component",
        "leverage_component",
        "funding_component",
        "liquidation_component",
        "market_structure_component",

        "primary_state",

        "risk_ready",
    ])

    .sort(
        "risk_rank"
    )
)


# ============================================================
# COMPONENT DETAILS
# ============================================================

print(
    "\nCOMPONENT DETAILS"
)


print(
    snapshot

    .sort(
        "provisional_risk_score",
        descending=True,
        nulls_last=True,
    )

    .select([
        "symbol",

        # ----------------------------------------------------
        # VOLATILITY
        # ----------------------------------------------------

        "vol_percentile_24h",
        "vol_expansion_cross_percentile",
        "volatility_component",

        # ----------------------------------------------------
        # LEVERAGE / OPEN INTEREST
        # ----------------------------------------------------

        "open_interest_change_common_1h",
        "oi_change_magnitude_percentile_1h",
        "leverage_component",

        # ----------------------------------------------------
        # FUNDING
        # ----------------------------------------------------

        "median_funding_rate",

        "funding_cross_confirmed_tail_percentile",

        "funding_confirmed_tail_percentile",

        "funding_component",

        "funding_component_source",

        # ----------------------------------------------------
        # LIQUIDATIONS
        # ----------------------------------------------------

        "liquidation_percentile_1h",

        "liquidations_to_oi_percentile_1h",

        "liquidation_confirmed_percentile_1h",

        "liquidation_component",

        # ----------------------------------------------------
        # MARKET STRUCTURE
        # ----------------------------------------------------

        "oi_hhi",

        "oi_concentration_percentile",

        "market_structure_component",
    ])
)


# ============================================================
# RISK READINESS
# ============================================================

print(
    "\nRISK READINESS"
)


print(
    snapshot.select([

        pl.col(
            "risk_ready"
        )
        .sum()
        .alias(
            "assets_ready"
        ),

        pl.col(
            "component_count"
        )
        .min()
        .alias(
            "min_components"
        ),

        pl.col(
            "component_count"
        )
        .median()
        .alias(
            "median_components"
        ),

        pl.col(
            "component_count"
        )
        .max()
        .alias(
            "max_components"
        ),
    ])
)


# ============================================================
# SCORE DISTRIBUTION
# ============================================================

print(
    "\nSCORE DISTRIBUTION"
)


print(
    snapshot.select([

        pl.col(
            "provisional_risk_score"
        )
        .min()
        .alias(
            "min_score"
        ),

        pl.col(
            "provisional_risk_score"
        )
        .median()
        .alias(
            "median_score"
        ),

        pl.col(
            "provisional_risk_score"
        )
        .mean()
        .alias(
            "mean_score"
        ),

        pl.col(
            "provisional_risk_score"
        )
        .max()
        .alias(
            "max_score"
        ),
    ])
)


# ============================================================
# COMPONENT DISTRIBUTIONS
# ============================================================

print(
    "\nCOMPONENT DISTRIBUTIONS"
)


component_columns = [
    "volatility_component",
    "leverage_component",
    "funding_component",
    "liquidation_component",
    "market_structure_component",
]


for component in component_columns:

    print(
        f"\n{component}"
    )


    print(
        snapshot.select([

            pl.col(
                component
            )
            .min()
            .alias(
                "min"
            ),

            pl.col(
                component
            )
            .median()
            .alias(
                "median"
            ),

            pl.col(
                component
            )
            .mean()
            .alias(
                "mean"
            ),

            pl.col(
                component
            )
            .max()
            .alias(
                "max"
            ),
        ])
    )


# ============================================================
# COMPONENT CORRELATIONS
# ============================================================

print(
    "\nCOMPONENT CORRELATIONS"
)


for i in range(
    len(
        component_columns
    )
):

    for j in range(
        i + 1,
        len(
            component_columns
        ),
    ):

        first = (
            component_columns[
                i
            ]
        )


        second = (
            component_columns[
                j
            ]
        )


        correlation = (
            pairwise_correlation(
                snapshot,
                first,
                second,
            )
        )


        if correlation is None:

            correlation_text = "NA"

        else:

            correlation_text = (
                f"{correlation:+.4f}"
            )


        print(
            f"{first:28s} "
            f"vs "
            f"{second:28s} "
            f"{correlation_text}"
        )


# ============================================================
# COMPONENT VS TOTAL SCORE
# ============================================================

print(
    "\nCOMPONENT VS TOTAL SCORE"
)


for component in component_columns:

    correlation = (
        pairwise_correlation(
            snapshot,
            component,
            "provisional_risk_score",
        )
    )


    if correlation is None:

        correlation_text = "NA"

    else:

        correlation_text = (
            f"{correlation:+.4f}"
        )


    print(
        f"{component:28s} "
        f"vs provisional_risk_score "
        f"{correlation_text}"
    )


# ============================================================
# FUNDING COMPONENT SOURCE
# ============================================================

print(
    "\nFUNDING COMPONENT SOURCE"
)


print(
    snapshot

    .group_by(
        "funding_component_source"
    )

    .len()

    .sort(
        "len",
        descending=True,
    )
)


# ============================================================
# RISK VERSION
# ============================================================

print(
    "\nRISK VERSION"
)


print(
    snapshot

    .group_by(
        "risk_version"
    )

    .len()

    .sort(
        "len",
        descending=True,
    )
)


# ============================================================
# MISSING COMPONENTS
# ============================================================

missing = (
    snapshot

    .filter(
        ~pl.col(
            "risk_ready"
        )
    )
)


if not missing.is_empty():

    print(
        "\nINCOMPLETE ASSETS"
    )


    print(
        missing.select([
            "symbol",

            "component_count",

            "missing_components",

            "state_ready_1h",

            "state_quality",
        ])
    )


# ============================================================
# TOP / BOTTOM RISK SNAPSHOT
# ============================================================

ready = (
    snapshot

    .filter(
        pl.col(
            "risk_ready"
        )
    )
)


if not ready.is_empty():

    print(
        "\nTOP 5 PROVISIONAL RISK"
    )


    print(
        ready

        .sort(
            "provisional_risk_score",
            descending=True,
        )

        .head(
            5
        )

        .select([
            "risk_rank",
            "symbol",
            "provisional_risk_score",

            "volatility_component",
            "leverage_component",
            "funding_component",
            "liquidation_component",
            "market_structure_component",

            "primary_state",
        ])
    )


    print(
        "\nBOTTOM 5 PROVISIONAL RISK"
    )


    print(
        ready

        .sort(
            "provisional_risk_score"
        )

        .head(
            5
        )

        .select([
            "risk_rank",
            "symbol",
            "provisional_risk_score",

            "volatility_component",
            "leverage_component",
            "funding_component",
            "liquidation_component",
            "market_structure_component",

            "primary_state",
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