"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";


const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const REFRESH_INTERVAL = 15_000;


type LiquidationAsset = {
  symbol: string;
  asset: string;

  total_liquidations_1h: number | null;
  long_liquidations_1h: number | null;
  short_liquidations_1h: number | null;

  total_liquidations_4h: number | null;
  total_liquidations_24h: number | null;

  long_liquidation_share_1h: number | null;

  liquidation_percentile_1h: number | null;

  liquidation_ratio_to_median_1h: number | null;

  total_open_interest: number | null;

  liquidations_to_oi_1h: number | null;

  timestamp: string | null;
};


export default function LiquidationsPanel() {
  const [
    rows,
    setRows,
  ] = useState<LiquidationAsset[]>([]);

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


  // ==========================================================
  // LOAD DATA
  // ==========================================================

  useEffect(() => {
    let mounted = true;


    async function loadData() {
      try {
        const response = await fetch(
          `${API_BASE}/api/liquidations/latest?t=${Date.now()}`,
          {
            cache: "no-store",
            headers: {
              Accept: "application/json",
            },
          },
        );


        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          );
        }


        const payload =
          await response.json();


        if (
          !payload ||
          !Array.isArray(
            payload.data,
          )
        ) {
          throw new Error(
            "Invalid liquidation response",
          );
        }


        if (!mounted) {
          return;
        }


        setRows(
          payload.data,
        );

        setError(null);

      } catch (err) {
        console.error(
          "Failed loading liquidation data:",
          err,
        );


        if (mounted) {
          setError(
            "LIQUIDATION DATA UNAVAILABLE",
          );
        }

      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }


    loadData();


    const interval =
      window.setInterval(
        loadData,
        REFRESH_INTERVAL,
      );


    return () => {
      mounted = false;

      window.clearInterval(
        interval,
      );
    };
  }, []);


  // ==========================================================
  // SORT BY CURRENT 1H LIQUIDATIONS
  // ==========================================================

  const sortedRows = useMemo(
    () =>
      [...rows].sort(
        (
          a,
          b,
        ) =>
          (
            b.total_liquidations_1h ??
            -Infinity
          )
          -
          (
            a.total_liquidations_1h ??
            -Infinity
          ),
      ),
    [rows],
  );


  const latestUpdate = useMemo(
    () =>
      latestTimestamp(
        rows,
      ),
    [rows],
  );


  // ==========================================================
  // UI
  // ==========================================================

  return (
    <section className="overflow-hidden border border-[#444] bg-[#0d0d0d]">

      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#444] bg-[#171717] px-4 py-3">

        <div>

          <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
            LIQUIDATION STRESS
          </div>

          <div className="mt-1 text-xs tracking-wide text-[#949494]">
            FORCED DELEVERAGING · DIRECTION · TEMPORAL PERCENTILE · OI-NORMALISED STRESS
          </div>

        </div>


        <div className="text-right">

          <div
            className={
              error
                ? "text-xs font-bold text-[#ff6666]"
                : "text-xs font-bold text-[#38d996]"
            }
          >
            ● {error ? "ERROR" : "ACTIVE"}
          </div>

          <div className="mt-1 text-[10px] text-[#808080]">
            {formatTimestamp(
              latestUpdate,
            )}
          </div>

        </div>

      </div>


      {/* STATUS */}
      {loading && (
        <div className="px-4 py-6 text-sm text-[#888]">
          LOADING LIQUIDATION SNAPSHOT...
        </div>
      )}


      {error && (
        <div className="border-b border-[#5a2c2c] bg-[#170b0b] px-4 py-4 text-sm text-[#ff7070]">
          {error}
        </div>
      )}


      {!loading &&
        !error &&
        sortedRows.length === 0 && (
          <div className="px-4 py-6 text-sm text-[#888]">
            NO LIQUIDATION DATA
          </div>
        )}


      {!loading &&
        !error &&
        sortedRows.length > 0 && (

          <div className="max-h-[560px] overflow-auto">

            <table className="w-full min-w-[1180px] border-collapse text-xs">

              <thead className="sticky top-0 z-10">

                <tr className="border-b border-[#444] bg-[#101010] text-[#a1a1a1]">

                  <Header>
                    ASSET
                  </Header>

                  <Header align="right">
                    1H LIQ
                  </Header>

                  <Header align="right">
                    LONG %
                  </Header>

                  <Header align="right">
                    4H LIQ
                  </Header>

                  <Header align="right">
                    24H LIQ
                  </Header>

                  <Header align="right">
                    1H PCTL
                  </Header>

                  <Header align="right">
                    VS 24H MED
                  </Header>

                  <Header align="right">
                    LIQ / OI 1H
                  </Header>

                  <Header
                    align="right"
                    last
                  >
                    DIRECTION
                  </Header>

                </tr>

              </thead>


              <tbody>

                {sortedRows.map(
                  (row) => (

                    <tr
                      key={row.symbol}
                      className="border-b border-[#2d2d2d] transition hover:bg-[#151515]"
                    >

                      {/* ASSET */}
                      <td className="border-r border-[#303030] px-4 py-3.5">

                        <div className="font-black text-[#49c6e5]">
                          {row.symbol}
                        </div>

                        <div className="mt-1 text-[10px] text-[#777]">
                          {row.asset}
                        </div>

                      </td>


                      {/* 1H LIQUIDATIONS */}
                      <td className="border-r border-[#303030] px-4 py-3.5 text-right font-black tabular-nums text-[#f2f2f2]">
                        {formatMoney(
                          row.total_liquidations_1h,
                        )}
                      </td>


                      {/* LONG SHARE */}
                      <td
                        className={`border-r border-[#303030] px-4 py-3.5 text-right font-semibold tabular-nums ${longShareColour(
                          row.long_liquidation_share_1h,
                        )}`}
                      >
                        {formatPercent(
                          row.long_liquidation_share_1h,
                        )}
                      </td>


                      {/* 4H LIQUIDATIONS */}
                      <td className="border-r border-[#303030] px-4 py-3.5 text-right font-semibold tabular-nums text-[#d0d0d0]">
                        {formatMoney(
                          row.total_liquidations_4h,
                        )}
                      </td>


                      {/* 24H LIQUIDATIONS */}
                      <td className="border-r border-[#303030] px-4 py-3.5 text-right font-semibold tabular-nums text-[#d0d0d0]">
                        {formatMoney(
                          row.total_liquidations_24h,
                        )}
                      </td>


                      {/* TEMPORAL PERCENTILE */}
                      <td
                        className={`border-r border-[#303030] px-4 py-3.5 text-right font-bold tabular-nums ${percentileColour(
                          row.liquidation_percentile_1h,
                        )}`}
                      >
                        {formatPercentile(
                          row.liquidation_percentile_1h,
                        )}
                      </td>


                      {/* CURRENT VS MEDIAN */}
                      <td className="border-r border-[#303030] px-4 py-3.5 text-right font-semibold tabular-nums text-[#c0c0c0]">
                        {formatRatio(
                          row.liquidation_ratio_to_median_1h,
                        )}
                      </td>


                      {/* LIQ / OI */}
                      <td className="border-r border-[#303030] px-4 py-3.5 text-right font-semibold tabular-nums text-[#c0c0c0]">
                        {formatBasisPoints(
                          row.liquidations_to_oi_1h,
                        )}
                      </td>


                      {/* DIRECTION */}
                      <td
                        className={`px-4 py-3.5 text-right font-black tracking-wide ${directionColour(
                          row.long_liquidation_share_1h,
                        )}`}
                      >
                        {liquidationDirection(
                          row.long_liquidation_share_1h,
                          row.total_liquidations_1h,
                        )}
                      </td>

                    </tr>

                  ),
                )}

              </tbody>

            </table>

          </div>
        )}


      {!loading &&
        !error &&
        sortedRows.length > 0 && (

          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-[#353535] bg-[#090909] px-4 py-2.5 text-[9px] tracking-wide text-[#707070]">

            <span>
              PCTL = CURRENT 1H ACTIVITY VS RECENT 24H SNAPSHOTS
            </span>

            <span>
              LONG = LONG POSITIONS LIQUIDATED
            </span>

            <span>
              LIQ/OI = 1H LIQUIDATIONS / CLEAN OPEN INTEREST
            </span>

            <span>
              DIRECTION: LONG ≥ 70% · SHORT ≤ 30% · OTHERWISE MIXED
            </span>

          </div>

        )}

    </section>
  );
}


// ============================================================
// TABLE HEADER
// ============================================================

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


// ============================================================
// FORMATTERS
// ============================================================

function formatMoney(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  if (value >= 1e9) {
    return `$${(
      value / 1e9
    ).toFixed(2)}B`;
  }


  if (value >= 1e6) {
    return `$${(
      value / 1e6
    ).toFixed(2)}M`;
  }


  if (value >= 1e3) {
    return `$${(
      value / 1e3
    ).toFixed(1)}K`;
  }


  return `$${value.toFixed(0)}`;
}


function formatPercent(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  return `${(
    value * 100
  ).toFixed(1)}%`;
}


function formatPercentile(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  return `${(
    value * 100
  ).toFixed(0)}P`;
}


function formatRatio(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  return `${value.toFixed(2)}×`;
}


function formatBasisPoints(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  return `${(
    value * 10_000
  ).toFixed(2)} bp`;
}


function formatTimestamp(
  value: string | null,
) {
  if (!value) {
    return "—";
  }


  const date =
    new Date(value);


  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return "—";
  }


  return `${date
    .toISOString()
    .slice(11, 19)} UTC`;
}


// ============================================================
// STATE
// ============================================================

function liquidationDirection(
  longShare: number | null,
  total: number | null,
) {
  if (
    total === null ||
    total <= 0 ||
    longShare === null
  ) {
    return "NONE";
  }


  if (longShare >= 0.7) {
    return "LONG";
  }


  if (longShare <= 0.3) {
    return "SHORT";
  }


  return "MIXED";
}


function directionColour(
  longShare: number | null,
) {
  if (longShare === null) {
    return "text-[#777]";
  }


  if (longShare >= 0.7) {
    return "text-[#ff6666]";
  }


  if (longShare <= 0.3) {
    return "text-[#38d996]";
  }


  return "text-[#ffb000]";
}


function longShareColour(
  longShare: number | null,
) {
  if (longShare === null) {
    return "text-[#777]";
  }


  if (longShare >= 0.8) {
    return "text-[#ff6666]";
  }


  if (longShare <= 0.2) {
    return "text-[#38d996]";
  }


  return "text-[#d0d0d0]";
}


function percentileColour(
  percentile: number | null,
) {
  if (percentile === null) {
    return "text-[#777]";
  }


  if (percentile >= 0.95) {
    return "text-[#ff6666]";
  }


  if (percentile >= 0.80) {
    return "text-[#ffb000]";
  }


  return "text-[#cfcfcf]";
}


function latestTimestamp(
  rows: LiquidationAsset[],
) {
  const times = rows
    .map(
      (row) =>
        row.timestamp,
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
    times.at(-1)
      ?.toISOString()
    ??
    null
  );
}
