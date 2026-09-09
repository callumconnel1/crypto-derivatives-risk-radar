from __future__ import annotations

import numpy as np
import polars as pl

from scipy.optimize import minimize
from scipy.stats import t as student_t


# ============================================================
# CONSTANTS
# ============================================================

PERIODS_PER_YEAR_5M = 365 * 24 * 12
PERIODS_PER_YEAR_1H = 365 * 24

FORWARD_WINDOW = 12

K = 250
WARMUP = 288


# ============================================================
# BASIC RETURNS / REALIZED VOLATILITY
# ============================================================

def prepare_5m_prices(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:

    required = {
        "timestamp",
        "symbol",
        "price",
    }

    missing = (
        required
        - set(dataframe.columns)
    )

    if missing:

        raise ValueError(
            f"Missing required columns: {missing}"
        )


    dataframe = (
        dataframe
        .sort([
            "symbol",
            "timestamp",
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


    # ========================================================
    # DETECT DISCONTINUITIES
    # ========================================================

    dataframe = dataframe.with_columns(
        pl.col("timestamp")
        .diff()
        .over("symbol")
        .alias("_time_gap")
    )


    # New continuous segment whenever observations are
    # separated by more than 10 minutes.
    dataframe = dataframe.with_columns(
        (
            pl.col("_time_gap")
            > pl.duration(
                minutes=10
            )
        )
        .fill_null(False)
        .cast(pl.Int64)
        .cum_sum()
        .over("symbol")
        .alias("_segment")
    )


    # ========================================================
    # RETURNS
    #
    # Crucially calculated WITHIN continuous segments only.
    # ========================================================

    dataframe = dataframe.with_columns(
        (
            pl.col("price")
            / pl.col("price")
            .shift(1)
        )
        .log()
        .over([
            "symbol",
            "_segment",
        ])
        .alias("log_return")
    )


    dataframe = dataframe.with_columns(
        pl.col("log_return")
        .pow(2)
        .alias("squared_return")
    )


    return dataframe.drop(
        "_time_gap"
    )


def add_realized_volatility(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:

    windows = {
        "1h": 12,
        "4h": 48,
        "24h": 288,
    }

    expressions = []

    for name, window in windows.items():

        expression = (
            (
                pl.col("squared_return")
                .rolling_sum(
                    window_size=window,
                    min_samples=window,
                )
                .over([
                    "symbol",
                    "_segment",
                ])
                * (
                    PERIODS_PER_YEAR_5M
                    / window
                )
            )
            .sqrt()
            .alias(
                f"realized_vol_{name}"
            )
        )

        expressions.append(
            expression
        )

    dataframe = dataframe.with_columns(
        expressions
    )

    dataframe = dataframe.with_columns(

        (
            pl.col("realized_vol_1h")
            / pl.col("realized_vol_24h")
        )
        .alias(
            "vol_ratio_1h_vs_24h"
        ),

        (
            pl.col("realized_vol_4h")
            / pl.col("realized_vol_24h")
        )
        .alias(
            "vol_ratio_4h_vs_24h"
        ),
    )

    return dataframe.drop(
        "_segment"
    )


# ============================================================
# REALIZED-VOL PERCENTILE
# ============================================================

def latest_vol_percentiles(
    dataframe: pl.DataFrame,
    lookback_days: int = 7,
) -> dict[str, float]:

    """
    Compare latest 24h RV against hourly sampled 24h RV history.

    Returns:
        {
            "BTC": 0.42,
            "ETH": 0.71,
            ...
        }
    """

    hourly = (
        dataframe
        .drop_nulls(
            "realized_vol_24h"
        )
        .sort([
            "symbol",
            "timestamp",
        ])
        .group_by_dynamic(
            "timestamp",
            every="1h",
            group_by="symbol",
        )
        .agg(
            pl.col(
                "realized_vol_24h"
            ).last()
        )
    )

    result = {}

    lookback_hours = (
        lookback_days * 24
    )

    for symbol in (
        hourly["symbol"]
        .unique()
        .to_list()
    ):

        history = (
            hourly
            .filter(
                pl.col("symbol")
                == symbol
            )
            .sort("timestamp")
        )

        values = history[
            "realized_vol_24h"
        ].to_numpy()

        values = values[
            np.isfinite(values)
        ]

        if len(values) == 0:
            result[symbol] = np.nan
            continue

        values = values[
            -lookback_hours:
        ]

        current = values[-1]

        percentile = np.mean(
            values <= current
        )

        result[symbol] = float(
            percentile
        )

    return result


# ============================================================
# TARGET
# ============================================================

def forward_realized_variance(
    returns: np.ndarray,
    window: int = 12,
) -> np.ndarray:

    squared_returns = (
        returns ** 2
    )

    target = np.full(
        len(returns),
        np.nan,
    )

    for t in range(
        len(returns) - window
    ):

        target[t] = (
            squared_returns[
                t + 1:
                t + 1 + window
            ]
            .sum()
        )

    return target


# ============================================================
# EWMA
# ============================================================

def ewma_variance(
    returns: np.ndarray,
    lam: float,
    warmup: int = WARMUP,
) -> np.ndarray:

    variance = np.full(
        len(returns),
        np.nan,
    )

    if len(returns) <= warmup:
        return variance

    variance[warmup] = np.var(
        returns[:warmup]
    )

    for t in range(
        warmup + 1,
        len(returns),
    ):

        variance[t] = (
            lam
            * variance[t - 1]
            + (1 - lam)
            * returns[t - 1] ** 2
        )

    return variance


def tune_ewma_lambda(
    returns: np.ndarray,
    lambda_grid: np.ndarray | None = None,
    forward_window: int = FORWARD_WINDOW,
    warmup: int = WARMUP,
) -> float:

    if lambda_grid is None:

        lambda_grid = np.arange(
            0.97,
            0.9996,
            0.0005,
        )

    target = forward_realized_variance(
        returns,
        window=forward_window,
    )

    train_end = (
        len(returns)
        - forward_window
    )

    best_lambda = None
    best_mse = np.inf

    for lam in lambda_grid:

        variance = ewma_variance(
            returns,
            lam,
            warmup=warmup,
        )

        forecast = (
            variance
            * forward_window
        )

        indices = np.arange(
            warmup,
            train_end,
        )

        valid = (
            np.isfinite(
                target[indices]
            )
            & np.isfinite(
                forecast[indices]
            )
        )

        if not valid.any():
            continue

        y = target[
            indices
        ][valid]

        yhat = forecast[
            indices
        ][valid]

        mse = np.mean(
            (y - yhat) ** 2
        )

        if mse < best_mse:

            best_mse = mse
            best_lambda = float(
                lam
            )

    if best_lambda is None:
        raise RuntimeError(
            "Could not fit EWMA lambda"
        )

    return best_lambda


def latest_ewma_1h_forecast(
    returns: np.ndarray,
    lam: float,
) -> float:

    variance = ewma_variance(
        returns,
        lam,
    )

    finite = variance[
        np.isfinite(variance)
    ]

    if len(finite) == 0:
        return np.nan

    next_5m_variance = (
        finite[-1]
    )

    return float(
        next_5m_variance
        * FORWARD_WINDOW
    )


# ============================================================
# SYMMETRIC POWER-LAW MEMORY MODEL
# ============================================================

def symmetric_power_law_memory(
    returns: np.ndarray,
    alpha: float,
    K: int = K,
) -> np.ndarray:

    squared_returns = (
        returns ** 2
    )

    weights = (
        np.arange(
            1,
            K + 1,
        )
        ** (-alpha)
    )

    memory = np.convolve(
        squared_returns,
        weights,
        mode="full",
    )[:len(returns)]

    return memory


def unpack_symmetric_params(
    theta: np.ndarray,
):

    c = np.exp(
        theta[0]
    )

    beta = np.exp(
        theta[1]
    )

    alpha = np.exp(
        theta[2]
    )

    nu = (
        2
        + np.exp(
            theta[3]
        )
    )

    return (
        c,
        beta,
        alpha,
        nu,
    )


def symmetric_power_law_nll(
    theta: np.ndarray,
    returns_pct: np.ndarray,
    K: int = K,
) -> float:

    (
        c,
        beta,
        alpha,
        nu,
    ) = unpack_symmetric_params(
        theta
    )

    if (
        alpha > 5
        or nu > 100
    ):
        return 1e20

    memory = symmetric_power_law_memory(
        returns_pct,
        alpha,
        K,
    )

    sigma2 = np.full(
        len(returns_pct),
        np.nan,
    )

    sigma2[1:] = (
        c
        + beta
        * memory[:-1]
    )

    valid = (
        np.arange(
            len(returns_pct)
        )
        >= K
    )

    valid &= (
        np.isfinite(sigma2)
        & (sigma2 > 0)
    )

    r = returns_pct[
        valid
    ]

    variance = sigma2[
        valid
    ]

    sigma = np.sqrt(
        variance
    )

    # Standardized Student-t
    scale = np.sqrt(
        (nu - 2)
        / nu
    )

    z = (
        r / sigma
    )

    log_density = (
        student_t.logpdf(
            z / scale,
            df=nu,
        )
        - np.log(scale)
        - np.log(sigma)
    )

    if not np.all(
        np.isfinite(
            log_density
        )
    ):
        return 1e20

    return float(
        -np.sum(
            log_density
        )
    )


def fit_symmetric_power_law(
    returns: np.ndarray,
    K: int = K,
):

    returns_pct = (
        returns * 100
    )

    variance = np.var(
        returns_pct
    )

    initial_alpha = 1.2

    memory = symmetric_power_law_memory(
        returns_pct,
        initial_alpha,
        K,
    )

    mean_memory = np.mean(
        memory[K:]
    )

    c0 = max(
        variance * 0.05,
        1e-8,
    )

    beta0 = max(
        variance
        * 0.95
        / mean_memory,
        1e-8,
    )

    theta0 = np.array([
        np.log(c0),
        np.log(beta0),
        np.log(initial_alpha),
        np.log(6.0 - 2.0),
    ])

    result = minimize(
        symmetric_power_law_nll,
        theta0,
        args=(
            returns_pct,
            K,
        ),
        method="L-BFGS-B",
        options={
            "maxiter": 3000,
            "ftol": 1e-11,
        },
    )

    params = unpack_symmetric_params(
        result.x
    )

    return (
        result,
        params,
    )


# ============================================================
# POWER-LAW MULTI-STEP FORECAST
# ============================================================

def symmetric_power_law_1h_forecast_at_origin(
    returns_pct: np.ndarray,
    origin: int,
    params,
    K: int = K,
    horizon: int = FORWARD_WINDOW,
) -> float:

    (
        c,
        beta,
        alpha,
        nu,
    ) = params

    future_variances = []

    historical = (
        returns_pct[
            max(
                0,
                origin - K + 1,
            ):
            origin + 1
        ][::-1]
    )

    for h in range(
        1,
        horizon + 1,
    ):

        max_observed = min(
            len(historical),
            K - h + 1,
        )

        observed_returns = (
            historical[
                :max_observed
            ]
        )

        observed_lags = np.arange(
            h,
            h + max_observed,
        )

        observed_weights = (
            observed_lags
            ** (-alpha)
        )

        historical_memory = np.sum(
            (
                observed_returns ** 2
            )
            * observed_weights
        )

        future_memory = 0.0

        for j in range(
            1,
            h,
        ):

            lag = (
                h - j
            )

            if lag > K:
                continue

            weight = (
                lag ** (-alpha)
            )

            future_memory += (
                future_variances[
                    j - 1
                ]
                * weight
            )

        expected_memory = (
            historical_memory
            + future_memory
        )

        sigma2 = (
            c
            + beta
            * expected_memory
        )

        future_variances.append(
            sigma2
        )

    return float(
        np.sum(
            future_variances
        )
    )


def latest_power_law_1h_forecast(
    returns: np.ndarray,
    params,
    K: int = K,
) -> float:

    returns_pct = (
        returns * 100
    )

    origin = (
        len(returns_pct) - 1
    )

    forecast_pct2 = (
        symmetric_power_law_1h_forecast_at_origin(
            returns_pct=returns_pct,
            origin=origin,
            params=params,
            K=K,
            horizon=FORWARD_WINDOW,
        )
    )

    return float(
        forecast_pct2
        / 100**2
    )


# ============================================================
# VARIANCE -> ANNUALISED VOL
# ============================================================

def annualise_1h_variance(
    variance_1h: float,
) -> float:

    if (
        variance_1h is None
        or not np.isfinite(
            variance_1h
        )
        or variance_1h < 0
    ):
        return np.nan

    return float(
        np.sqrt(
            variance_1h
            * PERIODS_PER_YEAR_1H
        )
    )


# ============================================================
# LATEST SNAPSHOT
# ============================================================

def build_latest_volatility_snapshot(
    prices: pl.DataFrame,
    model_params: pl.DataFrame,
    percentile_lookback_days: int = 7,
) -> pl.DataFrame:

    prices = prepare_5m_prices(
        prices
    )

    prices = add_realized_volatility(
        prices
    )

    percentiles = latest_vol_percentiles(
        prices,
        lookback_days=percentile_lookback_days,
    )

    rows = []

    symbols = (
        prices[
            "symbol"
        ]
        .unique()
        .sort()
        .to_list()
    )

    for symbol in symbols:

        asset_df = (
            prices
            .filter(
                pl.col("symbol")
                == symbol
            )
            .sort("timestamp")
            .drop_nulls(
                "log_return"
            )
        )

        if (
            asset_df.height
            < max(
                WARMUP,
                K,
            )
        ):
            continue

        params_row = (
            model_params
            .filter(
                pl.col("symbol")
                == symbol
            )
        )

        if params_row.is_empty():
            continue

        returns = (
            asset_df[
                "log_return"
            ]
            .to_numpy()
        )

        latest = (
            asset_df
            .drop_nulls(
                "realized_vol_24h"
            )
            .tail(1)
        )

        if latest.is_empty():
            continue

        c = params_row[
            "c"
        ][0]

        beta = params_row[
            "beta"
        ][0]

        alpha = params_row[
            "alpha"
        ][0]

        nu = params_row[
            "nu"
        ][0]

        ewma_lambda = params_row[
            "ewma_lambda"
        ][0]

        power_params = (
            c,
            beta,
            alpha,
            nu,
        )

        power_var_1h = (
            latest_power_law_1h_forecast(
                returns,
                power_params,
            )
        )

        ewma_var_1h = (
            latest_ewma_1h_forecast(
                returns,
                ewma_lambda,
            )
        )

        power_vol = (
            annualise_1h_variance(
                power_var_1h
            )
        )

        ewma_vol = (
            annualise_1h_variance(
                ewma_var_1h
            )
        )

        if (
            np.isfinite(ewma_vol)
            and ewma_vol > 0
        ):

            disagreement = (
                power_vol
                - ewma_vol
            ) / ewma_vol

        else:
            disagreement = np.nan

        latest_row = (
            latest
            .to_dicts()[0]
        )

        rows.append({
            "timestamp":
                latest_row[
                    "timestamp"
                ],

            "asset":
                latest_row.get(
                    "asset"
                ),

            "symbol":
                symbol,

            "price":
                latest_row[
                    "price"
                ],

            # ----------------------------------------
            # REALIZED VOL
            # ----------------------------------------

            "realized_vol_1h":
                latest_row[
                    "realized_vol_1h"
                ],

            "realized_vol_4h":
                latest_row[
                    "realized_vol_4h"
                ],

            "realized_vol_24h":
                latest_row[
                    "realized_vol_24h"
                ],

            "vol_ratio_1h_vs_24h":
                latest_row[
                    "vol_ratio_1h_vs_24h"
                ],

            "vol_ratio_4h_vs_24h":
                latest_row[
                    "vol_ratio_4h_vs_24h"
                ],

            "vol_percentile_24h":
                percentiles.get(
                    symbol,
                    np.nan,
                ),

            # ----------------------------------------
            # PRIMARY MODEL
            # ----------------------------------------

            "power_law_var_forecast_1h":
                power_var_1h,

            "power_law_vol_forecast":
                power_vol,

            # ----------------------------------------
            # SECONDARY MODEL
            # ----------------------------------------

            "ewma_var_forecast_1h":
                ewma_var_1h,

            "ewma_vol_forecast":
                ewma_vol,

            # ----------------------------------------
            # MODEL AGREEMENT
            # ----------------------------------------

            "model_disagreement":
                disagreement,

            # ----------------------------------------
            # PARAMETERS
            # ----------------------------------------

            "power_law_alpha":
                alpha,

            "power_law_beta":
                beta,

            "power_law_nu":
                nu,

            "ewma_lambda":
                ewma_lambda,
        })

    if not rows:
        return pl.DataFrame()

    return (
        pl.DataFrame(
            rows
        )
        .sort("symbol")
    )