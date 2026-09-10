"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";


type MarketAsset = {
  id?: number | null;
  asset: string;
  symbol: string;

  price: number | null;

  volume_24h: number | null;
  market_cap: number | null;

  // Raw CMC percentage-point fields, if retained.
  percent_change_1h?: number | null;
  percent_change_24h?: number | null;

  // Processed decimal-return fields.
  price_change_1h?: number | null;
  price_change_24h?: number | null;

  collected_at?: string | null;
  timestamp?: string | null;
};


const REFRESH_INTERVAL = 15_000;


export default function MarketTable() {
  const [
    assets,
    setAssets,
  ] = useState<MarketAsset[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    refreshing,
    setRefreshing,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );

  const [
    lastUpdated,
    setLastUpdated,
  ] = useState<Date | null>(
    null,
  );


  const timeoutRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  const mountedRef =
    useRef(true);


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
          },
        );


        if (!response.ok) {
          throw new Error(
            `Backend returned HTTP ${response.status}`,
          );
        }


        const result =
          await response.json();


        if (!mountedRef.current) {
          return;
        }


        if (!Array.isArray(result.data)) {
          throw new Error(
            "Backend response did not contain a data array",
          );
        }


        const rows =
          result.data as MarketAsset[];


        setAssets(
          rows,
        );


        setLastUpdated(
          latestTimestamp(
            rows,
          )
          ??
          new Date(),
        );


        setError(null);

      } catch (err) {
        if (!mountedRef.current) {
          return;
        }


        if (err instanceof Error) {
          setError(
            err.message,
          );
        } else {
          setError(
            "Failed to load market data",
          );
        }

      } finally {
        if (mountedRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [API_URL],
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
          REFRESH_INTERVAL,
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
      loadMarketData,
    );

    document.addEventListener(
      "visibilitychange",
      handleVisibilityChange,
    );


    return () => {
      mountedRef.current = false;


      if (timeoutRef.current) {
        clearTimeout(
          timeoutRef.current,
        );
      }


      window.removeEventListener(
        "focus",
        loadMarketData,
      );

      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange,
      );
    };
  }, [loadMarketData]);


  if (
    loading &&
    assets.length === 0
  ) {
    return (
      <div className="border border-[#444] bg-[#0d0d0d] p-6 text-sm text-[#c0c0c0]">
        LOADING SPOT SNAPSHOT...
      </div>
    );
  }


  return (
    <section className="overflow-hidden border border-[#444] bg-[#0b0b0b]">

      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#444] bg-[#171717] px-4 py-3">

        <div>

          <h2 className="text-sm font-black tracking-[0.08em] text-[#f5f5f5]">
            SPOT MARKET SNAPSHOT
          </h2>

          <div className="mt-1 text-xs tracking-wide text-[#999]">
            COLLECTOR-CACHED COINMARKETCAP DATA · FRONTEND DOES NOT CALL CMC DIRECTLY
          </div>

        </div>


        <div className="flex items-center gap-4 text-xs">

          <span
            className={
              error
                ? "font-bold text-[#ff5c5c]"
                : "font-bold text-[#38d996]"
            }
          >
            ● {error ? "ERROR" : "ACTIVE"}
          </span>


          {lastUpdated && (
            <span className="text-[#aaa]">
              {lastUpdated
                .toISOString()
                .slice(11, 19)} UTC
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
        <div className="border-b border-[#5a2c2c] bg-[#170b0b] px-4 py-3 text-sm text-[#ff8080]">
          MARKET DATA ERROR: {error}
        </div>
      )}


      <div className="max-h-[560px] overflow-auto">

        <table className="w-full min-w-[850px] border-collapse text-sm">

          <thead className="sticky top-0 z-20">

            <tr className="bg-[#141414] text-left text-xs text-[#d2d2d2] shadow-[0_1px_0_#3b3b3b]">

              <TableHeader>
                ASSET
              </TableHeader>

              <TableHeader align="right">
                PRICE
              </TableHeader>

              <TableHeader align="right">
                1H
              </TableHeader>

              <TableHeader align="right">
                24H
              </TableHeader>

              <TableHeader align="right">
                VOLUME 24H
              </TableHeader>

              <TableHeader
                align="right"
                last
              >
                MARKET CAP
              </TableHeader>

            </tr>

          </thead>


          <tbody>

            {assets.map(
              (asset) => {
                const change1h =
                  changePercent(
                    asset.price_change_1h,
                    asset.percent_change_1h,
                  );

                const change24h =
                  changePercent(
                    asset.price_change_24h,
                    asset.percent_change_24h,
                  );


                return (
                  <tr
                    key={asset.symbol}
                    className="
                      border-t border-[#333]
                      bg-[#0c0c0c]
                      transition
                      hover:bg-[#171717]
                    "
                  >

                    <td className="border-r border-[#333] px-4 py-3">

                      <div className="font-black text-[#ffffff]">
                        {asset.symbol}
                      </div>

                      <div className="mt-1 text-xs text-[#aaa]">
                        {asset.asset}
                      </div>

                    </td>


                    <td className="border-r border-[#333] px-4 py-3 text-right font-semibold tabular-nums text-[#f0f0f0]">
                      {formatPrice(
                        asset.price,
                      )}
                    </td>


                    <td
                      className={`
                        border-r
                        border-[#333]
                        px-4
                        py-3
                        text-right
                        font-semibold
                        tabular-nums
                        ${changeColour(
                          change1h,
                        )}
                      `}
                    >
                      {formatPercentPoints(
                        change1h,
                      )}
                    </td>


                    <td
                      className={`
                        border-r
                        border-[#333]
                        px-4
                        py-3
                        text-right
                        font-semibold
                        tabular-nums
                        ${changeColour(
                          change24h,
                        )}
                      `}
                    >
                      {formatPercentPoints(
                        change24h,
                      )}
                    </td>


                    <td className="border-r border-[#333] px-4 py-3 text-right tabular-nums text-[#d5d5d5]">
                      {formatCompactUSD(
                        asset.volume_24h,
                      )}
                    </td>


                    <td className="px-4 py-3 text-right tabular-nums text-[#d5d5d5]">
                      {formatCompactUSD(
                        asset.market_cap,
                      )}
                    </td>

                  </tr>
                );
              },
            )}

          </tbody>

        </table>

      </div>

    </section>
  );
}


function TableHeader({
  children,
  align = "left",
  last = false,
}: {
  children: React.ReactNode;
  align?: "left" | "right";
  last?: boolean;
}) {
  return (
    <th
      className={`
        px-4
        py-3
        font-bold
        tracking-wide
        ${
          last
            ? ""
            : "border-r border-[#444]"
        }
        ${
          align === "right"
            ? "text-right"
            : "text-left"
        }
      `}
    >
      {children}
    </th>
  );
}


function finite(
  value: number | null | undefined,
): value is number {
  return (
    value !== null &&
    value !== undefined &&
    Number.isFinite(value)
  );
}


function changePercent(
  processedDecimal:
    number | null | undefined,
  rawPercentagePoints:
    number | null | undefined,
) {
  if (
    finite(
      processedDecimal,
    )
  ) {
    return (
      processedDecimal *
      100
    );
  }

  if (
    finite(
      rawPercentagePoints,
    )
  ) {
    return rawPercentagePoints;
  }

  return null;
}


function changeColour(
  value: number | null,
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


function formatPercentPoints(
  value: number | null,
) {
  if (value === null) {
    return "—";
  }

  const prefix =
    value > 0
      ? "+"
      : "";

  return `${prefix}${value.toFixed(2)}%`;
}


function formatPrice(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  if (value >= 1000) {
    return `$${value.toLocaleString(
      "en-US",
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      },
    )}`;
  }

  if (value >= 1) {
    return `$${value.toFixed(2)}`;
  }

  return `$${value.toFixed(4)}`;
}


function formatCompactUSD(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      style: "currency",
      currency: "USD",
      notation: "compact",
      maximumFractionDigits: 2,
    },
  ).format(value);
}


function latestTimestamp(
  rows: MarketAsset[],
) {
  const times = rows
    .map(
      (row) =>
        row.collected_at ??
        row.timestamp ??
        null,
    )
    .filter(
      (
        value,
      ): value is string =>
        Boolean(value),
    )
    .map(
      (value) =>
        new Date(value),
    )
    .filter(
      (value) =>
        !Number.isNaN(
          value.getTime(),
        ),
    )
    .sort(
      (
        a,
        b,
      ) =>
        a.getTime() -
        b.getTime(),
    );

  return (
    times.at(-1) ??
    null
  );
}
