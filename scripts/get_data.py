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