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

  calculated_at?: string;
};


const REFRESH_INTERVAL = 15_000;


export default function VolatilityPanel() {
  const [data, setData] =
    useState<VolatilityAsset[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [lastUpdated, setLastUpdated] =
    useState<Date | null>(null);


  const timeoutRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null
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
          }
        );


        if (!response.ok) {
          throw new Error(
            `Backend returned HTTP ${response.status}`
          );
        }


        const result =
          await response.json();


        if (!Array.isArray(result.data)) {
          throw new Error(
            "Invalid volatility response"
          );
        }


        if (!mountedRef.current) {
          return;
        }


        setData(result.data);

        setLastUpdated(
          new Date()
        );

        setError(null);

      } catch (err) {
        if (!mountedRef.current) {
          return;
        }


        if (err instanceof Error) {
          setError(
            err.message
          );
        } else {
          setError(
            "Failed to load volatility data"
          );
        }

      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [API_URL]
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
          REFRESH_INTERVAL
        );
    }


    poll();


    return () => {
      mountedRef.current = false;


      if (timeoutRef.current) {
        clearTimeout(
          timeoutRef.current
        );
      }
    };

  }, [loadData]);


  if (loading) {
    return (
      <div className="border border-[#444] bg-[#0d0d0d] p-5 text-sm text-[#bbb]">
        LOADING VOLATILITY ENGINE...
      </div>
    );
  }


  return (
    <section className="border border-[#3f3f3f] bg-[#090909]">

      {/* HEADER */}

      <div className="flex items-center justify-between border-b border-[#3f3f3f] bg-[#151515] px-4 py-3">

        <div>

          <div className="text-sm font-bold tracking-wide text-[#ffb000]">
            VOLATILITY MONITOR
          </div>

          <div className="mt-1 text-xs text-[#929292]">
            REALIZED VOL + NEXT-1H CONDITIONAL FORECASTS · MAIN FIGURES ANNUALIZED
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
            ● {error ? "ERROR" : "ACTIVE"}
          </span>


          {lastUpdated && (
            <span className="text-[#999]">
              UPDATED{" "}
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}

        </div>

      </div>


      {/* ERROR */}

      {error && (
        <div className="border-b border-[#ff5c5c] bg-[#170b0b] px-4 py-3 text-sm text-[#ff7070]">
          {error}
        </div>
      )}


      {/* TABLE */}

      <div className="overflow-x-auto">

        <table className="w-full border-collapse text-sm">

          <thead>

            <tr className="bg-[#111] text-left text-[#cfcfcf]">

              <Header>
                ASSET
              </Header>

              <Header>
                RV 1H
              </Header>

              <Header>
                RV 4H
              </Header>

              <Header>
                RV 24H
              </Header>

              <Header>
                24H PCTL
              </Header>

              <Header>
                PL 1H FWD VOL
              </Header>

              <Header>
                EWMA 1H FWD VOL
              </Header>

              <Header>
                MODEL SPREAD
              </Header>

              <th className="px-4 py-3">
                4H / 24H
              </th>

            </tr>

          </thead>


          <tbody>

            {data.map((asset) => (

              <tr
                key={asset.symbol}
                className="border-t border-[#303030] transition hover:bg-[#141414]"
              >

                {/* ASSET */}

                <td className="border-r border-[#303030] px-4 py-4">

                  <div className="font-bold text-white">
                    {asset.symbol}
                  </div>

                  <div className="mt-1 text-xs text-[#888]">
                    {asset.asset}
                  </div>

                </td>


                {/* REALIZED VOL */}

                <ValueCell>
                  {formatVol(
                    asset.realized_vol_1h
                  )}
                </ValueCell>


                <ValueCell>
                  {formatVol(
                    asset.realized_vol_4h
                  )}
                </ValueCell>


                <ValueCell>
                  {formatVol(
                    asset.realized_vol_24h
                  )}
                </ValueCell>


                {/* PERCENTILE */}

                <ValueCell>
                  {formatPercentile(
                    asset.vol_percentile_24h
                  )}
                </ValueCell>


                {/* POWER-LAW FORECAST */}

                <ForecastCell
                  annualizedVol={
                    asset.power_law_vol_forecast
                  }
                  primary
                />


                {/* EWMA FORECAST */}

                <ForecastCell
                  annualizedVol={
                    asset.ewma_vol_forecast
                  }
                />


                {/* MODEL SPREAD */}

                <td
                  className={`
                    border-r
                    border-[#303030]
                    px-4
                    py-4
                    ${spreadColor(
                      asset.model_disagreement
                    )}
                  `}
                >
                  {formatSignedPercent(
                    asset.model_disagreement
                  )}
                </td>


                {/* VOL EXPANSION */}

                <td className="px-4 py-4 text-[#ddd]">
                  {formatRatio(
                    asset.vol_ratio_4h_vs_24h
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


/* ============================================================
   TABLE COMPONENTS
   ============================================================ */


function Header({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <th className="border-r border-[#333] px-4 py-3 font-semibold">
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
    <td className="border-r border-[#303030] px-4 py-4 text-[#ddd]">
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
    <td className="border-r border-[#303030] px-4 py-4">

      <div
        className={
          primary
            ? "font-semibold text-[#49c6e5]"
            : "font-semibold text-[#ddd]"
        }
      >
        {formatVol(
          annualizedVol
        )}

        <span className="ml-1 text-[10px] font-normal text-[#777]">
          ANN.
        </span>
      </div>


      <div className="mt-1 text-[10px] text-[#8a8a8a]">

        1H σ{" "}

        <span className="text-[#b8b8b8]">
          {formatOneHourSigma(
            annualizedVol
          )}
        </span>

      </div>

    </td>
  );
}


/* ============================================================
   FORMATTING
   ============================================================ */


function formatVol(
  value: number | null | undefined
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${(value * 100).toFixed(1)}%`;
}


function formatOneHourSigma(
  annualizedVol: number | null | undefined
) {
  if (
    annualizedVol == null ||
    !Number.isFinite(annualizedVol)
  ) {
    return "—";
  }

  /*
   * Main forecast is annualized volatility.
   *
   * Convert to the standard deviation implied over
   * the actual one-hour forecast horizon:
   *
   * sigma_1h = sigma_annual / sqrt(365 * 24)
   */

  const oneHourSigma =
    annualizedVol
    / Math.sqrt(
      365 * 24
    );

  return `${
    (
      oneHourSigma
      * 100
    ).toFixed(2)
  }%`;
}


function formatPercentile(
  value: number | null | undefined
) {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${
    (
      value * 100
    ).toFixed(0)
  }%`;
}


function formatRatio(
  value: number | null | undefined
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
  value: number | null | undefined
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

  return `${prefix}${
    (
      value * 100
    ).toFixed(1)
  }%`;
}


function spreadColor(
  value: number | null | undefined
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