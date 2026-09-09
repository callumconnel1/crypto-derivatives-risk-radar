import json
import os
from datetime import UTC, datetime
from pathlib import Path

import polars as pl


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

DEFAULT_BASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
)


def _normalise_datetime(
    value: datetime | None,
) -> datetime:

    if value is None:
        return datetime.now(UTC)

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC
        )

    return value.astimezone(UTC)


def _provider_signature(
    dataframe: pl.DataFrame,
) -> dict:

    signature = {
        "rows": dataframe.height,
    }

    if (
        "timestamp" in dataframe.columns
        and not dataframe.is_empty()
    ):

        try:

            maximum = dataframe.select(
                pl.col("timestamp").max()
            ).item()

            minimum = dataframe.select(
                pl.col("timestamp").min()
            ).item()

            signature[
                "provider_timestamp_max"
            ] = (
                maximum.isoformat()
                if hasattr(
                    maximum,
                    "isoformat",
                )
                else str(maximum)
            )

            signature[
                "provider_timestamp_min"
            ] = (
                minimum.isoformat()
                if hasattr(
                    minimum,
                    "isoformat",
                )
                else str(minimum)
            )

        except Exception:

            signature[
                "provider_timestamp_max"
            ] = None

            signature[
                "provider_timestamp_min"
            ] = None

    return signature


def _load_state(
    state_path: Path,
) -> dict | None:

    if not state_path.exists():
        return None

    try:

        with state_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return None


def _save_state(
    state_path: Path,
    state: dict,
) -> None:

    temporary = state_path.with_suffix(
        ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            state,
            file,
            indent=2,
        )

    os.replace(
        temporary,
        state_path,
    )


def save_data(
    dataframe: pl.DataFrame,
    dataset: str,
    collected_at: datetime | None = None,
    base_dir: Path = DEFAULT_BASE_DIR,
    deduplicate: bool = True,
) -> Path | None:

    """
    Save a Polars DataFrame into hourly Parquet partitions.

    Example dataset names:

        spot/quotes
        derivatives/market_pairs
        derivatives/crypto_liquidations
        derivatives/exchange_liquidations
        derivatives/global_liquidations
        derivatives/exchange_summary

    Repeated calls during the same hour are appended into
    the same Parquet partition.

    Duplicate provider snapshots are skipped.
    """

    if dataframe is None:
        return None

    if dataframe.is_empty():
        return None

    collected_at = _normalise_datetime(
        collected_at
    )

    dataset_dir = (
        base_dir
        / Path(dataset)
    )

    dataset_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    state_path = (
        dataset_dir
        / ".last_saved.json"
    )

    signature = _provider_signature(
        dataframe
    )

    previous_state = _load_state(
        state_path
    )

    if (
        previous_state is not None
        and previous_state.get(
            "signature"
        ) == signature
    ):

        return None

    # --------------------------------------------------------
    # Add collector timestamp
    # --------------------------------------------------------

    dataframe = dataframe.with_columns(
        pl.lit(
            collected_at
        )
        .cast(
            pl.Datetime(
                time_unit="us",
                time_zone="UTC",
            )
        )
        .alias(
            "collected_at"
        )
    )

    # --------------------------------------------------------
    # Hourly partition
    # --------------------------------------------------------

    date_directory = (
        dataset_dir
        / f"date={collected_at:%Y-%m-%d}"
    )

    date_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        date_directory
        / f"hour={collected_at:%H}.parquet"
    )

    # --------------------------------------------------------
    # Append into existing hourly partition
    # --------------------------------------------------------

    if output_path.exists():

        existing = pl.read_parquet(
            output_path
        )

        dataframe = pl.concat(
            [
                existing,
                dataframe,
            ],
            how="diagonal_relaxed",
        )

        if deduplicate:

            dedupe_columns = [
                column
                for column
                in dataframe.columns
                if column
                != "collected_at"
            ]

            if dedupe_columns:

                dataframe = (
                    dataframe.unique(
                        subset=dedupe_columns,
                        keep="last",
                        maintain_order=True,
                    )
                )

    # --------------------------------------------------------
    # Keep time ordering sensible
    # --------------------------------------------------------

    sort_columns = [
        column
        for column
        in [
            "timestamp",
            "collected_at",
        ]
        if column
        in dataframe.columns
    ]

    if sort_columns:

        dataframe = dataframe.sort(
            sort_columns
        )

    # --------------------------------------------------------
    # Atomic write
    # --------------------------------------------------------

    temporary_path = (
        output_path.parent
        / (
            output_path.stem
            + ".tmp.parquet"
        )
    )

    dataframe.write_parquet(
        temporary_path,
        compression="zstd",
        statistics=True,
    )

    os.replace(
        temporary_path,
        output_path,
    )

    # --------------------------------------------------------
    # Save state only after successful Parquet write
    # --------------------------------------------------------

    state = {
        "dataset": dataset,
        "signature": signature,
        "last_collected_at": (
            collected_at.isoformat()
        ),
        "last_file": str(
            output_path
        ),
    }

    _save_state(
        state_path,
        state,
    )

    return output_path