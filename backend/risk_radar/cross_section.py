from __future__ import annotations

import math

import polars as pl


# ============================================================
# HELPERS
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
    absolute: bool = False,
) -> list[float | None]:
    """
    Cross-sectional percentile rank in [0, 1].

    Lowest observation -> 0
    Highest observation -> 1

    Ties receive the average rank.

    If only one finite observation exists, assign 0.5.
    """

    result: list[
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


        numeric = float(
            value
        )


        if absolute:

            numeric = abs(
                numeric
            )


        valid.append(
            (
                index,
                numeric,
            )
        )


    count = len(
        valid
    )


    if count == 0:

        return result


    if count == 1:

        index, _ = valid[0]

        result[index] = 0.5

        return result


    valid.sort(
        key=lambda item:
            item[1]
    )


    position = 0


    while position < count:

        end = position + 1

        value = valid[
            position
        ][1]


        while (
            end < count
            and
            valid[end][1]
            == value
        ):

            end += 1


        # ranks are zero-indexed
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

            result[
                original_index
            ] = percentile


        position = end


    return result


def _minimum_if_finite(
    first,
    second,
) -> float | None:

    if not (
        _finite(first)
        and _finite(second)
    ):

        return None


    return min(
        float(first),
        float(second),
    )


# ============================================================
# CROSS-SECTIONAL FEATURES
# ============================================================


def add_cross_sectional_features(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:
    """
    Add relative signal-strength features across the tracked
    20-asset universe.

    These are descriptive ranks rather than a final risk score.
    """

    if dataframe.is_empty():

        return dataframe


    rows = dataframe.to_dicts()


    # ========================================================
    # SOURCE ARRAYS
    # ========================================================

    oi_changes = [
        row.get(
            "open_interest_change_common_1h"
        )
        for row in rows
    ]


    liquidation_oi = [
        row.get(
            "liquidations_to_oi_1h"
        )
        for row in rows
    ]


    funding = [
        row.get(
            "median_funding_rate"
        )
        for row in rows
    ]


    basis = [
        row.get(
            "median_index_basis"
        )
        for row in rows
    ]


    oi_hhi = [
        row.get(
            "oi_hhi"
        )
        for row in rows
    ]


    vol_ratio = [
        row.get(
            "vol_ratio_1h_vs_24h"
        )
        for row in rows
    ]


    price_changes = [
        row.get(
            "price_change_1h"
        )
        for row in rows
    ]


    # ========================================================
    # RANKS
    # ========================================================

    oi_magnitude_pct = (
        _percentile_rank(
            oi_changes,
            absolute=True,
        )
    )


    liquidation_oi_pct = (
        _percentile_rank(
            liquidation_oi,
            absolute=False,
        )
    )


    funding_magnitude_pct = (
        _percentile_rank(
            funding,
            absolute=True,
        )
    )


    basis_magnitude_pct = (
        _percentile_rank(
            basis,
            absolute=True,
        )
    )


    concentration_pct = (
        _percentile_rank(
            oi_hhi,
            absolute=False,
        )
    )


    vol_expansion_pct = (
        _percentile_rank(
            vol_ratio,
            absolute=False,
        )
    )


    price_magnitude_pct = (
        _percentile_rank(
            price_changes,
            absolute=True,
        )
    )


    # ========================================================
    # ATTACH
    # ========================================================

    for index, row in enumerate(
        rows
    ):

        row[
            "oi_change_magnitude_percentile_1h"
        ] = oi_magnitude_pct[
            index
        ]


        row[
            "liquidations_to_oi_percentile_1h"
        ] = liquidation_oi_pct[
            index
        ]


        row[
            "funding_magnitude_percentile"
        ] = funding_magnitude_pct[
            index
        ]


        row[
            "basis_magnitude_percentile"
        ] = basis_magnitude_pct[
            index
        ]


        row[
            "oi_concentration_percentile"
        ] = concentration_pct[
            index
        ]


        row[
            "vol_expansion_cross_percentile"
        ] = vol_expansion_pct[
            index
        ]


        row[
            "price_move_magnitude_percentile_1h"
        ] = price_magnitude_pct[
            index
        ]


        # ----------------------------------------------------
        # LIQUIDATION CONFIRMATION
        #
        # A liquidation observation must be unusual BOTH:
        #
        # 1. relative to the asset's own recent history
        # 2. relative to its current open interest compared
        #    with the other tracked assets
        #
        # Taking the minimum makes this deliberately
        # conservative.
        # ----------------------------------------------------

        row[
            "liquidation_confirmed_percentile_1h"
        ] = _minimum_if_finite(
            row.get(
                "liquidation_percentile_1h"
            ),
            row.get(
                "liquidations_to_oi_percentile_1h"
            ),
        )


    return pl.DataFrame(
        rows,
        infer_schema_length=None,
    )