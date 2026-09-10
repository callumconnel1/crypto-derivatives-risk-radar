from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

import numpy as np
import polars as pl


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_HORIZONS_HOURS = (
    1,
    4,
    24,
)

MAX_START_PRICE_STALENESS_MINUTES = 10
MAX_END_COVERAGE_GAP_MINUTES = 10

MIN_CROSS_SECTIONAL_PAIRS = 5


# ============================================================
# DATA STRUCTURES
# ============================================================


@dataclass(frozen=True)
class SeriesBundle:
    times: list[datetime]
    values: list[float]


# ============================================================
# EMPTY SCHEMAS
# ============================================================


def _empty_snapshot_ic() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "risk_snapshot_at":
                pl.Datetime(
                    time_zone="UTC"
                ),

            "horizon_hours":
                pl.Int64,

            "target":
                pl.String,

            "target_label":
                pl.String,

            "asset_count":
                pl.Int64,

            "spearman_ic":
                pl.Float64,
        }
    )


def _empty_metrics() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "horizon_hours":
                pl.Int64,

            "target":
                pl.String,

            "target_label":
                pl.String,

            "snapshot_count":
                pl.Int64,

            "median_asset_count":
                pl.Float64,

            "mean_spearman_ic":
                pl.Float64,

            "median_spearman_ic":
                pl.Float64,

            "positive_ic_rate":
                pl.Float64,

            "min_spearman_ic":
                pl.Float64,

            "max_spearman_ic":
                pl.Float64,
        }
    )


def _empty_quintiles() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "horizon_hours":
                pl.Int64,

            "target":
                pl.String,

            "target_label":
                pl.String,

            "risk_quintile":
                pl.Int64,

            "observation_count":
                pl.Int64,

            "snapshot_count":
                pl.Int64,

            "mean_outcome":
                pl.Float64,

            "median_outcome":
                pl.Float64,
        }
    )


def _empty_quintile_summary() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "horizon_hours":
                pl.Int64,

            "target":
                pl.String,

            "target_label":
                pl.String,

            "q1_mean":
                pl.Float64,

            "q5_mean":
                pl.Float64,

            "q5_minus_q1":
                pl.Float64,

            "q5_over_q1":
                pl.Float64,

            "quintile_monotonicity_spearman":
                pl.Float64,
        }
    )


def _empty_status() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "horizon_hours":
                pl.Int64,

            "risk_rows":
                pl.Int64,

            "risk_snapshots":
                pl.Int64,

            "price_ready_rows":
                pl.Int64,

            "price_ready_snapshots":
                pl.Int64,

            "liquidation_ready_rows":
                pl.Int64,

            "liquidation_ready_snapshots":
                pl.Int64,

            "price_ready_fraction":
                pl.Float64,

            "liquidation_ready_fraction":
                pl.Float64,
        }
    )


# ============================================================
# BASIC HELPERS
# ============================================================


def _finite(
    value: Any,
) -> bool:
    return (
        isinstance(
            value,
            (
                int,
                float,
                np.integer,
                np.floating,
            ),
        )
        and math.isfinite(
            float(value)
        )
    )


def _as_float(
    value: Any,
) -> float | None:
    if not _finite(
        value
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
                tzinfo=UTC,
            )

        return value.astimezone(
            UTC
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
                tzinfo=UTC,
            )

        return parsed.astimezone(
            UTC
        )

    return None


def _find_first_column(
    dataframe: pl.DataFrame,
    candidates: Iterable[str],
) -> str | None:
    columns = set(
        dataframe.columns
    )

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def _average_ranks(
    values: list[float],
) -> np.ndarray:
    """
    Average ranks for ties, starting from 1.
    """

    array = np.asarray(
        values,
        dtype=float,
    )

    order = np.argsort(
        array,
        kind="mergesort",
    )

    ranks = np.empty(
        len(array),
        dtype=float,
    )

    position = 0

    while position < len(
        array
    ):
        end = (
            position
            + 1
        )

        current = array[
            order[
                position
            ]
        ]

        while (
            end < len(array)
            and
            array[
                order[
                    end
                ]
            ]
            == current
        ):
            end += 1

        average_rank = (
            position
            + 1
            + end
        ) / 2.0

        ranks[
            order[
                position:end
            ]
        ] = average_rank

        position = end

    return ranks


def _pearson(
    first: list[float],
    second: list[float],
) -> float | None:
    if len(
        first
    ) < 2:
        return None

    x = np.asarray(
        first,
        dtype=float,
    )

    y = np.asarray(
        second,
        dtype=float,
    )

    if (
        np.std(
            x
        ) == 0
        or
        np.std(
            y
        ) == 0
    ):
        return None

    correlation = np.corrcoef(
        x,
        y,
    )[0, 1]

    if not math.isfinite(
        float(correlation)
    ):
        return None

    return float(
        correlation
    )


def _spearman(
    first: list[Any],
    second: list[Any],
) -> float | None:
    pairs = [
        (
            float(x),
            float(y),
        )
        for x, y in zip(
            first,
            second,
        )
        if (
            _finite(
                x
            )
            and
            _finite(
                y
            )
        )
    ]

    if len(
        pairs
    ) < 2:
        return None

    x = [
        pair[0]
        for pair in pairs
    ]

    y = [
        pair[1]
        for pair in pairs
    ]

    return _pearson(
        _average_ranks(
            x
        ).tolist(),
        _average_ranks(
            y
        ).tolist(),
    )


def _mean(
    values: list[Any],
) -> float | None:
    clean = [
        float(
            value
        )
        for value in values
        if _finite(
            value
        )
    ]

    if not clean:
        return None

    return (
        sum(
            clean
        )
        / len(
            clean
        )
    )


def _median(
    values: list[Any],
) -> float | None:
    clean = sorted(
        [
            float(
                value
            )
            for value in values
            if _finite(
                value
            )
        ]
    )

    if not clean:
        return None

    count = len(
        clean
    )

    midpoint = (
        count // 2
    )

    if count % 2:
        return clean[
            midpoint
        ]

    return (
        clean[
            midpoint - 1
        ]
        + clean[
            midpoint
        ]
    ) / 2.0


def _safe_ratio(
    numerator: Any,
    denominator: Any,
) -> float | None:
    if not (
        _finite(
            numerator
        )
        and
        _finite(
            denominator
        )
    ):
        return None

    denominator_value = float(
        denominator
    )

    if denominator_value == 0:
        return None

    return (
        float(
            numerator
        )
        / denominator_value
    )


# ============================================================
# PREPARE RISK HISTORY
# ============================================================


def prepare_risk_history(
    dataframe: pl.DataFrame,
    validation_start: datetime | None = None,
    risk_version: str | None = None,
) -> pl.DataFrame:
    if dataframe.is_empty():
        return pl.DataFrame(
            schema={
                "symbol":
                    pl.String,

                "risk_snapshot_at":
                    pl.Datetime(
                        time_zone="UTC"
                    ),

                "provisional_risk_score":
                    pl.Float64,
            }
        )

    time_column = _find_first_column(
        dataframe,
        (
            "risk_source_at",
            "risk_calculated_at",
            "risk_generated_at",
        ),
    )

    if time_column is None:
        raise ValueError(
            "Could not identify a risk snapshot timestamp. "
            "Expected one of: risk_source_at, "
            "risk_calculated_at, risk_generated_at."
        )

    if (
        "symbol"
        not in dataframe.columns
        or
        "provisional_risk_score"
        not in dataframe.columns
    ):
        raise ValueError(
            "Risk history requires symbol and "
            "provisional_risk_score."
        )

    selected_columns = [
        "symbol",
        time_column,
        "provisional_risk_score",
    ]

    for optional in (
        "risk_rank",
        "risk_cross_percentile",
        "risk_version",
        "primary_state",
        "volatility_component",
        "leverage_component",
        "funding_component",
        "liquidation_component",
        "market_structure_component",
    ):
        if optional in dataframe.columns:
            selected_columns.append(
                optional
            )

    rows = []

    for row in (
        dataframe
        .select(
            selected_columns
        )
        .to_dicts()
    ):
        timestamp = _as_utc_datetime(
            row.get(
                time_column
            )
        )

        score = _as_float(
            row.get(
                "provisional_risk_score"
            )
        )

        symbol = row.get(
            "symbol"
        )

        if (
            timestamp is None
            or score is None
            or not isinstance(
                symbol,
                str,
            )
            or not symbol
        ):
            continue

        if (
            validation_start is not None
            and
            timestamp
            < validation_start
        ):
            continue

        if (
            risk_version is not None
            and
            row.get(
                "risk_version"
            )
            != risk_version
        ):
            continue

        prepared = {
            "symbol":
                symbol,

            "risk_snapshot_at":
                timestamp,

            "provisional_risk_score":
                score,
        }

        for optional in (
            "risk_rank",
            "risk_cross_percentile",
            "risk_version",
            "primary_state",
            "volatility_component",
            "leverage_component",
            "funding_component",
            "liquidation_component",
            "market_structure_component",
        ):
            prepared[
                optional
            ] = row.get(
                optional
            )

        rows.append(
            prepared
        )

    if not rows:
        return pl.DataFrame(
            schema={
                "symbol":
                    pl.String,

                "risk_snapshot_at":
                    pl.Datetime(
                        time_zone="UTC"
                    ),

                "provisional_risk_score":
                    pl.Float64,
            }
        )

    return (
        pl.DataFrame(
            rows,
            infer_schema_length=None,
        )
        .unique(
            subset=[
                "symbol",
                "risk_snapshot_at",
            ],
            keep="last",
        )
        .sort([
            "risk_snapshot_at",
            "symbol",
        ])
    )


# ============================================================
# PREPARE SPOT HISTORY
# ============================================================


def prepare_spot_history(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    if dataframe.is_empty():
        return pl.DataFrame(
            schema={
                "symbol":
                    pl.String,

                "spot_timestamp":
                    pl.Datetime(
                        time_zone="UTC"
                    ),

                "price":
                    pl.Float64,
            }
        )

    time_column = _find_first_column(
        dataframe,
        (
            "timestamp",
            "last_updated",
            "collected_at",
            "calculated_at",
        ),
    )

    price_column = _find_first_column(
        dataframe,
        (
            "price",
            "price_usd",
            "quote_price",
            "close",
        ),
    )

    if time_column is None:
        raise ValueError(
            "Could not identify spot timestamp column. "
            "Expected timestamp, last_updated, "
            "collected_at, or calculated_at."
        )

    if price_column is None:
        raise ValueError(
            "Could not identify spot price column. "
            "Expected price, price_usd, quote_price, "
            "or close."
        )

    if "symbol" not in dataframe.columns:
        raise ValueError(
            "Spot history requires symbol."
        )

    rows = []

    for row in (
        dataframe
        .select([
            "symbol",
            time_column,
            price_column,
        ])
        .to_dicts()
    ):
        symbol = row.get(
            "symbol"
        )

        timestamp = _as_utc_datetime(
            row.get(
                time_column
            )
        )

        price = _as_float(
            row.get(
                price_column
            )
        )

        if (
            not isinstance(
                symbol,
                str,
            )
            or not symbol
            or timestamp is None
            or price is None
            or price <= 0
        ):
            continue

        rows.append(
            {
                "symbol":
                    symbol,

                "spot_timestamp":
                    timestamp,

                "price":
                    price,
            }
        )

    if not rows:
        return pl.DataFrame(
            schema={
                "symbol":
                    pl.String,

                "spot_timestamp":
                    pl.Datetime(
                        time_zone="UTC"
                    ),

                "price":
                    pl.Float64,
            }
        )

    return (
        pl.DataFrame(
            rows,
            infer_schema_length=None,
        )
        .unique(
            subset=[
                "symbol",
                "spot_timestamp",
            ],
            keep="last",
        )
        .sort([
            "symbol",
            "spot_timestamp",
        ])
    )


# ============================================================
# PREPARE STATE HISTORY
# ============================================================


def prepare_state_history(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    """
    State history is optional for price-based validation.

    When present, it supplies an independent forward
    liquidation-to-OI stress target.
    """

    empty = pl.DataFrame(
        schema={
            "symbol":
                pl.String,

            "state_timestamp":
                pl.Datetime(
                    time_zone="UTC"
                ),

            "liquidations_to_oi_1h":
                pl.Float64,
        }
    )

    if dataframe.is_empty():
        return empty

    if "symbol" not in dataframe.columns:
        raise ValueError(
            "State history requires symbol."
        )

    time_column = _find_first_column(
        dataframe,
        (
            "state_source_at",
            "state_calculated_at",
            "calculated_at",
            "timestamp",
        ),
    )

    if time_column is None:
        raise ValueError(
            "Could not identify state timestamp column."
        )

    target_column = _find_first_column(
        dataframe,
        (
            "liquidations_to_oi_1h",
            "liquidations_to_oi",
        ),
    )

    if target_column is None:
        return empty

    rows = []

    for row in (
        dataframe
        .select([
            "symbol",
            time_column,
            target_column,
        ])
        .to_dicts()
    ):
        symbol = row.get(
            "symbol"
        )

        timestamp = _as_utc_datetime(
            row.get(
                time_column
            )
        )

        value = _as_float(
            row.get(
                target_column
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

        rows.append(
            {
                "symbol":
                    symbol,

                "state_timestamp":
                    timestamp,

                "liquidations_to_oi_1h":
                    value,
            }
        )

    if not rows:
        return empty

    return (
        pl.DataFrame(
            rows,
            infer_schema_length=None,
        )
        .unique(
            subset=[
                "symbol",
                "state_timestamp",
            ],
            keep="last",
        )
        .sort([
            "symbol",
            "state_timestamp",
        ])
    )


# ============================================================
# SERIES INDEXING
# ============================================================


def _series_by_symbol(
    dataframe: pl.DataFrame,
    time_column: str,
    value_column: str,
) -> dict[
    str,
    SeriesBundle,
]:
    output: dict[
        str,
        SeriesBundle,
    ] = {}

    if dataframe.is_empty():
        return output

    for symbol in (
        dataframe[
            "symbol"
        ]
        .unique()
        .to_list()
    ):
        subset = (
            dataframe
            .filter(
                pl.col(
                    "symbol"
                )
                == symbol
            )
            .sort(
                time_column
            )
        )

        output[
            str(
                symbol
            )
        ] = SeriesBundle(
            times=(
                subset[
                    time_column
                ]
                .to_list()
            ),
            values=[
                (
                    float(
                        value
                    )
                    if _finite(
                        value
                    )
                    else float(
                        "nan"
                    )
                )
                for value in (
                    subset[
                        value_column
                    ]
                    .to_list()
                )
            ],
        )

    return output


# ============================================================
# FORWARD PRICE OUTCOMES
# ============================================================


def _forward_price_outcome(
    series: SeriesBundle,
    snapshot_at: datetime,
    horizon_hours: int,
) -> dict:
    target_end = (
        snapshot_at
        + timedelta(
            hours=horizon_hours
        )
    )

    times = series.times
    prices = series.values

    if not times:
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "NO SPOT HISTORY",
        }

    start_index = (
        bisect_right(
            times,
            snapshot_at,
        )
        - 1
    )

    if start_index < 0:
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "NO START PRICE",
        }

    start_time = times[
        start_index
    ]

    start_price = prices[
        start_index
    ]

    if (
        not _finite(
            start_price
        )
        or start_price <= 0
    ):
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "INVALID START PRICE",
        }

    start_staleness = (
        snapshot_at
        - start_time
    ).total_seconds() / 60.0

    if (
        start_staleness
        > MAX_START_PRICE_STALENESS_MINUTES
    ):
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "STALE START PRICE",

            "start_price_at":
                start_time,

            "start_price_staleness_minutes":
                start_staleness,
        }

    # The forward horizon is not mature until the source
    # series itself has progressed to or beyond target_end.
    #
    # The endpoint-gap tolerance below is only for sampling
    # irregularity around an already-mature horizon. It must not
    # be used to declare a still-future horizon complete.
    latest_available_at = times[-1]

    if (
        latest_available_at
        < target_end
    ):
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "HORIZON NOT MATURE",

            "start_price_at":
                start_time,

            "start_price":
                start_price,

            "latest_available_at":
                latest_available_at,

            "minutes_until_horizon":
                (
                    target_end
                    - latest_available_at
                ).total_seconds()
                / 60.0,
        }

    end_index_exclusive = (
        bisect_right(
            times,
            target_end,
        )
    )

    if (
        end_index_exclusive
        <= start_index + 1
    ):
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "NO FUTURE PRICE PATH",

            "start_price_at":
                start_time,

            "start_price":
                start_price,
        }

    final_index = (
        end_index_exclusive
        - 1
    )

    coverage_time = times[
        final_index
    ]

    end_gap_minutes = (
        target_end
        - coverage_time
    ).total_seconds() / 60.0

    if (
        end_gap_minutes
        > MAX_END_COVERAGE_GAP_MINUTES
    ):
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "HORIZON NOT MATURE",

            "start_price_at":
                start_time,

            "start_price":
                start_price,

            "coverage_at":
                coverage_time,

            "end_gap_minutes":
                end_gap_minutes,
        }

    window_prices = np.asarray(
        prices[
            start_index:
            end_index_exclusive
        ],
        dtype=float,
    )

    valid_mask = (
        np.isfinite(
            window_prices
        )
        &
        (
            window_prices
            > 0
        )
    )

    window_prices = (
        window_prices[
            valid_mask
        ]
    )

    if len(
        window_prices
    ) < 2:
        return {
            "price_outcome_ready":
                False,

            "price_outcome_reason":
                "INSUFFICIENT PRICE POINTS",
        }

    log_returns = np.diff(
        np.log(
            window_prices
        )
    )

    realized_path_vol_pct = (
        math.sqrt(
            float(
                np.sum(
                    log_returns
                    ** 2
                )
            )
        )
        * 100.0
    )

    relative_moves = (
        window_prices
        / start_price
        - 1.0
    )

    return {
        "price_outcome_ready":
            True,

        "price_outcome_reason":
            "READY",

        "start_price_at":
            start_time,

        "start_price":
            float(
                start_price
            ),

        "coverage_at":
            coverage_time,

        "end_gap_minutes":
            end_gap_minutes,

        "spot_observations":
            len(
                window_prices
            ),

        "realized_path_vol_pct":
            realized_path_vol_pct,

        "max_abs_move_pct":
            (
                float(
                    np.max(
                        np.abs(
                            relative_moves
                        )
                    )
                )
                * 100.0
            ),

        "downside_excursion_pct":
            (
                max(
                    0.0,
                    -float(
                        np.min(
                            relative_moves
                        )
                    ),
                )
                * 100.0
            ),

        "upside_excursion_pct":
            (
                max(
                    0.0,
                    float(
                        np.max(
                            relative_moves
                        )
                    ),
                )
                * 100.0
            ),

        "endpoint_abs_return_pct":
            (
                abs(
                    float(
                        window_prices[-1]
                        / start_price
                        - 1.0
                    )
                )
                * 100.0
            ),
    }


# ============================================================
# FORWARD LIQUIDATION OUTCOME
# ============================================================


def _forward_liquidation_outcome(
    series: SeriesBundle | None,
    snapshot_at: datetime,
    horizon_hours: int,
) -> dict:
    if series is None:
        return {
            "liquidation_outcome_ready":
                False,

            "liquidation_outcome_reason":
                "NO STATE HISTORY",
        }

    target_end = (
        snapshot_at
        + timedelta(
            hours=horizon_hours
        )
    )

    times = series.times
    values = series.values

    if not times:
        return {
            "liquidation_outcome_ready":
                False,

            "liquidation_outcome_reason":
                "NO STATE HISTORY",
        }

    # As with the price target, do not treat the endpoint
    # tolerance as permission to look at an incomplete future
    # horizon. The source history must first extend to target_end.
    latest_available_at = times[-1]

    if (
        latest_available_at
        < target_end
    ):
        return {
            "liquidation_outcome_ready":
                False,

            "liquidation_outcome_reason":
                "HORIZON NOT MATURE",

            "liquidation_latest_available_at":
                latest_available_at,

            "liquidation_minutes_until_horizon":
                (
                    target_end
                    - latest_available_at
                ).total_seconds()
                / 60.0,
        }

    start_index = (
        bisect_right(
            times,
            snapshot_at,
        )
    )

    end_index_exclusive = (
        bisect_right(
            times,
            target_end,
        )
    )

    if (
        end_index_exclusive
        <= start_index
    ):
        return {
            "liquidation_outcome_ready":
                False,

            "liquidation_outcome_reason":
                "NO FUTURE LIQUIDATION DATA",
        }

    coverage_time = times[
        end_index_exclusive - 1
    ]

    end_gap_minutes = (
        target_end
        - coverage_time
    ).total_seconds() / 60.0

    if (
        end_gap_minutes
        > MAX_END_COVERAGE_GAP_MINUTES
    ):
        return {
            "liquidation_outcome_ready":
                False,

            "liquidation_outcome_reason":
                "HORIZON NOT MATURE",

            "liquidation_coverage_at":
                coverage_time,

            "liquidation_end_gap_minutes":
                end_gap_minutes,
        }

    clean = [
        float(
            value
        )
        for value in (
            values[
                start_index:
                end_index_exclusive
            ]
        )
        if _finite(
            value
        )
    ]

    if not clean:
        return {
            "liquidation_outcome_ready":
                False,

            "liquidation_outcome_reason":
                "NO FINITE LIQUIDATION VALUES",
        }

    return {
        "liquidation_outcome_ready":
            True,

        "liquidation_outcome_reason":
            "READY",

        "liquidation_coverage_at":
            coverage_time,

        "liquidation_end_gap_minutes":
            end_gap_minutes,

        "liquidation_observations":
            len(
                clean
            ),

        # The source feature is itself a rolling 1h quantity.
        # Taking the future maximum avoids double-counting that
        # would arise from summing overlapping 1h windows.
        "max_liquidations_to_oi_1h":
            max(
                clean
            ),

        "mean_liquidations_to_oi_1h":
            _mean(
                clean
            ),
    }


# ============================================================
# BUILD LONG-FORM FORWARD SAMPLES
# ============================================================


def build_forward_samples(
    risk_history: pl.DataFrame,
    spot_history: pl.DataFrame,
    state_history: pl.DataFrame | None = None,
    horizons_hours: tuple[int, ...] = DEFAULT_HORIZONS_HOURS,
) -> pl.DataFrame:
    if risk_history.is_empty():
        return pl.DataFrame(
            schema={
                "symbol":
                    pl.String,

                "risk_snapshot_at":
                    pl.Datetime(
                        time_zone="UTC"
                    ),

                "horizon_hours":
                    pl.Int64,

                "target_end_at":
                    pl.Datetime(
                        time_zone="UTC"
                    ),

                "provisional_risk_score":
                    pl.Float64,

                "price_outcome_ready":
                    pl.Boolean,

                "liquidation_outcome_ready":
                    pl.Boolean,
            }
        )

    spot_by_symbol = _series_by_symbol(
        spot_history,
        "spot_timestamp",
        "price",
    )

    if (
        state_history is not None
        and
        not state_history.is_empty()
    ):
        liquidation_by_symbol = _series_by_symbol(
            state_history,
            "state_timestamp",
            "liquidations_to_oi_1h",
        )
    else:
        liquidation_by_symbol = {}

    output = []

    for risk_row in risk_history.to_dicts():
        symbol = risk_row[
            "symbol"
        ]

        snapshot_at = risk_row[
            "risk_snapshot_at"
        ]

        spot_series = (
            spot_by_symbol.get(
                symbol
            )
        )

        for horizon_hours in horizons_hours:
            if spot_series is None:
                price_outcome = {
                    "price_outcome_ready":
                        False,

                    "price_outcome_reason":
                        "NO SPOT HISTORY",
                }
            else:
                price_outcome = (
                    _forward_price_outcome(
                        spot_series,
                        snapshot_at,
                        horizon_hours,
                    )
                )

            liquidation_outcome = (
                _forward_liquidation_outcome(
                    liquidation_by_symbol.get(
                        symbol
                    ),
                    snapshot_at,
                    horizon_hours,
                )
            )

            output.append(
                {
                    "symbol":
                        symbol,

                    "risk_snapshot_at":
                        snapshot_at,

                    "horizon_hours":
                        horizon_hours,

                    "target_end_at":
                        (
                            snapshot_at
                            + timedelta(
                                hours=horizon_hours
                            )
                        ),

                    "provisional_risk_score":
                        risk_row.get(
                            "provisional_risk_score"
                        ),

                    "risk_rank":
                        risk_row.get(
                            "risk_rank"
                        ),

                    "risk_cross_percentile":
                        risk_row.get(
                            "risk_cross_percentile"
                        ),

                    "risk_version":
                        risk_row.get(
                            "risk_version"
                        ),

                    "primary_state":
                        risk_row.get(
                            "primary_state"
                        ),

                    "volatility_component":
                        risk_row.get(
                            "volatility_component"
                        ),

                    "leverage_component":
                        risk_row.get(
                            "leverage_component"
                        ),

                    "funding_component":
                        risk_row.get(
                            "funding_component"
                        ),

                    "liquidation_component":
                        risk_row.get(
                            "liquidation_component"
                        ),

                    "market_structure_component":
                        risk_row.get(
                            "market_structure_component"
                        ),

                    **price_outcome,
                    **liquidation_outcome,
                }
            )

    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )
        .sort([
            "horizon_hours",
            "risk_snapshot_at",
            "symbol",
        ])
    )


# ============================================================
# QUINTILE ASSIGNMENT
# ============================================================


def add_cross_sectional_risk_quintiles(
    samples: pl.DataFrame,
) -> pl.DataFrame:
    if samples.is_empty():
        return samples

    rows = samples.to_dicts()

    groups: dict[
        tuple[
            int,
            datetime,
        ],
        list[int],
    ] = {}

    for index, row in enumerate(
        rows
    ):
        key = (
            int(
                row[
                    "horizon_hours"
                ]
            ),
            row[
                "risk_snapshot_at"
            ],
        )

        groups.setdefault(
            key,
            [],
        ).append(
            index
        )

    for indices in groups.values():
        valid = [
            index
            for index in indices
            if _finite(
                rows[
                    index
                ].get(
                    "provisional_risk_score"
                )
            )
        ]

        valid.sort(
            key=lambda index:
                float(
                    rows[
                        index
                    ][
                        "provisional_risk_score"
                    ]
                )
        )

        count = len(
            valid
        )

        for position, index in enumerate(
            valid
        ):
            if count == 1:
                quintile = 3
            else:
                quintile = min(
                    5,
                    int(
                        position
                        * 5
                        / count
                    )
                    + 1,
                )

            rows[
                index
            ][
                "risk_quintile"
            ] = quintile

        for index in indices:
            if (
                "risk_quintile"
                not in rows[
                    index
                ]
            ):
                rows[
                    index
                ][
                    "risk_quintile"
                ] = None

    return pl.DataFrame(
        rows,
        infer_schema_length=None,
    )


# ============================================================
# VALIDATION TARGETS
# ============================================================


TARGETS = (
    (
        "realized_path_vol_pct",
        "Future path realised volatility",
        "price_outcome_ready",
    ),
    (
        "max_abs_move_pct",
        "Future maximum absolute move",
        "price_outcome_ready",
    ),
    (
        "downside_excursion_pct",
        "Future downside excursion",
        "price_outcome_ready",
    ),
    (
        "max_liquidations_to_oi_1h",
        "Future maximum 1h liquidations/OI",
        "liquidation_outcome_ready",
    ),
)


# ============================================================
# SNAPSHOT INFORMATION COEFFICIENTS
# ============================================================


def build_snapshot_information_coefficients(
    samples: pl.DataFrame,
) -> pl.DataFrame:
    """
    For each risk snapshot and horizon, compute the
    cross-sectional Spearman IC:

        rank(current CDRR score)
                    vs
        rank(subsequent realised stress)

    This is preferable to relying only on a pooled correlation
    because neighbouring observations overlap heavily in time.
    """

    if samples.is_empty():
        return _empty_snapshot_ic()

    output = []

    horizons = (
        samples[
            "horizon_hours"
        ]
        .unique()
        .sort()
        .to_list()
    )

    for horizon in horizons:
        horizon_frame = (
            samples
            .filter(
                pl.col(
                    "horizon_hours"
                )
                == horizon
            )
        )

        snapshot_times = (
            horizon_frame[
                "risk_snapshot_at"
            ]
            .unique()
            .sort()
            .to_list()
        )

        for snapshot_at in snapshot_times:
            snapshot = (
                horizon_frame
                .filter(
                    pl.col(
                        "risk_snapshot_at"
                    )
                    == snapshot_at
                )
            )

            for (
                target,
                target_label,
                ready_column,
            ) in TARGETS:
                if (
                    target
                    not in snapshot.columns
                    or
                    ready_column
                    not in snapshot.columns
                ):
                    continue

                ready = snapshot.filter(
                    pl.col(
                        ready_column
                    )
                    == True
                )

                pairs = [
                    (
                        row.get(
                            "provisional_risk_score"
                        ),
                        row.get(
                            target
                        ),
                    )
                    for row
                    in ready.to_dicts()
                    if (
                        _finite(
                            row.get(
                                "provisional_risk_score"
                            )
                        )
                        and
                        _finite(
                            row.get(
                                target
                            )
                        )
                    )
                ]

                if (
                    len(
                        pairs
                    )
                    < MIN_CROSS_SECTIONAL_PAIRS
                ):
                    continue

                ic = _spearman(
                    [
                        pair[0]
                        for pair in pairs
                    ],
                    [
                        pair[1]
                        for pair in pairs
                    ],
                )

                if ic is None:
                    continue

                output.append(
                    {
                        "risk_snapshot_at":
                            snapshot_at,

                        "horizon_hours":
                            int(
                                horizon
                            ),

                        "target":
                            target,

                        "target_label":
                            target_label,

                        "asset_count":
                            len(
                                pairs
                            ),

                        "spearman_ic":
                            ic,
                    }
                )

    if not output:
        return _empty_snapshot_ic()

    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )
        .sort([
            "horizon_hours",
            "target",
            "risk_snapshot_at",
        ])
    )


# ============================================================
# AGGREGATE IC METRICS
# ============================================================


def build_validation_metrics(
    snapshot_ic: pl.DataFrame,
) -> pl.DataFrame:
    if snapshot_ic.is_empty():
        return _empty_metrics()

    return (
        snapshot_ic
        .group_by([
            "horizon_hours",
            "target",
            "target_label",
        ])
        .agg([
            pl.len().alias(
                "snapshot_count"
            ),

            pl.col(
                "asset_count"
            )
            .median()
            .alias(
                "median_asset_count"
            ),

            pl.col(
                "spearman_ic"
            )
            .mean()
            .alias(
                "mean_spearman_ic"
            ),

            pl.col(
                "spearman_ic"
            )
            .median()
            .alias(
                "median_spearman_ic"
            ),

            (
                pl.col(
                    "spearman_ic"
                )
                > 0
            )
            .mean()
            .alias(
                "positive_ic_rate"
            ),

            pl.col(
                "spearman_ic"
            )
            .min()
            .alias(
                "min_spearman_ic"
            ),

            pl.col(
                "spearman_ic"
            )
            .max()
            .alias(
                "max_spearman_ic"
            ),
        ])
        .sort([
            "horizon_hours",
            "target",
        ])
    )


# ============================================================
# QUINTILE ANALYSIS
# ============================================================


def build_quintile_analysis(
    samples: pl.DataFrame,
) -> pl.DataFrame:
    if samples.is_empty():
        return _empty_quintiles()

    output = []

    horizons = (
        samples[
            "horizon_hours"
        ]
        .unique()
        .sort()
        .to_list()
    )

    for horizon in horizons:
        horizon_frame = samples.filter(
            pl.col(
                "horizon_hours"
            )
            == horizon
        )

        for (
            target,
            target_label,
            ready_column,
        ) in TARGETS:
            if (
                target
                not in horizon_frame.columns
                or
                ready_column
                not in horizon_frame.columns
                or
                "risk_quintile"
                not in horizon_frame.columns
            ):
                continue

            ready = (
                horizon_frame
                .filter(
                    (
                        pl.col(
                            ready_column
                        )
                        == True
                    )
                    &
                    pl.col(
                        target
                    ).is_not_null()
                    &
                    pl.col(
                        "risk_quintile"
                    ).is_not_null()
                )
            )

            if ready.is_empty():
                continue

            for quintile in range(
                1,
                6,
            ):
                bucket = ready.filter(
                    pl.col(
                        "risk_quintile"
                    )
                    == quintile
                )

                if bucket.is_empty():
                    continue

                output.append(
                    {
                        "horizon_hours":
                            int(
                                horizon
                            ),

                        "target":
                            target,

                        "target_label":
                            target_label,

                        "risk_quintile":
                            quintile,

                        "observation_count":
                            bucket.height,

                        "snapshot_count":
                            (
                                bucket[
                                    "risk_snapshot_at"
                                ]
                                .n_unique()
                            ),

                        "mean_outcome":
                            _mean(
                                bucket[
                                    target
                                ]
                                .to_list()
                            ),

                        "median_outcome":
                            _median(
                                bucket[
                                    target
                                ]
                                .to_list()
                            ),
                    }
                )

    if not output:
        return _empty_quintiles()

    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )
        .sort([
            "horizon_hours",
            "target",
            "risk_quintile",
        ])
    )


# ============================================================
# QUINTILE SUMMARY
# ============================================================


def build_quintile_summary(
    quintiles: pl.DataFrame,
) -> pl.DataFrame:
    if quintiles.is_empty():
        return _empty_quintile_summary()

    output = []

    groups = (
        quintiles
        .select([
            "horizon_hours",
            "target",
            "target_label",
        ])
        .unique()
        .to_dicts()
    )

    for group in groups:
        horizon = group[
            "horizon_hours"
        ]

        target = group[
            "target"
        ]

        subset = quintiles.filter(
            (
                pl.col(
                    "horizon_hours"
                )
                == horizon
            )
            &
            (
                pl.col(
                    "target"
                )
                == target
            )
        )

        means = {
            int(
                row[
                    "risk_quintile"
                ]
            ):
                row[
                    "mean_outcome"
                ]
            for row
            in subset.to_dicts()
        }

        q1 = means.get(
            1
        )

        q5 = means.get(
            5
        )

        ordered_quintiles = [
            quintile
            for quintile in range(
                1,
                6,
            )
            if _finite(
                means.get(
                    quintile
                )
            )
        ]

        ordered_means = [
            means[
                quintile
            ]
            for quintile
            in ordered_quintiles
        ]

        monotonicity = (
            _spearman(
                ordered_quintiles,
                ordered_means,
            )
            if len(
                ordered_quintiles
            )
            >= 3
            else None
        )

        output.append(
            {
                "horizon_hours":
                    horizon,

                "target":
                    target,

                "target_label":
                    group[
                        "target_label"
                    ],

                "q1_mean":
                    q1,

                "q5_mean":
                    q5,

                "q5_minus_q1":
                    (
                        float(
                            q5
                        )
                        - float(
                            q1
                        )
                        if (
                            _finite(
                                q5
                            )
                            and
                            _finite(
                                q1
                            )
                        )
                        else None
                    ),

                "q5_over_q1":
                    _safe_ratio(
                        q5,
                        q1,
                    ),

                "quintile_monotonicity_spearman":
                    monotonicity,
            }
        )

    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )
        .sort([
            "horizon_hours",
            "target",
        ])
    )


# ============================================================
# HORIZON MATURITY STATUS
# ============================================================


def build_horizon_status(
    samples: pl.DataFrame,
) -> pl.DataFrame:
    if samples.is_empty():
        return _empty_status()

    output = []

    horizons = (
        samples[
            "horizon_hours"
        ]
        .unique()
        .sort()
        .to_list()
    )

    for horizon in horizons:
        subset = samples.filter(
            pl.col(
                "horizon_hours"
            )
            == horizon
        )

        total_rows = (
            subset.height
        )

        total_snapshots = (
            subset[
                "risk_snapshot_at"
            ]
            .n_unique()
        )

        price_ready = (
            subset.filter(
                pl.col(
                    "price_outcome_ready"
                )
                == True
            )
        )

        liquidation_ready = (
            subset.filter(
                pl.col(
                    "liquidation_outcome_ready"
                )
                == True
            )
            if (
                "liquidation_outcome_ready"
                in subset.columns
            )
            else pl.DataFrame()
        )

        output.append(
            {
                "horizon_hours":
                    int(
                        horizon
                    ),

                "risk_rows":
                    total_rows,

                "risk_snapshots":
                    total_snapshots,

                "price_ready_rows":
                    price_ready.height,

                "price_ready_snapshots":
                    (
                        price_ready[
                            "risk_snapshot_at"
                        ]
                        .n_unique()
                        if not price_ready.is_empty()
                        else 0
                    ),

                "liquidation_ready_rows":
                    liquidation_ready.height,

                "liquidation_ready_snapshots":
                    (
                        liquidation_ready[
                            "risk_snapshot_at"
                        ]
                        .n_unique()
                        if not liquidation_ready.is_empty()
                        else 0
                    ),

                "price_ready_fraction":
                    (
                        price_ready.height
                        / total_rows
                        if total_rows
                        else 0.0
                    ),

                "liquidation_ready_fraction":
                    (
                        liquidation_ready.height
                        / total_rows
                        if total_rows
                        else 0.0
                    ),
            }
        )

    return pl.DataFrame(
        output,
        infer_schema_length=None,
    ).sort(
        "horizon_hours"
    )


# ============================================================
# COMPLETE VALIDATION
# ============================================================


def run_forward_validation(
    risk_history: pl.DataFrame,
    spot_history: pl.DataFrame,
    state_history: pl.DataFrame | None = None,
    validation_start: datetime | None = None,
    risk_version: str | None = None,
    horizons_hours: tuple[int, ...] = DEFAULT_HORIZONS_HOURS,
) -> dict[
    str,
    pl.DataFrame,
]:
    risk = prepare_risk_history(
        risk_history,
        validation_start=validation_start,
        risk_version=risk_version,
    )

    spot = prepare_spot_history(
        spot_history
    )

    if state_history is not None:
        states = prepare_state_history(
            state_history
        )
    else:
        states = None

    samples = build_forward_samples(
        risk_history=risk,
        spot_history=spot,
        state_history=states,
        horizons_hours=horizons_hours,
    )

    samples = add_cross_sectional_risk_quintiles(
        samples
    )

    snapshot_ic = (
        build_snapshot_information_coefficients(
            samples
        )
    )

    metrics = build_validation_metrics(
        snapshot_ic
    )

    quintiles = build_quintile_analysis(
        samples
    )

    quintile_summary = (
        build_quintile_summary(
            quintiles
        )
    )

    status = build_horizon_status(
        samples
    )

    return {
        "samples":
            samples,

        "snapshot_ic":
            snapshot_ic,

        "metrics":
            metrics,

        "quintiles":
            quintiles,

        "quintile_summary":
            quintile_summary,

        "status":
            status,
    }
