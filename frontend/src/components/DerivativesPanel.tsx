"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";


const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";


type DerivativesAsset = {
  symbol: string;
  asset: string;

  raw_market_count: number;
  fresh_market_count: number;
  cmc_outlier_count: number;

  raw_total_oi: number | null;
  total_open_interest: number | null;
  clean_oi_market_count: number;

  open_interest_change_common_1h: number | null;
  common_oi_overlap_min_share_1h: number | null;
  common_oi_change_available_1h: boolean | null;

  median_funding_rate: number | null;
  funding_p25: number | null;
  funding_p75: number | null;
  funding_market_count: number;
  funding_iqr: number | null;

  median_index_basis: number | null;
  basis_p25: number | null;
  basis_p75: number | null;
  basis_market_count: number;
  basis_iqr: number | null;

  calculated_at: string | null;

  clean_oi_venues: number | null;
  oi_hhi: number | null;
  oi_top_venue_share: number | null;
};


export default function DerivativesPanel() {
  const [
    rows,
    setRows,
  ] = useState<DerivativesAsset[]>([]);

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
          `${API_BASE}/api/derivatives/latest?t=${Date.now()}`,
          {
            cache: "no-store",
          },
        );


        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          );
        }


        const payload =
          await response.json();


        if (!mounted) {
          return;
        }


        setRows(
          payload.data ?? [],
        );

        setError(null);

      } catch (err) {
        console.error(
          "Failed loading derivatives data:",
          err,
        );


        if (mounted) {
          setError(
            "DERIVATIVES DATA UNAVAILABLE",
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
        15_000,
      );


    return () => {
      mounted = false;

      window.clearInterval(
        interval,
      );
    };
  }, []);


  // ==========================================================
  // SORT BY CLEAN OPEN INTEREST
  // ==========================================================

  const sortedRows = useMemo(
    () =>
      [...rows].sort(
        (
          a,
          b,
        ) =>
          (
            b.total_open_interest ??
            -Infinity
          )
          -
          (
            a.total_open_interest ??
            -Infinity
          ),
      ),
    [rows],
  );


  const latestUpdate =
    sortedRows.length > 0
      ? sortedRows[0].calculated_at
      : null;


  return (
    <section className="overflow-hidden border border-[#444] bg-[#0d0d0d]">

      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#444] bg-[#171717] px-4 py-3">

        <div>

          <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
            DERIVATIVES MARKET STATE
          </div>

          <div className="mt-1 text-xs tracking-wide text-[#949494]">
            CLEANED PERPETUAL MARKET AGGREGATES · COMMON-UNIVERSE OI · FUNDING · BASIS · CONCENTRATION
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
          LOADING DERIVATIVES SNAPSHOT...
        </div>
      )}


      {error && (
        <div className="px-4 py-6 text-sm text-[#ff5c5c]">
          {error}
        </div>
      )}


      {!loading &&
        !error &&
        sortedRows.length === 0 && (
          <div className="px-4 py-6 text-sm text-[#888]">
            NO DERIVATIVES DATA
          </div>
        )}


      {!loading &&
        !error &&
        sortedRows.length > 0 && (

          <div className="max-h-[560px] overflow-auto">

            <table className="w-full min-w-[1450px] border-collapse text-xs">

              <thead className="sticky top-0 z-20">

                <tr className="border-b border-[#4b4b4b] bg-[#141414] text-[#b5b5b5] shadow-[0_1px_0_#3b3b3b]">

                  <Header>
                    ASSET
                  </Header>

                  <Header align="right">
                    OPEN INTEREST
                  </Header>

                  <Header align="right">
                    COMMON OI 1H
                  </Header>

                  <Header align="right">
                    COMMON SHARE
                  </Header>

                  <Header align="right">
                    VALID MKTS
                  </Header>

                  <Header align="right">
                    MEDIAN FUNDING
                  </Header>

                  <Header align="right">
                    FUND IQR
                  </Header>

                  <Header align="right">
                    MEDIAN BASIS
                  </Header>

                  <Header align="right">
                    BASIS IQR
                  </Header>

                  <Header align="right">
                    OI HHI
                  </Header>

                  <Header align="right">
                    TOP VENUE
                  </Header>

                  <Header
                    align="right"
                    last
                  >
                    VENUES
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

                      <td className="border-r border-[#303030] px-4 py-3">

                        <div className="font-black text-[#49c6e5]">
                          {row.symbol}
                        </div>

                        <div className="mt-1 text-[10px] text-[#999]">
                          {row.asset}
                        </div>

                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right font-black tabular-nums text-[#f2f2f2]">
                        {formatMoney(
                          row.total_open_interest,
                        )}
                      </td>


                      <td
                        className={`border-r border-[#303030] px-4 py-3 text-right font-bold tabular-nums ${changeColour(
                          row.open_interest_change_common_1h,
                        )}`}
                      >
                        {row.common_oi_change_available_1h
                          ? formatSignedPercent(
                              row.open_interest_change_common_1h,
                            )
                          : "—"}
                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#c8c8c8]">
                        {formatPercent(
                          row.common_oi_overlap_min_share_1h,
                        )}
                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right">

                        <span className="font-semibold text-[#d0d0d0]">
                          {row.clean_oi_market_count}
                        </span>

                        <span className="text-[#666]">
                          {" / "}
                          {row.raw_market_count}
                        </span>

                      </td>


                      <td
                        className={`border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums ${rateColour(
                          row.median_funding_rate,
                        )}`}
                      >
                        {formatSignedRate(
                          row.median_funding_rate,
                        )}
                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#b8b8b8]">
                        {formatUnsignedRate(
                          row.funding_iqr,
                        )}
                      </td>


                      <td
                        className={`border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums ${rateColour(
                          row.median_index_basis,
                        )}`}
                      >
                        {formatSignedRate(
                          row.median_index_basis,
                        )}
                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#b8b8b8]">
                        {formatUnsignedRate(
                          row.basis_iqr,
                        )}
                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#d0d0d0]">
                        {formatHHI(
                          row.oi_hhi,
                        )}
                      </td>


                      <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#d0d0d0]">
                        {formatPercent(
                          row.oi_top_venue_share,
                        )}
                      </td>


                      <td className="px-4 py-3 text-right tabular-nums text-[#999]">
                        {row.clean_oi_venues ?? "—"}
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

          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-[#353535] bg-[#090909] px-4 py-2.5 text-[10px] tracking-wide text-[#858585]">

            <span>
              PROVIDER AGE ≤ 15 MIN
            </span>

            <span>
              BASE ASSET MATCHED
            </span>

            <span>
              CMC OUTLIERS EXCLUDED
            </span>

            <span>
              OI VENUE CONSISTENCY FILTER
            </span>

            <span>
              COMMON-UNIVERSE OI USED FOR 1H CHANGE
            </span>

            <span>
              FUNDING NOT ANNUALISED
            </span>

          </div>

        )}

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


function formatMoney(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  if (
    Math.abs(value) >= 1e12
  ) {
    return `$${(
      value / 1e12
    ).toFixed(2)}T`;
  }


  if (
    Math.abs(value) >= 1e9
  ) {
    return `$${(
      value / 1e9
    ).toFixed(2)}B`;
  }


  if (
    Math.abs(value) >= 1e6
  ) {
    return `$${(
      value / 1e6
    ).toFixed(1)}M`;
  }


  return `$${value.toLocaleString()}`;
}


function formatSignedRate(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  const percent =
    value * 100;


  const sign =
    percent > 0
      ? "+"
      : "";


  return `${sign}${percent.toFixed(4)}%`;
}


function formatUnsignedRate(
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
  ).toFixed(4)}%`;
}


function formatSignedPercent(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  const percent =
    value * 100;


  const sign =
    percent > 0
      ? "+"
      : "";


  return `${sign}${percent.toFixed(2)}%`;
}


function formatHHI(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }


  return value.toFixed(3);
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


function rateColour(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "text-[#777]";
  }


  if (value > 0) {
    return "text-[#ffb000]";
  }


  if (value < 0) {
    return "text-[#49c6e5]";
  }


  return "text-[#cfcfcf]";
}


function changeColour(
  value: number | null,
) {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "text-[#888]";
  }


  if (value > 0) {
    return "text-[#38d996]";
  }


  if (value < 0) {
    return "text-[#ff6666]";
  }


  return "text-[#cfcfcf]";
}
