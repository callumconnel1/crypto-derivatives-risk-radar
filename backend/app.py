from pathlib import Path
import math

import polars as pl

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scripts.get_data import get_latest_quotes


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

VOLATILITY_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility"
    / "latest.parquet"
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Crypto Derivatives Risk Radar API",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.0.138:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DEFAULT MARKET UNIVERSE
# ============================================================

DEFAULT_IDS = [
    1,      # BTC
    1027,   # ETH
    5426,   # SOL
    52,     # XRP
    74,     # DOGE
]


# ============================================================
# HELPERS
# ============================================================

def clean_records(
    dataframe: pl.DataFrame,
) -> list[dict]:

    records = dataframe.to_dicts()

    cleaned = []

    for row in records:

        clean_row = {}

        for key, value in row.items():

            if (
                isinstance(value, float)
                and not math.isfinite(value)
            ):
                value = None

            clean_row[key] = value

        cleaned.append(clean_row)

    return cleaned


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "online",
        "service": "Crypto Derivatives Risk Radar API",
    }


# ============================================================
# LIVE SPOT MARKET
# ============================================================

@app.get("/api/market/latest")
def market_latest():

    try:

        dataframe = get_latest_quotes(
            ids=DEFAULT_IDS,
            convert="USD",
        )

        return {
            "data": clean_records(
                dataframe
            ),
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


# ============================================================
# VOLATILITY SNAPSHOT
# ============================================================

@app.get("/api/volatility/latest")
def volatility_latest():

    if not VOLATILITY_LATEST_PATH.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Volatility snapshot not found. "
                "Run scripts/update_volatility.py."
            ),
        )

    try:

        dataframe = pl.read_parquet(
            VOLATILITY_LATEST_PATH
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed reading volatility snapshot: "
                f"{error}"
            ),
        ) from error

    if dataframe.is_empty():

        return {
            "data": [],
        }

    return {
        "data": clean_records(
            dataframe
        ),
    }