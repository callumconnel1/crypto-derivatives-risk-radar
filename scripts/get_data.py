import polars as pl
import httpx
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

load_dotenv()

API_KEY = os.getenv("CMC_API_KEY")

if API_KEY is None:
    raise RuntimeError("API key was not found")

BASE_URL = "https://pro-api.coinmarketcap.com"

headers = {
    "X-CMC_PRO_API_KEY": API_KEY,
    "Accept": "application/json",
}


# ------------------------------------------------------------------
# REQUEST / ERROR HANDLING
# ------------------------------------------------------------------

def make_request(FULL_URL: str, params: dict) -> dict:

    try:
        response = httpx.get(
            FULL_URL,
            headers=headers,
            params=params,
            timeout=30.0
        )

    except httpx.TimeoutException as error:
        raise RuntimeError(
            f"CoinMarketCap request timed out: {error}"
        ) from error

    except httpx.ConnectError as error:
        raise RuntimeError(
            f"Could not connect to CoinMarketCap: {error}"
        ) from error

    except httpx.RequestError as error:
        raise RuntimeError(
            f"CoinMarketCap request failed: {error}"
        ) from error

    print("Status code:", response.status_code)

    # Try to decode the CMC response even when the HTTP request failed
    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"CoinMarketCap returned a non-JSON response "
            f"(HTTP {response.status_code})"
        ) from error

    if response.status_code != 200:

        status = data.get("status", {})

        error_code = status.get(
            "error_code",
            response.status_code
        )

        error_message = status.get(
            "error_message",
            "No error message returned"
        )

        if response.status_code == 400:
            raise ValueError(
                f"CMC Bad Request ({error_code}): {error_message}"
            )

        elif response.status_code == 401:
            raise PermissionError(
                f"CMC Authentication Error ({error_code}): "
                f"{error_message}"
            )

        elif response.status_code == 403:
            raise PermissionError(
                f"CMC Forbidden ({error_code}): "
                f"{error_message}"
            )

        elif response.status_code == 404:
            raise RuntimeError(
                f"CMC endpoint not found ({error_code}): "
                f"{error_message}"
            )

        elif response.status_code == 429:

            retry_after = response.headers.get("Retry-After")

            message = (
                f"CMC Rate Limit Exceeded ({error_code}): "
                f"{error_message}"
            )

            if retry_after is not None:
                message += f" Retry after {retry_after} seconds."

            raise RuntimeError(message)

        elif 500 <= response.status_code < 600:
            raise RuntimeError(
                f"CMC Server Error "
                f"(HTTP {response.status_code}, "
                f"CMC {error_code}): {error_message}"
            )

        else:
            raise RuntimeError(
                f"CMC API Error "
                f"(HTTP {response.status_code}, "
                f"CMC {error_code}): {error_message}"
            )

    # HTTP 200, but check CMC's own status object as well
    status = data.get("status", {})

    if status.get("error_code", 0) != 0:
        raise RuntimeError(
            f"CMC API Error ({status.get('error_code')}): "
            f"{status.get('error_message')}"
        )

    return data


# ------------------------------------------------------------------
# HELPER FOR DIFFERENT RESPONSE STRUCTURES
# ------------------------------------------------------------------

def get_asset_list(data: dict, ids: list[int]) -> list[dict]:

    api_data = data["data"]

    # Some CMC endpoints return:
    #
    # "data": [
    #     {...},
    #     {...}
    # ]
    if isinstance(api_data, list):
        return api_data

    # Single asset:
    #
    # "data": {
    #     "id": 1,
    #     "name": "Bitcoin",
    #     ...
    # }
    if "id" in api_data:
        return [api_data]

    # Multiple assets:
    #
    # "data": {
    #     "1": {...},
    #     "1027": {...}
    # }
    assets = []

    for id in ids:

        asset = api_data.get(str(id))

        if asset is None:
            continue

        if isinstance(asset, list):
            assets.extend(asset)
        else:
            assets.append(asset)

    return assets


# ------------------------------------------------------------------
# 1. HISTORICAL QUOTES
# ------------------------------------------------------------------

def get_historical_quotes(
    ids: list[int],
    time_start: str,
    time_end: str,
    interval: str,
    convert: str = "USD"
) -> pl.DataFrame:

    END_URL = "/v3/cryptocurrency/quotes/historical"

    FULL_URL = BASE_URL + END_URL

    id_string = ",".join(map(str, ids))

    params = {
        "id": id_string,
        "time_start": time_start,
        "time_end": time_end,
        "interval": interval,
        "convert": convert,
    }

    data = make_request(FULL_URL, params)

    quotes = {}

    asset_names = []
    symbols = []

    for id in ids:

        asset = data["data"][str(id)]

        quotes[asset["name"]] = asset["quotes"]

        asset_names.append(asset["name"])
        symbols.append(asset["symbol"])

    list_dataframe = []

    for name, symbol in zip(asset_names, symbols):

        asset_quotes = quotes[name]

        dataframe = pl.DataFrame({
            "timestamp": [
                q["timestamp"]
                for q in asset_quotes
            ],
            "asset": [name] * len(asset_quotes),
            "symbol": [symbol] * len(asset_quotes),
            "price": [
                q["quote"][convert]["price"]
                for q in asset_quotes
            ],
        })

        dataframe = dataframe.with_columns(
            pl.col("timestamp")
            .str.to_datetime(time_zone="UTC")
            .alias("timestamp")
        )

        list_dataframe.append(dataframe)

    full_dataframe = pl.concat(list_dataframe)

    return full_dataframe


# ------------------------------------------------------------------
# 2. LATEST QUOTES
# ------------------------------------------------------------------

def get_latest_quotes(
    ids: list[int],
    convert: str = "USD"
) -> pl.DataFrame:

    END_URL = "/v3/cryptocurrency/quotes/latest"

    FULL_URL = BASE_URL + END_URL

    id_string = ",".join(map(str, ids))

    params = {
        "id": id_string,
        "convert": convert,
    }

    data = make_request(FULL_URL, params)

    assets = get_asset_list(data, ids)

    rows = []

    for asset in assets:

        quote_data = asset["quote"]

        # Current V3 API may return quote as a list.
        if isinstance(quote_data, list):

            quote = next(
                q
                for q in quote_data
                if q["symbol"] == convert
            )

        # Keeps parser tolerant if CMC returns keyed quote data.
        else:
            quote = quote_data[convert]

        timestamp = (
            quote.get("last_updated")
            or asset.get("last_updated")
        )

        rows.append({
            "timestamp": timestamp,
            "asset": asset["name"],
            "symbol": asset["symbol"],
            "price": quote["price"],
        })

    full_dataframe = pl.DataFrame(rows)

    full_dataframe = full_dataframe.with_columns(
        pl.col("timestamp")
        .str.to_datetime(time_zone="UTC")
        .alias("timestamp")
    )

    return full_dataframe


# ------------------------------------------------------------------
# 3. HISTORICAL OHLCV
# ------------------------------------------------------------------

def get_historical_ohlcv(
    ids: list[int],
    time_start: str,
    time_end: str,
    time_period: str = "hourly",
    interval: str = "1h",
    convert: str = "USD"
) -> pl.DataFrame:

    END_URL = "/v2/cryptocurrency/ohlcv/historical"

    FULL_URL = BASE_URL + END_URL

    id_string = ",".join(map(str, ids))

    params = {
        "id": id_string,
        "time_start": time_start,
        "time_end": time_end,
        "time_period": time_period,
        "interval": interval,
        "convert": convert,
    }

    data = make_request(FULL_URL, params)

    assets = get_asset_list(data, ids)

    list_dataframe = []

    for asset in assets:

        asset_quotes = asset["quotes"]

        dataframe = pl.DataFrame({
            "timestamp": [
                q["time_open"]
                for q in asset_quotes
            ],
            "asset": [
                asset["name"]
            ] * len(asset_quotes),
            "symbol": [
                asset["symbol"]
            ] * len(asset_quotes),

            "open": [
                q["quote"][convert]["open"]
                for q in asset_quotes
            ],
            "high": [
                q["quote"][convert]["high"]
                for q in asset_quotes
            ],
            "low": [
                q["quote"][convert]["low"]
                for q in asset_quotes
            ],
            "close": [
                q["quote"][convert]["close"]
                for q in asset_quotes
            ],
            "volume": [
                q["quote"][convert]["volume"]
                for q in asset_quotes
            ],
            "market_cap": [
                q["quote"][convert]["market_cap"]
                for q in asset_quotes
            ],
        })

        dataframe = dataframe.with_columns(
            pl.col("timestamp")
            .str.to_datetime(time_zone="UTC")
            .alias("timestamp")
        )

        list_dataframe.append(dataframe)

    full_dataframe = pl.concat(list_dataframe)

    return full_dataframe


# ------------------------------------------------------------------
# 4. LATEST OHLCV
# ------------------------------------------------------------------

def get_latest_ohlcv(
    ids: list[int],
    convert: str = "USD"
) -> pl.DataFrame:

    END_URL = "/v2/cryptocurrency/ohlcv/latest"

    FULL_URL = BASE_URL + END_URL

    id_string = ",".join(map(str, ids))

    params = {
        "id": id_string,
        "convert": convert,
    }

    data = make_request(FULL_URL, params)

    assets = get_asset_list(data, ids)

    rows = []

    for asset in assets:

        quote = asset["quote"][convert]

        rows.append({
            "timestamp": asset["last_updated"],
            "asset": asset["name"],
            "symbol": asset["symbol"],
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "volume": quote["volume"],
        })

    full_dataframe = pl.DataFrame(rows)

    full_dataframe = full_dataframe.with_columns(
        pl.col("timestamp")
        .str.to_datetime(time_zone="UTC")
        .alias("timestamp")
    )

    return full_dataframe


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------

if __name__ == "__main__":

    ids = [1, 1027, 5426]

    start = "2026-08-07"
    end = "2026-08-14"

    interval = "5m"

    data = get_historical_quotes(
        ids,
        start,
        end,
        interval
    )

    print(data.head(20))

import math
import os
import time
from typing import Any

import httpx
import polars as pl
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("CMC_API_KEY")

if API_KEY is None:
    raise RuntimeError("API key was not found")


BASE_URL = "https://pro-api.coinmarketcap.com"

headers = {
    "X-CMC_PRO_API_KEY": API_KEY,
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 30.0


# ============================================================
# EXCEPTIONS
# ============================================================

class CMCAPIError(RuntimeError):
    pass


class CMCRateLimitError(CMCAPIError):
    pass


class CMCCreditLimitError(CMCAPIError):
    pass


# ============================================================
# REQUEST HANDLING
# ============================================================

def make_request(
    END_URL: str,
    params: dict | None = None,
    client: httpx.Client | None = None,
    max_retries: int = 5,
) -> dict:

    FULL_URL = BASE_URL + END_URL

    owns_client = client is None

    if client is None:
        client = httpx.Client(timeout=REQUEST_TIMEOUT)

    try:

        for attempt in range(max_retries):

            try:

                response = client.get(
                    FULL_URL,
                    headers=headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )

            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.RequestError,
            ) as error:

                if attempt == max_retries - 1:
                    raise CMCAPIError(
                        f"CMC request failed after {max_retries} attempts: {error}"
                    ) from error

                wait = min(2 ** attempt, 30)

                time.sleep(wait)

                continue

            try:
                data = response.json()

            except ValueError as error:

                raise CMCAPIError(
                    f"CMC returned non-JSON response "
                    f"(HTTP {response.status_code})"
                ) from error

            status = data.get("status", {})

            error_code = str(
                status.get(
                    "error_code",
                    response.status_code,
                )
            )

            error_message = status.get(
                "error_message",
                "",
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:

                if error_code not in ("0", "None"):
                    raise CMCAPIError(
                        f"CMC API error {error_code}: "
                        f"{error_message}"
                    )

                return data

            # ------------------------------------------------
            # BAD REQUEST
            # ------------------------------------------------

            if response.status_code == 400:

                raise CMCAPIError(
                    f"CMC bad request ({error_code}): "
                    f"{error_message}"
                )

            # ------------------------------------------------
            # AUTHENTICATION / PLAN ACCESS
            # ------------------------------------------------

            if response.status_code == 401:

                raise CMCAPIError(
                    f"CMC authentication failed ({error_code}): "
                    f"{error_message}"
                )

            if response.status_code == 403:

                raise CMCAPIError(
                    f"CMC endpoint unavailable to this plan "
                    f"({error_code}): {error_message}"
                )

            if response.status_code == 404:

                raise CMCAPIError(
                    f"CMC endpoint not found ({error_code}): "
                    f"{error_message}"
                )

            # ------------------------------------------------
            # RATE / CREDIT LIMITS
            # ------------------------------------------------

            if response.status_code == 429:

                # Minute rate limit
                if error_code == "1007":

                    retry_after = response.headers.get(
                        "Retry-After"
                    )

                    if retry_after is not None:

                        try:
                            wait = float(retry_after)

                        except ValueError:
                            wait = min(2 ** attempt, 60)

                    else:
                        wait = min(2 ** attempt, 60)

                    if attempt == max_retries - 1:

                        raise CMCRateLimitError(
                            f"CMC minute rate limit exceeded: "
                            f"{error_message}"
                        )

                    time.sleep(wait)

                    continue

                # Monthly/daily credit limit
                if error_code == "1008":

                    raise CMCCreditLimitError(
                        f"CMC credit limit reached: "
                        f"{error_message}"
                    )

                if attempt == max_retries - 1:

                    raise CMCRateLimitError(
                        f"CMC returned HTTP 429: "
                        f"{error_message}"
                    )

                time.sleep(min(2 ** attempt, 60))

                continue

            # ------------------------------------------------
            # SERVER ERRORS
            # ------------------------------------------------

            if 500 <= response.status_code < 600:

                if attempt == max_retries - 1:

                    raise CMCAPIError(
                        f"CMC server error "
                        f"(HTTP {response.status_code}): "
                        f"{error_message}"
                    )

                time.sleep(min(2 ** attempt, 30))

                continue

            raise CMCAPIError(
                f"CMC request failed "
                f"(HTTP {response.status_code}, "
                f"CMC {error_code}): "
                f"{error_message}"
            )

        raise CMCAPIError(
            "CMC request exhausted retry attempts"
        )

    finally:

        if owns_client:
            client.close()


# ============================================================
# HELPERS
# ============================================================

def _select_quote(
    quote_data: Any,
    convert: str,
) -> dict:

    if quote_data is None:
        return {}

    if isinstance(quote_data, list):

        for quote in quote_data:

            symbol = (
                quote.get("convert_symbol")
                or quote.get("symbol")
            )

            if symbol == convert:
                return quote

        if len(quote_data) > 0:
            return quote_data[0]

        return {}

    if isinstance(quote_data, dict):

        if convert in quote_data:
            return quote_data[convert]

        for quote in quote_data.values():

            if not isinstance(quote, dict):
                continue

            symbol = (
                quote.get("convert_symbol")
                or quote.get("symbol")
            )

            if symbol == convert:
                return quote

    return {}


def _iter_assets(
    api_data: Any,
    ids: list[int] | None = None,
) -> list[dict]:

    if isinstance(api_data, list):
        return api_data

    if not isinstance(api_data, dict):
        return []

    if "id" in api_data:
        return [api_data]

    assets = []

    if ids is not None:

        for id in ids:

            asset = api_data.get(str(id))

            if asset is None:
                continue

            if isinstance(asset, list):
                assets.extend(asset)

            else:
                assets.append(asset)

        return assets

    for asset in api_data.values():

        if isinstance(asset, dict):
            assets.append(asset)

        elif isinstance(asset, list):
            assets.extend(asset)

    return assets


def _parse_timestamp(
    dataframe: pl.DataFrame,
    column: str = "timestamp",
) -> pl.DataFrame:

    if (
        dataframe.is_empty()
        or column not in dataframe.columns
    ):
        return dataframe

    if dataframe.schema[column] == pl.String:

        dataframe = dataframe.with_columns(
            pl.col(column)
            .str.to_datetime(
                time_zone="UTC",
                strict=False,
            )
            .alias(column)
        )

    return dataframe


def _add_liquidation_features(
    dataframe: pl.DataFrame,
) -> pl.DataFrame:

    if dataframe.is_empty():
        return dataframe

    expressions = []

    for horizon in ["1h", "4h", "24h"]:

        total = pl.col(
            f"total_liquidations_{horizon}"
        )

        long = pl.col(
            f"long_liquidations_{horizon}"
        )

        short = pl.col(
            f"short_liquidations_{horizon}"
        )

        expressions.extend([
            pl.when(total > 0)
            .then(
                (long - short) / total
            )
            .otherwise(None)
            .alias(
                f"liquidation_imbalance_{horizon}"
            ),

            pl.when(total > 0)
            .then(
                long / total
            )
            .otherwise(None)
            .alias(
                f"long_liquidation_share_{horizon}"
            ),

            pl.when(total > 0)
            .then(
                short / total
            )
            .otherwise(None)
            .alias(
                f"short_liquidation_share_{horizon}"
            ),
        ])

    dataframe = dataframe.with_columns(
        expressions
    )

    previous_3h_average = (
        (
            pl.col("total_liquidations_4h")
            - pl.col("total_liquidations_1h")
        )
        / 3
    )

    average_24h_hour = (
        pl.col("total_liquidations_24h")
        / 24
    )

    dataframe = dataframe.with_columns(
        pl.when(previous_3h_average > 0)
        .then(
            pl.col("total_liquidations_1h")
            / previous_3h_average
        )
        .otherwise(None)
        .alias(
            "liquidation_intensity_1h_vs_prev3h"
        ),

        pl.when(average_24h_hour > 0)
        .then(
            pl.col("total_liquidations_1h")
            / average_24h_hour
        )
        .otherwise(None)
        .alias(
            "liquidation_intensity_1h_vs_24h"
        ),
    )

    return dataframe


# ============================================================
# KEY / USAGE INFORMATION
# ============================================================

def get_key_info(
    client: httpx.Client | None = None,
) -> dict:

    data = make_request(
        "/v1/key/info",
        client=client,
    )

    return data["data"]


# ============================================================
# HISTORICAL QUOTES
# ============================================================

def get_historical_quotes(
    ids: list[int],
    time_start: str,
    time_end: str,
    interval: str,
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v3/cryptocurrency/quotes/historical"
    )

    id_string = ",".join(
        map(str, ids)
    )

    params = {
        "id": id_string,
        "time_start": time_start,
        "time_end": time_end,
        "interval": interval,
        "convert": convert,
    }

    data = make_request(
        END_URL,
        params=params,
        client=client,
    )

    quotes = {}

    asset_names = []
    symbols = []

    for id in ids:

        asset = data["data"].get(str(id))

        if asset is None:
            continue

        quotes[
            asset["name"]
        ] = asset["quotes"]

        asset_names.append(
            asset["name"]
        )

        symbols.append(
            asset["symbol"]
        )

    list_dataframe = []

    for name, symbol in zip(
        asset_names,
        symbols,
    ):

        asset_quotes = quotes[name]

        dataframe = pl.DataFrame({
            "timestamp": [
                q["timestamp"]
                for q in asset_quotes
            ],

            "asset": [
                name
            ] * len(asset_quotes),

            "symbol": [
                symbol
            ] * len(asset_quotes),

            "price": [
                q["quote"][convert]["price"]
                for q in asset_quotes
            ],
        })

        dataframe = _parse_timestamp(
            dataframe
        )

        list_dataframe.append(
            dataframe
        )

    if not list_dataframe:
        return pl.DataFrame()

    return pl.concat(
        list_dataframe,
        how="diagonal_relaxed",
    )


# ============================================================
# LATEST QUOTES
# ============================================================

def get_latest_quotes(
    ids: list[int],
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v3/cryptocurrency/quotes/latest"
    )

    params = {
        "id": ",".join(
            map(str, ids)
        ),
        "convert": convert,
    }

    data = make_request(
        END_URL,
        params=params,
        client=client,
    )

    assets = _iter_assets(
        data["data"],
        ids,
    )

    rows = []

    for asset in assets:

        quote = _select_quote(
            asset.get("quote"),
            convert,
        )

        if not quote:
            continue

        rows.append({
            "timestamp": (
                quote.get("last_updated")
                or asset.get("last_updated")
            ),

            "id": asset.get("id"),

            "asset": asset.get("name"),

            "symbol": asset.get("symbol"),

            "price": quote.get("price"),

            "volume_24h": quote.get(
                "volume_24h"
            ),

            "cex_volume_24h": quote.get(
                "cex_volume_24h"
            ),

            "dex_volume_24h": quote.get(
                "dex_volume_24h"
            ),

            "volume_change_24h": quote.get(
                "volume_change_24h"
            ),

            "percent_change_1h": quote.get(
                "percent_change_1h"
            ),

            "percent_change_24h": quote.get(
                "percent_change_24h"
            ),

            "percent_change_7d": quote.get(
                "percent_change_7d"
            ),

            "market_cap": quote.get(
                "market_cap"
            ),

            "market_cap_dominance": quote.get(
                "market_cap_dominance"
            ),

            "fully_diluted_market_cap": quote.get(
                "fully_diluted_market_cap"
            ),

            "circulating_supply": asset.get(
                "circulating_supply"
            ),

            "total_supply": asset.get(
                "total_supply"
            ),

            "max_supply": asset.get(
                "max_supply"
            ),
        })

    dataframe = pl.DataFrame(rows)

    return _parse_timestamp(
        dataframe
    )


# ============================================================
# HISTORICAL OHLCV
# ============================================================

def get_historical_ohlcv(
    ids: list[int],
    time_start: str,
    time_end: str,
    time_period: str = "hourly",
    interval: str = "1h",
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v2/cryptocurrency/ohlcv/historical"
    )

    params = {
        "id": ",".join(
            map(str, ids)
        ),
        "time_start": time_start,
        "time_end": time_end,
        "time_period": time_period,
        "interval": interval,
        "convert": convert,
    }

    data = make_request(
        END_URL,
        params=params,
        client=client,
    )

    assets = _iter_assets(
        data["data"],
        ids,
    )

    frames = []

    for asset in assets:

        quotes = asset.get(
            "quotes",
            []
        )

        rows = []

        for quote_data in quotes:

            quote = _select_quote(
                quote_data.get("quote"),
                convert,
            )

            if not quote:
                continue

            rows.append({
                "timestamp": (
                    quote_data.get("time_open")
                    or quote.get("timestamp")
                ),

                "id": asset.get("id"),

                "asset": asset.get("name"),

                "symbol": asset.get("symbol"),

                "open": quote.get("open"),

                "high": quote.get("high"),

                "low": quote.get("low"),

                "close": quote.get("close"),

                "volume": quote.get("volume"),

                "market_cap": quote.get(
                    "market_cap"
                ),
            })

        if rows:

            frame = pl.DataFrame(rows)

            frame = _parse_timestamp(
                frame
            )

            frames.append(
                frame
            )

    if not frames:
        return pl.DataFrame()

    return pl.concat(
        frames,
        how="diagonal_relaxed",
    )


# ============================================================
# LATEST OHLCV
# ============================================================

def get_latest_ohlcv(
    ids: list[int],
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v2/cryptocurrency/ohlcv/latest"
    )

    params = {
        "id": ",".join(
            map(str, ids)
        ),
        "convert": convert,
    }

    data = make_request(
        END_URL,
        params=params,
        client=client,
    )

    assets = _iter_assets(
        data["data"],
        ids,
    )

    rows = []

    for asset in assets:

        quote = _select_quote(
            asset.get("quote"),
            convert,
        )

        if not quote:
            continue

        rows.append({
            "timestamp": (
                quote.get("last_updated")
                or asset.get("last_updated")
            ),

            "id": asset.get("id"),

            "asset": asset.get("name"),

            "symbol": asset.get("symbol"),

            "open": quote.get("open"),

            "high": quote.get("high"),

            "low": quote.get("low"),

            "close": quote.get("close"),

            "volume": quote.get("volume"),

            "market_cap": quote.get(
                "market_cap"
            ),
        })

    dataframe = pl.DataFrame(rows)

    return _parse_timestamp(
        dataframe
    )


# ============================================================
# DERIVATIVE MARKET PAIRS BY CRYPTOCURRENCY
# ============================================================

def get_derivative_market_pairs(
    ids: list[int],
    category: str = "all",
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v5/cryptocurrency/derivatives/"
        "market-pairs/list/latest"
    )

    rows = []

    for id in ids:

        start = 1
        limit = 250

        while True:

            params = {
                "crypto_id": id,
                "start": start,
                "limit": limit,
                "category": category,
                "convert": convert,
            }

            data = make_request(
                END_URL,
                params=params,
                client=client,
            )

            crypto = data["data"]

            market_pairs = crypto.get(
                "market_pairs",
                [],
            )

            for market in market_pairs:

                exchange = market.get(
                    "exchange",
                    {},
                )

                base = market.get(
                    "market_pair_base",
                    {},
                )

                quote_currency = market.get(
                    "market_pair_quote",
                    {},
                )

                reported = _select_quote(
                    market.get(
                        "exchange_reported_quotes"
                    ),
                    convert,
                )

                normalized = _select_quote(
                    market.get("quotes"),
                    convert,
                )

                rows.append({
                    "timestamp": (
                        reported.get(
                            "last_updated"
                        )
                        or normalized.get(
                            "last_updated"
                        )
                    ),

                    "crypto_id": crypto.get(
                        "crypto_id"
                    ),

                    "asset": crypto.get(
                        "crypto_name"
                    ),

                    "symbol": crypto.get(
                        "symbol"
                    ),

                    "market_id": market.get(
                        "market_id"
                    ),

                    "market_pair": (
                        market.get(
                            "market_pair_symbol"
                        )
                        or market.get(
                            "market_pair"
                        )
                    ),

                    "category": market.get(
                        "category"
                    ),

                    "fee_type": market.get(
                        "fee_type"
                    ),

                    "exchange_id": exchange.get(
                        "exchange_id"
                    ),

                    "exchange": exchange.get(
                        "exchange_name"
                    ),

                    "exchange_slug": exchange.get(
                        "exchange_slug"
                    ),

                    "base_id": base.get(
                        "crypto_id"
                    ),

                    "base_symbol": base.get(
                        "symbol"
                    ),

                    "quote_id": quote_currency.get(
                        "crypto_id"
                    ),

                    "quote_symbol": quote_currency.get(
                        "symbol"
                    ),

                    "reported_price": reported.get(
                        "price"
                    ),

                    "volume_24h_base": reported.get(
                        "volume_24h_base"
                    ),

                    "volume_24h_quote": reported.get(
                        "volume_24h_quote"
                    ),

                    "price": (
                        normalized.get("price")
                        if normalized
                        else reported.get("price")
                    ),

                    "volume_24h": normalized.get(
                        "volume_24h"
                    ),

                    "open_interest": (
                        reported.get(
                            "open_interest"
                        )
                        if reported.get(
                            "open_interest"
                        ) is not None
                        else normalized.get(
                            "open_interest"
                        )
                    ),

                    "index_price": reported.get(
                        "index_price"
                    ),

                    "index_basis": reported.get(
                        "index_basis"
                    ),

                    "funding_rate": reported.get(
                        "funding_rate"
                    ),

                    "outlier_detected": market.get(
                        "outlier_detected",
                        False,
                    ),

                    "exclusions": (
                        market.get("exclusions")
                        or []
                    ),
                })

            total = crypto.get(
                "num_market_pairs",
                len(market_pairs),
            )

            if (
                not market_pairs
                or start - 1 + len(market_pairs)
                >= total
            ):
                break

            start += limit

    dataframe = pl.DataFrame(rows)

    return _parse_timestamp(
        dataframe
    )


# ============================================================
# DERIVATIVES EXCHANGE SUMMARY
# ============================================================

def get_derivatives_exchanges(
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v5/exchange/derivatives/list"
    )

    params = {
        "start": 1,
        "limit": 5000,
        "sort": "volume_24h",
        "sort_dir": "desc",
        "convert": convert,
    }

    data = make_request(
        END_URL,
        params=params,
        client=client,
    )

    exchanges = data["data"].get(
        "exchanges",
        [],
    )

    rows = []

    for exchange in exchanges:

        quote = _select_quote(
            exchange.get("quotes"),
            convert,
        )

        rows.append({
            "timestamp": (
                quote.get("last_updated")
                or exchange.get("last_updated")
            ),

            "exchange_id": exchange.get(
                "exchange_id"
            ),

            "exchange": exchange.get(
                "exchange_name"
            ),

            "exchange_slug": exchange.get(
                "exchange_slug"
            ),

            "rank": exchange.get("rank"),

            "num_market_pairs": exchange.get(
                "num_market_pairs"
            ),

            "traffic_score": exchange.get(
                "traffic_score"
            ),

            "exchange_score": exchange.get(
                "exchange_score"
            ),

            "liquidity_score": exchange.get(
                "liquidity_score"
            ),

            "open_interest": quote.get(
                "open_interest"
            ),

            "open_interest_usd": quote.get(
                "open_interest_usd"
            ),

            "derivative_volume": quote.get(
                "derivative_volume"
            ),

            "derivative_volume_usd": quote.get(
                "derivative_volume_usd"
            ),

            "maker_fees": quote.get(
                "maker_fees"
            ),

            "taker_fees": quote.get(
                "taker_fees"
            ),
        })

    dataframe = pl.DataFrame(rows)

    return _parse_timestamp(
        dataframe
    )


# ============================================================
# LIQUIDATIONS BY CRYPTOCURRENCY
# ============================================================

def get_crypto_liquidations(
    ids: list[int],
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v5/derivatives/liquidations/"
        "cryptocurrency/list/latest"
    )

    rows = []

    # Endpoint limit is 250
    chunk_size = 250

    for chunk_start in range(
        0,
        len(ids),
        chunk_size,
    ):

        chunk = ids[
            chunk_start:
            chunk_start + chunk_size
        ]

        params = {
            "crypto_id": ",".join(
                map(str, chunk)
            ),
            "limit": 250,
            "skip_invalid": "true",
            "convert": convert,
        }

        data = make_request(
            END_URL,
            params=params,
            client=client,
        )

        cryptocurrencies = (
            data["data"].get(
                "cryptocurrencies",
                [],
            )
        )

        for crypto in cryptocurrencies:

            quote = _select_quote(
                crypto.get("quotes"),
                convert,
            )

            if not quote:
                continue

            rows.append({
                "timestamp": quote.get(
                    "last_updated"
                ),

                "crypto_id": crypto.get(
                    "crypto_id"
                ),

                "asset": crypto.get(
                    "name"
                ),

                "symbol": crypto.get(
                    "symbol"
                ),

                "cmc_rank": crypto.get(
                    "cmc_rank"
                ),

                "total_liquidations_1h":
                    quote.get(
                        "total_liquidations_1h"
                    ),

                "long_liquidations_1h":
                    quote.get(
                        "long_liquidations_1h"
                    ),

                "short_liquidations_1h":
                    quote.get(
                        "short_liquidations_1h"
                    ),

                "total_liquidations_4h":
                    quote.get(
                        "total_liquidations_4h"
                    ),

                "long_liquidations_4h":
                    quote.get(
                        "long_liquidations_4h"
                    ),

                "short_liquidations_4h":
                    quote.get(
                        "short_liquidations_4h"
                    ),

                "total_liquidations_24h":
                    quote.get(
                        "total_liquidations_24h"
                    ),

                "long_liquidations_24h":
                    quote.get(
                        "long_liquidations_24h"
                    ),

                "short_liquidations_24h":
                    quote.get(
                        "short_liquidations_24h"
                    ),
            })

    dataframe = pl.DataFrame(rows)

    dataframe = _parse_timestamp(
        dataframe
    )

    return _add_liquidation_features(
        dataframe
    )


# ============================================================
# LIQUIDATIONS BY EXCHANGE
# ============================================================

def get_exchange_liquidations(
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v5/derivatives/liquidations/"
        "exchange/list/latest"
    )

    rows = []

    start = 1
    limit = 250

    while True:

        params = {
            "start": start,
            "limit": limit,
            "sort": "total_liquidations_24h",
            "sort_dir": "desc",
            "convert": convert,
        }

        data = make_request(
            END_URL,
            params=params,
            client=client,
        )

        result = data["data"]

        exchanges = result.get(
            "exchanges",
            [],
        )

        for exchange in exchanges:

            quote = _select_quote(
                exchange.get("quotes"),
                convert,
            )

            if not quote:
                continue

            rows.append({
                "timestamp": quote.get(
                    "last_updated"
                ),

                "exchange_id": exchange.get(
                    "exchange_id"
                ),

                "exchange": exchange.get(
                    "name"
                ),

                "slug": exchange.get(
                    "slug"
                ),

                "total_liquidations_1h":
                    quote.get(
                        "total_liquidations_1h"
                    ),

                "long_liquidations_1h":
                    quote.get(
                        "long_liquidations_1h"
                    ),

                "short_liquidations_1h":
                    quote.get(
                        "short_liquidations_1h"
                    ),

                "total_liquidations_4h":
                    quote.get(
                        "total_liquidations_4h"
                    ),

                "long_liquidations_4h":
                    quote.get(
                        "long_liquidations_4h"
                    ),

                "short_liquidations_4h":
                    quote.get(
                        "short_liquidations_4h"
                    ),

                "total_liquidations_24h":
                    quote.get(
                        "total_liquidations_24h"
                    ),

                "long_liquidations_24h":
                    quote.get(
                        "long_liquidations_24h"
                    ),

                "short_liquidations_24h":
                    quote.get(
                        "short_liquidations_24h"
                    ),
            })

        if (
            not result.get("has_more")
            or not exchanges
        ):
            break

        start += limit

    dataframe = pl.DataFrame(rows)

    dataframe = _parse_timestamp(
        dataframe
    )

    dataframe = _add_liquidation_features(
        dataframe
    )

    if dataframe.is_empty():
        return dataframe

    share_expressions = []

    for horizon in [
        "1h",
        "4h",
        "24h",
    ]:

        column = (
            f"total_liquidations_{horizon}"
        )

        total = pl.col(column).sum()

        share_expressions.append(
            pl.when(total > 0)
            .then(
                pl.col(column) / total
            )
            .otherwise(None)
            .alias(
                f"tracked_exchange_share_{horizon}"
            )
        )

    return dataframe.with_columns(
        share_expressions
    )


# ============================================================
# GLOBAL LIQUIDATIONS
# ============================================================

def get_global_liquidations(
    convert: str = "USD",
    client: httpx.Client | None = None,
) -> pl.DataFrame:

    END_URL = (
        "/v5/derivatives/liquidations/"
        "quotes/latest"
    )

    params = {
        "convert": convert,
    }

    data = make_request(
        END_URL,
        params=params,
        client=client,
    )

    quote = _select_quote(
        data["data"].get("quotes"),
        convert,
    )

    if not quote:
        return pl.DataFrame()

    dataframe = pl.DataFrame({
        "timestamp": [
            quote.get("last_updated")
        ],

        "total_liquidations_1h": [
            quote.get(
                "total_liquidations_1h"
            )
        ],

        "long_liquidations_1h": [
            quote.get(
                "long_liquidations_1h"
            )
        ],

        "short_liquidations_1h": [
            quote.get(
                "short_liquidations_1h"
            )
        ],

        "total_liquidations_4h": [
            quote.get(
                "total_liquidations_4h"
            )
        ],

        "long_liquidations_4h": [
            quote.get(
                "long_liquidations_4h"
            )
        ],

        "short_liquidations_4h": [
            quote.get(
                "short_liquidations_4h"
            )
        ],

        "total_liquidations_24h": [
            quote.get(
                "total_liquidations_24h"
            )
        ],

        "long_liquidations_24h": [
            quote.get(
                "long_liquidations_24h"
            )
        ],

        "short_liquidations_24h": [
            quote.get(
                "short_liquidations_24h"
            )
        ],
    })

    dataframe = _parse_timestamp(
        dataframe
    )

    return _add_liquidation_features(
        dataframe
    )