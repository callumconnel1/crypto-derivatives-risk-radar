from __future__ import annotations

import os
import sys
from pathlib import Path

import polars as pl


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from backend.risk_radar.spot import (
    build_latest_spot_snapshot,
)


# ============================================================
# PATHS
# ============================================================

RAW_SPOT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "spot"
    / "quotes"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "spot"
)

LATEST_PATH = (
    OUTPUT_DIR
    / "latest.parquet"
)


# ============================================================
# HELPERS
# ============================================================


def read_all_parquet(
    directory: Path,
) -> pl.DataFrame:

    files = sorted(
        directory.rglob(
            "*.parquet"
        )
    )


    if not files:

        raise FileNotFoundError(
            f"No Parquet files found in {directory}"
        )


    return pl.concat(
        [
            pl.read_parquet(path)
            for path in files
        ],
        how="diagonal_relaxed",
    )


def atomic_write(
    dataframe: pl.DataFrame,
    path: Path,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    temporary = (
        path.parent
        / f".{path.name}.tmp"
    )


    dataframe.write_parquet(
        temporary
    )


    os.replace(
        temporary,
        path,
    )


# ============================================================
# LOAD
# ============================================================

print(
    "Loading spot history..."
)


history = read_all_parquet(
    RAW_SPOT_DIR
)


print(
    "Rows:",
    history.height,
)

print(
    "Snapshots:",
    history[
        "collected_at"
    ].n_unique(),
)


history_start = (
    history[
        "collected_at"
    ].min()
)

history_end = (
    history[
        "collected_at"
    ].max()
)


span_hours = (
    (
        history_end
        - history_start
    ).total_seconds()
    / 3600.0
)


print(
    "Start:",
    history_start,
)

print(
    "End:",
    history_end,
)

print(
    "Span:",
    f"{span_hours:.2f} hours",
)


# ============================================================
# BUILD SNAPSHOT
# ============================================================

snapshot = (
    build_latest_spot_snapshot(
        history
    )
)


# ============================================================
# SAVE
# ============================================================

atomic_write(
    snapshot,
    LATEST_PATH,
)


# ============================================================
# DISPLAY
# ============================================================

print(
    "\nSPOT SNAPSHOT"
)


print(
    snapshot.select([
        "symbol",
        "price",

        "price_change_1h",
        "price_change_4h",
        "price_change_24h",

        "percent_change_1h",

        "price_reference_offset_minutes_1h",

        "price_change_available_1h",
        "price_change_available_4h",
        "price_change_available_24h",
    ])
)


print(
    "\nPRICE CHANGE AVAILABILITY"
)


print(
    snapshot.select([
        pl.col(
            "price_change_available_1h"
        )
        .sum()
        .alias(
            "assets_1h"
        ),

        pl.col(
            "price_change_available_4h"
        )
        .sum()
        .alias(
            "assets_4h"
        ),

        pl.col(
            "price_change_available_24h"
        )
        .sum()
        .alias(
            "assets_24h"
        ),
    ])
)


print(
    "\nSaved:",
    LATEST_PATH,
)