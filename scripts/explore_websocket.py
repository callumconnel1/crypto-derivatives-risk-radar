import asyncio
import json
import os

from dotenv import load_dotenv
from websockets.asyncio.client import connect

load_dotenv()

API_KEY = os.getenv("CMC_API_KEY")

if API_KEY is None:
    raise RuntimeError("API key was not found")


URI = "wss://pro-stream.coinmarketcap.com/v1"

headers = {
    "X-CMC_PRO_API_KEY": API_KEY,
}

asset_names = {
    1: "Bitcoin",
    1027: "Ethereum",
    5426: "Solana",
}

async def main():

    async with connect(
        URI,
        additional_headers=headers,
    ) as websocket:

        print("Connected to CoinMarketCap")

        subscribe_message = {
            "id": 1,
            "method": "subscribe",
            "channel": "market@crypto_latest_price",
            "params": {
                "crypto_ids": [1, 1027, 5426]
            },
        }

        await websocket.send(
            json.dumps(subscribe_message)
        )

        print("Subscription sent")

        async for raw_message in websocket:

            message = json.loads(raw_message)

            if message.get("type") != "data":
                print(message)
                continue

            data = message["data"]

            id = data["cid"]

            print(
                f"{asset_names.get(id, id)} | "
                f"${data['p']:,.2f} | "
                f"{data['p24h']:+.2f}%"
            )


asyncio.run(main())