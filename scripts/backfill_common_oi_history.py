from __future__ import annotations

import os
import sys
from bisect import bisect_right
from datetime import timedelta
from pathlib import Path
from statistics import median

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


from backend.risk_radar.derivatives import (
    build_latest_derivatives_snapshot,
    prepare_common_oi_market_snapshot,
)


# ============================================================
# PATHS
# ============================================================

MARKET_PAIR_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "market_pairs"
)

EXCHANGE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "derivatives"
    / "exchange_summary"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "derivatives"
    / "markets_history.parquet"
)


# ============================================================
# CONFIGURATION
# ============================================================

RETENTION_HOURS = 26

MAX_PAIRING_SKEW_SECONDS = 300.0


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
            f"No parquet files found in {directory}"
        )


    print(
        f"Reading {len(files)} files from {directory}"
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


def latest_time_at_or_before(
    target,
    candidates,
):
    """
    Return the newest candidate timestamp that is not later
    than the target timestamp.

    Uses binary search because the candidate timestamps are
    already sorted.

    This guarantees that historical reconstruction contains
    no endpoint look-ahead.
    """

    position = (
        bisect_right(
            candidates,
            target,
        )
        - 1
    )


    if position < 0:

        return (
            None,
            None,
        )


    selected = (
        candidates[
            position
        ]
    )


    skew_seconds = (
        target
        - selected
    ).total_seconds()


    return (
        selected,
        skew_seconds,
    )


# ============================================================
# LOAD RAW HISTORY
# ============================================================

market_pairs = read_all_parquet(
    MARKET_PAIR_DIR
)

exchange_summary = read_all_parquet(
    EXCHANGE_DIR
)


if (
    "collected_at"
    not in market_pairs.columns
):

    raise ValueError(
        "market-pair history has no collected_at column"
    )


if (
    "collected_at"
    not in exchange_summary.columns
):

    raise ValueError(
        "exchange-summary history has no collected_at column"
    )


# ============================================================
# LIMIT RAW INPUT TO RETENTION WINDOW
# ============================================================

latest_market_time = (
    market_pairs[
        "collected_at"
    ].max()
)


if latest_market_time is None:

    raise RuntimeError(
        "No market-pair timestamps found"
    )


cutoff = (
    latest_market_time
    - timedelta(
        hours=RETENTION_HOURS
    )
)


market_pairs = (
    market_pairs

    .filter(
        pl.col(
            "collected_at"
        )
        >= cutoff
    )
)


exchange_summary = (
    exchange_summary

    .filter(
        pl.col(
            "collected_at"
        )
        >= (
            cutoff
            - timedelta(
                minutes=10
            )
        )
    )
)


# ============================================================
# SNAPSHOT TIMES
# ============================================================

market_times = sorted(
    market_pairs[
        "collected_at"
    ]
    .unique()
    .to_list()
)


exchange_times = sorted(
    exchange_summary[
        "collected_at"
    ]
    .unique()
    .to_list()
)


print(
    "\nRAW HISTORY"
)


print(
    "Market-pair snapshots:",
    len(
        market_times
    ),
)


print(
    "Exchange snapshots:",
    len(
        exchange_times
    ),
)


if market_times:

    print(
        "Market start:",
        market_times[0],
    )

    print(
        "Market end:",
        market_times[-1],
    )


# ============================================================
# PRESERVE EXISTING NON-RECONSTRUCTED HISTORY
# ============================================================

existing_preserved = None


if OUTPUT_PATH.exists():

    existing = pl.read_parquet(
        OUTPUT_PATH
    )


    if not existing.is_empty():

        # Any timestamp represented by the raw market-pair
        # history will be reconstructed from scratch below.
        #
        # We therefore REMOVE those timestamps from the old
        # processed file before merging. This guarantees that
        # rows produced by an older backfill algorithm cannot
        # overwrite the newly reconstructed no-look-ahead
        # version.

        existing_preserved = (
            existing
            .filter(
                ~pl.col(
                    "collected_at"
                ).is_in(
                    market_times
                )
            )
        )


        print(
            "\nEXISTING HISTORY"
        )

        print(
            "Existing rows:",
            existing.height,
        )

        print(
            "Preserved rows outside raw reconstruction window:",
            existing_preserved.height,
        )


# ============================================================
# RECONSTRUCT CLEAN MARKET SNAPSHOTS
# ============================================================

reconstructed_frames = []

pairing_skews = []

processed = 0

skipped = 0


for (
    index,
    market_time,
) in enumerate(
    market_times,
    start=1,
):

    (
        exchange_time,
        skew_seconds,
    ) = latest_time_at_or_before(
        market_time,
        exchange_times,
    )


    if (
        exchange_time is None
        or
        skew_seconds is None
        or
        skew_seconds
        > MAX_PAIRING_SKEW_SECONDS
    ):

        print(
            f"[{index:03d}/{len(market_times):03d}] "
            f"SKIP {market_time} "
            f"— no earlier exchange snapshot "
            f"within {MAX_PAIRING_SKEW_SECONDS:.0f}s"
        )

        skipped += 1

        continue


    historical_markets = (
        market_pairs

        .filter(
            pl.col(
                "collected_at"
            )
            == market_time
        )
    )


    historical_exchange = (
        exchange_summary

        .filter(
            pl.col(
                "collected_at"
            )
            == exchange_time
        )
    )


    try:

        (
            _,
            cleaned_markets,
        ) = build_latest_derivatives_snapshot(
            historical_markets,
            historical_exchange,
        )


        clean_history = (
            prepare_common_oi_market_snapshot(
                cleaned_markets
            )
        )


        if clean_history.is_empty():

            print(
                f"[{index:03d}/{len(market_times):03d}] "
                f"EMPTY {market_time}"
            )

            skipped += 1

            continue


        reconstructed_frames.append(
            clean_history
        )


        pairing_skews.append(
            skew_seconds
        )


        processed += 1


        print(
            f"[{index:03d}/{len(market_times):03d}] "
            f"OK {market_time} "
            f"| exchange {exchange_time} "
            f"| lag {skew_seconds:.1f}s "
            f"| rows {clean_history.height}"
        )


    except Exception as exc:

        print(
            f"[{index:03d}/{len(market_times):03d}] "
            f"ERROR {market_time}: {exc}"
        )

        skipped += 1


# ============================================================
# BUILD FINAL HISTORY
# ============================================================

frames = []


# Preserve snapshots that are no longer reconstructable from
# currently retained raw files.

if (
    existing_preserved is not None
    and
    not existing_preserved.is_empty()
):

    frames.append(
        existing_preserved
    )


# Reconstructed snapshots are appended AFTER existing data.
# Therefore, even if a duplicate somehow remains, keep="last"
# gives priority to the newly reconstructed version.

frames.extend(
    reconstructed_frames
)


if not frames:

    raise RuntimeError(
        "No clean historical market snapshots could be reconstructed"
    )


history = (
    pl.concat(
        frames,
        how="diagonal_relaxed",
    )

    .unique(
        subset=[
            "symbol",
            "market_id",
            "exchange_id",
            "collected_at",
        ],
        keep="last",
    )

    .sort([
        "collected_at",
        "symbol",
        "exchange_id",
        "market_id",
    ])
)


# ============================================================
# FINAL RETENTION WINDOW
# ============================================================

latest_time = (
    history[
        "collected_at"
    ].max()
)


if latest_time is not None:

    final_cutoff = (
        latest_time
        - timedelta(
            hours=RETENTION_HOURS
        )
    )


    history = (
        history

        .filter(
            pl.col(
                "collected_at"
            )
            >= final_cutoff
        )
    )


# ============================================================
# SAVE
# ============================================================

atomic_write(
    history,
    OUTPUT_PATH,
)


# ============================================================
# DIAGNOSTICS
# ============================================================

start = (
    history[
        "collected_at"
    ].min()
)

end = (
    history[
        "collected_at"
    ].max()
)


if (
    start is not None
    and
    end is not None
):

    span_hours = (
        (
            end
            - start
        ).total_seconds()
        / 3600.0
    )

else:

    span_hours = 0.0


print(
    "\n"
    + "=" * 70
)

print(
    "BACKFILL COMPLETE"
)

print(
    "=" * 70
)


print(
    "Processed snapshots:",
    processed,
)

print(
    "Skipped snapshots:",
    skipped,
)

print(
    "Final rows:",
    history.height,
)

print(
    "Final snapshots:",
    history[
        "collected_at"
    ].n_unique(),
)

print(
    "Start:",
    start,
)

print(
    "End:",
    end,
)

print(
    "Span:",
    f"{span_hours:.2f} hours",
)


if pairing_skews:

    print(
        "Median endpoint lag:",
        f"{median(pairing_skews):.2f}s",
    )

    print(
        "Maximum endpoint lag:",
        f"{max(pairing_skews):.2f}s",
    )


print(
    "\nSaved:",
    OUTPUT_PATH,
)