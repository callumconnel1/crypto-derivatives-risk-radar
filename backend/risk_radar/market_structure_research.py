from __future__ import annotations

import math
from typing import Any

import polars as pl


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


def _clamp01(
    value: Any,
) -> float | None:
    if not _finite(
        value
    ):
        return None

    return max(
        0.0,
        min(
            1.0,
            float(
                value
            ),
        ),
    )


def _mean_available(
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


def _weighted_mean_available(
    values: list[
        tuple[
            Any,
            float,
        ]
    ],
) -> float | None:
    clean = [
        (
            float(
                value
            ),
            float(
                weight
            ),
        )
        for value, weight
        in values
        if (
            _finite(
                value
            )
            and
            _finite(
                weight
            )
            and
            float(
                weight
            ) > 0
        )
    ]

    if not clean:
        return None

    numerator = sum(
        value * weight
        for value, weight
        in clean
    )

    denominator = sum(
        weight
        for _, weight
        in clean
    )

    if denominator <= 0:
        return None

    return (
        numerator
        / denominator
    )


def _percentile_rank(
    values: list[Any],
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
        if not _finite(
            value
        ):
            continue

        valid.append(
            (
                index,
                float(
                    value
                ),
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

        value = (
            valid[
                position
            ][1]
        )

        while (
            end < count
            and
            valid[
                end
            ][1]
            == value
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


def _competition_rank(
    values: list[Any],
) -> list[int | None]:
    finite_values = sorted(
        [
            float(
                value
            )
            for value in values
            if _finite(
                value
            )
        ],
        reverse=True,
    )

    output: list[
        int | None
    ] = []

    for value in values:
        if not _finite(
            value
        ):
            output.append(
                None
            )

            continue

        numeric = float(
            value
        )

        output.append(
            1
            + sum(
                candidate
                > numeric
                for candidate
                in finite_values
            )
        )

    return output


# ============================================================
# BASIS SOURCE SELECTION
# ============================================================


def _basis_level_component(
    basis_row: dict,
) -> tuple[
    float | None,
    str,
]:
    """
    Use historical + cross confirmation only when the basis
    history gate is actually ready. Otherwise use the explicitly
    labelled cross-sectional warm-up percentile.
    """

    history_ready = (
        basis_row.get(
            "basis_history_available"
        )
        is True
    )

    confirmed = _clamp01(
        basis_row.get(
            "basis_confirmed_magnitude_percentile"
        )
    )

    warmup = _clamp01(
        basis_row.get(
            "basis_warmup_magnitude_percentile"
        )
    )

    if (
        history_ready
        and
        confirmed is not None
    ):
        return (
            confirmed,
            "HISTORICAL + CROSS CONFIRMED",
        )

    if warmup is not None:
        return (
            warmup,
            "CROSS-SECTIONAL WARMUP",
        )

    return (
        None,
        "UNAVAILABLE",
    )


def _basis_dispersion_component(
    basis_row: dict,
) -> tuple[
    float | None,
    str,
]:
    """
    Cross-venue basis dispersion is treated separately from
    central basis magnitude.
    """

    history_ready = (
        basis_row.get(
            "basis_dispersion_history_available"
        )
        is True
    )

    confirmed = _clamp01(
        basis_row.get(
            "basis_dispersion_confirmed_percentile"
        )
    )

    warmup = _clamp01(
        basis_row.get(
            "basis_dispersion_warmup_percentile"
        )
    )

    if (
        history_ready
        and
        confirmed is not None
    ):
        return (
            confirmed,
            "HISTORICAL + CROSS CONFIRMED",
        )

    if warmup is not None:
        return (
            warmup,
            "CROSS-SECTIONAL WARMUP",
        )

    return (
        None,
        "UNAVAILABLE",
    )


# ============================================================
# RESEARCH SNAPSHOT
# ============================================================


def build_market_structure_research(
    risk_latest: pl.DataFrame,
    basis_latest: pl.DataFrame,
) -> pl.DataFrame:
    """
    Research-only comparison of market-structure formulations.

    Production CDRR is NOT modified.

    Current production fifth factor:
        concentration only

    Candidate A:
        equal mean of
            OI concentration,
            basis magnitude,
            basis dispersion

    Candidate B:
        50% OI concentration
        25% basis magnitude
        25% basis dispersion

    Candidate risk scores are counterfactuals that replace only
    the existing 20% market-structure component while leaving the
    other four production components unchanged.
    """

    if risk_latest.is_empty():
        return risk_latest

    if basis_latest.is_empty():
        raise ValueError(
            "Basis snapshot is empty."
        )

    required_risk = [
        "symbol",
        "provisional_risk_score",
        "risk_rank",
        "volatility_component",
        "leverage_component",
        "funding_component",
        "liquidation_component",
        "market_structure_component",
        "oi_concentration_percentile",
    ]

    required_basis = [
        "symbol",
        "median_index_basis",
        "basis_iqr",
        "basis_history_available",
        "basis_dispersion_history_available",
        "basis_confirmed_magnitude_percentile",
        "basis_dispersion_confirmed_percentile",
        "basis_warmup_magnitude_percentile",
        "basis_dispersion_warmup_percentile",
    ]

    missing_risk = [
        column
        for column in required_risk
        if column not in risk_latest.columns
    ]

    missing_basis = [
        column
        for column in required_basis
        if column not in basis_latest.columns
    ]

    if missing_risk:
        raise ValueError(
            "Missing risk columns: "
            + ", ".join(
                missing_risk
            )
        )

    if missing_basis:
        raise ValueError(
            "Missing basis columns: "
            + ", ".join(
                missing_basis
            )
        )

    basis_by_symbol = {
        row[
            "symbol"
        ]: row
        for row
        in basis_latest.to_dicts()
    }

    output: list[
        dict
    ] = []

    for risk_row in risk_latest.to_dicts():
        symbol = risk_row[
            "symbol"
        ]

        basis_row = (
            basis_by_symbol.get(
                symbol
            )
        )

        if basis_row is None:
            basis_row = {}

        concentration = _clamp01(
            risk_row.get(
                "oi_concentration_percentile"
            )
        )

        (
            basis_level,
            basis_level_source,
        ) = _basis_level_component(
            basis_row
        )

        (
            basis_dispersion,
            basis_dispersion_source,
        ) = _basis_dispersion_component(
            basis_row
        )

        equal_three = _mean_available(
            [
                concentration,
                basis_level,
                basis_dispersion,
            ]
        )

        concentration_half = (
            _weighted_mean_available(
                [
                    (
                        concentration,
                        0.50,
                    ),
                    (
                        basis_level,
                        0.25,
                    ),
                    (
                        basis_dispersion,
                        0.25,
                    ),
                ]
            )
        )

        production_score = (
            risk_row.get(
                "provisional_risk_score"
            )
        )

        production_structure = (
            _clamp01(
                risk_row.get(
                    "market_structure_component"
                )
            )
        )

        if (
            _finite(
                production_score
            )
            and
            production_structure
            is not None
            and
            equal_three is not None
        ):
            candidate_score_equal_three = (
                float(
                    production_score
                )
                + 20.0
                * (
                    equal_three
                    - production_structure
                )
            )
        else:
            candidate_score_equal_three = None

        if (
            _finite(
                production_score
            )
            and
            production_structure
            is not None
            and
            concentration_half
            is not None
        ):
            candidate_score_concentration_half = (
                float(
                    production_score
                )
                + 20.0
                * (
                    concentration_half
                    - production_structure
                )
            )
        else:
            candidate_score_concentration_half = None

        output.append(
            {
                "symbol":
                    symbol,

                "asset":
                    risk_row.get(
                        "asset"
                    ),

                "primary_state":
                    risk_row.get(
                        "primary_state"
                    ),

                # --------------------------------------------
                # CURRENT PRODUCTION CONTEXT
                # --------------------------------------------
                "production_risk_rank":
                    risk_row.get(
                        "risk_rank"
                    ),

                "production_risk_score":
                    production_score,

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

                "production_market_structure_component":
                    production_structure,

                # --------------------------------------------
                # STRUCTURE CHANNELS
                # --------------------------------------------
                "oi_concentration_component":
                    concentration,

                "median_index_basis":
                    basis_row.get(
                        "median_index_basis"
                    ),

                "basis_level_component":
                    basis_level,

                "basis_level_source":
                    basis_level_source,

                "basis_iqr":
                    basis_row.get(
                        "basis_iqr"
                    ),

                "basis_dispersion_component":
                    basis_dispersion,

                "basis_dispersion_source":
                    basis_dispersion_source,

                "basis_calibration_ready":
                    basis_row.get(
                        "basis_calibration_ready"
                    ),

                # --------------------------------------------
                # CANDIDATE STRUCTURE FORMULATIONS
                # --------------------------------------------
                "candidate_structure_equal_three":
                    equal_three,

                "candidate_structure_concentration_half":
                    concentration_half,

                # --------------------------------------------
                # COUNTERFACTUAL RISK SCORES
                # --------------------------------------------
                "candidate_risk_score_equal_three":
                    candidate_score_equal_three,

                "candidate_risk_score_concentration_half":
                    candidate_score_concentration_half,

                "candidate_score_delta_equal_three":
                    (
                        candidate_score_equal_three
                        - float(
                            production_score
                        )
                        if (
                            _finite(
                                candidate_score_equal_three
                            )
                            and
                            _finite(
                                production_score
                            )
                        )
                        else None
                    ),

                "candidate_score_delta_concentration_half":
                    (
                        candidate_score_concentration_half
                        - float(
                            production_score
                        )
                        if (
                            _finite(
                                candidate_score_concentration_half
                            )
                            and
                            _finite(
                                production_score
                            )
                        )
                        else None
                    ),
            }
        )

    equal_three_scores = [
        row.get(
            "candidate_risk_score_equal_three"
        )
        for row in output
    ]

    concentration_half_scores = [
        row.get(
            "candidate_risk_score_concentration_half"
        )
        for row in output
    ]

    equal_three_ranks = (
        _competition_rank(
            equal_three_scores
        )
    )

    concentration_half_ranks = (
        _competition_rank(
            concentration_half_scores
        )
    )

    equal_three_percentiles = (
        _percentile_rank(
            equal_three_scores
        )
    )

    concentration_half_percentiles = (
        _percentile_rank(
            concentration_half_scores
        )
    )

    for index, row in enumerate(
        output
    ):
        row[
            "candidate_risk_rank_equal_three"
        ] = equal_three_ranks[
            index
        ]

        row[
            "candidate_risk_rank_concentration_half"
        ] = concentration_half_ranks[
            index
        ]

        row[
            "candidate_risk_percentile_equal_three"
        ] = equal_three_percentiles[
            index
        ]

        row[
            "candidate_risk_percentile_concentration_half"
        ] = concentration_half_percentiles[
            index
        ]

        production_rank = (
            row.get(
                "production_risk_rank"
            )
        )

        candidate_rank = (
            row.get(
                "candidate_risk_rank_equal_three"
            )
        )

        if (
            isinstance(
                production_rank,
                int,
            )
            and
            isinstance(
                candidate_rank,
                int,
            )
        ):
            row[
                "rank_change_equal_three"
            ] = (
                production_rank
                - candidate_rank
            )
        else:
            row[
                "rank_change_equal_three"
            ] = None

        candidate_rank = (
            row.get(
                "candidate_risk_rank_concentration_half"
            )
        )

        if (
            isinstance(
                production_rank,
                int,
            )
            and
            isinstance(
                candidate_rank,
                int,
            )
        ):
            row[
                "rank_change_concentration_half"
            ] = (
                production_rank
                - candidate_rank
            )
        else:
            row[
                "rank_change_concentration_half"
            ] = None

    return (
        pl.DataFrame(
            output,
            infer_schema_length=None,
        )
        .sort(
            "production_risk_rank"
        )
    )
