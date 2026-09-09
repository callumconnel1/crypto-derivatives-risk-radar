import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

BACKEND_DIR = (
    PROJECT_ROOT / "backend"
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.append(
        str(BACKEND_DIR)
    )


from risk_radar.volatility import (
    fit_symmetric_power_law,
    prepare_5m_prices,
    tune_ewma_lambda,
)


# ============================================================
# PATHS
# ============================================================

SOURCE_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility_5m"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "model_params.parquet"
)


# ============================================================
# LOAD ALL ASSETS
# ============================================================

files = sorted(
    SOURCE_DIR.glob(
        "*.parquet"
    )
)

if not files:
    raise RuntimeError(
        f"No volatility data found in {SOURCE_DIR}"
    )


frames = [
    pl.read_parquet(file)
    for file in files
]

prices = pl.concat(
    frames,
    how="diagonal_relaxed",
)

prices = prepare_5m_prices(
    prices
)


# ============================================================
# FIT
# ============================================================

rows = []

symbols = (
    prices["symbol"]
    .unique()
    .sort()
    .to_list()
)


for i, symbol in enumerate(
    symbols,
    start=1,
):

    print(
        f"[{i:02d}/{len(symbols)}] "
        f"Fitting {symbol}..."
    )

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

    returns = (
        asset_df[
            "log_return"
        ]
        .to_numpy()
    )

    if len(returns) < 1000:

        print(
            f"    skipping: "
            f"only {len(returns)} returns"
        )

        continue


    # ========================================================
    # PRIMARY MODEL
    # ========================================================

    power_result, power_params = (
        fit_symmetric_power_law(
            returns
        )
    )

    (
        c,
        beta,
        alpha,
        nu,
    ) = power_params


    # ========================================================
    # SECONDARY MODEL
    # ========================================================

    ewma_lambda = (
        tune_ewma_lambda(
            returns
        )
    )


    print(
        f"    "
        f"alpha={alpha:.4f} "
        f"beta={beta:.4f} "
        f"nu={nu:.3f} "
        f"lambda={ewma_lambda:.4f}"
    )


    rows.append({
        "symbol":
            symbol,

        "c":
            c,

        "beta":
            beta,

        "alpha":
            alpha,

        "nu":
            nu,

        "ewma_lambda":
            ewma_lambda,

        "power_law_fit_success":
            power_result.success,

        "power_law_nll":
            power_result.fun,

        "fitted_at":
            datetime.now(
                UTC
            ),
    })


# ============================================================
# SAVE
# ============================================================

params_df = pl.DataFrame(
    rows
)

params_df.write_parquet(
    OUTPUT_PATH,
    compression="zstd",
)

print(
    f"\nSaved model parameters:"
    f"\n{OUTPUT_PATH}"
)

print(
    f"\nAssets fitted: "
    f"{params_df.height}"
)

print(
    params_df.select([
        "symbol",
        "alpha",
        "beta",
        "nu",
        "ewma_lambda",
    ])
)