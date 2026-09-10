from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
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

if str(
    PROJECT_ROOT
) not in sys.path:
    sys.path.insert(
        0,
        str(
            PROJECT_ROOT
        ),
    )


from backend.risk_radar.forward_validation import (
    run_forward_validation,
)


# ============================================================
# DEFAULT VALIDATION EPOCH
# ============================================================

# First known complete collector cycle after the current
# liquidation calibration + basis research plumbing was live:
#
# 2026-09-10 18:22 BST == 2026-09-10 17:22 UTC.
#
# This intentionally excludes earlier risk-history rows produced
# under slightly different provisional calibration logic even
# though the risk-version string remained unchanged.
DEFAULT_VALIDATION_START = (
    "2026-09-10T17:22:00+00:00"
)


# ============================================================
# PATHS
# ============================================================

RISK_HISTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "risk"
    / "history.parquet"
)

STATE_HISTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "states"
    / "history.parquet"
)

PROCESSED_SPOT_HISTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "spot"
    / "history.parquet"
)

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
    / "research"
    / "forward_validation"
)


# ============================================================
# ARGUMENTS
# ============================================================


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Validate current CDRR rankings against "
            "subsequent realised market stress."
        )
    )

    parser.add_argument(
        "--start",
        default=DEFAULT_VALIDATION_START,
        help=(
            "Validation epoch as ISO-8601. "
            "Default is the first complete collector cycle "
            "after the current provisional methodology "
            "was installed."
        ),
    )

    parser.add_argument(
        "--risk-version",
        default=None,
        help=(
            "Optional exact risk_version filter."
        ),
    )

    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=[
            1,
            4,
            24,
        ],
        help=(
            "Forward horizons in hours. "
            "Default: 1 4 24"
        ),
    )

    return parser.parse_args()


# ============================================================
# HELPERS
# ============================================================


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
            pl.read_parquet(
                path
            )
            for path in files
        ],
        how="diagonal_relaxed",
    )


def parse_iso_datetime(
    value: str,
) -> datetime:
    text = value.strip()

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    parsed = datetime.fromisoformat(
        text
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=UTC
        )

    return parsed.astimezone(
        UTC
    )


def load_spot_history() -> tuple[
    pl.DataFrame,
    str,
]:
    if PROCESSED_SPOT_HISTORY_PATH.exists():
        return (
            pl.read_parquet(
                PROCESSED_SPOT_HISTORY_PATH
            ),
            str(
                PROCESSED_SPOT_HISTORY_PATH
            ),
        )

    return (
        read_all_parquet(
            RAW_SPOT_DIR
        ),
        str(
            RAW_SPOT_DIR
        ),
    )


def print_frame(
    title: str,
    dataframe: pl.DataFrame,
) -> None:
    print(
        f"\n{title}"
    )

    if dataframe.is_empty():
        print(
            "NO MATURE OBSERVATIONS YET"
        )

        return

    print(
        dataframe
    )


# ============================================================
# LOAD
# ============================================================

args = parse_arguments()

validation_start = parse_iso_datetime(
    args.start
)

horizons = tuple(
    sorted(
        set(
            args.horizons
        )
    )
)


if not RISK_HISTORY_PATH.exists():
    raise FileNotFoundError(
        f"Risk history missing: {RISK_HISTORY_PATH}"
    )


risk_history = pl.read_parquet(
    RISK_HISTORY_PATH
)


spot_history, spot_source = (
    load_spot_history()
)


if STATE_HISTORY_PATH.exists():
    state_history = pl.read_parquet(
        STATE_HISTORY_PATH
    )
else:
    state_history = None


print(
    "Risk history:",
    risk_history.shape,
)

print(
    "Spot history:",
    spot_history.shape,
)

print(
    "Spot source:",
    spot_source,
)

print(
    "State history:",
    (
        state_history.shape
        if state_history is not None
        else "UNAVAILABLE"
    ),
)

print(
    "Validation start:",
    validation_start.isoformat(),
)

print(
    "Horizons:",
    horizons,
)


# ============================================================
# VALIDATE
# ============================================================

results = run_forward_validation(
    risk_history=risk_history,
    spot_history=spot_history,
    state_history=state_history,
    validation_start=validation_start,
    risk_version=args.risk_version,
    horizons_hours=horizons,
)


samples = results[
    "samples"
]

snapshot_ic = results[
    "snapshot_ic"
]

metrics = results[
    "metrics"
]

quintiles = results[
    "quintiles"
]

quintile_summary = results[
    "quintile_summary"
]

status = results[
    "status"
]


# ============================================================
# SAVE
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


outputs = {
    "samples.parquet":
        samples,

    "snapshot_ic.parquet":
        snapshot_ic,

    "metrics.parquet":
        metrics,

    "quintiles.parquet":
        quintiles,

    "quintile_summary.parquet":
        quintile_summary,

    "status.parquet":
        status,
}


for filename, dataframe in outputs.items():
    atomic_write(
        dataframe,
        OUTPUT_DIR
        / filename,
    )


# ============================================================
# DISPLAY
# ============================================================

print_frame(
    "FORWARD HORIZON STATUS",
    status,
)

print_frame(
    "CROSS-SECTIONAL FORWARD-STRESS IC",
    metrics,
)

print_frame(
    "RISK QUINTILE FORWARD-STRESS SUMMARY",
    quintile_summary,
)

print_frame(
    "RISK QUINTILE DETAIL",
    quintiles,
)


if not snapshot_ic.is_empty():
    recent_ic = (
        snapshot_ic
        .sort(
            "risk_snapshot_at",
            descending=True,
        )
        .head(
            24
        )
    )
else:
    recent_ic = (
        snapshot_ic
    )


print_frame(
    "MOST RECENT SNAPSHOT IC OBSERVATIONS",
    recent_ic,
)


# ============================================================
# OUTPUT
# ============================================================

print(
    "\nSaved validation outputs:"
)


for filename in outputs:
    print(
        OUTPUT_DIR
        / filename
    )


print(
    "\nInterpretation:"
)

print(
    "Positive Spearman IC means higher current CDRR "
    "rankings were associated with greater subsequent "
    "realised stress."
)

print(
    "Q5 is the highest-risk cross-sectional quintile; "
    "Q1 is the lowest."
)

print(
    "Do not infer statistical significance from the "
    "first few hours: neighbouring forward windows overlap "
    "heavily and observations are serially dependent."
)
