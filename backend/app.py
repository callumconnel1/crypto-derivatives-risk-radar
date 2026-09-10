from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


SPOT_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "spot"
    / "latest.parquet"
)


VOLATILITY_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "volatility"
    / "latest.parquet"
)


DERIVATIVES_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
    / "latest.parquet"
)


LIQUIDATIONS_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "liquidations"
    / "latest.parquet"
)


LIQUIDATIONS_GLOBAL_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "liquidations"
    / "global_latest.parquet"
)


LIQUIDATIONS_EXCHANGES_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "liquidations"
    / "exchanges_latest.parquet"
)


STATES_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "states"
    / "latest.parquet"
)


RISK_LATEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "risk"
    / "latest.parquet"
)


# ============================================================
# SNAPSHOT DEFINITIONS
# ============================================================

SNAPSHOTS = {
    "spot": {
        "path": SPOT_LATEST_PATH,
        "update_script": "scripts/update_spot.py",
    },

    "volatility": {
        "path": VOLATILITY_LATEST_PATH,
        "update_script": "scripts/update_volatility.py",
    },

    "derivatives": {
        "path": DERIVATIVES_LATEST_PATH,
        "update_script": "scripts/update_derivatives.py",
    },

    "liquidations": {
        "path": LIQUIDATIONS_LATEST_PATH,
        "update_script": "scripts/update_liquidations.py",
    },

    "liquidations_global": {
        "path": LIQUIDATIONS_GLOBAL_PATH,
        "update_script": "scripts/update_liquidations.py",
    },

    "liquidations_exchanges": {
        "path": LIQUIDATIONS_EXCHANGES_PATH,
        "update_script": "scripts/update_liquidations.py",
    },

    "states": {
        "path": STATES_LATEST_PATH,
        "update_script": "scripts/update_states.py",
    },

    "risk": {
        "path": RISK_LATEST_PATH,
        "update_script": "scripts/update_risk.py",
    },
}


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Crypto Derivatives Risk Radar API",
    version="0.2.0",
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
# JSON SAFETY
# ============================================================

def clean_value(
    value: Any,
) -> Any:
    """
    Convert values into JSON-safe objects.

    In particular:
        NaN  -> None
        +inf -> None
        -inf -> None

    Datetimes are deliberately preserved because FastAPI
    serialises them as ISO-8601 timestamps.
    """

    if isinstance(
        value,
        float,
    ):

        if not math.isfinite(
            value
        ):

            return None


        return value


    if isinstance(
        value,
        dict,
    ):

        return {
            key: clean_value(
                item
            )
            for key, item
            in value.items()
        }


    if isinstance(
        value,
        list,
    ):

        return [
            clean_value(
                item
            )
            for item in value
        ]


    if isinstance(
        value,
        tuple,
    ):

        return [
            clean_value(
                item
            )
            for item in value
        ]


    return value


def clean_records(
    dataframe: pl.DataFrame,
) -> list[dict]:
    """
    Convert a Polars DataFrame into JSON-safe records.
    """

    records = (
        dataframe.to_dicts()
    )


    return [
        {
            key: clean_value(
                value
            )
            for key, value
            in row.items()
        }
        for row in records
    ]


# ============================================================
# SNAPSHOT READING
# ============================================================

def read_snapshot(
    path: Path,
    snapshot_name: str,
    update_script: str,
) -> pl.DataFrame:
    """
    Load a processed snapshot.

    503 is used when the endpoint exists but the underlying
    processed dataset has not yet been produced.
    """

    if not path.exists():

        raise HTTPException(
            status_code=503,
            detail=(
                f"{snapshot_name} snapshot is not available yet. "
                f"Run {update_script}."
            ),
        )


    try:

        dataframe = (
            pl.read_parquet(
                path
            )
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed reading "
                f"{snapshot_name.lower()} snapshot: "
                f"{error}"
            ),
        ) from error


    return dataframe


def snapshot_response(
    path: Path,
    snapshot_name: str,
    update_script: str,
) -> dict:
    """
    Standard API response for processed snapshots.
    """

    dataframe = read_snapshot(
        path=path,
        snapshot_name=snapshot_name,
        update_script=update_script,
    )


    if dataframe.is_empty():

        return {
            "data": [],
        }


    return {
        "data": clean_records(
            dataframe
        ),
    }


# ============================================================
# HEALTH HELPERS
# ============================================================

def snapshot_health(
    path: Path,
) -> dict:
    """
    Return basic filesystem-level health information for one
    processed snapshot.
    """

    if not path.exists():

        return {
            "available": False,
            "rows": None,
            "modified_at": None,
            "age_seconds": None,
            "error": None,
        }


    try:

        modified_timestamp = (
            path.stat()
            .st_mtime
        )


        modified_at = (
            datetime.fromtimestamp(
                modified_timestamp,
                tz=timezone.utc,
            )
        )


        age_seconds = max(
            0.0,
            (
                datetime.now(
                    timezone.utc
                )
                - modified_at
            ).total_seconds(),
        )


        dataframe = (
            pl.read_parquet(
                path
            )
        )


        return {
            "available": True,
            "rows": dataframe.height,
            "modified_at": (
                modified_at
                .isoformat()
            ),
            "age_seconds": (
                round(
                    age_seconds,
                    3,
                )
            ),
            "error": None,
        }


    except Exception as error:

        return {
            "available": False,
            "rows": None,
            "modified_at": None,
            "age_seconds": None,
            "error": str(
                error
            ),
        }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "online",
        "service": (
            "Crypto Derivatives Risk Radar API"
        ),
        "version": "0.2.0",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    snapshot_status = {
        name: snapshot_health(
            config[
                "path"
            ]
        )
        for name, config
        in SNAPSHOTS.items()
    }


    core_snapshots = [
        "spot",
        "volatility",
        "derivatives",
        "liquidations",
        "states",
        "risk",
    ]


    core_available = all(
        snapshot_status[
            name
        ][
            "available"
        ]
        for name in core_snapshots
    )


    return {
        "status": (
            "healthy"
            if core_available
            else "degraded"
        ),

        "service": (
            "Crypto Derivatives Risk Radar API"
        ),

        "version": "0.2.0",

        "checked_at": (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        ),

        "snapshots": snapshot_status,
    }


# ============================================================
# SPOT MARKET
# ============================================================

@app.get("/api/market/latest")
def market_latest():
    """
    Read the collector-produced local spot snapshot.

    This endpoint does NOT call CoinMarketCap directly.
    """

    return snapshot_response(
        path=SPOT_LATEST_PATH,
        snapshot_name="Spot",
        update_script=(
            "scripts/update_spot.py"
        ),
    )


# ============================================================
# VOLATILITY
# ============================================================

@app.get("/api/volatility/latest")
def volatility_latest():

    return snapshot_response(
        path=VOLATILITY_LATEST_PATH,
        snapshot_name="Volatility",
        update_script=(
            "scripts/update_volatility.py"
        ),
    )


# ============================================================
# DERIVATIVES
# ============================================================

@app.get("/api/derivatives/latest")
def derivatives_latest():

    return snapshot_response(
        path=DERIVATIVES_LATEST_PATH,
        snapshot_name="Derivatives",
        update_script=(
            "scripts/update_derivatives.py"
        ),
    )


# ============================================================
# ASSET LIQUIDATIONS
# ============================================================

@app.get("/api/liquidations/latest")
def liquidations_latest():

    return snapshot_response(
        path=LIQUIDATIONS_LATEST_PATH,
        snapshot_name="Liquidations",
        update_script=(
            "scripts/update_liquidations.py"
        ),
    )


# ============================================================
# GLOBAL LIQUIDATIONS
# ============================================================

@app.get("/api/liquidations/global")
def liquidations_global():

    return snapshot_response(
        path=LIQUIDATIONS_GLOBAL_PATH,
        snapshot_name=(
            "Global liquidations"
        ),
        update_script=(
            "scripts/update_liquidations.py"
        ),
    )


# ============================================================
# EXCHANGE LIQUIDATIONS
# ============================================================

@app.get("/api/liquidations/exchanges")
def liquidations_exchanges():

    return snapshot_response(
        path=LIQUIDATIONS_EXCHANGES_PATH,
        snapshot_name=(
            "Exchange liquidations"
        ),
        update_script=(
            "scripts/update_liquidations.py"
        ),
    )


# ============================================================
# MARKET STATES
# ============================================================

@app.get("/api/states/latest")
def states_latest():

    return snapshot_response(
        path=STATES_LATEST_PATH,
        snapshot_name="Market states",
        update_script=(
            "scripts/update_states.py"
        ),
    )


# ============================================================
# CDRR RISK
# ============================================================

@app.get("/api/risk/latest")
def risk_latest():

    dataframe = read_snapshot(
        path=RISK_LATEST_PATH,
        snapshot_name="CDRR risk",
        update_script=(
            "scripts/update_risk.py"
        ),
    )


    if dataframe.is_empty():

        return {
            "data": [],
        }


    # Ensure API consumers receive the risk universe in
    # descending risk order even if Parquet row ordering
    # changes later.
    if (
        "provisional_risk_score"
        in dataframe.columns
    ):

        dataframe = (
            dataframe

            .sort(
                "provisional_risk_score",
                descending=True,
                nulls_last=True,
            )
        )


    return {
        "data": clean_records(
            dataframe
        ),
    }