from __future__ import annotations

import math
from datetime import datetime, timezone

import polars as pl

from backend.risk_radar.cross_section import (
    add_cross_sectional_features,
)


# ============================================================
# CONFIGURATION
# ============================================================

LIQUIDATION_ELEVATED_PERCENTILE = 0.80
LIQUIDATION_EXTREME_PERCENTILE = 0.95

LIQUIDATION_DIRECTION_SHARE = 0.70

MAX_SOURCE_SKEW_SECONDS = 600.0


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


def _direction(
    value,
    positive: str,
    negative: str,
    flat: str = "FLAT",
    unavailable: str = "UNAVAILABLE",
) -> str:

    if not _finite(value):

        return unavailable


    if value > 0:

        return positive


    if value < 0:

        return negative


    return flat


def _format_percent(
    value,
    decimals: int = 2,
) -> str:

    if not _finite(value):

        return "NA"


    return (
        f"{float(value) * 100:+.{decimals}f}%"
    )


def _format_rate(
    value,
) -> str:

    if not _finite(value):

        return "NA"


    return (
        f"{float(value) * 100:+.4f}%"
    )


def _format_number(
    value,
    decimals: int = 2,
) -> str:

    if not _finite(value):

        return "NA"


    return (
        f"{float(value):.{decimals}f}"
    )


def _format_percentile(
    value,
) -> str:

    if not _finite(value):

        return "NA"


    return (
        f"{float(value) * 100:.0f}P"
    )


# ============================================================
# JOIN INPUT SNAPSHOTS
# ============================================================


def join_state_inputs(
    spot: pl.DataFrame,
    volatility: pl.DataFrame,
    derivatives: pl.DataFrame,
    funding: pl.DataFrame,
    liquidations: pl.DataFrame,
) -> pl.DataFrame:

    # ========================================================
    # SPOT
    # ========================================================

    spot_columns = [
        "symbol",
        "asset",
        "price",

        "price_change_1h",
        "price_change_4h",
        "price_change_24h",

        "price_change_available_1h",
        "price_change_available_4h",
        "price_change_available_24h",

        "collected_at",
    ]


    spot_columns = [
        column
        for column in spot_columns
        if column in spot.columns
    ]


    combined = (
        spot

        .select(
            spot_columns
        )

        .rename({
            "collected_at":
                "spot_calculated_at",
        })
    )


    # ========================================================
    # VOLATILITY
    # ========================================================

    volatility_columns = [
        "symbol",

        "realized_vol_1h",
        "realized_vol_4h",
        "realized_vol_24h",

        "vol_ratio_1h_vs_24h",
        "vol_ratio_4h_vs_24h",

        "vol_percentile_24h",

        "power_law_vol_forecast",
        "ewma_vol_forecast",
        "model_disagreement",

        "calculated_at",
    ]


    volatility_columns = [
        column
        for column in volatility_columns
        if column in volatility.columns
    ]


    vol = (
        volatility

        .select(
            volatility_columns
        )

        .rename({
            "calculated_at":
                "volatility_calculated_at",
        })
    )


    combined = (
        combined

        .join(
            vol,
            on="symbol",
            how="left",
        )
    )


    # ========================================================
    # DERIVATIVES
    # ========================================================

    derivatives_columns = [
        "symbol",

        "total_open_interest",

        # Legacy aggregate OI change.
        # Retained only for diagnostics.
        "open_interest_change_1h",
        "open_interest_change_4h",
        "open_interest_change_24h",

        "oi_change_available_1h",
        "oi_change_available_4h",
        "oi_change_available_24h",

        "oi_market_coverage_change_1h",
        "oi_venue_coverage_change_1h",

        # Production common-universe OI.
        "open_interest_change_common_1h",
        "open_interest_change_common_4h",
        "open_interest_change_common_24h",

        "common_oi_change_available_1h",
        "common_oi_change_available_4h",
        "common_oi_change_available_24h",

        "common_market_count_1h",
        "common_market_count_4h",
        "common_market_count_24h",

        "common_venue_count_1h",
        "common_venue_count_4h",
        "common_venue_count_24h",

        "common_oi_share_current_1h",
        "common_oi_share_current_4h",
        "common_oi_share_current_24h",

        "common_oi_share_reference_1h",
        "common_oi_share_reference_4h",
        "common_oi_share_reference_24h",

        "common_oi_overlap_min_share_1h",
        "common_oi_overlap_min_share_4h",
        "common_oi_overlap_min_share_24h",

        "common_oi_reference_time_1h",
        "common_oi_reference_time_4h",
        "common_oi_reference_time_24h",

        "common_oi_reference_offset_minutes_1h",
        "common_oi_reference_offset_minutes_4h",
        "common_oi_reference_offset_minutes_24h",

        "median_funding_rate",
        "funding_iqr",
        "funding_market_count",

        "median_index_basis",
        "basis_iqr",
        "basis_market_count",

        "oi_hhi",
        "oi_top_venue_share",

        "clean_oi_market_count",
        "clean_oi_venues",

        "calculated_at",
    ]


    derivatives_columns = [
        column
        for column in derivatives_columns
        if column in derivatives.columns
    ]


    deriv = (
        derivatives

        .select(
            derivatives_columns
        )

        .rename({
            "calculated_at":
                "derivatives_calculated_at",
        })
    )


    combined = (
        combined

        .join(
            deriv,
            on="symbol",
            how="left",
        )
    )


    # ========================================================
    # FUNDING CALIBRATION
    # ========================================================

    funding_columns = [
        "symbol",

        "funding_cross_percentile",

        "funding_cross_directional_tail_percentile",
        "funding_cross_magnitude_percentile",
        "funding_cross_confirmed_tail_percentile",

        "funding_history_percentile",

        "funding_history_directional_tail_percentile",
        "funding_history_magnitude_percentile",
        "funding_history_confirmed_tail_percentile",

        "funding_confirmed_tail_percentile",

        "funding_history_observations",
        "funding_history_distinct_values",
        "funding_history_span_hours",
        "funding_history_available",

        "funding_history_median",
        "funding_history_p25",
        "funding_history_p75",
        "funding_history_iqr",
        "funding_history_mad",

        "funding_robust_z",

        "funding_crowding_state",

        "funding_calculated_at",
    ]


    funding_columns = [
        column
        for column in funding_columns
        if column in funding.columns
    ]


    funding_features = (
        funding

        .select(
            funding_columns
        )
    )


    combined = (
        combined

        .join(
            funding_features,
            on="symbol",
            how="left",
        )
    )


    # ========================================================
    # LIQUIDATIONS
    # ========================================================

    liquidation_columns = [
        "symbol",

        "total_liquidations_1h",
        "total_liquidations_4h",
        "total_liquidations_24h",

        "long_liquidation_share_1h",
        "short_liquidation_share_1h",
        "liquidation_imbalance_1h",

        "liquidation_percentile_1h",
        "liquidation_percentile_4h",
        "liquidation_percentile_24h",

        "liquidation_ratio_to_median_1h",

        "liquidations_to_oi_1h",
        "liquidations_to_oi_4h",
        "liquidations_to_oi_24h",

        "collected_at",
    ]


    liquidation_columns = [
        column
        for column in liquidation_columns
        if column in liquidations.columns
    ]


    liq = (
        liquidations

        .select(
            liquidation_columns
        )

        .rename({
            "collected_at":
                "liquidations_calculated_at",
        })
    )


    combined = (
        combined

        .join(
            liq,
            on="symbol",
            how="left",
        )
    )


    return combined


# ============================================================
# SOURCE TIMING
# ============================================================


def source_timing(
    row: dict,
) -> tuple[
    datetime | None,
    datetime | None,
    float | None,
    bool,
]:
    """
    Calculate timing diagnostics across the five processed
    state inputs:

        spot
        volatility
        derivatives
        funding
        liquidations

    Returns:
        oldest source timestamp
        newest source timestamp
        total skew in seconds
        whether inputs are synchronised
    """

    timestamps = []


    for column in [
        "spot_calculated_at",
        "volatility_calculated_at",
        "derivatives_calculated_at",
        "funding_calculated_at",
        "liquidations_calculated_at",
    ]:

        value = row.get(
            column
        )


        if isinstance(
            value,
            datetime,
        ):

            timestamps.append(
                value
            )


    if not timestamps:

        return (
            None,
            None,
            None,
            False,
        )


    oldest = min(
        timestamps
    )


    newest = max(
        timestamps
    )


    skew_seconds = (
        newest
        - oldest
    ).total_seconds()


    synchronised = (
        len(timestamps) == 5
        and
        skew_seconds
        <= MAX_SOURCE_SKEW_SECONDS
    )


    return (
        oldest,
        newest,
        skew_seconds,
        synchronised,
    )


# ============================================================
# COMMON-UNIVERSE OI HELPERS
# ============================================================


def _oi_change_1h(
    row: dict,
) -> float | None:

    if (
        row.get(
            "common_oi_change_available_1h"
        )
        is not True
    ):

        return None


    value = row.get(
        "open_interest_change_common_1h"
    )


    if not _finite(value):

        return None


    return float(
        value
    )


def oi_change_quality(
    row: dict,
) -> str:

    if (
        row.get(
            "common_oi_change_available_1h"
        )
        is not True
    ):

        return (
            "COMMON HISTORY BUILDING"
        )


    overlap = row.get(
        "common_oi_overlap_min_share_1h"
    )


    if not _finite(overlap):

        return "UNVERIFIED"


    return "COMMON UNIVERSE"


# ============================================================
# PRIMITIVE MARKET STATES
# ============================================================


def price_state(
    row: dict,
) -> str:

    return _direction(
        row.get(
            "price_change_1h"
        ),
        positive="UP",
        negative="DOWN",
    )


def oi_state(
    row: dict,
) -> str:

    value = _oi_change_1h(
        row
    )


    if value is None:

        return "UNAVAILABLE"


    if value > 0:

        return "BUILDING"


    if value < 0:

        return "CONTRACTING"


    return "FLAT"


def volatility_state(
    row: dict,
) -> str:

    ratio = row.get(
        "vol_ratio_1h_vs_24h"
    )


    if not _finite(ratio):

        return "UNAVAILABLE"


    if ratio > 1:

        return "EXPANDING"


    if ratio < 1:

        return "CONTRACTING"


    return "NEUTRAL"


def funding_state(
    row: dict,
) -> str:

    funding = row.get(
        "median_funding_rate"
    )


    return _direction(
        funding,
        positive="POSITIVE",
        negative="NEGATIVE",
        flat="NEUTRAL",
    )


def basis_state(
    row: dict,
) -> str:

    basis = row.get(
        "median_index_basis"
    )


    return _direction(
        basis,
        positive="PREMIUM",
        negative="DISCOUNT",
        flat="FLAT",
    )


def liquidation_state(
    row: dict,
) -> str:

    percentile = row.get(
        "liquidation_confirmed_percentile_1h"
    )


    long_share = row.get(
        "long_liquidation_share_1h"
    )


    if not _finite(percentile):

        return "UNAVAILABLE"


    if (
        percentile
        < LIQUIDATION_ELEVATED_PERCENTILE
    ):

        return "NORMAL"


    intensity = (
        "EXTREME"
        if percentile
        >= LIQUIDATION_EXTREME_PERCENTILE
        else "ELEVATED"
    )


    if not _finite(long_share):

        return (
            f"{intensity} MIXED"
        )


    if (
        long_share
        >= LIQUIDATION_DIRECTION_SHARE
    ):

        return (
            f"{intensity} LONG"
        )


    if (
        long_share
        <= (
            1
            - LIQUIDATION_DIRECTION_SHARE
        )
    ):

        return (
            f"{intensity} SHORT"
        )


    return (
        f"{intensity} MIXED"
    )


# ============================================================
# LEVERAGE STATE
# ============================================================


def leverage_state(
    row: dict,
) -> str:

    oi_change = _oi_change_1h(
        row
    )


    if oi_change is None:

        return (
            "COMMON OI HISTORY BUILDING"
        )


    price_change = row.get(
        "price_change_1h"
    )


    if not _finite(
        price_change
    ):

        return "UNAVAILABLE"


    if oi_change < 0:

        return "DELEVERAGING"


    if oi_change == 0:

        return "OI FLAT"


    if price_change > 0:

        return (
            "OI BUILD INTO RALLY"
        )


    if price_change < 0:

        return (
            "OI BUILD INTO SELLOFF"
        )


    return "OI BUILD"


# ============================================================
# PRIMARY MARKET STATE
# ============================================================


def primary_state(
    row: dict,
) -> str:
    """
    Primary state intentionally does not yet use historical
    funding crowding.

    funding_crowding_state remains HISTORY BUILDING until the
    funding-history gate is satisfied.

    This avoids allowing an immature historical distribution
    to influence the market-state classification.
    """

    oi = oi_state(
        row
    )


    liq = liquidation_state(
        row
    )


    leverage = leverage_state(
        row
    )


    vol = volatility_state(
        row
    )


    # ========================================================
    # OI CONTRACTION + LIQUIDATION STRESS
    # ========================================================

    if oi == "CONTRACTING":

        if (
            "LONG" in liq
            and (
                "ELEVATED" in liq
                or
                "EXTREME" in liq
            )
        ):

            return (
                "LONG LIQUIDATION STRESS"
            )


        if (
            "SHORT" in liq
            and (
                "ELEVATED" in liq
                or
                "EXTREME" in liq
            )
        ):

            return (
                "SHORT LIQUIDATION STRESS"
            )


        if (
            "ELEVATED" in liq
            or
            "EXTREME" in liq
        ):

            return (
                "FORCED DELEVERAGING"
            )


        return "DELEVERAGING"


    # ========================================================
    # OI BUILD
    # ========================================================

    if oi == "BUILDING":

        return leverage


    # ========================================================
    # COMMON OI HISTORY NOT READY
    # ========================================================

    if (
        "EXTREME LONG"
        in liq
    ):

        return (
            "LONG LIQUIDATION PRESSURE"
        )


    if (
        "EXTREME SHORT"
        in liq
    ):

        return (
            "SHORT LIQUIDATION PRESSURE"
        )


    # ========================================================
    # VOLATILITY-ONLY PARTIAL STATE
    # ========================================================

    if vol == "EXPANDING":

        return (
            "VOLATILITY EXPANSION"
        )


    return "NORMAL / MIXED"


# ============================================================
# EXPLAINABILITY
# ============================================================


def state_evidence(
    row: dict,
) -> str:

    oi_change = _oi_change_1h(
        row
    )


    price_change = row.get(
        "price_change_1h"
    )


    funding = row.get(
        "median_funding_rate"
    )


    funding_cross_confirmed = (
        row.get(
            "funding_cross_confirmed_tail_percentile"
        )
    )


    funding_history_available = (
        row.get(
            "funding_history_available"
        )
        is True
    )


    funding_crowding = row.get(
        "funding_crowding_state"
    )


    liq_percentile = row.get(
        "liquidation_percentile_1h"
    )


    long_share = row.get(
        "long_liquidation_share_1h"
    )


    vol_ratio = row.get(
        "vol_ratio_1h_vs_24h"
    )


    liq_oi_percentile = row.get(
        "liquidations_to_oi_percentile_1h"
    )


    confirmed_liq_percentile = row.get(
        "liquidation_confirmed_percentile_1h"
    )


    oi_magnitude_percentile = row.get(
        "oi_change_magnitude_percentile_1h"
    )


    liq_text = (
        _format_percentile(
            liq_percentile
        )
    )


    liq_oi_text = (
        _format_percentile(
            liq_oi_percentile
        )
    )


    confirmed_liq_text = (
        _format_percentile(
            confirmed_liq_percentile
        )
    )


    oi_strength_text = (
        _format_percentile(
            oi_magnitude_percentile
        )
    )


    funding_cross_text = (
        _format_percentile(
            funding_cross_confirmed
        )
    )


    if _finite(
        long_share
    ):

        direction_text = (
            f"{long_share * 100:.0f}% LONG"
        )

    else:

        direction_text = "NA"


    if funding_history_available:

        funding_history_text = (
            funding_crowding
            if isinstance(
                funding_crowding,
                str,
            )
            else "UNAVAILABLE"
        )

    else:

        funding_history_text = (
            "HISTORY BUILDING"
        )


    coverage = (
        oi_change_quality(
            row
        )
    )


    return (
        f"PRICE {_format_percent(price_change)}"

        f" | OI {_format_percent(oi_change)}"
        f" [{oi_strength_text}]"

        f" | FUND {_format_rate(funding)}"
        f" [{funding_cross_text} CROSS"
        f" / {funding_history_text}]"

        f" | LIQ {liq_text} HIST"
        f" / {liq_oi_text} OI"
        f" / {confirmed_liq_text} CONF"
        f" ({direction_text})"

        f" | VOL RATIO {_format_number(vol_ratio)}"

        f" | OI QUALITY {coverage}"
    )


# ============================================================
# COMPLETE STATE SNAPSHOT
# ============================================================


def build_state_snapshot(
    spot: pl.DataFrame,
    volatility: pl.DataFrame,
    derivatives: pl.DataFrame,
    funding: pl.DataFrame,
    liquidations: pl.DataFrame,
) -> pl.DataFrame:

    combined = join_state_inputs(
        spot=spot,
        volatility=volatility,
        derivatives=derivatives,
        funding=funding,
        liquidations=liquidations,
    )


    if combined.is_empty():

        return combined


    combined = (
        add_cross_sectional_features(
            combined
        )
    )


    generated_at = datetime.now(
        timezone.utc
    )


    output = []


    for row in combined.to_dicts():

        (
            source_start_at,
            source_at,
            source_skew_seconds,
            inputs_synchronised,
        ) = source_timing(
            row
        )


        row[
            "state_source_start_at"
        ] = source_start_at


        row[
            "state_source_at"
        ] = source_at


        row[
            "state_source_skew_seconds"
        ] = source_skew_seconds


        row[
            "inputs_synchronised"
        ] = inputs_synchronised


        row[
            "state_generated_at"
        ] = generated_at


        # ====================================================
        # COMPONENT STATES
        # ====================================================

        row[
            "price_state_1h"
        ] = price_state(
            row
        )


        row[
            "oi_state_1h"
        ] = oi_state(
            row
        )


        row[
            "volatility_state"
        ] = volatility_state(
            row
        )


        row[
            "funding_state"
        ] = funding_state(
            row
        )


        row[
            "basis_state"
        ] = basis_state(
            row
        )


        row[
            "liquidation_state"
        ] = liquidation_state(
            row
        )


        row[
            "oi_change_quality_1h"
        ] = oi_change_quality(
            row
        )


        row[
            "leverage_state"
        ] = leverage_state(
            row
        )


        row[
            "primary_state"
        ] = primary_state(
            row
        )


        # ====================================================
        # READINESS
        # ====================================================

        row[
            "state_ready_1h"
        ] = (
            row.get(
                "price_change_available_1h"
            )
            is True
            and
            row.get(
                "common_oi_change_available_1h"
            )
            is True
            and
            inputs_synchronised
        )


        # ====================================================
        # STATE QUALITY
        # ====================================================

        row[
            "state_quality"
        ] = (
            "HIGH QUALITY"
            if (
                row[
                    "state_ready_1h"
                ]
                and
                row.get(
                    "oi_change_quality_1h"
                )
                == "COMMON UNIVERSE"
                and
                _finite(
                    row.get(
                        "common_oi_overlap_min_share_1h"
                    )
                )
            )
            else (
                "INCOMPLETE"
                if not row[
                    "state_ready_1h"
                ]
                else "UNVERIFIED"
            )
        )


        # ====================================================
        # EXPLAINABILITY
        # ====================================================

        row[
            "state_evidence"
        ] = state_evidence(
            row
        )


        # ====================================================
        # CANONICAL STATE TIME
        # ====================================================

        row[
            "state_calculated_at"
        ] = (
            source_at
            if source_at is not None
            else generated_at
        )


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