from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import polars as pl


# ============================================================
# CONFIGURATION
# ============================================================

HISTORY_WINDOW_DAYS = 7

# Operational warm-up gates, not statistical claims.
MIN_HISTORY_SPAN_HOURS = 24.0
MIN_HISTORY_OBSERVATIONS = 120
MIN_DISTINCT_VALUES = 8


# ============================================================
# BASIC HELPERS
# ============================================================


def _finite(
    value: Any,
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


def _as_float(
    value: Any,
) -> float | None:
    if not _finite(
        value,
    ):
        return None

    return float(
        value
    )


def _as_utc_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc,
            )

        return value.astimezone(
            timezone.utc
        )

    if isinstance(
        value,
        str,
    ):
        text = value.strip()

        if not text:
            return None

        if text.endswith(
            "Z"
        ):
            text = (
                text[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                text
            )
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc,
            )

        return parsed.astimezone(
            timezone.utc
        )

    return None


def _quantile(
    values: list[float],
    q: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(
        values
    )

    if len(
        ordered
    ) == 1:
        return ordered[0]

    position = (
        len(ordered) - 1
    ) * q

    lower = math.floor(
        position
    )

    upper = math.ceil(
        position
    )

    if lower == upper:
        return ordered[
            lower
        ]

    weight = (
        position
        - lower
    )

    return (
        ordered[lower]
        * (
            1.0
            - weight
        )
        +
        ordered[upper]
        * weight
    )


def _median(
    values: list[float],
) -> float | None:
    return _quantile(
        values,
        0.5,
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
            value
            - centre
        )
        for value in values
    ]

    return _median(
        deviations
    )


def _robust_z(
    value: float | None,
    history: list[float],
) -> float | None:
    if (
        value is None
        or not history
    ):
        return None

    centre = _median(
        history
    )

    mad = _mad(
        history
    )

    if (
        centre is None
        or mad is None
        or mad <= 0
    ):
        return None

    # 0.67449 makes MAD-based z comparable to a Gaussian z-score.
    return (
        0.6744897501960817
        * (
            value
            - centre
        )
        / mad
    )


def _empirical_midrank_percentile(
    value: float | None,
    history: list[float],
    absolute: bool = False,
) -> float | None:
    """
    Historical empirical percentile using a midrank treatment
    for ties:

        P = (N_< + 0.5 N_=) / N

    Historical observations are expected to contain only data
    strictly prior to the current snapshot.
    """

    if (
        value is None
        or not history
    ):
        return None

    current = (
        abs(
            value
        )
        if absolute
        else value
    )

    comparison = [
        (
            abs(
                candidate
            )
            if absolute
            else candidate
        )
        for candidate in history
    ]

    less = sum(
        candidate
        < current
        for candidate
        in comparison
    )

    equal = sum(
        candidate
        == current
        for candidate
        in comparison
    )

    return (
        less
        + 0.5
        * equal
    ) / len(
        comparison
    )


def _cross_sectional_rank(
    values: list[float | None],
    absolute: bool = False,
) -> list[float | None]:
    """
    Cross-sectional percentile rank on [0, 1].

    Lowest finite value -> 0
    Highest finite value -> 1
    Ties receive average rank.
    """

    result: list[
        float | None
    ] = [
        None
        for _ in values
    ]

    valid: list[
        tuple[
            int,
            float,
        ]
    ] = []

    for index, value in enumerate(
        values
    ):
        if value is None:
            continue

        ranked_value = (
            abs(
                value
            )
            if absolute
            else value
        )

        valid.append(
            (
                index,
                ranked_value,
            )
        )

    count = len(
        valid
    )

    if count == 0:
        return result

    if count == 1:
        result[
            valid[0][0]
        ] = 0.5

        return result

    valid.sort(
        key=lambda item:
            item[1]
    )

    position = 0

    while position < count:
        end = (
            position
            + 1
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
                end
                - 1
            )
        ) / 2.0

        percentile = (
            average_rank
            / (
                count
                - 1
            )
        )

        for i in range(
            position,
            end,
        ):
            original_index = (
                valid[
                    i
                ][0]
            )

            result[
                original_index
            ] = percentile

        position = end

    return result


def _history_span_hours(
    timestamps: list[datetime],
) -> float:
    if len(
        timestamps
    ) < 2:
        return 0.0

    return max(
        0.0,
        (
            max(
                timestamps
            )
            - min(
                timestamps
            )
        ).total_seconds()
        / 3600.0,
    )


def _history_ready(
    values: list[float],
    timestamps: list[datetime],
) -> tuple[
    bool,
    int,
    int,
    float,
]:
    observations = len(
        values
    )

    distinct_values = len(
        set(
            values
        )
    )

    span_hours = (
        _history_span_hours(
            timestamps
        )
    )

    ready = (
        observations
        >= MIN_HISTORY_OBSERVATIONS
        and
        distinct_values
        >= MIN_DISTINCT_VALUES
        and
        span_hours
        >= MIN_HISTORY_SPAN_HOURS
    )

    return (
        ready,
        observations,
        distinct_values,
        span_hours,
    )


def _direction(
    value: float | None,
) -> str:
    if value is None:
        return "UNAVAILABLE"

    if value > 0:
        return "PREMIUM"

    if value < 0:
        return "DISCOUNT"

    return "FLAT"


# ============================================================
# HISTORY PREPARATION
# ============================================================


def _prepare_history(
    derivatives_history: pl.DataFrame,
) -> dict[
    str,
    list[dict],
]:
    grouped: dict[
        str,
        list[dict],
    ] = defaultdict(
        list
    )

    if derivatives_history.is_empty():
        return grouped

    for row in derivatives_history.to_dicts():
        symbol = row.get(
            "symbol"
        )

        timestamp = _as_utc_datetime(
            row.get(
                "calculated_at"
            )
        )

        if (
            not isinstance(
                symbol,
                str,
            )
            or not symbol
            or timestamp is None
        ):
            continue

        grouped[
            symbol
        ].append(
            {
                "timestamp":
                    timestamp,

                "median_index_basis":
                    _as_float(
                        row.get(
                            "median_index_basis"
                        )
                    ),

                "basis_iqr":
                    _as_float(
                        row.get(
                            "basis_iqr"
                        )
                    ),
            }
        )

    for symbol in grouped:
        grouped[
            symbol
        ].sort(
            key=lambda row:
                row[
                    "timestamp"
                ]
        )

    return grouped


# ============================================================
# SNAPSHOT BUILDER
# ============================================================


def build_basis_snapshot(
    derivatives_latest: pl.DataFrame,
    derivatives_history: pl.DataFrame,
) -> pl.DataFrame:
    """
    Calibrate basis level and cross-venue basis dispersion.

    The engine intentionally does NOT collapse these two
    channels into one final risk factor yet.

    Central basis magnitude:
        abs(median_index_basis)

    Cross-venue dispersion:
        basis_iqr

    Both receive:
        - a cross-sectional percentile,
        - a historical empirical percentile,
        - a conservative confirmed percentile once history
          passes the operational warm-up gate.

    Confirmed percentile:
        min(cross-sectional percentile,
            historical percentile)

    During warm-up, confirmed historical values remain null.
    """

    if derivatives_latest.is_empty():
        return derivatives_latest

    required = [
        "symbol",
        "median_index_basis",
        "basis_iqr",
        "basis_market_count",
        "calculated_at",
    ]

    missing = [
        column
        for column in required
        if column not in derivatives_latest.columns
    ]

    if missing:
        raise ValueError(
            "Missing derivatives columns required "
            "for basis calibration: "
            + ", ".join(
                missing
            )
        )

    latest_rows = (
        derivatives_latest
        .to_dicts()
    )

    basis_values = [
        _as_float(
            row.get(
                "median_index_basis"
            )
        )
        for row in latest_rows
    ]

    dispersion_values = [
        _as_float(
            row.get(
                "basis_iqr"
            )
        )
        for row in latest_rows
    ]

    basis_cross_signed = (
        _cross_sectional_rank(
            basis_values,
            absolute=False,
        )
    )

    basis_cross_magnitude = (
        _cross_sectional_rank(
            basis_values,
            absolute=True,
        )
    )

    dispersion_cross = (
        _cross_sectional_rank(
            dispersion_values,
            absolute=False,
        )
    )

    history_by_symbol = (
        _prepare_history(
            derivatives_history
        )
    )

    output: list[
        dict
    ] = []

    generated_at = datetime.now(
        timezone.utc
    )

    for index, row in enumerate(
        latest_rows
    ):
        symbol = row.get(
            "symbol"
        )

        asset = row.get(
            "asset"
        )

        current_time = (
            _as_utc_datetime(
                row.get(
                    "calculated_at"
                )
            )
            or generated_at
        )

        current_basis = (
            basis_values[
                index
            ]
        )

        current_dispersion = (
            dispersion_values[
                index
            ]
        )

        window_start = (
            current_time
            - timedelta(
                days=HISTORY_WINDOW_DAYS,
            )
        )

        prior = [
            observation
            for observation
            in history_by_symbol.get(
                str(
                    symbol
                ),
                [],
            )
            if (
                window_start
                <= observation[
                    "timestamp"
                ]
                < current_time
            )
        ]

        basis_history_rows = [
            observation
            for observation
            in prior
            if observation[
                "median_index_basis"
            ] is not None
        ]

        basis_history = [
            float(
                observation[
                    "median_index_basis"
                ]
            )
            for observation
            in basis_history_rows
        ]

        basis_timestamps = [
            observation[
                "timestamp"
            ]
            for observation
            in basis_history_rows
        ]

        dispersion_history_rows = [
            observation
            for observation
            in prior
            if observation[
                "basis_iqr"
            ] is not None
        ]

        dispersion_history = [
            float(
                observation[
                    "basis_iqr"
                ]
            )
            for observation
            in dispersion_history_rows
        ]

        dispersion_timestamps = [
            observation[
                "timestamp"
            ]
            for observation
            in dispersion_history_rows
        ]

        (
            basis_ready,
            basis_observations,
            basis_distinct,
            basis_span_hours,
        ) = _history_ready(
            basis_history,
            basis_timestamps,
        )

        (
            dispersion_ready,
            dispersion_observations,
            dispersion_distinct,
            dispersion_span_hours,
        ) = _history_ready(
            dispersion_history,
            dispersion_timestamps,
        )

        basis_history_signed_percentile = (
            _empirical_midrank_percentile(
                current_basis,
                basis_history,
                absolute=False,
            )
        )

        basis_history_magnitude_percentile = (
            _empirical_midrank_percentile(
                current_basis,
                basis_history,
                absolute=True,
            )
        )

        dispersion_history_percentile = (
            _empirical_midrank_percentile(
                current_dispersion,
                dispersion_history,
                absolute=False,
            )
        )

        basis_cross_mag = (
            basis_cross_magnitude[
                index
            ]
        )

        dispersion_cross_percentile = (
            dispersion_cross[
                index
            ]
        )

        if (
            basis_ready
            and
            basis_cross_mag is not None
            and
            basis_history_magnitude_percentile
            is not None
        ):
            basis_confirmed = min(
                basis_cross_mag,
                basis_history_magnitude_percentile,
            )
        else:
            basis_confirmed = None

        if (
            dispersion_ready
            and
            dispersion_cross_percentile
            is not None
            and
            dispersion_history_percentile
            is not None
        ):
            dispersion_confirmed = min(
                dispersion_cross_percentile,
                dispersion_history_percentile,
            )
        else:
            dispersion_confirmed = None

        basis_p25 = _quantile(
            basis_history,
            0.25,
        )

        basis_median = _median(
            basis_history
        )

        basis_p75 = _quantile(
            basis_history,
            0.75,
        )

        dispersion_p25 = _quantile(
            dispersion_history,
            0.25,
        )

        dispersion_median = _median(
            dispersion_history
        )

        dispersion_p75 = _quantile(
            dispersion_history,
            0.75,
        )

        output.append(
            {
                # --------------------------------------------
                # IDENTITY
                # --------------------------------------------
                "symbol":
                    symbol,

                "asset":
                    asset,

                # --------------------------------------------
                # CURRENT RAW BASIS INPUTS
                # --------------------------------------------
                "median_index_basis":
                    current_basis,

                "basis_iqr":
                    current_dispersion,

                "basis_market_count":
                    row.get(
                        "basis_market_count"
                    ),

                "basis_direction":
                    _direction(
                        current_basis
                    ),

                # --------------------------------------------
                # CROSS-SECTIONAL CALIBRATION
                # --------------------------------------------
                "basis_cross_percentile":
                    basis_cross_signed[
                        index
                    ],

                "basis_cross_magnitude_percentile":
                    basis_cross_mag,

                "basis_dispersion_cross_percentile":
                    dispersion_cross_percentile,

                # --------------------------------------------
                # HISTORICAL BASIS LEVEL CALIBRATION
                # --------------------------------------------
                "basis_history_percentile":
                    basis_history_signed_percentile,

                "basis_history_magnitude_percentile":
                    basis_history_magnitude_percentile,

                "basis_history_observations":
                    basis_observations,

                "basis_history_distinct_values":
                    basis_distinct,

                "basis_history_span_hours":
                    basis_span_hours,

                "basis_history_available":
                    basis_ready,

                "basis_history_median":
                    basis_median,

                "basis_history_p25":
                    basis_p25,

                "basis_history_p75":
                    basis_p75,

                "basis_history_iqr":
                    (
                        basis_p75
                        - basis_p25
                        if (
                            basis_p25
                            is not None
                            and
                            basis_p75
                            is not None
                        )
                        else None
                    ),

                "basis_history_mad":
                    _mad(
                        basis_history
                    ),

                "basis_robust_z":
                    _robust_z(
                        current_basis,
                        basis_history,
                    ),

                # --------------------------------------------
                # HISTORICAL DISPERSION CALIBRATION
                # --------------------------------------------
                "basis_dispersion_history_percentile":
                    dispersion_history_percentile,

                "basis_dispersion_history_observations":
                    dispersion_observations,

                "basis_dispersion_history_distinct_values":
                    dispersion_distinct,

                "basis_dispersion_history_span_hours":
                    dispersion_span_hours,

                "basis_dispersion_history_available":
                    dispersion_ready,

                "basis_dispersion_history_median":
                    dispersion_median,

                "basis_dispersion_history_p25":
                    dispersion_p25,

                "basis_dispersion_history_p75":
                    dispersion_p75,

                "basis_dispersion_history_iqr":
                    (
                        dispersion_p75
                        - dispersion_p25
                        if (
                            dispersion_p25
                            is not None
                            and
                            dispersion_p75
                            is not None
                        )
                        else None
                    ),

                "basis_dispersion_history_mad":
                    _mad(
                        dispersion_history
                    ),

                "basis_dispersion_robust_z":
                    _robust_z(
                        current_dispersion,
                        dispersion_history,
                    ),

                # --------------------------------------------
                # CONSERVATIVE CONFIRMATION
                # --------------------------------------------
                "basis_confirmed_magnitude_percentile":
                    basis_confirmed,

                "basis_dispersion_confirmed_percentile":
                    dispersion_confirmed,

                # Warm-up proxies are explicit and are not
                # presented as historical confirmation.
                "basis_warmup_magnitude_percentile":
                    basis_cross_mag,

                "basis_dispersion_warmup_percentile":
                    dispersion_cross_percentile,

                # --------------------------------------------
                # READINESS
                # --------------------------------------------
                "basis_calibration_ready":
                    (
                        basis_ready
                        and
                        dispersion_ready
                    ),

                "basis_calibration_state":
                    (
                        "READY"
                        if (
                            basis_ready
                            and
                            dispersion_ready
                        )
                        else "HISTORY BUILDING"
                    ),

                # --------------------------------------------
                # TIMING
                # --------------------------------------------
                "basis_source_at":
                    current_time,

                "basis_generated_at":
                    generated_at,

                "basis_calculated_at":
                    current_time,
            }
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
