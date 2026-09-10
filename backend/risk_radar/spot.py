from __future__ import annotations

import math
from datetime import timedelta

import polars as pl


# ============================================================
# CONFIGURATION
# ============================================================

PRICE_CHANGE_HORIZONS = {
    "1h": 1,
    "4h": 4,
    "24h": 24,
}

PRICE_REFERENCE_TOLERANCE_MINUTES = 10.0


# ============================================================
# HELPERS
# ============================================================


def _finite_positive(
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
        and float(value) > 0
    )


def prepare_spot_history(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    """
    Prepare collected CMC spot history.

    collected_at is used as our own snapshot clock.
    timestamp remains the provider observation timestamp.
    """

    if dataframe.is_empty():
        return dataframe


    return (
        dataframe
        .sort([
            "symbol",
            "collected_at",
        ])
        .unique(
            subset=[
                "symbol",
                "collected_at",
            ],
            keep="last",
            maintain_order=True,
        )
    )


# ============================================================
# PRICE CHANGE FEATURES
# ============================================================


def build_latest_spot_snapshot(
    spot_history: pl.DataFrame,
) -> pl.DataFrame:
    """
    Build the latest 20-asset spot snapshot and calculate
    1h, 4h and 24h price changes from our own collected data.

    For each horizon we select the newest snapshot at or
    before t-h, provided it is within the allowed tolerance.
    """

    history = prepare_spot_history(
        spot_history
    )


    if history.is_empty():
        return history


    latest_time = (
        history[
            "collected_at"
        ].max()
    )


    latest = (
        history
        .filter(
            pl.col(
                "collected_at"
            )
            == latest_time
        )
        .sort(
            "symbol"
        )
    )


    output_rows = []


    for row in latest.to_dicts():

        symbol = row.get(
            "symbol"
        )

        current_time = row.get(
            "collected_at"
        )

        current_price = row.get(
            "price"
        )


        symbol_history = (
            history
            .filter(
                pl.col("symbol")
                == symbol
            )
            .sort(
                "collected_at"
            )
        )


        for (
            label,
            hours,
        ) in (
            PRICE_CHANGE_HORIZONS
            .items()
        ):

            # ----------------------------------------------
            # DEFAULTS
            # ----------------------------------------------

            row[
                f"price_change_{label}"
            ] = None

            row[
                f"price_change_usd_{label}"
            ] = None

            row[
                f"log_return_{label}"
            ] = None

            row[
                f"price_reference_{label}"
            ] = None

            row[
                f"price_reference_time_{label}"
            ] = None

            row[
                f"price_reference_offset_minutes_{label}"
            ] = None

            row[
                f"price_change_available_{label}"
            ] = False


            if current_time is None:
                continue


            target_time = (
                current_time
                - timedelta(
                    hours=hours
                )
            )


            # ----------------------------------------------
            # REFERENCE SNAPSHOT
            # ----------------------------------------------

            reference = (
                symbol_history
                .filter(
                    pl.col(
                        "collected_at"
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
                    "collected_at"
                )
            )


            reference_price = (
                reference_row.get(
                    "price"
                )
            )


            if reference_time is None:
                continue


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
                PRICE_REFERENCE_TOLERANCE_MINUTES
            ):
                continue


            # ----------------------------------------------
            # STORE REFERENCE
            # ----------------------------------------------

            row[
                f"price_reference_{label}"
            ] = reference_price

            row[
                f"price_reference_time_{label}"
            ] = reference_time

            row[
                f"price_reference_offset_minutes_{label}"
            ] = offset_minutes


            # ----------------------------------------------
            # CALCULATE CHANGE
            # ----------------------------------------------

            if not (
                _finite_positive(
                    current_price
                )
                and _finite_positive(
                    reference_price
                )
            ):
                continue


            price_change = (
                current_price
                / reference_price
                - 1.0
            )


            row[
                f"price_change_{label}"
            ] = price_change


            row[
                f"price_change_usd_{label}"
            ] = (
                current_price
                - reference_price
            )


            row[
                f"log_return_{label}"
            ] = math.log(
                current_price
                / reference_price
            )


            row[
                f"price_change_available_{label}"
            ] = True


        output_rows.append(
            row
        )


    result = pl.DataFrame(
        output_rows,
        infer_schema_length=None,
    )


    # Ensure unavailable horizons do not become Null columns.
    expressions = []


    for label in (
        PRICE_CHANGE_HORIZONS
    ):

        for column in [
            f"price_change_{label}",
            f"price_change_usd_{label}",
            f"log_return_{label}",
            f"price_reference_{label}",
            f"price_reference_offset_minutes_{label}",
        ]:

            expressions.append(
                pl.col(column)
                .cast(
                    pl.Float64,
                    strict=False,
                )
            )


        expressions.append(
            pl.col(
                f"price_reference_time_{label}"
            )
            .cast(
                pl.Datetime(
                    "us",
                    "UTC",
                ),
                strict=False,
            )
        )


        expressions.append(
            pl.col(
                f"price_change_available_{label}"
            )
            .cast(
                pl.Boolean,
                strict=False,
            )
        )


    return (
        result
        .with_columns(
            expressions
        )
        .sort(
            "market_cap",
            descending=True,
        )
    )