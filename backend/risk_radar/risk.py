from __future__ import annotations

import math
from datetime import datetime, timezone

import polars as pl


# ============================================================
# CONFIGURATION
# ============================================================

RISK_VERSION = "provisional_v1_equal_weight"

VOLATILITY_WEIGHT = 0.20
LEVERAGE_WEIGHT = 0.20
FUNDING_WEIGHT = 0.20
LIQUIDATION_WEIGHT = 0.20
MARKET_STRUCTURE_WEIGHT = 0.20


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


def _clamp01(
    value,
) -> float | None:

    if not _finite(value):

        return None


    return max(
        0.0,
        min(
            1.0,
            float(value),
        ),
    )


def _mean_available(
    values: list,
) -> float | None:

    clean = [
        float(value)
        for value in values
        if _finite(value)
    ]


    if not clean:

        return None


    return (
        sum(clean)
        / len(clean)
    )


def _percentile_rank(
    values: list,
) -> list[float | None]:
    """
    Cross-sectional percentile rank.

    Lowest finite value -> 0
    Highest finite value -> 1

    Ties receive average rank.
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
                valid[
                    i
                ][0]
            )


            output[
                original_index
            ] = percentile


        position = end


    return output


# ============================================================
# COMPONENT BUILDERS
# ============================================================


def volatility_component(
    row: dict,
) -> tuple[
    float | None,
    int,
]:
    """
    Volatility stress combines:

    1. Own-history volatility percentile.
    2. Current cross-sectional volatility-expansion percentile.

    If only one is available, that observation is used.

    This is provisional. We expose both underlying quantities
    so the combination can be validated before final weights
    are selected.
    """

    historical = _clamp01(
        row.get(
            "vol_percentile_24h"
        )
    )


    cross_expansion = _clamp01(
        row.get(
            "vol_expansion_cross_percentile"
        )
    )


    inputs = [
        value
        for value in [
            historical,
            cross_expansion,
        ]
        if value is not None
    ]


    component = (
        _mean_available(
            inputs
        )
    )


    return (
        component,
        len(inputs),
    )


def leverage_component(
    row: dict,
) -> float | None:
    """
    Magnitude of the validated common-universe 1h OI change.

    Direction is deliberately excluded from the risk magnitude.
    """

    if (
        row.get(
            "common_oi_change_available_1h"
        )
        is not True
    ):

        return None


    return _clamp01(
        row.get(
            "oi_change_magnitude_percentile_1h"
        )
    )


def funding_component(
    row: dict,
) -> tuple[
    float | None,
    str,
]:
    """
    Funding component uses full historical confirmation once
    funding history is ready.

    During warm-up, it uses only the already-validated
    cross-sectional confirmed funding-tail percentile.

    The source is stored explicitly.
    """

    history_ready = (
        row.get(
            "funding_history_available"
        )
        is True
    )


    historical_confirmed = (
        _clamp01(
            row.get(
                "funding_confirmed_tail_percentile"
            )
        )
    )


    cross_confirmed = (
        _clamp01(
            row.get(
                "funding_cross_confirmed_tail_percentile"
            )
        )
    )


    if (
        history_ready
        and
        historical_confirmed
        is not None
    ):

        return (
            historical_confirmed,
            "HISTORICAL + CROSS CONFIRMED",
        )


    if cross_confirmed is not None:

        return (
            cross_confirmed,
            "CROSS-SECTIONAL WARMUP",
        )


    return (
        None,
        "UNAVAILABLE",
    )


def liquidation_component(
    row: dict,
) -> float | None:
    """
    Confirmed liquidation stress already conservatively
    combines own-history liquidation intensity with
    liquidation-to-OI cross-sectional materiality.
    """

    return _clamp01(
        row.get(
            "liquidation_confirmed_percentile_1h"
        )
    )


def market_structure_component(
    row: dict,
) -> float | None:
    """
    Current provisional market-structure factor.

    Higher OI concentration percentile means a larger share of
    derivatives exposure is concentrated into fewer venues.

    This is intentionally kept separate from basis dispersion
    for now so that the fifth factor remains interpretable.
    """

    return _clamp01(
        row.get(
            "oi_concentration_percentile"
        )
    )


# ============================================================
# BUILD RISK SNAPSHOT
# ============================================================


def build_risk_snapshot(
    states: pl.DataFrame,
) -> pl.DataFrame:
    """
    Construct the provisional CDRR risk ranking.

    The risk score measures stress magnitude, not expected
    price direction.

    Primary state remains the directional / regime descriptor.
    """

    if states.is_empty():

        return states


    required = [
        "symbol",
        "state_source_at",
    ]


    missing = [
        column
        for column in required
        if column not in states.columns
    ]


    if missing:

        raise ValueError(
            "Missing state columns required "
            "for risk calculation: "
            + ", ".join(
                missing
            )
        )


    generated_at = datetime.now(
        timezone.utc
    )


    output = []


    for state_row in states.to_dicts():

        symbol = (
            state_row.get(
                "symbol"
            )
        )


        asset = (
            state_row.get(
                "asset"
            )
        )


        primary_state = (
            state_row.get(
                "primary_state"
            )
        )


        state_quality = (
            state_row.get(
                "state_quality"
            )
        )


        state_ready = (
            state_row.get(
                "state_ready_1h"
            )
            is True
        )


        # ====================================================
        # VOLATILITY
        # ====================================================

        (
            vol_component,
            vol_input_count,
        ) = volatility_component(
            state_row
        )


        # ====================================================
        # LEVERAGE / OI
        # ====================================================

        lev_component = (
            leverage_component(
                state_row
            )
        )


        # ====================================================
        # FUNDING
        # ====================================================

        (
            fund_component,
            fund_source,
        ) = funding_component(
            state_row
        )


        # ====================================================
        # LIQUIDATIONS
        # ====================================================

        liq_component = (
            liquidation_component(
                state_row
            )
        )


        # ====================================================
        # MARKET STRUCTURE
        # ====================================================

        structure_component = (
            market_structure_component(
                state_row
            )
        )


        components = {
            "volatility":
                vol_component,

            "leverage":
                lev_component,

            "funding":
                fund_component,

            "liquidation":
                liq_component,

            "market_structure":
                structure_component,
        }


        missing_components = [
            name
            for name, value
            in components.items()
            if not _finite(value)
        ]


        component_count = (
            len(components)
            - len(
                missing_components
            )
        )


        risk_ready = (
            state_ready
            and
            component_count
            == len(
                components
            )
        )


        if risk_ready:

            provisional_score = (
                100.0
                * (
                    VOLATILITY_WEIGHT
                    * float(
                        vol_component
                    )
                    +
                    LEVERAGE_WEIGHT
                    * float(
                        lev_component
                    )
                    +
                    FUNDING_WEIGHT
                    * float(
                        fund_component
                    )
                    +
                    LIQUIDATION_WEIGHT
                    * float(
                        liq_component
                    )
                    +
                    MARKET_STRUCTURE_WEIGHT
                    * float(
                        structure_component
                    )
                )
            )

        else:

            provisional_score = None


        risk_source_at = (
            state_row.get(
                "state_source_at"
            )
        )


        output.append({

            # ------------------------------------------------
            # IDENTITY
            # ------------------------------------------------

            "symbol":
                symbol,

            "asset":
                asset,


            # ------------------------------------------------
            # STATE CONTEXT
            # ------------------------------------------------

            "primary_state":
                primary_state,

            "state_quality":
                state_quality,

            "state_ready_1h":
                state_ready,


            # ------------------------------------------------
            # VOLATILITY INPUTS
            # ------------------------------------------------

            "vol_percentile_24h":
                state_row.get(
                    "vol_percentile_24h"
                ),

            "vol_expansion_cross_percentile":
                state_row.get(
                    "vol_expansion_cross_percentile"
                ),

            "volatility_component":
                vol_component,

            "volatility_component_inputs":
                vol_input_count,


            # ------------------------------------------------
            # LEVERAGE INPUTS
            # ------------------------------------------------

            "open_interest_change_common_1h":
                state_row.get(
                    "open_interest_change_common_1h"
                ),

            "common_oi_overlap_min_share_1h":
                state_row.get(
                    "common_oi_overlap_min_share_1h"
                ),

            "oi_change_magnitude_percentile_1h":
                state_row.get(
                    "oi_change_magnitude_percentile_1h"
                ),

            "leverage_component":
                lev_component,


            # ------------------------------------------------
            # FUNDING INPUTS
            # ------------------------------------------------

            "median_funding_rate":
                state_row.get(
                    "median_funding_rate"
                ),

            "funding_cross_confirmed_tail_percentile":
                state_row.get(
                    "funding_cross_confirmed_tail_percentile"
                ),

            "funding_confirmed_tail_percentile":
                state_row.get(
                    "funding_confirmed_tail_percentile"
                ),

            "funding_history_available":
                state_row.get(
                    "funding_history_available"
                ),

            "funding_crowding_state":
                state_row.get(
                    "funding_crowding_state"
                ),

            "funding_component":
                fund_component,

            "funding_component_source":
                fund_source,


            # ------------------------------------------------
            # LIQUIDATION INPUTS
            # ------------------------------------------------

            "liquidation_percentile_1h":
                state_row.get(
                    "liquidation_percentile_1h"
                ),

            "liquidations_to_oi_percentile_1h":
                state_row.get(
                    "liquidations_to_oi_percentile_1h"
                ),

            "liquidation_confirmed_percentile_1h":
                state_row.get(
                    "liquidation_confirmed_percentile_1h"
                ),

            "liquidation_component":
                liq_component,


            # ------------------------------------------------
            # MARKET-STRUCTURE INPUTS
            # ------------------------------------------------

            "oi_hhi":
                state_row.get(
                    "oi_hhi"
                ),

            "oi_top_venue_share":
                state_row.get(
                    "oi_top_venue_share"
                ),

            "oi_concentration_percentile":
                state_row.get(
                    "oi_concentration_percentile"
                ),

            "market_structure_component":
                structure_component,


            # ------------------------------------------------
            # WEIGHTS
            # ------------------------------------------------

            "volatility_weight":
                VOLATILITY_WEIGHT,

            "leverage_weight":
                LEVERAGE_WEIGHT,

            "funding_weight":
                FUNDING_WEIGHT,

            "liquidation_weight":
                LIQUIDATION_WEIGHT,

            "market_structure_weight":
                MARKET_STRUCTURE_WEIGHT,


            # ------------------------------------------------
            # SCORE
            # ------------------------------------------------

            "component_count":
                component_count,

            "missing_components":
                ", ".join(
                    missing_components
                )
                if missing_components
                else "",

            "risk_ready":
                risk_ready,

            "provisional_risk_score":
                provisional_score,

            "risk_version":
                RISK_VERSION,


            # ------------------------------------------------
            # TIMING
            # ------------------------------------------------

            "risk_source_at":
                risk_source_at,

            "risk_generated_at":
                generated_at,

            "risk_calculated_at":
                (
                    risk_source_at
                    if isinstance(
                        risk_source_at,
                        datetime,
                    )
                    else generated_at
                ),
        })


    # ========================================================
    # CROSS-SECTIONAL SCORE RANKING
    # ========================================================

    scores = [
        row.get(
            "provisional_risk_score"
        )
        for row in output
    ]


    score_percentiles = (
        _percentile_rank(
            scores
        )
    )


    finite_scores = sorted(
        [
            float(score)
            for score in scores
            if _finite(score)
        ],
        reverse=True,
    )


    for index, row in enumerate(
        output
    ):

        score = row.get(
            "provisional_risk_score"
        )


        row[
            "risk_cross_percentile"
        ] = (
            score_percentiles[
                index
            ]
        )


        if _finite(score):

            # Competition ranking:
            #
            # 80, 70, 70, 60
            # -> ranks 1, 2, 2, 4
            row[
                "risk_rank"
            ] = (
                1
                + sum(
                    candidate
                    > float(score)
                    for candidate
                    in finite_scores
                )
            )

        else:

            row[
                "risk_rank"
            ] = None


    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )

        .sort(
            [
                "risk_ready",
                "provisional_risk_score",
            ],
            descending=[
                True,
                True,
            ],
            nulls_last=True,
        )
    )