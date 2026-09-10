"""
Crypto Derivatives Risk Radar
Continuous CoinMarketCap collector.

Run once for testing:

    python scripts/collect_data.py --once

Run continuously:

    python scripts/collect_data.py

Run in background:

    nohup .venv/bin/python scripts/collect_data.py \
        > data/raw/collector.out 2>&1 &

Custom assets:

    python scripts/collect_data.py \
        --ids 1 1027 5426 52

Force a slower polling interval:

    python scripts/collect_data.py \
        --interval 300

The collector will NEVER poll faster than the safe interval
calculated from:
    - CMC's cache frequency
    - current per-minute rate limit
    - current monthly credit usage
    - remaining time until the monthly reset
"""

import argparse
import logging
import math
import os
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import httpx
import polars as pl

import subprocess
import sys

from get_data import (
    CMCAPIError,
    CMCCreditLimitError,
    get_crypto_liquidations,
    get_derivative_market_pairs,
    get_derivatives_exchanges,
    get_exchange_liquidations,
    get_global_liquidations,
    get_key_info,
    get_latest_quotes,
)

from save_data import save_data


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

LOG_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "collector.log"
)

LOCK_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / ".collector.lock"
)

LOG_FILE.parent.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            LOG_FILE
        ),
    ],
)

logger = logging.getLogger(
    "cmc_collector"
)

# ============================================================
# DEFAULT UNIVERSE
# ============================================================

DEFAULT_IDS = [
    1,      # BTC
    1027,   # ETH
    5426,   # SOL
    52,     # XRP
    1839,   # BNB
    74,     # DOGE
    2010,   # ADA
    1975,   # LINK
    5805,   # AVAX
    20947,  # SUI
    1958,   # TRX
    6636,   # DOT
    2,      # LTC
    1831,   # BCH
    7083,   # UNI
    21794,  # APT
    6535,   # NEAR
    1321,   # ETC
    8916,   # ICP
    2280,   # FIL
]


# ============================================================
# SAFETY SETTINGS
# ============================================================

# CMC derivatives cache is 60 seconds.
# Never poll faster than this.
MIN_INTERVAL_SECONDS = 65

# Keep 10% of the monthly allocation in reserve.
DEFAULT_BUDGET_FRACTION = 0.90

# Stay comfortably under minute rate limits.
RATE_LIMIT_UTILISATION = 0.80


STOP_EVENT = Event()


# ============================================================
# SIGNAL HANDLING
# ============================================================

def handle_signal(
    signum,
    frame,
) -> None:

    logger.info(
        "Shutdown signal received"
    )

    STOP_EVENT.set()


signal.signal(
    signal.SIGINT,
    handle_signal,
)

signal.signal(
    signal.SIGTERM,
    handle_signal,
)


# ============================================================
# LOCK FILE
# ============================================================

def _process_exists(
    pid: int,
) -> bool:

    try:

        os.kill(
            pid,
            0,
        )

    except ProcessLookupError:
        return False

    except PermissionError:
        return True

    return True


def acquire_lock() -> int:

    LOCK_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if LOCK_FILE.exists():

        try:

            old_pid = int(
                LOCK_FILE
                .read_text()
                .strip()
            )

        except Exception:
            old_pid = None

        if (
            old_pid is not None
            and _process_exists(
                old_pid
            )
        ):

            raise RuntimeError(
                f"Collector already running "
                f"with PID {old_pid}"
            )

        logger.warning(
            "Removing stale collector lock"
        )

        LOCK_FILE.unlink(
            missing_ok=True
        )

    file_descriptor = os.open(
        LOCK_FILE,
        os.O_CREAT
        | os.O_EXCL
        | os.O_WRONLY,
    )

    os.write(
        file_descriptor,
        str(
            os.getpid()
        ).encode(),
    )

    return file_descriptor


def release_lock(
    file_descriptor: int,
) -> None:

    try:
        os.close(
            file_descriptor
        )

    except OSError:
        pass

    LOCK_FILE.unlink(
        missing_ok=True
    )


# ============================================================
# TIME HELPERS
# ============================================================

def parse_timestamp(
    value: str | None,
) -> datetime | None:

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        ).astimezone(
            UTC
        )

    except ValueError:
        return None


def interruptible_sleep(
    seconds: float,
) -> None:

    STOP_EVENT.wait(
        timeout=max(
            0,
            seconds,
        )
    )


# ============================================================
# USAGE / BUDGET HELPERS
# ============================================================

def get_monthly_usage(
    info: dict,
) -> tuple[
    int,
    int,
    int,
]:

    plan = info.get(
        "plan",
        {},
    )

    usage = info.get(
        "usage",
        {},
    )

    month = usage.get(
        "current_month",
        {},
    )

    monthly_limit = int(
        plan.get(
            "credit_limit_monthly",
            (
                month.get(
                    "credits_used",
                    0,
                )
                + month.get(
                    "credits_left",
                    0,
                )
            ),
        )
    )

    credits_used = int(
        month.get(
            "credits_used",
            0,
        )
    )

    credits_left = int(
        month.get(
            "credits_left",
            max(
                0,
                monthly_limit
                - credits_used,
            ),
        )
    )

    return (
        monthly_limit,
        credits_used,
        credits_left,
    )


def get_seconds_until_reset(
    info: dict,
) -> float:

    plan = info.get(
        "plan",
        {},
    )

    reset_timestamp = parse_timestamp(
        plan.get(
            "credit_limit_monthly_reset_timestamp"
        )
    )

    if reset_timestamp is None:

        return (
            timedelta(
                days=30
            ).total_seconds()
        )

    seconds = (
        reset_timestamp
        - datetime.now(UTC)
    ).total_seconds()

    return max(
        seconds,
        60,
    )


def calculate_safe_interval(
    info: dict,
    estimated_cycle_credits: int,
    estimated_requests_per_cycle: int,
    budget_fraction: float,
) -> int:

    (
        monthly_limit,
        _,
        credits_left,
    ) = get_monthly_usage(
        info
    )

    seconds_until_reset = (
        get_seconds_until_reset(
            info
        )
    )

    # --------------------------------------------------------
    # Reserve part of the plan for manual development,
    # frontend calls, debugging, etc.
    # --------------------------------------------------------

    reserve = int(
        monthly_limit
        * (
            1
            - budget_fraction
        )
    )

    usable_credits_left = (
        credits_left
        - reserve
    )

    if usable_credits_left <= 0:

        return int(
            seconds_until_reset
            + 60
        )

    # --------------------------------------------------------
    # Credit-budget interval
    #
    # cycles_remaining =
    # usable credits / credits per cycle
    #
    # interval =
    # seconds to reset / cycles remaining
    # --------------------------------------------------------

    credit_interval = (
        estimated_cycle_credits
        * seconds_until_reset
        / usable_credits_left
    )

    # --------------------------------------------------------
    # Minute rate-limit interval
    # --------------------------------------------------------

    rate_limit = int(
        info.get(
            "plan",
            {},
        ).get(
            "rate_limit_minute",
            600,
        )
    )

    allowed_requests_per_minute = max(
        1,
        rate_limit
        * RATE_LIMIT_UTILISATION,
    )

    rate_interval = (
        estimated_requests_per_cycle
        / allowed_requests_per_minute
        * 60
    )

    safe_interval = max(
        MIN_INTERVAL_SECONDS,
        credit_interval,
        rate_interval,
    )

    # Round to next 5 seconds
    safe_interval = int(
        math.ceil(
            safe_interval / 5
        )
        * 5
    )

    return safe_interval


# ============================================================
# SAVE HELPER
# ============================================================

def save_frame(
    dataframe: pl.DataFrame,
    dataset: str,
    collected_at: datetime,
) -> None:

    if (
        dataframe is None
        or dataframe.is_empty()
    ):

        logger.warning(
            "%s returned no rows",
            dataset,
        )

        return

    path = save_data(
        dataframe=dataframe,
        dataset=dataset,
        collected_at=collected_at,
    )

    if path is None:

        logger.info(
            "%s unchanged - skipped duplicate snapshot",
            dataset,
        )

    else:

        logger.info(
            "%s saved | rows=%d | %s",
            dataset,
            dataframe.height,
            path,
        )


# ============================================================
# ONE COLLECTION CYCLE
# ============================================================

def collect_cycle(
    client: httpx.Client,
    ids: list[int],
    category: str,
    convert: str,
    include_spot: bool,
    request_spacing: float,
) -> None:

    collected_at = datetime.now(
        UTC
    )

    logger.info(
        "Starting collection cycle"
    )

    # --------------------------------------------------------
    # SPOT MARKET SNAPSHOT
    # --------------------------------------------------------

    if include_spot:

        try:

            spot = get_latest_quotes(
                ids=ids,
                convert=convert,
                client=client,
            )

            save_frame(
                spot,
                "spot/quotes",
                collected_at,
            )

        except CMCCreditLimitError:
            raise

        except Exception:

            logger.exception(
                "Failed collecting spot quotes"
            )

    # --------------------------------------------------------
    # DERIVATIVE MARKET PAIRS
    #
    # One request per cryptocurrency so a single bad asset
    # cannot destroy the entire market-pair snapshot.
    # --------------------------------------------------------

    market_frames = []

    for id in ids:

        if STOP_EVENT.is_set():
            return

        try:

            frame = (
                get_derivative_market_pairs(
                    ids=[id],
                    category=category,
                    convert=convert,
                    client=client,
                )
            )

            if not frame.is_empty():

                market_frames.append(
                    frame
                )

        except CMCCreditLimitError:
            raise

        except Exception:

            logger.exception(
                "Failed collecting derivative "
                "market pairs for id=%s",
                id,
            )

        interruptible_sleep(
            request_spacing
        )

    if market_frames:

        market_pairs = pl.concat(
            market_frames,
            how="diagonal_relaxed",
        )

        save_frame(
            market_pairs,
            "derivatives/market_pairs",
            collected_at,
        )

    # --------------------------------------------------------
    # CRYPTO LIQUIDATIONS
    # --------------------------------------------------------

    try:

        crypto_liquidations = (
            get_crypto_liquidations(
                ids=ids,
                convert=convert,
                client=client,
            )
        )

        save_frame(
            crypto_liquidations,
            "derivatives/crypto_liquidations",
            collected_at,
        )

    except CMCCreditLimitError:
        raise

    except Exception:

        logger.exception(
            "Failed collecting crypto liquidations"
        )

    # --------------------------------------------------------
    # GLOBAL LIQUIDATIONS
    # --------------------------------------------------------

    global_liquidations = None

    try:

        global_liquidations = (
            get_global_liquidations(
                convert=convert,
                client=client,
            )
        )

        save_frame(
            global_liquidations,
            "derivatives/global_liquidations",
            collected_at,
        )

    except CMCCreditLimitError:
        raise

    except Exception:

        logger.exception(
            "Failed collecting global liquidations"
        )

    # --------------------------------------------------------
    # EXCHANGE LIQUIDATIONS
    # --------------------------------------------------------

    try:

        exchange_liquidations = (
            get_exchange_liquidations(
                convert=convert,
                client=client,
            )
        )

        # Add share of GLOBAL liquidation activity,
        # not just share of returned exchanges.
        if (
            global_liquidations is not None
            and not global_liquidations.is_empty()
            and not exchange_liquidations.is_empty()
        ):

            expressions = []

            for horizon in [
                "1h",
                "4h",
                "24h",
            ]:

                global_total = (
                    global_liquidations[
                        f"total_liquidations_{horizon}"
                    ][0]
                )

                if (
                    global_total is not None
                    and global_total > 0
                ):

                    expressions.append(
                        (
                            pl.col(
                                f"total_liquidations_{horizon}"
                            )
                            / global_total
                        ).alias(
                            f"global_liquidation_share_{horizon}"
                        )
                    )

            if expressions:

                exchange_liquidations = (
                    exchange_liquidations
                    .with_columns(
                        expressions
                    )
                )

        save_frame(
            exchange_liquidations,
            "derivatives/exchange_liquidations",
            collected_at,
        )

    except CMCCreditLimitError:
        raise

    except Exception:

        logger.exception(
            "Failed collecting exchange liquidations"
        )

    # --------------------------------------------------------
    # DERIVATIVES EXCHANGE SUMMARY
    # --------------------------------------------------------

    try:

        exchange_summary = (
            get_derivatives_exchanges(
                convert=convert,
                client=client,
            )
        )

        save_frame(
            exchange_summary,
            "derivatives/exchange_summary",
            collected_at,
        )

    except CMCCreditLimitError:
        raise

    except Exception:

        logger.exception(
            "Failed collecting derivatives "
            "exchange summary"
        )

    # ============================================================
    # UPDATE SPOT FEATURE ENGINE
    # ============================================================

    try:

        spot_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_spot.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(spot_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            logger.info(
                "Spot snapshot updated"
            )

        else:

            logger.error(
                "Spot update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Spot update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating spot snapshot"
        )

    # ============================================================
    # UPDATE VOLATILITY ENGINE
    # ============================================================

    try:

        volatility_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_volatility.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(volatility_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            logger.info(
                "Volatility snapshot updated"
            )

        else:

            logger.error(
                "Volatility update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Volatility update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating volatility snapshot"
        )


    # ============================================================
    # UPDATE DERIVATIVES ENGINE
    # ============================================================

    try:

        derivatives_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_derivatives.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(derivatives_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            logger.info(
                "Derivatives snapshot updated"
            )

        else:

            logger.error(
                "Derivatives update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Derivatives update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating derivatives snapshot"
        )

    # ============================================================
    # UPDATE FUNDING CALIBRATION ENGINE
    # ============================================================

    try:

        funding_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_funding.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(funding_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            logger.info(
                "Funding snapshot updated"
            )

        else:

            logger.error(
                "Funding update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Funding update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating funding snapshot"
        )

    # ============================================================
    # UPDATE BASIS CALIBRATION ENGINE
    # ============================================================

    basis_update_ok = False

    try:

        basis_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_basis.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(basis_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            basis_update_ok = True

            logger.info(
                "Basis snapshot updated"
            )

        else:

            logger.error(
                "Basis update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Basis update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating basis snapshot"
        )

    # ============================================================
    # UPDATE LIQUIDATION ENGINE
    # ============================================================

    try:

        liquidation_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_liquidations.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(liquidation_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            logger.info(
                "Liquidation snapshot updated"
            )

        else:

            logger.error(
                "Liquidation update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Liquidation update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating liquidation snapshot"
        )

    # ============================================================
    # UPDATE MARKET STATE ENGINE
    # ============================================================

    try:

        state_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_states.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(state_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            logger.info(
                "Market state snapshot updated"
            )

        else:

            logger.error(
                "Market state update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Market state update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating market state snapshot"
        )

    # ============================================================
    # UPDATE PROVISIONAL CDRR RISK ENGINE
    # ============================================================

    risk_update_ok = False

    try:

        risk_script = (
            PROJECT_ROOT
            / "scripts"
            / "update_risk.py"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(risk_script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:

            risk_update_ok = True

            logger.info(
                "Risk snapshot updated"
            )

        else:

            logger.error(
                "Risk update failed:\n%s",
                result.stderr,
            )

    except subprocess.TimeoutExpired:

        logger.error(
            "Risk update timed out"
        )

    except Exception:

        logger.exception(
            "Failed updating risk snapshot"
        )


    # ============================================================
    # UPDATE MARKET-STRUCTURE RESEARCH HISTORY
    #
    # Research-only:
    # - no API credits
    # - does not modify production risk/latest.parquet
    # - requires both fresh basis and fresh risk snapshots
    # ============================================================

    if (
        basis_update_ok
        and risk_update_ok
    ):

        try:

            research_script = (
                PROJECT_ROOT
                / "scripts"
                / "analyse_market_structure.py"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(research_script),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:

                logger.info(
                    "Market structure research snapshot updated"
                )

            else:

                logger.error(
                    "Market structure research update failed:\n%s",
                    result.stderr,
                )

        except subprocess.TimeoutExpired:

            logger.error(
                "Market structure research update timed out"
            )

        except Exception:

            logger.exception(
                "Failed updating market structure research"
            )

    else:

        logger.warning(
            "Market structure research skipped | "
            "basis_update_ok=%s | risk_update_ok=%s",
            basis_update_ok,
            risk_update_ok,
        )


    logger.info(
        "Collection cycle complete"
    )


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Continuously collect "
            "CoinMarketCap derivatives data"
        )
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        type=int,
        default=DEFAULT_IDS,
        help=(
            "CoinMarketCap cryptocurrency IDs"
        ),
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help=(
            "Requested polling interval in seconds. "
            "0 = fully automatic. "
            "Unsafe values are automatically increased."
        ),
    )

    parser.add_argument(
        "--category",
        choices=[
            "all",
            "perpetual",
            "futures",
        ],
        default="all",
        help=(
            "Derivative contracts to collect"
        ),
    )

    parser.add_argument(
        "--convert",
        default="USD",
    )

    parser.add_argument(
        "--budget-fraction",
        type=float,
        default=DEFAULT_BUDGET_FRACTION,
        help=(
            "Maximum fraction of monthly credits "
            "the collector should budget for. "
            "Default: 0.90"
        ),
    )

    parser.add_argument(
        "--no-spot",
        action="store_true",
        help=(
            "Disable latest spot quote collection"
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Run one collection cycle and exit"
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    args = parse_arguments()

    if not (
        0
        < args.budget_fraction
        <= 1
    ):

        raise ValueError(
            "--budget-fraction must be "
            "between 0 and 1"
        )

    lock_descriptor = acquire_lock()

    logger.info(
        "Collector started | PID=%d",
        os.getpid(),
    )

    logger.info(
        "Tracking %d assets | category=%s",
        len(args.ids),
        args.category,
    )

    # Initial conservative estimate:
    #
    # - one derivative market request per asset
    # - crypto liquidation
    # - global liquidation
    # - exchange liquidation
    # - exchange summary
    # - spot quotes
    estimated_cycle_credits = (
        len(args.ids)
        + 5
    )

    # key/info calls are free credits,
    # but they still count toward minute request limits.
    estimated_requests_per_cycle = (
        len(args.ids)
        + 7
    )

    try:

        with httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        ) as client:

            while not STOP_EVENT.is_set():

                # ------------------------------------------------
                # Check usage BEFORE collection
                # ------------------------------------------------

                try:

                    info_before = (
                        get_key_info(
                            client=client
                        )
                    )

                except Exception:

                    logger.exception(
                        "Unable to read CMC usage info"
                    )

                    interruptible_sleep(
                        60
                    )

                    continue

                (
                    monthly_limit,
                    credits_used_before,
                    credits_left,
                ) = get_monthly_usage(
                    info_before
                )

                logger.info(
                    "CMC credits | used=%s | "
                    "left=%s | limit=%s",
                    credits_used_before,
                    credits_left,
                    monthly_limit,
                )

                reserve = int(
                    monthly_limit
                    * (
                        1
                        - args.budget_fraction
                    )
                )

                if credits_left <= reserve:

                    seconds_to_reset = (
                        get_seconds_until_reset(
                            info_before
                        )
                    )

                    logger.warning(
                        "Credit reserve reached. "
                        "Pausing until next reset "
                        "(approximately %.2f hours)",
                        seconds_to_reset / 3600,
                    )

                    interruptible_sleep(
                        seconds_to_reset
                        + 60
                    )

                    continue

                # ------------------------------------------------
                # Determine request spacing from live rate limit
                # ------------------------------------------------

                rate_limit = int(
                    info_before.get(
                        "plan",
                        {},
                    ).get(
                        "rate_limit_minute",
                        600,
                    )
                )

                request_spacing = (
                    60
                    / max(
                        1,
                        rate_limit
                        * RATE_LIMIT_UTILISATION,
                    )
                )

                # ------------------------------------------------
                # COLLECT
                # ------------------------------------------------

                try:

                    collect_cycle(
                        client=client,
                        ids=args.ids,
                        category=args.category,
                        convert=args.convert,
                        include_spot=(
                            not args.no_spot
                        ),
                        request_spacing=request_spacing,
                    )

                except CMCCreditLimitError:

                    logger.exception(
                        "CMC credit limit reached"
                    )

                    interruptible_sleep(
                        3600
                    )

                    continue

                except Exception:

                    logger.exception(
                        "Unexpected collector error"
                    )

                if args.once:
                    break

                if STOP_EVENT.is_set():
                    break

                # ------------------------------------------------
                # Check actual credit cost AFTER cycle
                # ------------------------------------------------

                try:

                    info_after = (
                        get_key_info(
                            client=client
                        )
                    )

                    (
                        _,
                        credits_used_after,
                        _,
                    ) = get_monthly_usage(
                        info_after
                    )

                    actual_cycle_credits = max(
                        1,
                        credits_used_after
                        - credits_used_before,
                    )

                    estimated_cycle_credits = (
                        actual_cycle_credits
                    )

                    safe_interval = (
                        calculate_safe_interval(
                            info=info_after,
                            estimated_cycle_credits=(
                                estimated_cycle_credits
                            ),
                            estimated_requests_per_cycle=(
                                estimated_requests_per_cycle
                            ),
                            budget_fraction=(
                                args.budget_fraction
                            ),
                        )
                    )

                except Exception:

                    logger.exception(
                        "Could not calculate dynamic "
                        "credit interval"
                    )

                    safe_interval = max(
                        MIN_INTERVAL_SECONDS,
                        180,
                    )

                # ------------------------------------------------
                # Respect user-requested interval,
                # but never allow it to be less safe than
                # the calculated interval.
                # ------------------------------------------------

                if args.interval > 0:

                    interval = max(
                        args.interval,
                        safe_interval,
                    )

                else:

                    interval = (
                        safe_interval
                    )

                logger.info(
                    "Cycle used approximately %d credits",
                    estimated_cycle_credits,
                )

                logger.info(
                    "Next collection in %d seconds "
                    "(%.2f minutes)",
                    interval,
                    interval / 60,
                )

                interruptible_sleep(
                    interval
                )

    finally:

        release_lock(
            lock_descriptor
        )

        logger.info(
            "Collector stopped"
        )


if __name__ == "__main__":
    main()
