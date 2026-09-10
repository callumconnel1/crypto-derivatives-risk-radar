"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";


type VolatilityAsset = {
  timestamp: string;

  asset: string | null;
  symbol: string;

  price: number | null;

  realized_vol_1h: number | null;
  realized_vol_4h: number | null;
  realized_vol_24h: number | null;

  vol_ratio_1h_vs_24h: number | null;
  vol_ratio_4h_vs_24h: number | null;

  vol_percentile_24h: number | null;

  power_law_vol_forecast: number | null;
  ewma_vol_forecast: number | null;

  model_disagreement: number | null;

  power_law_alpha: number | null;
  power_law_beta: number | null;
  power_law_nu: number | null;

  ewma_lambda: number | null;

  calculated_at?: string | null;
};


const REFRESH_INTERVAL = 15_000;


export default function VolatilityPanel() {
  const [
    data,
    setData,
  ] = useState<VolatilityAsset[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

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


  const loadData = useCallback(
    async () => {
      try {
        const response = await fetch(
          `${API_URL}/api/volatility/latest?t=${Date.now()}`,
          {
            cache: "no-store",
          },
        );


        if (!response.ok) {
          throw new Error(
            `Backend returned HTTP ${response.status}`,
          );
        }


        const result =
          await response.json();


        if (!Array.isArray(result.data)) {
          throw new Error(
            "Invalid volatility response",
          );
        }


        if (!mountedRef.current) {
          return;
        }


        const rows =
          result.data as VolatilityAsset[];


        setData(
          rows,
        );


        setLastUpdated(
          latestCalculatedAt(
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
            "Failed to load volatility data",
          );
        }

      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [API_URL],
  );


  useEffect(() => {
    mountedRef.current = true;


    async function poll() {
      await loadData();


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


    return () => {
      mountedRef.current = false;


      if (timeoutRef.current) {
        clearTimeout(
          timeoutRef.current,
        );
      }
    };
  }, [loadData]);


  if (
    loading &&
    data.length === 0
  ) {
    return (
      <div className="border border-[#444] bg-[#0d0d0d] p-6 text-sm text-[#bbb]">
        LOADING VOLATILITY ENGINE...
      </div>
    );
  }


  return (
    <section className="overflow-hidden border border-[#444] bg-[#090909]">

      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#444] bg-[#171717] px-4 py-3">

        <div>

          <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
            VOLATILITY MONITOR
          </div>

          <div className="mt-1 text-xs text-[#999]">
            REALISED VOL + NEXT-1H CONDITIONAL FORECASTS · MAIN FIGURES ANNUALISED
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
            <span className="text-[#999]">
              {lastUpdated
                .toISOString()
                .slice(11, 19)} UTC
            </span>
          )}

        </div>

      </div>


      {/* ERROR */}
      {error && (
        <div className="border-b border-[#5a2c2c] bg-[#170b0b] px-4 py-3 text-sm text-[#ff7070]">
          {error}
        </div>
      )}


      {/* TABLE */}
      <div className="max-h-[560px] overflow-auto">

        <table className="w-full min-w-[1050px] border-collapse text-sm">

          <thead className="sticky top-0 z-20">

            <tr className="bg-[#141414] text-left text-xs text-[#d2d2d2] shadow-[0_1px_0_#3b3b3b]">

              <Header>
                ASSET
              </Header>

              <Header align="right">
                RV 1H
              </Header>

              <Header align="right">
                RV 4H
              </Header>

              <Header align="right">
                RV 24H
              </Header>

              <Header align="right">
                24H PCTL
              </Header>

              <Header align="right">
                PL 1H FWD
              </Header>

              <Header align="right">
                EWMA 1H FWD
              </Header>

              <Header align="right">
                MODEL SPREAD
              </Header>

              <Header
                align="right"
                last
              >
                4H / 24H
              </Header>

            </tr>

          </thead>


          <tbody>

            {data.map(
              (asset) => (

                <tr
                  key={asset.symbol}
                  className="border-t border-[#303030] transition hover:bg-[#151515]"
                >

                  {/* ASSET */}
                  <td className="border-r border-[#303030] px-4 py-3">

                    <div className="font-black text-white">
                      {asset.symbol}
                    </div>

                    <div className="mt-1 text-xs text-[#aaa]">
                      {asset.asset}
                    </div>

                  </td>


                  <ValueCell>
                    {formatVol(
                      asset.realized_vol_1h,
                    )}
                  </ValueCell>


                  <ValueCell>
                    {formatVol(
                      asset.realized_vol_4h,
                    )}
                  </ValueCell>


                  <ValueCell>
                    {formatVol(
                      asset.realized_vol_24h,
                    )}
                  </ValueCell>


                  <ValueCell>
                    {formatPercentile(
                      asset.vol_percentile_24h,
                    )}
                  </ValueCell>


                  <ForecastCell
                    annualizedVol={
                      asset.power_law_vol_forecast
                    }
                    primary
                  />


                  <ForecastCell
                    annualizedVol={
                      asset.ewma_vol_forecast
                    }
                  />


                  <td
                    className={`
                      border-r
                      border-[#303030]
                      px-4
                      py-3
                      text-right
                      font-semibold
                      tabular-nums
                      ${spreadColor(
                        asset.model_disagreement,
                      )}
                    `}
                  >
                    {formatSignedPercent(
                      asset.model_disagreement,
                    )}
                  </td>


                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-[#ddd]">
                    {formatRatio(
                      asset.vol_ratio_4h_vs_24h,
                    )}
                  </td>

                </tr>

              ),
            )}

          </tbody>

        </table>

      </div>

    </section>
  );
}


function Header({
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
        whitespace-nowrap
        px-4
        py-3
        font-bold
        tracking-wide
        ${
          last
            ? ""
            : "border-r border-[#333]"
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


function ValueCell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#ddd]">
      {children}
    </td>
  );
}


function ForecastCell({
  annualizedVol,
  primary = false,
}: {
  annualizedVol: number | null;
  primary?: boolean;
}) {
  return (
    <td className="border-r border-[#303030] px-4 py-3 text-right">

      <div
        className={
          primary
            ? "font-black tabular-nums text-[#49c6e5]"
            : "font-semibold tabular-nums text-[#ddd]"
        }
      >
        {formatVol(
          annualizedVol,
        )}

        <span className="ml-1 text-[9px] font-normal text-[#929292]">
          ANN.
        </span>
      </div>


      <div className="mt-1 text-[10px] text-[#999]">

        1H σ{" "}

        <span className="font-medium text-[#b8b8b8]">
          {formatOneHourSigma(
            annualizedVol,
          )}
        </span>

      </div>

    </td>
  );
}


function formatVol(
  value: number | null | undefined,
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(1)}%`;
}


function formatOneHourSigma(
  annualizedVol: number | null | undefined,
) {
  if (
    annualizedVol == null ||
    !Number.isFinite(annualizedVol)
  ) {
    return "—";
  }

  const oneHourSigma =
    annualizedVol
    /
    Math.sqrt(
      365 * 24,
    );

  return `${(
    oneHourSigma *
    100
  ).toFixed(2)}%`;
}


function formatPercentile(
  value: number | null | undefined,
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(0)}P`;
}


function formatRatio(
  value: number | null | undefined,
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${value.toFixed(2)}×`;
}


function formatSignedPercent(
  value: number | null | undefined,
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  const prefix =
    value > 0
      ? "+"
      : "";

  return `${prefix}${(
    value * 100
  ).toFixed(1)}%`;
}


function spreadColor(
  value: number | null | undefined,
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "text-[#999]";
  }

  const magnitude =
    Math.abs(value);


  if (magnitude < 0.10) {
    return "text-[#38d996]";
  }


  if (magnitude < 0.25) {
    return "text-[#ffb000]";
  }


  return "text-[#ff6666]";
}


function latestCalculatedAt(
  rows: VolatilityAsset[],
) {
  const times = rows
    .map(
      (row) =>
        row.calculated_at ??
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
