from __future__ import annotations

import math
from datetime import timedelta

import polars as pl

# ============================================================
# CONFIGURATION
# ============================================================

MAX_PROVIDER_AGE_MINUTES = 15.0

# Our 20 tracked assets should not have more OI than the
# exchange reports across its entire derivatives venue.
#
# A 10% tolerance allows for endpoint timing differences.
MAX_TRACKED_VS_EXCHANGE_OI = 1.10


# ============================================================
# SNAPSHOT HELPERS
# ============================================================


def latest_snapshot(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    """
    Return the most recent collector snapshot.
    """

    if dataframe.is_empty():
        return dataframe

    latest_time = (
        dataframe["collected_at"]
        .max()
    )

    return dataframe.filter(
        pl.col("collected_at")
        == latest_time
    )


# ============================================================
# MARKET PREPARATION
# ============================================================


def prepare_latest_markets(
    market_pairs: pl.DataFrame,
    exchange_summary: pl.DataFrame,
) -> pl.DataFrame:
    """
    Prepare the latest derivatives market-pair snapshot.

    The function:

        1. Selects the latest collector snapshot.
        2. Keeps only contracts where the tracked asset is
           the base / underlying asset.
        3. Deduplicates repeated market IDs.
        4. Calculates provider-data age.
        5. Cross-checks exchange-level OI.
        6. Creates metric-specific validity flags.

    No rows are destroyed solely because a metric is bad.
    Instead, validity columns determine which observations
    can contribute to OI, funding and basis aggregates.
    """

    markets = latest_snapshot(
        market_pairs
    )

    exchanges = latest_snapshot(
        exchange_summary
    )


    if markets.is_empty():
        return markets


    # --------------------------------------------------------
    # PROVIDER FRESHNESS
    # --------------------------------------------------------

    markets = markets.with_columns(
        (
            (
                pl.col("collected_at")
                - pl.col("timestamp")
            )
            .dt.total_seconds()
            / 60.0
        ).alias("provider_age_minutes")
    )


    # --------------------------------------------------------
    # UNDERLYING-ASSET FILTER
    #
    # Example:
    #
    # ETH/BTC can appear when requesting both ETH and BTC.
    #
    # For BTC derivatives risk we do not want an ETH
    # derivative merely because BTC is the quote asset.
    # --------------------------------------------------------

    markets = markets.filter(
        pl.col("base_symbol")
        == pl.col("symbol")
    )


    # --------------------------------------------------------
    # DUPLICATE MARKET IDs
    #
    # A small number of provider responses contain repeated
    # market IDs for the same asset.
    #
    # Keep the most recently updated provider observation.
    # --------------------------------------------------------

    markets = (
        markets
        .sort(
            [
                "symbol",
                "market_id",
                "timestamp",
            ],
            descending=[
                False,
                False,
                True,
            ],
        )
        .unique(
            subset=[
                "symbol",
                "market_id",
            ],
            keep="first",
            maintain_order=True,
        )
    )


    # ========================================================
    # EXCHANGE OI CONSISTENCY
    # ========================================================

    tracked_exchange_oi = (
        markets
        .filter(
            pl.col("open_interest")
            .is_not_null()
            & pl.col("open_interest")
            .is_finite()
            & (
                pl.col("open_interest")
                >= 0
            )
        )
        .group_by([
            "exchange_id",
            "exchange",
        ])
        .agg(
            pl.col("open_interest")
            .sum()
            .alias(
                "tracked_exchange_oi"
            )
        )
    )


    if exchanges.is_empty():

        venue_quality = (
            tracked_exchange_oi
            .with_columns([
                pl.lit(
                    None,
                    dtype=pl.Float64,
                ).alias(
                    "exchange_total_oi"
                ),

                pl.lit(
                    None,
                    dtype=pl.Float64,
                ).alias(
                    "tracked_vs_exchange_oi"
                ),

                pl.lit(
                    False,
                ).alias(
                    "oi_venue_verified"
                ),

                pl.lit(
                    True,
                ).alias(
                    "oi_venue_consistent"
                ),
            ])
        )

    else:

        exchange_oi = (
            exchanges
            .select([
                "exchange_id",

                pl.col(
                    "open_interest"
                ).alias(
                    "exchange_total_oi"
                ),
            ])
            .unique(
                subset=[
                    "exchange_id"
                ],
                keep="first",
            )
        )


        venue_quality = (
            tracked_exchange_oi
            .join(
                exchange_oi,
                on="exchange_id",
                how="left",
            )
            .with_columns(
                pl.when(
                    pl.col(
                        "exchange_total_oi"
                    ).is_not_null()
                    & pl.col(
                        "exchange_total_oi"
                    ).is_finite()
                    & (
                        pl.col(
                            "exchange_total_oi"
                        )
                        > 0
                    )
                )
                .then(
                    pl.col(
                        "tracked_exchange_oi"
                    )
                    /
                    pl.col(
                        "exchange_total_oi"
                    )
                )
                .otherwise(
                    None
                )
                .alias(
                    "tracked_vs_exchange_oi"
                )
            )
            .with_columns([
                pl.col(
                    "tracked_vs_exchange_oi"
                )
                .is_not_null()
                .alias(
                    "oi_venue_verified"
                ),

                pl.when(
                    pl.col(
                        "tracked_vs_exchange_oi"
                    ).is_null()
                )
                .then(
                    True
                )
                .otherwise(
                    pl.col(
                        "tracked_vs_exchange_oi"
                    )
                    <= MAX_TRACKED_VS_EXCHANGE_OI
                )
                .alias(
                    "oi_venue_consistent"
                ),
            ])
        )


    markets = markets.join(
        venue_quality.select([
            "exchange_id",
            "tracked_exchange_oi",
            "exchange_total_oi",
            "tracked_vs_exchange_oi",
            "oi_venue_verified",
            "oi_venue_consistent",
        ]),
        on="exchange_id",
        how="left",
    )


    # ========================================================
    # QUALITY FLAGS
    # ========================================================

    markets = markets.with_columns(
        (
            pl.col(
                "provider_age_minutes"
            ).is_not_null()
            & (
                pl.col(
                    "provider_age_minutes"
                )
                <= MAX_PROVIDER_AGE_MINUTES
            )
        ).alias(
            "is_fresh"
        )
    )


    # --------------------------------------------------------
    # OI QUALITY
    # --------------------------------------------------------

    markets = markets.with_columns(
        (
            pl.col("is_fresh")

            & (
                ~pl.col(
                    "outlier_detected"
                ).fill_null(False)
            )

            & pl.col(
                "open_interest"
            ).is_not_null()

            & pl.col(
                "open_interest"
            ).is_finite()

            & (
                pl.col(
                    "open_interest"
                )
                >= 0
            )

            & pl.col(
                "oi_venue_consistent"
            ).fill_null(True)

        ).alias(
            "oi_valid"
        )
    )


    # --------------------------------------------------------
    # FUNDING QUALITY
    #
    # We intentionally do not annualise or rescale funding
    # here. Exchange funding intervals need to be verified
    # before making cross-venue annualised comparisons.
    # --------------------------------------------------------

    markets = markets.with_columns(
        (
            pl.col("is_fresh")

            & (
                ~pl.col(
                    "outlier_detected"
                ).fill_null(False)
            )

            & pl.col(
                "funding_rate"
            ).is_not_null()

            & pl.col(
                "funding_rate"
            ).is_finite()

        ).alias(
            "funding_valid"
        )
    )


    # --------------------------------------------------------
    # BASIS QUALITY
    #
    # Median and dispersion statistics will provide most
    # of the robustness here rather than imposing a tight
    # arbitrary numerical cutoff.
    # --------------------------------------------------------

    markets = markets.with_columns(
        (
            pl.col("is_fresh")

            & (
                ~pl.col(
                    "outlier_detected"
                ).fill_null(False)
            )

            & pl.col(
                "index_basis"
            ).is_not_null()

            & pl.col(
                "index_basis"
            ).is_finite()

        ).alias(
            "basis_valid"
        )
    )


    return markets


# ============================================================
# OPEN INTEREST CONCENTRATION
# ============================================================


def calculate_oi_concentration(
    markets: pl.DataFrame,
) -> pl.DataFrame:
    """
    Calculate OI concentration per asset.

    HHI:

        HHI = sum_i (OI_i / total_OI)^2

    where i represents exchanges.

    HHI approaches 1 when OI is concentrated at one venue
    and falls as OI becomes more distributed.
    """

    valid = markets.filter(
        pl.col("oi_valid")
    )


    if valid.is_empty():

        return pl.DataFrame({
            "symbol": [],
            "clean_oi_venues": [],
            "oi_hhi": [],
            "oi_top_venue_share": [],
        })


    venue_oi = (
        valid
        .group_by([
            "symbol",
            "exchange_id",
            "exchange",
        ])
        .agg(
            pl.col(
                "open_interest"
            )
            .sum()
            .alias(
                "venue_oi"
            )
        )
        .with_columns(
            pl.col(
                "venue_oi"
            )
            .sum()
            .over(
                "symbol"
            )
            .alias(
                "asset_total_oi"
            )
        )
        .with_columns(
            pl.when(
                pl.col(
                    "asset_total_oi"
                )
                > 0
            )
            .then(
                pl.col(
                    "venue_oi"
                )
                /
                pl.col(
                    "asset_total_oi"
                )
            )
            .otherwise(
                None
            )
            .alias(
                "venue_oi_share"
            )
        )
    )


    return (
        venue_oi
        .group_by(
            "symbol"
        )
        .agg([
            pl.len().alias(
                "clean_oi_venues"
            ),

            (
                pl.col(
                    "venue_oi_share"
                )
                ** 2
            )
            .sum()
            .alias(
                "oi_hhi"
            ),

            pl.col(
                "venue_oi_share"
            )
            .max()
            .alias(
                "oi_top_venue_share"
            ),
        ])
    )


# ============================================================
# ASSET-LEVEL SNAPSHOT
# ============================================================


def aggregate_derivatives_snapshot(
    markets: pl.DataFrame,
) -> pl.DataFrame:
    """
    Convert the cleaned market-level dataset into one row
    per tracked crypto asset.
    """

    if markets.is_empty():
        return markets


    collected_at = (
        markets["collected_at"]
        .max()
    )


    aggregates = (
        markets
        .group_by(
            "symbol"
        )
        .agg([

            pl.col(
                "asset"
            )
            .drop_nulls()
            .first()
            .alias(
                "asset"
            ),


            # ================================================
            # MARKET COVERAGE
            # ================================================

            pl.len().alias(
                "raw_market_count"
            ),

            pl.col(
                "is_fresh"
            )
            .sum()
            .alias(
                "fresh_market_count"
            ),

            pl.col(
                "outlier_detected"
            )
            .fill_null(False)
            .sum()
            .alias(
                "cmc_outlier_count"
            ),


            # ================================================
            # OPEN INTEREST
            # ================================================

            pl.col(
                "open_interest"
            )
            .sum()
            .alias(
                "raw_total_oi"
            ),

            pl.when(
                pl.col(
                    "oi_valid"
                )
            )
            .then(
                pl.col(
                    "open_interest"
                )
            )
            .otherwise(
                None
            )
            .sum()
            .alias(
                "total_open_interest"
            ),

            pl.col(
                "oi_valid"
            )
            .sum()
            .alias(
                "clean_oi_market_count"
            ),


            # ================================================
            # FUNDING
            # ================================================

            pl.when(
                pl.col(
                    "funding_valid"
                )
            )
            .then(
                pl.col(
                    "funding_rate"
                )
            )
            .otherwise(
                None
            )
            .median()
            .alias(
                "median_funding_rate"
            ),

            pl.when(
                pl.col(
                    "funding_valid"
                )
            )
            .then(
                pl.col(
                    "funding_rate"
                )
            )
            .otherwise(
                None
            )
            .quantile(
                0.25
            )
            .alias(
                "funding_p25"
            ),

            pl.when(
                pl.col(
                    "funding_valid"
                )
            )
            .then(
                pl.col(
                    "funding_rate"
                )
            )
            .otherwise(
                None
            )
            .quantile(
                0.75
            )
            .alias(
                "funding_p75"
            ),

            pl.col(
                "funding_valid"
            )
            .sum()
            .alias(
                "funding_market_count"
            ),


            # ================================================
            # BASIS
            # ================================================

            pl.when(
                pl.col(
                    "basis_valid"
                )
            )
            .then(
                pl.col(
                    "index_basis"
                )
            )
            .otherwise(
                None
            )
            .median()
            .alias(
                "median_index_basis"
            ),

            pl.when(
                pl.col(
                    "basis_valid"
                )
            )
            .then(
                pl.col(
                    "index_basis"
                )
            )
            .otherwise(
                None
            )
            .quantile(
                0.25
            )
            .alias(
                "basis_p25"
            ),

            pl.when(
                pl.col(
                    "basis_valid"
                )
            )
            .then(
                pl.col(
                    "index_basis"
                )
            )
            .otherwise(
                None
            )
            .quantile(
                0.75
            )
            .alias(
                "basis_p75"
            ),

            pl.col(
                "basis_valid"
            )
            .sum()
            .alias(
                "basis_market_count"
            ),

        ])
        .with_columns([

            (
                pl.col(
                    "funding_p75"
                )
                -
                pl.col(
                    "funding_p25"
                )
            ).alias(
                "funding_iqr"
            ),

            (
                pl.col(
                    "basis_p75"
                )
                -
                pl.col(
                    "basis_p25"
                )
            ).alias(
                "basis_iqr"
            ),

            pl.lit(
                collected_at
            ).alias(
                "calculated_at"
            ),
        ])
    )


    concentration = (
        calculate_oi_concentration(
            markets
        )
    )


    return (
        aggregates
        .join(
            concentration,
            on="symbol",
            how="left",
        )
        .sort(
            "total_open_interest",
            descending=True,
        )
    )


# ============================================================
# COMPLETE PIPELINE
# ============================================================


def build_latest_derivatives_snapshot(
    market_pairs: pl.DataFrame,
    exchange_summary: pl.DataFrame,
) -> tuple[
    pl.DataFrame,
    pl.DataFrame,
]:
    """
    Build the latest derivatives state.

    Returns:

        asset_snapshot,
        cleaned_market_snapshot
    """

    cleaned_markets = (
        prepare_latest_markets(
            market_pairs,
            exchange_summary,
        )
    )


    asset_snapshot = (
        aggregate_derivatives_snapshot(
            cleaned_markets
        )
    )


    return (
        asset_snapshot,
        cleaned_markets,
    )

# ============================================================
# OPEN-INTEREST CHANGE FEATURES
# ============================================================

OI_CHANGE_HORIZONS = {
    "1h": 1,
    "4h": 4,
    "24h": 24,
}

# We do not require an observation at exactly t-h.
# The latest observation at or before t-h is accepted if it
# falls within this tolerance.
OI_REFERENCE_TOLERANCE_MINUTES = 10.0


def _finite_positive(
    value,
) -> bool:

    return (
        isinstance(
            value,
            (int, float),
        )
        and math.isfinite(value)
        and value > 0
    )


def _coverage_change(
    current,
    reference,
) -> float | None:

    if not _finite_positive(
        reference
    ):
        return None

    if not isinstance(
        current,
        (int, float),
    ):
        return None

    if not math.isfinite(
        float(current)
    ):
        return None

    return (
        float(current)
        / float(reference)
        - 1.0
    )


def add_oi_change_features(
    history: pl.DataFrame,
    latest_snapshot: pl.DataFrame,
) -> pl.DataFrame:
    """
    Add 1h, 4h and 24h cleaned-open-interest changes to the
    latest asset snapshot.

    The reference observation is the newest snapshot at or
    before t-h.

    It must be within OI_REFERENCE_TOLERANCE_MINUTES of the
    requested horizon.

    We also retain market/venue coverage changes so downstream
    risk logic can detect OI changes caused by data-universe
    changes rather than genuine leverage changes.
    """

    if latest_snapshot.is_empty():
        return latest_snapshot


    if (
        history.is_empty()
        or "calculated_at"
        not in history.columns
    ):

        result = latest_snapshot

        for label in (
            OI_CHANGE_HORIZONS
        ):

            result = (
                result
                .with_columns([
                    pl.lit(
                        None,
                        dtype=pl.Float64,
                    ).alias(
                        f"open_interest_change_{label}"
                    ),

                    pl.lit(
                        None,
                        dtype=pl.Float64,
                    ).alias(
                        f"open_interest_change_usd_{label}"
                    ),

                    pl.lit(
                        None,
                        dtype=pl.Float64,
                    ).alias(
                        f"open_interest_reference_{label}"
                    ),

                    pl.lit(
                        None,
                        dtype=pl.Datetime(
                            "us",
                            "UTC",
                        ),
                    ).alias(
                        f"open_interest_reference_time_{label}"
                    ),

                    pl.lit(
                        None,
                        dtype=pl.Float64,
                    ).alias(
                        f"oi_reference_offset_minutes_{label}"
                    ),

                    pl.lit(
                        None,
                        dtype=pl.Float64,
                    ).alias(
                        f"oi_market_coverage_change_{label}"
                    ),

                    pl.lit(
                        None,
                        dtype=pl.Float64,
                    ).alias(
                        f"oi_venue_coverage_change_{label}"
                    ),

                    pl.lit(
                        False,
                    ).alias(
                        f"oi_change_available_{label}"
                    ),
                ])
            )

        return result


    history = history.sort([
        "symbol",
        "calculated_at",
    ])


    output_rows = []


    for row in (
        latest_snapshot.to_dicts()
    ):

        symbol = row.get(
            "symbol"
        )

        current_time = row.get(
            "calculated_at"
        )

        current_oi = row.get(
            "total_open_interest"
        )


        symbol_history = (
            history
            .filter(
                pl.col("symbol")
                == symbol
            )
            .sort(
                "calculated_at"
            )
        )


        for (
            label,
            hours,
        ) in OI_CHANGE_HORIZONS.items():

            # ------------------------------------------------
            # DEFAULT VALUES
            # ------------------------------------------------

            row[
                f"open_interest_change_{label}"
            ] = None

            row[
                f"open_interest_change_usd_{label}"
            ] = None

            row[
                f"open_interest_reference_{label}"
            ] = None

            row[
                f"open_interest_reference_time_{label}"
            ] = None

            row[
                f"oi_reference_offset_minutes_{label}"
            ] = None

            row[
                f"oi_market_coverage_change_{label}"
            ] = None

            row[
                f"oi_venue_coverage_change_{label}"
            ] = None

            row[
                f"oi_change_available_{label}"
            ] = False


            if current_time is None:
                continue


            target_time = (
                current_time
                - timedelta(
                    hours=hours
                )
            )


            # ------------------------------------------------
            # FIND MOST RECENT OBSERVATION AT OR BEFORE t-h
            # ------------------------------------------------

            reference = (
                symbol_history
                .filter(
                    pl.col(
                        "calculated_at"
                    )
                    <= target_time
                )
                .tail(1)
            )


            if reference.is_empty():
                continue


            reference_row = (
                reference.row(
                    0,
                    named=True,
                )
            )


            reference_time = (
                reference_row.get(
                    "calculated_at"
                )
            )


            if reference_time is None:
                continue


            offset_minutes = (
                (
                    target_time
                    - reference_time
                ).total_seconds()
                / 60.0
            )


            # Observation is too far from requested horizon.
            if (
                offset_minutes < 0
                or offset_minutes
                > OI_REFERENCE_TOLERANCE_MINUTES
            ):
                continue


            reference_oi = (
                reference_row.get(
                    "total_open_interest"
                )
            )


            row[
                f"open_interest_reference_{label}"
            ] = reference_oi

            row[
                f"open_interest_reference_time_{label}"
            ] = reference_time

            row[
                f"oi_reference_offset_minutes_{label}"
            ] = offset_minutes


            # ------------------------------------------------
            # COVERAGE DIAGNOSTICS
            # ------------------------------------------------

            row[
                f"oi_market_coverage_change_{label}"
            ] = _coverage_change(
                row.get(
                    "clean_oi_market_count"
                ),
                reference_row.get(
                    "clean_oi_market_count"
                ),
            )


            row[
                f"oi_venue_coverage_change_{label}"
            ] = _coverage_change(
                row.get(
                    "clean_oi_venues"
                ),
                reference_row.get(
                    "clean_oi_venues"
                ),
            )


            # ------------------------------------------------
            # OI CHANGE
            # ------------------------------------------------

            if not (
                _finite_positive(
                    current_oi
                )
                and _finite_positive(
                    reference_oi
                )
            ):
                continue


            row[
                f"open_interest_change_{label}"
            ] = (
                current_oi
                / reference_oi
                - 1.0
            )


            row[
                f"open_interest_change_usd_{label}"
            ] = (
                current_oi
                - reference_oi
            )


            row[
                f"oi_change_available_{label}"
            ] = True


        output_rows.append(
            row
        )


    return pl.DataFrame(
        output_rows
    )


# ============================================================
# COMMON-UNIVERSE OPEN-INTEREST CHANGES
# ============================================================

COMMON_OI_CHANGE_HORIZONS = {
    "1h": 1,
    "4h": 4,
    "24h": 24,
}

COMMON_OI_REFERENCE_TOLERANCE_MINUTES = 10.0


def prepare_common_oi_market_snapshot(
    cleaned_markets: pl.DataFrame,
) -> pl.DataFrame:
    """
    Store only the fields required to construct common-universe
    OI changes.

    Only OI-valid markets are retained.

    A market observation is identified by:
        symbol
        market_id
        exchange_id

    collected_at identifies the collection cycle.
    """

    if cleaned_markets.is_empty():

        return cleaned_markets


    required_columns = [
        "symbol",
        "market_id",
        "exchange_id",
        "exchange",
        "open_interest",
        "oi_valid",
        "collected_at",
    ]


    missing = [
        column
        for column in required_columns
        if column not in cleaned_markets.columns
    ]


    if missing:

        raise ValueError(
            "Missing columns required for common OI history: "
            + ", ".join(missing)
        )


    return (
        cleaned_markets

        .filter(
            pl.col("oi_valid")
            .fill_null(False)
        )

        .filter(
            pl.col("symbol")
            .is_not_null()
        )

        .filter(
            pl.col("market_id")
            .is_not_null()
        )

        .filter(
            pl.col("exchange_id")
            .is_not_null()
        )

        .filter(
            pl.col("open_interest")
            .is_not_null()
            &
            pl.col("open_interest")
            .is_finite()
            &
            (
                pl.col("open_interest")
                >= 0
            )
        )

        .select([
            "symbol",
            "market_id",
            "exchange_id",
            "exchange",
            "open_interest",
            "collected_at",
        ])

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


def _add_empty_common_oi_columns(
    dataframe: pl.DataFrame,
    label: str,
) -> pl.DataFrame:

    return dataframe.with_columns([

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"open_interest_change_common_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"open_interest_change_common_usd_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"common_oi_current_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"common_oi_reference_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Int64,
        ).alias(
            f"common_market_count_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Int64,
        ).alias(
            f"common_venue_count_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"common_oi_share_current_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"common_oi_share_reference_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"common_oi_overlap_min_share_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Datetime(
                "us",
                "UTC",
            ),
        ).alias(
            f"common_oi_reference_time_{label}"
        ),

        pl.lit(
            None,
            dtype=pl.Float64,
        ).alias(
            f"common_oi_reference_offset_minutes_{label}"
        ),

        pl.lit(
            False,
        ).alias(
            f"common_oi_change_available_{label}"
        ),
    ])


def add_common_universe_oi_features(
    market_history: pl.DataFrame,
    latest_snapshot: pl.DataFrame,
) -> pl.DataFrame:
    """
    Calculate OI changes on the intersection of markets that
    were OI-valid at both t and t-h.

    For each horizon:

        I = S_t ∩ S_(t-h)

        delta_OI_common
            = sum(OI_t over I)
              / sum(OI_(t-h) over I)
              - 1

    This removes mechanical OI changes created by contracts or
    venues entering/leaving the clean aggregation universe.
    """

    result = latest_snapshot


    if (
        market_history.is_empty()
        or latest_snapshot.is_empty()
    ):

        for label in (
            COMMON_OI_CHANGE_HORIZONS
        ):

            result = (
                _add_empty_common_oi_columns(
                    result,
                    label,
                )
            )

        return result


    history = (
        market_history
        .sort(
            "collected_at"
        )
    )


    snapshot_times = (
        history
        .select(
            "collected_at"
        )
        .unique()
        .sort(
            "collected_at"
        )[
            "collected_at"
        ]
        .to_list()
    )


    if not snapshot_times:

        for label in (
            COMMON_OI_CHANGE_HORIZONS
        ):

            result = (
                _add_empty_common_oi_columns(
                    result,
                    label,
                )
            )

        return result


    current_time = (
        snapshot_times[-1]
    )


    current = (
        history
        .filter(
            pl.col(
                "collected_at"
            )
            == current_time
        )
    )


    for (
        label,
        hours,
    ) in (
        COMMON_OI_CHANGE_HORIZONS
        .items()
    ):

        target_time = (
            current_time
            - timedelta(
                hours=hours
            )
        )


        candidates = [
            value
            for value in snapshot_times
            if value <= target_time
        ]


        if not candidates:

            result = (
                _add_empty_common_oi_columns(
                    result,
                    label,
                )
            )

            continue


        reference_time = (
            candidates[-1]
        )


        offset_minutes = (
            (
                target_time
                - reference_time
            )
            .total_seconds()
            / 60.0
        )


        if (
            offset_minutes < 0
            or offset_minutes
            >
            COMMON_OI_REFERENCE_TOLERANCE_MINUTES
        ):

            result = (
                _add_empty_common_oi_columns(
                    result,
                    label,
                )
            )

            continue


        reference = (
            history
            .filter(
                pl.col(
                    "collected_at"
                )
                == reference_time
            )
        )


        # ====================================================
        # TOTAL VALID OI AT EACH SNAPSHOT
        # ====================================================

        current_totals = (
            current

            .group_by(
                "symbol"
            )

            .agg(
                pl.col(
                    "open_interest"
                )
                .sum()
                .alias(
                    "_current_total_valid_oi"
                )
            )
        )


        reference_totals = (
            reference

            .group_by(
                "symbol"
            )

            .agg(
                pl.col(
                    "open_interest"
                )
                .sum()
                .alias(
                    "_reference_total_valid_oi"
                )
            )
        )


        # ====================================================
        # INTERSECTION
        # ====================================================

        current_for_join = (
            current

            .select([
                "symbol",
                "market_id",
                "exchange_id",
                "open_interest",
            ])

            .rename({
                "open_interest":
                    "_oi_current",
            })
        )


        reference_for_join = (
            reference

            .select([
                "symbol",
                "market_id",
                "exchange_id",
                "open_interest",
            ])

            .rename({
                "open_interest":
                    "_oi_reference",
            })
        )


        common = (
            current_for_join
            .join(
                reference_for_join,
                on=[
                    "symbol",
                    "market_id",
                    "exchange_id",
                ],
                how="inner",
            )
        )


        if common.is_empty():

            result = (
                _add_empty_common_oi_columns(
                    result,
                    label,
                )
            )

            continue


        # ====================================================
        # COMMON-UNIVERSE AGGREGATION
        # ====================================================

        common_summary = (
            common

            .group_by(
                "symbol"
            )

            .agg([

                pl.col(
                    "_oi_current"
                )
                .sum()
                .alias(
                    f"common_oi_current_{label}"
                ),

                pl.col(
                    "_oi_reference"
                )
                .sum()
                .alias(
                    f"common_oi_reference_{label}"
                ),

                pl.len()
                .cast(
                    pl.Int64
                )
                .alias(
                    f"common_market_count_{label}"
                ),

                pl.col(
                    "exchange_id"
                )
                .n_unique()
                .cast(
                    pl.Int64
                )
                .alias(
                    f"common_venue_count_{label}"
                ),
            ])
        )


        features = (
            common_summary

            .join(
                current_totals,
                on="symbol",
                how="left",
            )

            .join(
                reference_totals,
                on="symbol",
                how="left",
            )

            .with_columns([

                (
                    pl.col(
                        f"common_oi_current_{label}"
                    )
                    /
                    pl.col(
                        f"common_oi_reference_{label}"
                    )
                    - 1.0
                ).alias(
                    f"open_interest_change_common_{label}"
                ),

                (
                    pl.col(
                        f"common_oi_current_{label}"
                    )
                    -
                    pl.col(
                        f"common_oi_reference_{label}"
                    )
                ).alias(
                    f"open_interest_change_common_usd_{label}"
                ),

                (
                    pl.col(
                        f"common_oi_current_{label}"
                    )
                    /
                    pl.col(
                        "_current_total_valid_oi"
                    )
                ).alias(
                    f"common_oi_share_current_{label}"
                ),

                (
                    pl.col(
                        f"common_oi_reference_{label}"
                    )
                    /
                    pl.col(
                        "_reference_total_valid_oi"
                    )
                ).alias(
                    f"common_oi_share_reference_{label}"
                ),

                pl.lit(
                    reference_time
                )
                .cast(
                    pl.Datetime(
                        "us",
                        "UTC",
                    )
                )
                .alias(
                    f"common_oi_reference_time_{label}"
                ),

                pl.lit(
                    float(
                        offset_minutes
                    )
                )
                .alias(
                    f"common_oi_reference_offset_minutes_{label}"
                ),
            ])

            .with_columns(

                pl.min_horizontal([
                    pl.col(
                        f"common_oi_share_current_{label}"
                    ),
                    pl.col(
                        f"common_oi_share_reference_{label}"
                    ),
                ])
                .alias(
                    f"common_oi_overlap_min_share_{label}"
                )

            )

            .with_columns(

                (
                    (
                        pl.col(
                            f"common_market_count_{label}"
                        )
                        > 0
                    )
                    &
                    (
                        pl.col(
                            f"common_oi_reference_{label}"
                        )
                        > 0
                    )
                    &
                    (
                        pl.col(
                            f"common_oi_current_{label}"
                        )
                        >= 0
                    )
                )
                .alias(
                    f"common_oi_change_available_{label}"
                )

            )

            .select([
                "symbol",

                f"open_interest_change_common_{label}",
                f"open_interest_change_common_usd_{label}",

                f"common_oi_current_{label}",
                f"common_oi_reference_{label}",

                f"common_market_count_{label}",
                f"common_venue_count_{label}",

                f"common_oi_share_current_{label}",
                f"common_oi_share_reference_{label}",
                f"common_oi_overlap_min_share_{label}",

                f"common_oi_reference_time_{label}",
                f"common_oi_reference_offset_minutes_{label}",

                f"common_oi_change_available_{label}",
            ])
        )


        result = (
            result
            .join(
                features,
                on="symbol",
                how="left",
            )
            .with_columns(

                pl.col(
                    f"common_oi_change_available_{label}"
                )
                .fill_null(False)

            )
        )


    return result