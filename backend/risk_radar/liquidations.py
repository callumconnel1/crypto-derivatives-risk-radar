from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

import polars as pl


# ============================================================
# CONFIGURATION
# ============================================================

LOOKBACK_HOURS = 24

# We still calculate warm-up percentiles before this point, but
# expose whether the intended 24h temporal baseline is mature.
MIN_BASELINE_SPAN_HOURS = 23.0


# ============================================================
# HELPERS
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


def _clean_numeric_values(
    values: list[Any],
) -> list[float]:
    return [
        float(value)
        for value in values
        if _finite(value)
    ]


def _midrank_percentile(
    values: list[Any],
    current: Any,
) -> float | None:
    """
    Empirical percentile with midrank tie handling:

        P = (N_< + 0.5 N_=) / N

    `values` should contain only observations strictly prior
    to the current snapshot.

    This prevents repeated zeros or repeated provider values
    from being pushed artificially to the top of the empirical
    distribution by a <= comparison.
    """

    if not _finite(current):
        return None

    clean = _clean_numeric_values(
        values
    )

    if not clean:
        return None

    current_value = float(
        current
    )

    less = sum(
        value < current_value
        for value in clean
    )

    equal = sum(
        value == current_value
        for value in clean
    )

    return (
        less
        + 0.5 * equal
    ) / len(
        clean
    )


def _median(
    values: list[Any],
) -> float | None:
    clean = sorted(
        _clean_numeric_values(
            values
        )
    )

    count = len(
        clean
    )

    if count == 0:
        return None

    midpoint = (
        count // 2
    )

    if count % 2 == 1:
        return clean[
            midpoint
        ]

    return (
        clean[
            midpoint - 1
        ]
        +
        clean[
            midpoint
        ]
    ) / 2.0


def _span_hours(
    timestamps: list[Any],
) -> float:
    clean = [
        timestamp
        for timestamp in timestamps
        if timestamp is not None
    ]

    if len(
        clean
    ) < 2:
        return 0.0

    return max(
        0.0,
        (
            max(clean)
            - min(clean)
        ).total_seconds()
        / 3600.0,
    )


def _direction_label(
    total_liquidations: Any,
    long_share: Any,
) -> str:
    if (
        not _finite(
            total_liquidations
        )
        or float(
            total_liquidations
        ) <= 0
        or not _finite(
            long_share
        )
    ):
        return "NONE"

    share = float(
        long_share
    )

    if share >= 0.70:
        return "LONG"

    if share <= 0.30:
        return "SHORT"

    return "MIXED"


def _directional_imbalance(
    long_share: Any,
) -> float | None:
    """
    0 = perfectly balanced long/short liquidations.
    1 = entirely one-sided liquidation flow.

    This is descriptive only. It is deliberately not multiplied
    into the stress score here.
    """

    if not _finite(
        long_share
    ):
        return None

    share = max(
        0.0,
        min(
            1.0,
            float(
                long_share
            ),
        ),
    )

    return abs(
        2.0 * share
        - 1.0
    )


def _baseline_metrics(
    prior: pl.DataFrame,
    current_row: dict,
) -> dict:
    """
    Build prior-only temporal calibration statistics for one
    asset/global snapshot.
    """

    timestamps = (
        prior[
            "timestamp"
        ].to_list()
        if (
            not prior.is_empty()
            and
            "timestamp"
            in prior.columns
        )
        else []
    )

    span_hours = _span_hours(
        timestamps
    )

    observations = (
        prior.height
    )

    coverage = min(
        1.0,
        span_hours
        / LOOKBACK_HOURS,
    )

    complete = (
        span_hours
        >= MIN_BASELINE_SPAN_HOURS
    )

    result = {
        "baseline_observations":
            observations,

        "baseline_span_hours":
            span_hours,

        "baseline_coverage":
            coverage,

        "baseline_complete":
            complete,
    }

    for horizon in (
        "1h",
        "4h",
        "24h",
    ):
        column = (
            f"total_liquidations_{horizon}"
        )

        prior_values = (
            prior[
                column
            ].to_list()
            if (
                not prior.is_empty()
                and
                column
                in prior.columns
            )
            else []
        )

        current = (
            current_row.get(
                column
            )
        )

        result[
            f"percentile_{horizon}"
        ] = _midrank_percentile(
            prior_values,
            current,
        )

        result[
            f"median_{horizon}"
        ] = _median(
            prior_values
        )

        clean_values = (
            _clean_numeric_values(
                prior_values
            )
        )

        result[
            f"distinct_{horizon}"
        ] = len(
            set(
                clean_values
            )
        )

        if _finite(
            current
        ):
            current_value = float(
                current
            )

            result[
                f"equal_count_{horizon}"
            ] = sum(
                value
                == current_value
                for value
                in clean_values
            )
        else:
            result[
                f"equal_count_{horizon}"
            ] = 0

    return result


def prepare_crypto_history(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    """
    Clean collected cryptocurrency liquidation history.

    Provider timestamp is used as the market-data timestamp.
    collected_at remains the local collection timestamp.
    """

    if dataframe.is_empty():
        return dataframe

    return (
        dataframe
        .sort([
            "symbol",
            "timestamp",
            "collected_at",
        ])
        .unique(
            subset=[
                "symbol",
                "timestamp",
            ],
            keep="last",
            maintain_order=True,
        )
    )


def prepare_global_history(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    if dataframe.is_empty():
        return dataframe

    return (
        dataframe
        .sort([
            "timestamp",
            "collected_at",
        ])
        .unique(
            subset=[
                "timestamp",
            ],
            keep="last",
            maintain_order=True,
        )
    )


def prepare_exchange_history(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    if dataframe.is_empty():
        return dataframe

    return (
        dataframe
        .sort([
            "exchange_id",
            "timestamp",
            "collected_at",
        ])
        .unique(
            subset=[
                "exchange_id",
                "timestamp",
            ],
            keep="last",
            maintain_order=True,
        )
    )


# ============================================================
# ASSET LIQUIDATION SNAPSHOT
# ============================================================


def build_asset_snapshot(
    crypto_history: pl.DataFrame,
    derivatives_latest: pl.DataFrame | None = None,
) -> pl.DataFrame:
    history = prepare_crypto_history(
        crypto_history
    )

    if history.is_empty():
        return history

    latest = (
        history
        .sort([
            "symbol",
            "timestamp",
        ])
        .unique(
            subset=[
                "symbol",
            ],
            keep="last",
            maintain_order=True,
        )
    )

    baseline_rows: list[
        dict
    ] = []

    for current_row in latest.to_dicts():
        symbol = current_row[
            "symbol"
        ]

        current_timestamp = (
            current_row[
                "timestamp"
            ]
        )

        lookback_start = (
            current_timestamp
            - timedelta(
                hours=LOOKBACK_HOURS
            )
        )

        # Critical change:
        # baseline is strictly prior to the current observation.
        prior = history.filter(
            (
                pl.col(
                    "symbol"
                )
                == symbol
            )
            &
            (
                pl.col(
                    "timestamp"
                )
                >= lookback_start
            )
            &
            (
                pl.col(
                    "timestamp"
                )
                < current_timestamp
            )
        )

        metrics = _baseline_metrics(
            prior,
            current_row,
        )

        baseline_rows.append(
            {
                "symbol":
                    symbol,

                "liquidation_baseline_observations":
                    metrics[
                        "baseline_observations"
                    ],

                "liquidation_baseline_span_hours":
                    metrics[
                        "baseline_span_hours"
                    ],

                "liquidation_baseline_coverage_24h":
                    metrics[
                        "baseline_coverage"
                    ],

                "liquidation_history_24h_complete":
                    metrics[
                        "baseline_complete"
                    ],

                "liquidation_percentile_1h":
                    metrics[
                        "percentile_1h"
                    ],

                "liquidation_percentile_4h":
                    metrics[
                        "percentile_4h"
                    ],

                "liquidation_percentile_24h":
                    metrics[
                        "percentile_24h"
                    ],

                "liquidation_activity_percentile_1h":
                    metrics[
                        "percentile_1h"
                    ],

                "liquidation_activity_percentile_4h":
                    metrics[
                        "percentile_4h"
                    ],

                "liquidation_activity_percentile_24h":
                    metrics[
                        "percentile_24h"
                    ],

                "median_liquidations_1h_24h":
                    metrics[
                        "median_1h"
                    ],

                "median_liquidations_4h_24h":
                    metrics[
                        "median_4h"
                    ],

                "median_liquidations_24h_24h":
                    metrics[
                        "median_24h"
                    ],

                "liquidation_baseline_distinct_1h":
                    metrics[
                        "distinct_1h"
                    ],

                "liquidation_baseline_equal_count_1h":
                    metrics[
                        "equal_count_1h"
                    ],
            }
        )

    baseline = pl.DataFrame(
        baseline_rows,
        infer_schema_length=None,
    )

    snapshot = (
        latest
        .join(
            baseline,
            on="symbol",
            how="left",
        )
    )

    # ========================================================
    # CURRENT / BASELINE RATIOS
    # ========================================================

    snapshot = snapshot.with_columns([
        pl.when(
            pl.col(
                "median_liquidations_1h_24h"
            ) > 0
        )
        .then(
            pl.col(
                "total_liquidations_1h"
            )
            /
            pl.col(
                "median_liquidations_1h_24h"
            )
        )
        .otherwise(None)
        .alias(
            "liquidation_ratio_to_median_1h"
        ),

        pl.when(
            pl.col(
                "median_liquidations_4h_24h"
            ) > 0
        )
        .then(
            pl.col(
                "total_liquidations_4h"
            )
            /
            pl.col(
                "median_liquidations_4h_24h"
            )
        )
        .otherwise(None)
        .alias(
            "liquidation_ratio_to_median_4h"
        ),
    ])

    # ========================================================
    # OPEN-INTEREST NORMALISATION
    # ========================================================

    if (
        derivatives_latest is not None
        and not derivatives_latest.is_empty()
        and "total_open_interest"
        in derivatives_latest.columns
    ):
        oi = (
            derivatives_latest
            .select([
                "symbol",
                "total_open_interest",
            ])
            .unique(
                subset=[
                    "symbol"
                ],
                keep="last",
            )
        )

        snapshot = (
            snapshot
            .join(
                oi,
                on="symbol",
                how="left",
            )
        )

    elif (
        "total_open_interest"
        not in snapshot.columns
    ):
        snapshot = snapshot.with_columns(
            pl.lit(
                None,
                dtype=pl.Float64,
            ).alias(
                "total_open_interest"
            )
        )

    snapshot = snapshot.with_columns([
        pl.when(
            pl.col(
                "total_open_interest"
            ) > 0
        )
        .then(
            pl.col(
                "total_liquidations_1h"
            )
            /
            pl.col(
                "total_open_interest"
            )
        )
        .otherwise(None)
        .alias(
            "liquidations_to_oi_1h"
        ),

        pl.when(
            pl.col(
                "total_open_interest"
            ) > 0
        )
        .then(
            pl.col(
                "total_liquidations_4h"
            )
            /
            pl.col(
                "total_open_interest"
            )
        )
        .otherwise(None)
        .alias(
            "liquidations_to_oi_4h"
        ),

        pl.when(
            pl.col(
                "total_open_interest"
            ) > 0
        )
        .then(
            pl.col(
                "total_liquidations_24h"
            )
            /
            pl.col(
                "total_open_interest"
            )
        )
        .otherwise(None)
        .alias(
            "liquidations_to_oi_24h"
        ),
    ])

    # ========================================================
    # DIRECTIONAL FLOW — DESCRIPTIVE, NOT A STRESS MULTIPLIER
    # ========================================================

    direction_records = []

    for row in snapshot.to_dicts():
        direction_records.append(
            {
                "symbol":
                    row[
                        "symbol"
                    ],

                "liquidation_direction_1h":
                    _direction_label(
                        row.get(
                            "total_liquidations_1h"
                        ),
                        row.get(
                            "long_liquidation_share_1h"
                        ),
                    ),

                "liquidation_directional_imbalance_1h":
                    _directional_imbalance(
                        row.get(
                            "long_liquidation_share_1h"
                        )
                    ),
            }
        )

    direction_frame = pl.DataFrame(
        direction_records,
        infer_schema_length=None,
    )

    snapshot = (
        snapshot
        .join(
            direction_frame,
            on="symbol",
            how="left",
        )
    )

    return (
        snapshot
        .sort(
            "total_liquidations_1h",
            descending=True,
            nulls_last=True,
        )
    )


# ============================================================
# EXCHANGE SNAPSHOT
# ============================================================


def build_exchange_snapshot(
    exchange_history: pl.DataFrame,
) -> pl.DataFrame:
    history = prepare_exchange_history(
        exchange_history
    )

    if history.is_empty():
        return history

    snapshot = (
        history
        .sort([
            "exchange_id",
            "timestamp",
        ])
        .unique(
            subset=[
                "exchange_id",
            ],
            keep="last",
            maintain_order=True,
        )
    )

    # Provider-reported global_liquidation_share_1h is retained
    # as raw metadata, but is NOT trusted for HHI because those
    # shares need not sum exactly to one across returned rows.
    #
    # Instead, concentration is based on latest exchange
    # liquidation totals and normalised over the tracked exchange
    # set represented in this snapshot.
    positive_total = (
        snapshot
        .filter(
            pl.col(
                "total_liquidations_1h"
            ).is_not_null()
            &
            (
                pl.col(
                    "total_liquidations_1h"
                ) > 0
            )
        )[
            "total_liquidations_1h"
        ]
        .sum()
    )

    if (
        positive_total is not None
        and
        positive_total > 0
    ):
        snapshot = snapshot.with_columns(
            pl.when(
                pl.col(
                    "total_liquidations_1h"
                ).is_not_null()
                &
                (
                    pl.col(
                        "total_liquidations_1h"
                    ) > 0
                )
            )
            .then(
                pl.col(
                    "total_liquidations_1h"
                )
                /
                pl.lit(
                    positive_total
                )
            )
            .otherwise(
                0.0
            )
            .alias(
                "normalized_liquidation_share_1h"
            )
        )

    else:
        snapshot = snapshot.with_columns(
            pl.lit(
                None,
                dtype=pl.Float64,
            ).alias(
                "normalized_liquidation_share_1h"
            )
        )

    return (
        snapshot
        .sort(
            "total_liquidations_1h",
            descending=True,
            nulls_last=True,
        )
    )


# ============================================================
# GLOBAL LIQUIDATION SNAPSHOT
# ============================================================


def build_global_snapshot(
    global_history: pl.DataFrame,
    exchange_history: pl.DataFrame | None = None,
) -> pl.DataFrame:
    history = prepare_global_history(
        global_history
    )

    if history.is_empty():
        return history

    latest = (
        history
        .sort(
            "timestamp"
        )
        .tail(1)
    )

    current_row = (
        latest
        .row(
            0,
            named=True,
        )
    )

    latest_timestamp = (
        current_row[
            "timestamp"
        ]
    )

    lookback_start = (
        latest_timestamp
        - timedelta(
            hours=LOOKBACK_HOURS
        )
    )

    prior = history.filter(
        (
            pl.col(
                "timestamp"
            )
            >= lookback_start
        )
        &
        (
            pl.col(
                "timestamp"
            )
            < latest_timestamp
        )
    )

    metrics = _baseline_metrics(
        prior,
        current_row,
    )

    latest = latest.with_columns([
        pl.lit(
            metrics[
                "percentile_1h"
            ]
        ).alias(
            "global_liquidation_percentile_1h"
        ),

        pl.lit(
            metrics[
                "percentile_4h"
            ]
        ).alias(
            "global_liquidation_percentile_4h"
        ),

        pl.lit(
            metrics[
                "percentile_24h"
            ]
        ).alias(
            "global_liquidation_percentile_24h"
        ),

        pl.lit(
            metrics[
                "median_1h"
            ]
        ).alias(
            "global_median_liquidations_1h_24h"
        ),

        pl.lit(
            metrics[
                "baseline_observations"
            ]
        ).alias(
            "global_baseline_observations"
        ),

        pl.lit(
            metrics[
                "baseline_span_hours"
            ]
        ).alias(
            "global_baseline_span_hours"
        ),

        pl.lit(
            metrics[
                "baseline_coverage"
            ]
        ).alias(
            "global_baseline_coverage_24h"
        ),

        pl.lit(
            metrics[
                "baseline_complete"
            ]
        ).alias(
            "global_history_24h_complete"
        ),

        pl.lit(
            metrics[
                "equal_count_1h"
            ]
        ).alias(
            "global_baseline_equal_count_1h"
        ),
    ])

    # ========================================================
    # EXCHANGE CONCENTRATION
    # ========================================================

    if (
        exchange_history is not None
        and not exchange_history.is_empty()
    ):
        exchanges = build_exchange_snapshot(
            exchange_history
        )

        valid = exchanges.filter(
            pl.col(
                "normalized_liquidation_share_1h"
            ).is_not_null()
            &
            (
                pl.col(
                    "normalized_liquidation_share_1h"
                ) > 0
            )
        )

        if not valid.is_empty():
            top_exchange = (
                valid
                .sort(
                    "normalized_liquidation_share_1h",
                    descending=True,
                )
                .row(
                    0,
                    named=True,
                )
            )

            hhi_1h = (
                valid
                .select(
                    (
                        pl.col(
                            "normalized_liquidation_share_1h"
                        )
                        ** 2
                    )
                    .sum()
                )
                .item()
            )

            normalized_sum = (
                valid[
                    "normalized_liquidation_share_1h"
                ]
                .sum()
            )

            exchange_total = (
                valid[
                    "total_liquidations_1h"
                ]
                .sum()
            )

            if (
                "global_liquidation_share_1h"
                in valid.columns
            ):
                raw_provider_share_sum = (
                    valid[
                        "global_liquidation_share_1h"
                    ]
                    .drop_nulls()
                    .sum()
                )

                top_provider_share = (
                    top_exchange.get(
                        "global_liquidation_share_1h"
                    )
                )
            else:
                raw_provider_share_sum = None
                top_provider_share = None

            latest = latest.with_columns([
                pl.lit(
                    top_exchange[
                        "exchange"
                    ]
                ).alias(
                    "top_liquidation_exchange_1h"
                ),

                # Normalised share over the tracked exchange
                # snapshot. This is the concentration input.
                pl.lit(
                    top_exchange[
                        "normalized_liquidation_share_1h"
                    ]
                ).alias(
                    "top_liquidation_exchange_share_1h"
                ),

                # Provider raw share retained for diagnostics.
                pl.lit(
                    top_provider_share
                ).alias(
                    "top_liquidation_exchange_provider_share_1h"
                ),

                pl.lit(
                    hhi_1h
                ).alias(
                    "exchange_liquidation_hhi_1h"
                ),

                pl.lit(
                    normalized_sum
                ).alias(
                    "exchange_liquidation_normalized_share_sum_1h"
                ),

                pl.lit(
                    raw_provider_share_sum
                ).alias(
                    "exchange_liquidation_provider_share_sum_1h"
                ),

                pl.lit(
                    exchange_total
                ).alias(
                    "exchange_liquidation_total_1h"
                ),
            ])

    return latest


# ============================================================
# COMPLETE PIPELINE
# ============================================================


def build_liquidation_snapshots(
    crypto_history: pl.DataFrame,
    global_history: pl.DataFrame,
    exchange_history: pl.DataFrame,
    derivatives_latest: pl.DataFrame | None = None,
) -> tuple[
    pl.DataFrame,
    pl.DataFrame,
    pl.DataFrame,
]:
    assets = build_asset_snapshot(
        crypto_history=crypto_history,
        derivatives_latest=derivatives_latest,
    )

    exchanges = build_exchange_snapshot(
        exchange_history
    )

    global_snapshot = (
        build_global_snapshot(
            global_history=global_history,
            exchange_history=exchange_history,
        )
    )

    return (
        assets,
        global_snapshot,
        exchanges,
    )
