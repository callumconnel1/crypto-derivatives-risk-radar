"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";


type MarketAsset = {
  timestamp: string;
  id: number;
  asset: string;
  symbol: string;

  price: number;

  volume_24h: number | null;
  percent_change_1h: number | null;
  percent_change_24h: number | null;

  market_cap: number | null;
};


const REFRESH_INTERVAL = 15_000;


export default function MarketTable() {
  const [assets, setAssets] = useState<MarketAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [lastUpdated, setLastUpdated] =
    useState<Date | null>(null);

  const timeoutRef =
    useRef<ReturnType<typeof setTimeout> | null>(null);

  const mountedRef = useRef(true);

  const API_URL =
    process.env.NEXT_PUBLIC_API_URL ??
    "http://127.0.0.1:8000";


  const loadMarketData = useCallback(
    async () => {
      try {
        setRefreshing(true);

        const response = await fetch(
          `${API_URL}/api/market/latest?t=${Date.now()}`,
          {
            method: "GET",
            cache: "no-store",

            headers: {
              Accept: "application/json",
            },
          }
        );

        if (!response.ok) {
          throw new Error(
            `Backend returned HTTP ${response.status}`
          );
        }

        const result = await response.json();

        if (!mountedRef.current) {
          return;
        }

        if (!Array.isArray(result.data)) {
          throw new Error(
            "Backend response did not contain a data array"
          );
        }

        setAssets(result.data);

        setLastUpdated(
          new Date()
        );

        setError(null);
      } catch (err) {
        if (!mountedRef.current) {
          return;
        }

        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError(
            "Failed to load market data"
          );
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [API_URL]
  );


  useEffect(() => {
    mountedRef.current = true;

    async function poll() {
      await loadMarketData();

      if (!mountedRef.current) {
        return;
      }

      timeoutRef.current =
        setTimeout(
          poll,
          REFRESH_INTERVAL
        );
    }

    poll();


    function handleVisibilityChange() {
      if (
        document.visibilityState === "visible"
      ) {
        loadMarketData();
      }
    }


    window.addEventListener(
      "focus",
      loadMarketData
    );

    document.addEventListener(
      "visibilitychange",
      handleVisibilityChange
    );


    return () => {
      mountedRef.current = false;

      if (timeoutRef.current) {
        clearTimeout(
          timeoutRef.current
        );
      }

      window.removeEventListener(
        "focus",
        loadMarketData
      );

      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange
      );
    };
  }, [loadMarketData]);


  if (
    loading &&
    assets.length === 0
  ) {
    return (
      <div className="border border-[#444] bg-[#0d0d0d] p-6 text-sm text-[#c0c0c0]">
        LOADING MARKET DATA...
      </div>
    );
  }


  return (
    <section>
      <div className="mb-4 flex items-end justify-between gap-4">

        <div>
          <h2 className="text-base font-bold tracking-wide text-[#f5f5f5]">
            LIVE MARKET DATA
          </h2>

          <div className="mt-1 text-xs tracking-wide text-[#a0a0a0]">
            COINMARKETCAP SPOT MARKET SNAPSHOT
          </div>
        </div>


        <div className="flex items-center gap-4 text-xs">

          <span
            className={
              error
                ? "text-[#ff5c5c]"
                : "text-[#38d996]"
            }
          >
            ● {error ? "ERROR" : "LIVE"}
          </span>


          {lastUpdated && (
            <span className="text-[#aaa]">
              UPDATED{" "}
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}


          <button
            onClick={loadMarketData}
            disabled={refreshing}
            className="
              border border-[#555]
              bg-[#111]
              px-4 py-2
              text-xs
              font-semibold
              tracking-wide
              text-[#ddd]
              transition
              hover:border-[#888]
              hover:bg-[#181818]
              hover:text-white
              disabled:cursor-wait
              disabled:opacity-50
            "
          >
            {refreshing
              ? "UPDATING..."
              : "REFRESH"}
          </button>

        </div>
      </div>


      {error && (
        <div className="mb-3 border border-[#ff5c5c] bg-[#170b0b] px-4 py-3 text-sm text-[#ff8080]">
          MARKET DATA ERROR: {error}
        </div>
      )}


      <div className="overflow-x-auto border border-[#444]">

        <table className="w-full border-collapse text-sm">

          <thead>
            <tr className="bg-[#191919] text-left text-[#e0e0e0]">

              <TableHeader>
                ASSET
              </TableHeader>

              <TableHeader>
                PRICE
              </TableHeader>

              <TableHeader>
                1H
              </TableHeader>

              <TableHeader>
                24H
              </TableHeader>

              <TableHeader>
                VOLUME 24H
              </TableHeader>

              <th className="px-4 py-3 font-bold tracking-wide">
                MARKET CAP
              </th>

            </tr>
          </thead>


          <tbody>

            {assets.map((asset) => (
              <tr
                key={asset.id}
                className="
                  border-t border-[#333]
                  bg-[#0c0c0c]
                  transition
                  hover:bg-[#171717]
                "
              >

                <td className="border-r border-[#333] px-4 py-4">

                  <div className="font-bold text-[#ffffff]">
                    {asset.symbol}
                  </div>

                  <div className="mt-1 text-xs text-[#aaa]">
                    {asset.asset}
                  </div>

                </td>


                <td className="border-r border-[#333] px-4 py-4 font-medium text-[#ededed]">
                  {formatPrice(
                    asset.price
                  )}
                </td>


                <td
                  className={`
                    border-r
                    border-[#333]
                    px-4
                    py-4
                    font-medium
                    ${changeColour(
                      asset.percent_change_1h
                    )}
                  `}
                >
                  {formatPercent(
                    asset.percent_change_1h
                  )}
                </td>


                <td
                  className={`
                    border-r
                    border-[#333]
                    px-4
                    py-4
                    font-medium
                    ${changeColour(
                      asset.percent_change_24h
                    )}
                  `}
                >
                  {formatPercent(
                    asset.percent_change_24h
                  )}
                </td>


                <td className="border-r border-[#333] px-4 py-4 text-[#d5d5d5]">
                  {formatCompactUSD(
                    asset.volume_24h
                  )}
                </td>


                <td className="px-4 py-4 text-[#d5d5d5]">
                  {formatCompactUSD(
                    asset.market_cap
                  )}
                </td>

              </tr>
            ))}

          </tbody>
        </table>
      </div>
    </section>
  );
}


function TableHeader({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <th className="border-r border-[#444] px-4 py-3 font-bold tracking-wide">
      {children}
    </th>
  );
}


function changeColour(
  value: number | null
) {
  if (value === null) {
    return "text-[#aaa]";
  }

  if (value > 0) {
    return "text-[#38d996]";
  }

  if (value < 0) {
    return "text-[#ff6666]";
  }

  return "text-[#bbb]";
}


function formatPercent(
  value: number | null
) {
  if (value === null) {
    return "—";
  }

  const prefix =
    value > 0 ? "+" : "";

  return `${prefix}${value.toFixed(2)}%`;
}


function formatPrice(
  value: number
) {
  if (value >= 1000) {
    return `$${value.toLocaleString(
      "en-US",
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }
    )}`;
  }

  if (value >= 1) {
    return `$${value.toFixed(2)}`;
  }

  return `$${value.toFixed(4)}`;
}


function formatCompactUSD(
  value: number | null
) {
  if (value === null) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      style: "currency",
      currency: "USD",
      notation: "compact",
      maximumFractionDigits: 2,
    }
  ).format(value);
}