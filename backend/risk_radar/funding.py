from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import polars as pl


# ============================================================
# CONFIGURATION
# ============================================================

MIN_HISTORY_SPAN_HOURS = 24.0

MIN_HISTORY_OBSERVATIONS = 120

MIN_DISTINCT_FUNDING_VALUES = 8

HISTORY_WINDOW_DAYS = 7

FUNDING_CROWDED_PERCENTILE = 0.80
FUNDING_EXTREME_PERCENTILE = 0.95


# ============================================================
# BASIC HELPERS
# ============================================================


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


def _percentile_rank(
    values: list,
) -> list[float | None]:
    """
    Cross-sectional percentile rank in [0, 1].

    Lowest finite value -> 0
    Highest finite value -> 1

    Ties receive their average rank.
    """

    output: list[
        float | None
    ] = [
        None
        for _ in values
    ]


    valid = []


    for index, value in enumerate(
        values
    ):

        if not _finite(value):

            continue


        valid.append(
            (
                index,
                float(value),
            )
        )


    count = len(
        valid
    )


    if count == 0:

        return output


    if count == 1:

        index, _ = valid[0]

        output[
            index
        ] = 0.5

        return output


    valid.sort(
        key=lambda item:
            item[1]
    )


    position = 0


    while position < count:

        end = (
            position + 1
        )


        current_value = (
            valid[
                position
            ][1]
        )


        while (
            end < count
            and
            valid[end][1]
            == current_value
        ):

            end += 1


        average_rank = (
            position
            + (
                end - 1
            )
        ) / 2.0


        percentile = (
            average_rank
            / (
                count - 1
            )
        )


        for i in range(
            position,
            end,
        ):

            original_index = (
                valid[i][0]
            )


            output[
                original_index
            ] = percentile


        position = end


    return output


def _historical_percentile(
    current: float,
    history: list[float],
) -> float | None:
    """
    Mid-rank empirical percentile of current against prior
    observations only.
    """

    if not _finite(
        current
    ):

        return None


    clean_history = [
        float(value)
        for value in history
        if _finite(value)
    ]


    count = len(
        clean_history
    )


    if count == 0:

        return None


    current = float(
        current
    )


    less = sum(
        value < current
        for value in clean_history
    )


    equal = sum(
        value == current
        for value in clean_history
    )


    return (
        less
        + 0.5 * equal
    ) / count


def _historical_magnitude_percentile(
    current,
    history: list[float],
) -> float | None:
    """
    Historical percentile of absolute funding magnitude.

    This prevents a tiny funding observation from appearing
    extreme merely because its sign is unusual.
    """

    if not _finite(
        current
    ):

        return None


    magnitude_history = [
        abs(
            float(value)
        )
        for value in history
        if _finite(value)
    ]


    if not magnitude_history:

        return None


    return _historical_percentile(
        current=abs(
            float(current)
        ),
        history=magnitude_history,
    )


def _quantile(
    values: list[float],
    quantile: float,
) -> float | None:

    if not values:

        return None


    series = pl.Series(
        "value",
        values,
        dtype=pl.Float64,
    )


    result = series.quantile(
        quantile,
        interpolation="linear",
    )


    if result is None:

        return None


    return float(
        result
    )


def _median(
    values: list[float],
) -> float | None:

    return _quantile(
        values,
        0.50,
    )


def _mad(
    values: list[float],
) -> float | None:

    centre = _median(
        values
    )


    if centre is None:

        return None


    deviations = [
        abs(
            value - centre
        )
        for value in values
    ]


    return _median(
        deviations
    )


def _directional_tail_percentile(
    funding_rate,
    percentile,
) -> float | None:
    """
    Convert a signed percentile into directional tail
    extremeness.

    Positive funding:
        upper tail -> long-side pressure

    Negative funding:
        lower tail -> short-side pressure
    """

    if not (
        _finite(funding_rate)
        and
        _finite(percentile)
    ):

        return None


    rate = float(
        funding_rate
    )


    percentile = float(
        percentile
    )


    if rate > 0:

        return percentile


    if rate < 0:

        return (
            1.0
            - percentile
        )


    return 0.0


def _minimum_if_finite(
    first,
    second,
) -> float | None:

    if not (
        _finite(first)
        and
        _finite(second)
    ):

        return None


    return min(
        float(first),
        float(second),
    )


# ============================================================
# HISTORY PREPARATION
# ============================================================


def prepare_funding_history(
    derivatives_history: pl.DataFrame,
) -> pl.DataFrame:

    required = [
        "symbol",
        "median_funding_rate",
        "calculated_at",
    ]


    missing = [
        column
        for column in required
        if column
        not in derivatives_history.columns
    ]


    if missing:

        raise ValueError(
            "Missing funding-history columns: "
            + ", ".join(
                missing
            )
        )


    history = (
        derivatives_history

        .select([
            "symbol",
            "median_funding_rate",
            "calculated_at",
        ])

        .filter(
            pl.col(
                "symbol"
            ).is_not_null()
        )

        .filter(
            pl.col(
                "calculated_at"
            ).is_not_null()
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


    latest_time = (
        history[
            "calculated_at"
        ].max()
    )


    if latest_time is not None:

        cutoff = (
            latest_time
            - timedelta(
                days=HISTORY_WINDOW_DAYS
            )
        )


        history = (
            history

            .filter(
                pl.col(
                    "calculated_at"
                )
                >= cutoff
            )
        )


    return history


# ============================================================
# FUNDING CROWDING CLASSIFICATION
# ============================================================


def classify_funding_crowding(
    funding_rate,
    confirmed_tail_percentile,
    history_available: bool,
) -> str:

    if not history_available:

        return "HISTORY BUILDING"


    if not (
        _finite(funding_rate)
        and
        _finite(
            confirmed_tail_percentile
        )
    ):

        return "UNAVAILABLE"


    rate = float(
        funding_rate
    )


    percentile = float(
        confirmed_tail_percentile
    )


    if (
        percentile
        < FUNDING_CROWDED_PERCENTILE
    ):

        return "NORMAL"


    intensity = (
        "EXTREME"
        if percentile
        >= FUNDING_EXTREME_PERCENTILE
        else "CROWDED"
    )


    if rate > 0:

        return (
            f"{intensity} LONG"
        )


    if rate < 0:

        return (
            f"{intensity} SHORT"
        )


    return "NORMAL"


# ============================================================
# SNAPSHOT BUILDER
# ============================================================


def build_funding_snapshot(
    derivatives_latest: pl.DataFrame,
    derivatives_history: pl.DataFrame,
) -> pl.DataFrame:
    """
    Construct funding-crowding features.

    CROSS-SECTIONAL SIGNAL

        directional tail
            = signed position in current cross section

        magnitude percentile
            = rank of |funding|

        cross confirmed
            = min(
                directional tail,
                magnitude percentile
              )


    HISTORICAL SIGNAL

        directional tail
            = signed position in own historical distribution

        magnitude percentile
            = historical percentile of |funding|

        historical confirmed
            = min(
                directional tail,
                magnitude percentile
              )


    FINAL CROWDING SIGNAL

        confirmed
            = min(
                cross confirmed,
                historical confirmed
              )


    Historical classification remains unavailable until the
    minimum history requirements are satisfied.
    """

    if derivatives_latest.is_empty():

        return derivatives_latest


    required_latest = [
        "symbol",
        "asset",
        "median_funding_rate",
        "funding_iqr",
        "funding_market_count",
        "calculated_at",
    ]


    missing = [
        column
        for column in required_latest
        if column
        not in derivatives_latest.columns
    ]


    if missing:

        raise ValueError(
            "Missing latest funding columns: "
            + ", ".join(
                missing
            )
        )


    history = prepare_funding_history(
        derivatives_history
    )


    latest = (
        derivatives_latest

        .select([
            "symbol",
            "asset",
            "median_funding_rate",
            "funding_iqr",
            "funding_market_count",
            "calculated_at",
        ])

        .sort(
            "symbol"
        )
    )


    rows = (
        latest.to_dicts()
    )


    # ========================================================
    # CURRENT CROSS SECTION
    # ========================================================

    funding_values = [
        row.get(
            "median_funding_rate"
        )
        for row in rows
    ]


    absolute_funding_values = [
        (
            abs(
                float(value)
            )
            if _finite(value)
            else None
        )
        for value in funding_values
    ]


    funding_signed_percentiles = (
        _percentile_rank(
            funding_values
        )
    )


    funding_absolute_percentiles = (
        _percentile_rank(
            absolute_funding_values
        )
    )


    generated_at = datetime.now(
        timezone.utc
    )


    output = []


    # ========================================================
    # PER-ASSET CALIBRATION
    # ========================================================

    for index, row in enumerate(
        rows
    ):

        symbol = row[
            "symbol"
        ]


        current_time = row.get(
            "calculated_at"
        )


        current_funding = row.get(
            "median_funding_rate"
        )


        # ====================================================
        # PRIOR HISTORY ONLY
        # ====================================================

        prior = (
            history

            .filter(
                pl.col(
                    "symbol"
                )
                == symbol
            )
        )


        if isinstance(
            current_time,
            datetime,
        ):

            prior = (
                prior

                .filter(
                    pl.col(
                        "calculated_at"
                    )
                    < current_time
                )
            )


        prior_values = [
            float(value)
            for value in (
                prior[
                    "median_funding_rate"
                ].to_list()
            )
            if _finite(value)
        ]


        observation_count = len(
            prior_values
        )


        distinct_count = len(
            set(
                prior_values
            )
        )


        first_time = (
            prior[
                "calculated_at"
            ].min()
            if not prior.is_empty()
            else None
        )


        last_time = (
            prior[
                "calculated_at"
            ].max()
            if not prior.is_empty()
            else None
        )


        if (
            isinstance(
                first_time,
                datetime,
            )
            and
            isinstance(
                last_time,
                datetime,
            )
        ):

            span_hours = (
                (
                    last_time
                    - first_time
                ).total_seconds()
                / 3600.0
            )

        else:

            span_hours = 0.0


        history_available = (
            observation_count
            >= MIN_HISTORY_OBSERVATIONS
            and
            span_hours
            >= MIN_HISTORY_SPAN_HOURS
            and
            distinct_count
            >= MIN_DISTINCT_FUNDING_VALUES
        )


        # ====================================================
        # HISTORICAL DISTRIBUTION
        # ====================================================

        if (
            history_available
            and
            _finite(
                current_funding
            )
        ):

            history_percentile = (
                _historical_percentile(
                    current=float(
                        current_funding
                    ),
                    history=prior_values,
                )
            )


            history_magnitude_percentile = (
                _historical_magnitude_percentile(
                    current=(
                        current_funding
                    ),
                    history=(
                        prior_values
                    ),
                )
            )

        else:

            history_percentile = None

            history_magnitude_percentile = None


        history_median = (
            _median(
                prior_values
            )
            if prior_values
            else None
        )


        history_p25 = (
            _quantile(
                prior_values,
                0.25,
            )
            if prior_values
            else None
        )


        history_p75 = (
            _quantile(
                prior_values,
                0.75,
            )
            if prior_values
            else None
        )


        history_iqr = (
            (
                history_p75
                - history_p25
            )
            if (
                history_p25
                is not None
                and
                history_p75
                is not None
            )
            else None
        )


        history_mad = (
            _mad(
                prior_values
            )
            if prior_values
            else None
        )


        # ====================================================
        # ROBUST HISTORICAL Z
        # ====================================================

        if (
            history_available
            and
            _finite(
                current_funding
            )
            and
            _finite(
                history_median
            )
            and
            _finite(
                history_mad
            )
            and
            float(
                history_mad
            )
            > 0
        ):

            robust_sigma = (
                1.4826
                * float(
                    history_mad
                )
            )


            robust_z = (
                (
                    float(
                        current_funding
                    )
                    - float(
                        history_median
                    )
                )
                / robust_sigma
            )

        else:

            robust_z = None


        # ====================================================
        # CROSS-SECTIONAL SIGNAL
        # ====================================================

        cross_percentile = (
            funding_signed_percentiles[
                index
            ]
        )


        cross_magnitude_percentile = (
            funding_absolute_percentiles[
                index
            ]
        )


        cross_directional_tail = (
            _directional_tail_percentile(
                current_funding,
                cross_percentile,
            )
        )


        cross_confirmed_tail = (
            _minimum_if_finite(
                cross_directional_tail,
                cross_magnitude_percentile,
            )
        )


        # ====================================================
        # HISTORICAL SIGNAL
        # ====================================================

        history_directional_tail = (
            _directional_tail_percentile(
                current_funding,
                history_percentile,
            )
        )


        history_confirmed_tail = (
            _minimum_if_finite(
                history_directional_tail,
                history_magnitude_percentile,
            )
        )


        # ====================================================
        # FINAL CONFIRMATION
        # ====================================================

        confirmed_tail = (
            _minimum_if_finite(
                cross_confirmed_tail,
                history_confirmed_tail,
            )
            if history_available
            else None
        )


        crowding_state = (
            classify_funding_crowding(
                funding_rate=(
                    current_funding
                ),
                confirmed_tail_percentile=(
                    confirmed_tail
                ),
                history_available=(
                    history_available
                ),
            )
        )


        # ====================================================
        # OUTPUT
        # ====================================================

        row[
            "funding_cross_percentile"
        ] = cross_percentile


        row[
            "funding_cross_magnitude_percentile"
        ] = cross_magnitude_percentile


        row[
            "funding_cross_directional_tail_percentile"
        ] = cross_directional_tail


        row[
            "funding_cross_confirmed_tail_percentile"
        ] = cross_confirmed_tail


        # Compatibility alias.
        row[
            "funding_cross_tail_percentile"
        ] = cross_directional_tail


        row[
            "funding_history_percentile"
        ] = history_percentile


        row[
            "funding_history_magnitude_percentile"
        ] = history_magnitude_percentile


        row[
            "funding_history_directional_tail_percentile"
        ] = history_directional_tail


        row[
            "funding_history_confirmed_tail_percentile"
        ] = history_confirmed_tail


        # Compatibility alias.
        row[
            "funding_history_tail_percentile"
        ] = history_directional_tail


        row[
            "funding_confirmed_tail_percentile"
        ] = confirmed_tail


        row[
            "funding_history_observations"
        ] = observation_count


        row[
            "funding_history_distinct_values"
        ] = distinct_count


        row[
            "funding_history_span_hours"
        ] = span_hours


        row[
            "funding_history_available"
        ] = history_available


        row[
            "funding_history_median"
        ] = history_median


        row[
            "funding_history_p25"
        ] = history_p25


        row[
            "funding_history_p75"
        ] = history_p75


        row[
            "funding_history_iqr"
        ] = history_iqr


        row[
            "funding_history_mad"
        ] = history_mad


        row[
            "funding_robust_z"
        ] = robust_z


        row[
            "funding_crowding_state"
        ] = crowding_state


        row[
            "funding_calculated_at"
        ] = current_time


        row[
            "funding_generated_at"
        ] = generated_at


        output.append(
            row
        )


    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )

        .sort(
            "symbol"
        )
    )