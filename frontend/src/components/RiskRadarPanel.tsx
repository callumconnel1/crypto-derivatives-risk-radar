import type { ReactNode } from "react";


export type RiskRadarRow = {
  risk_rank: number | null;
  symbol: string;
  asset: string | null;

  provisional_risk_score: number | null;
  risk_cross_percentile: number | null;

  volatility_component: number | null;
  leverage_component: number | null;
  funding_component: number | null;
  liquidation_component: number | null;
  market_structure_component: number | null;

  funding_component_source: string | null;

  primary_state: string | null;
  state_quality: string | null;

  risk_ready: boolean;
  risk_source_at: string | null;
};


export default function RiskRadarPanel({
  rows,
  loading,
  error,
}: {
  rows: RiskRadarRow[];
  loading: boolean;
  error: string | null;
}) {
  const sortedRows = [...rows].sort(
    (
      a,
      b,
    ) => {
      if (
        a.risk_rank !== null &&
        b.risk_rank !== null
      ) {
        return (
          a.risk_rank -
          b.risk_rank
        );
      }

      return (
        (
          b.provisional_risk_score ??
          -Infinity
        )
        -
        (
          a.provisional_risk_score ??
          -Infinity
        )
      );
    },
  );


  const latestSource =
    sortedRows
      .map(
        (row) =>
          row.risk_source_at,
      )
      .filter(
        (
          value,
        ): value is string =>
          Boolean(value),
      )
      .sort()
      .at(-1) ?? null;


  return (
    <section className="overflow-hidden border border-[#484848] bg-[#0b0b0b]">

      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#484848] bg-[#171717] px-4 py-3">

        <div>

          <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
            CDRR PROVISIONAL RISK RANKING
          </div>

          <div className="mt-1 text-xs text-[#9a9a9a]">
            EQUAL-WEIGHT 5-FACTOR STRESS SCORE · MAGNITUDE ONLY · NOT A PRICE FORECAST
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

          <div className="mt-1 text-[10px] text-[#858585]">
            {formatTimestamp(
              latestSource,
            )}
          </div>

        </div>

      </div>


      {loading && rows.length === 0 && (
        <div className="px-4 py-6 text-sm text-[#999]">
          LOADING RISK SNAPSHOT...
        </div>
      )}


      {error && (
        <div className="border-b border-[#5a2c2c] bg-[#170b0b] px-4 py-3 text-sm text-[#ff7b7b]">
          {error}
        </div>
      )}


      {!loading &&
        !error &&
        sortedRows.length === 0 && (
          <div className="px-4 py-6 text-sm text-[#999]">
            NO RISK DATA
          </div>
        )}


      {sortedRows.length > 0 && (

        <div className="max-h-[560px] overflow-auto">

          <table className="w-full min-w-[1180px] border-collapse text-xs">

            <thead className="sticky top-0 z-20">

              <tr className="border-b border-[#4b4b4b] bg-[#141414] text-[#b8b8b8] shadow-[0_1px_0_#3b3b3b]">

                <Header>
                  RANK
                </Header>

                <Header>
                  ASSET
                </Header>

                <Header align="right">
                  SCORE
                </Header>

                <Header align="right">
                  X-SEC PCTL
                </Header>

                <Header>
                  PRIMARY STATE
                </Header>

                <Header align="right">
                  VOL
                </Header>

                <Header align="right">
                  OI
                </Header>

                <Header align="right">
                  FUND
                </Header>

                <Header align="right">
                  LIQ
                </Header>

                <Header align="right">
                  STRUCT
                </Header>

                <Header>
                  FUND SOURCE
                </Header>

                <Header align="right">
                  QUALITY
                </Header>

              </tr>

            </thead>


            <tbody>

              {sortedRows.map(
                (row) => (

                  <tr
                    key={row.symbol}
                    className={`
                      border-b
                      border-[#2d2d2d]
                      transition
                      hover:bg-[#171717]
                      ${
                        row.risk_rank !== null &&
                        row.risk_rank <= 3
                          ? "bg-[#100f09]"
                          : "bg-[#0b0b0b]"
                      }
                    `}
                  >

                    <td className="px-4 py-3 font-bold tabular-nums text-[#8f8f8f]">
                      {row.risk_rank !== null
                        ? `#${row.risk_rank}`
                        : "—"}
                    </td>


                    <td className="px-4 py-3">

                      <div className="font-black text-[#49c6e5]">
                        {row.symbol}
                      </div>

                      <div className="mt-0.5 text-[10px] text-[#9a9a9a]">
                        {row.asset ?? "—"}
                      </div>

                    </td>


                    <td className="px-4 py-3 text-right">

                      <div className="text-base font-black tabular-nums text-[#ffb000]">
                        {formatScore(
                          row.provisional_risk_score,
                        )}
                      </div>

                      <div className="mt-1 text-[10px] text-[#8f8f8f]">
                        /100
                      </div>

                    </td>


                    <td className="px-4 py-3 text-right font-semibold tabular-nums text-[#d6d6d6]">
                      {formatPercentile(
                        row.risk_cross_percentile,
                      )}
                    </td>


                    <td className={`px-4 py-3 font-semibold ${stateColour(
                      row.primary_state,
                    )}`}>
                      {row.primary_state ?? "—"}
                    </td>


                    <FactorCell
                      value={
                        row.volatility_component
                      }
                    />

                    <FactorCell
                      value={
                        row.leverage_component
                      }
                    />

                    <FactorCell
                      value={
                        row.funding_component
                      }
                    />

                    <FactorCell
                      value={
                        row.liquidation_component
                      }
                    />

                    <FactorCell
                      value={
                        row.market_structure_component
                      }
                    />


                    <td className="px-4 py-3 text-[11px] font-medium text-[#b0b0b0]">
                      {shortFundingSource(
                        row.funding_component_source,
                      )}
                    </td>


                    <td className="px-4 py-3 text-right">

                      <span
                        className={
                          row.risk_ready
                            ? "font-bold text-[#38d996]"
                            : "font-bold text-[#ff6666]"
                        }
                      >
                        {row.risk_ready
                          ? "READY"
                          : "PARTIAL"}
                      </span>

                      <div className="mt-1 text-[10px] text-[#929292]">
                        {row.state_quality ?? "—"}
                      </div>

                    </td>

                  </tr>

                ),
              )}

            </tbody>

          </table>

        </div>
      )}


      {sortedRows.length > 0 && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-[#353535] bg-[#090909] px-4 py-2.5 text-[10px] tracking-wide text-[#8a8a8a]">

          <span>
            SCORE VERSION: PROVISIONAL V1
          </span>

          <span>
            FIVE FACTORS · 20% EACH
          </span>

          <span>
            FUNDING USES CROSS-SECTIONAL WARM-UP UNTIL HISTORY IS READY
          </span>

          <span>
            SCORE RANKS RELATIVE STRESS ACROSS THE TRACKED UNIVERSE
          </span>

        </div>
      )}

    </section>
  );
}


function Header({
  children,
  align = "left",
}: {
  children: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`whitespace-nowrap px-4 py-3 font-bold tracking-[0.05em] ${
        align === "right"
          ? "text-right"
          : "text-left"
      }`}
    >
      {children}
    </th>
  );
}


function FactorCell({
  value,
}: {
  value: number | null;
}) {
  const percent =
    finite(
      value,
    )
      ? Math.max(
          0,
          Math.min(
            100,
            value * 100,
          ),
        )
      : null;


  return (
    <td className="px-4 py-3 text-right">

      <div className="font-bold tabular-nums text-[#d9d9d9]">
        {percent !== null
          ? percent.toFixed(0)
          : "—"}
      </div>

      <div className="ml-auto mt-1.5 h-1 w-14 bg-[#303030]">

        <div
          className="h-full bg-[#ffb000]"
          style={{
            width: `${
              percent ?? 0
            }%`,
          }}
        />

      </div>

    </td>
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


function formatScore(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return value.toFixed(1);
}


function formatPercentile(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(0)}P`;
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


function shortFundingSource(
  value: string | null,
) {
  if (!value) {
    return "—";
  }

  if (
    value ===
    "CROSS-SECTIONAL WARMUP"
  ) {
    return "X-SEC WARMUP";
  }

  if (
    value ===
    "HISTORICAL + CROSS CONFIRMED"
  ) {
    return "HIST + X-SEC";
  }

  return value;
}


function stateColour(
  state: string | null,
) {
  if (!state) {
    return "text-[#aaa]";
  }

  if (
    state.includes(
      "LIQUIDATION",
    )
  ) {
    return "text-[#ff6666]";
  }

  if (
    state.includes(
      "SELLOFF",
    )
  ) {
    return "text-[#ffb000]";
  }

  if (
    state.includes(
      "RALLY",
    )
  ) {
    return "text-[#49c6e5]";
  }

  if (
    state.includes(
      "DELEVERAGING",
    )
  ) {
    return "text-[#d2d2d2]";
  }

  return "text-[#bcbcbc]";
}
