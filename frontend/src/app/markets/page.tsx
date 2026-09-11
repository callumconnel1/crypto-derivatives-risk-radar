"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";
import { InfoTip, StatusBanner, TerminalNav } from "@/components/TerminalChrome";



const REFRESH_INTERVAL = 15_000;


type SpotAsset = {
  id?: number | null;
  symbol: string;
  asset: string | null;

  price: number | null;
  volume_24h: number | null;
  market_cap: number | null;

  percent_change_1h?: number | null;
  percent_change_24h?: number | null;

  price_change_1h?: number | null;
  price_change_24h?: number | null;

  collected_at?: string | null;
  timestamp?: string | null;
};


type DerivativesAsset = {
  symbol: string;
  asset: string | null;

  total_open_interest: number | null;
  open_interest_change_common_1h: number | null;
  common_oi_overlap_min_share_1h: number | null;
  common_oi_change_available_1h: boolean | null;

  median_funding_rate: number | null;
  funding_iqr: number | null;

  median_index_basis: number | null;
  basis_iqr: number | null;

  oi_hhi: number | null;
  oi_top_venue_share: number | null;

  clean_oi_market_count: number | null;
  raw_market_count: number | null;
  clean_oi_venues: number | null;

  calculated_at: string | null;
};


type LiquidationAsset = {
  symbol: string;
  asset: string | null;

  total_liquidations_1h: number | null;
  total_liquidations_4h: number | null;
  total_liquidations_24h: number | null;

  long_liquidation_share_1h: number | null;
  liquidation_percentile_1h: number | null;
  liquidation_ratio_to_median_1h: number | null;
  liquidations_to_oi_1h: number | null;

  timestamp: string | null;
};


type RiskAsset = {
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


type VolatilityAsset = {
  timestamp: string | null;

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

  calculated_at?: string | null;
};


type MarketRow = {
  symbol: string;
  asset: string;

  spot: SpotAsset | null;
  derivatives: DerivativesAsset | null;
  liquidations: LiquidationAsset | null;
  risk: RiskAsset | null;
  volatility: VolatilityAsset | null;
};


type SortKey =
  | "risk"
  | "symbol"
  | "price"
  | "change1h"
  | "change24h"
  | "oi"
  | "oi1h"
  | "funding"
  | "basis"
  | "liqOi"
  | "rv24h";


async function fetchDataArray<T>(
  endpoint: string,
): Promise<T[]> {
  const response = await fetch(
    `${endpoint}?t=${Date.now()}`,
    {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      `${endpoint} returned HTTP ${response.status}`,
    );
  }

  const payload = await response.json();

  if (!Array.isArray(payload.data)) {
    throw new Error(
      `${endpoint} did not return a data array`,
    );
  }

  return payload.data as T[];
}


export default function MarketsPage() {
  const [
    spotRows,
    setSpotRows,
  ] = useState<SpotAsset[]>([]);

  const [
    derivativesRows,
    setDerivativesRows,
  ] = useState<DerivativesAsset[]>([]);

  const [
    liquidationRows,
    setLiquidationRows,
  ] = useState<LiquidationAsset[]>([]);

  const [
    riskRows,
    setRiskRows,
  ] = useState<RiskAsset[]>([]);

  const [
    volatilityRows,
    setVolatilityRows,
  ] = useState<VolatilityAsset[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    degradedSources,
    setDegradedSources,
  ] = useState<string[]>([]);

  const [
    search,
    setSearch,
  ] = useState("");

  const [
    stateFilter,
    setStateFilter,
  ] = useState("ALL");

  const [
    sortKey,
    setSortKey,
  ] = useState<SortKey>("risk");

  const [
    sortDirection,
    setSortDirection,
  ] = useState<"asc" | "desc">("asc");

  const [
    selectedSymbol,
    setSelectedSymbol,
  ] = useState<string | null>(null);


  // ==========================================================
  // LOAD ALL MARKET SURFACES
  // ==========================================================

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      const results =
        await Promise.allSettled([
          fetchDataArray<SpotAsset>(
            "/api/market/latest",
          ),
          fetchDataArray<DerivativesAsset>(
            "/api/derivatives/latest",
          ),
          fetchDataArray<LiquidationAsset>(
            "/api/liquidations/latest",
          ),
          fetchDataArray<RiskAsset>(
            "/api/risk/latest",
          ),
          fetchDataArray<VolatilityAsset>(
            "/api/volatility/latest",
          ),
        ]);

      if (!mounted) {
        return;
      }

      const failed: string[] = [];

      const spotResult = results[0];

      if (spotResult.status === "fulfilled") {
        setSpotRows(
          spotResult.value,
        );
      } else {
        failed.push("SPOT");
      }

      const derivativesResult = results[1];

      if (
        derivativesResult.status ===
        "fulfilled"
      ) {
        setDerivativesRows(
          derivativesResult.value,
        );
      } else {
        failed.push("DERIVATIVES");
      }

      const liquidationResult = results[2];

      if (
        liquidationResult.status ===
        "fulfilled"
      ) {
        setLiquidationRows(
          liquidationResult.value,
        );
      } else {
        failed.push("LIQUIDATIONS");
      }

      const riskResult = results[3];

      if (riskResult.status === "fulfilled") {
        setRiskRows(
          riskResult.value,
        );
      } else {
        failed.push("RISK");
      }

      const volatilityResult = results[4];

      if (
        volatilityResult.status ===
        "fulfilled"
      ) {
        setVolatilityRows(
          volatilityResult.value,
        );
      } else {
        failed.push("VOLATILITY");
      }

      setDegradedSources(
        failed,
      );

      setLoading(false);
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
  // MERGE BY SYMBOL
  // ==========================================================

  const rows = useMemo(
    () => {
      const symbols = new Set<string>();

      for (const row of spotRows) {
        symbols.add(row.symbol);
      }

      for (const row of derivativesRows) {
        symbols.add(row.symbol);
      }

      for (const row of liquidationRows) {
        symbols.add(row.symbol);
      }

      for (const row of riskRows) {
        symbols.add(row.symbol);
      }

      for (const row of volatilityRows) {
        symbols.add(row.symbol);
      }

      const spotMap = new Map(
        spotRows.map(
          (row) => [
            row.symbol,
            row,
          ],
        ),
      );

      const derivativesMap = new Map(
        derivativesRows.map(
          (row) => [
            row.symbol,
            row,
          ],
        ),
      );

      const liquidationMap = new Map(
        liquidationRows.map(
          (row) => [
            row.symbol,
            row,
          ],
        ),
      );

      const riskMap = new Map(
        riskRows.map(
          (row) => [
            row.symbol,
            row,
          ],
        ),
      );

      const volatilityMap = new Map(
        volatilityRows.map(
          (row) => [
            row.symbol,
            row,
          ],
        ),
      );

      return Array.from(
        symbols,
      ).map(
        (symbol): MarketRow => {
          const spot =
            spotMap.get(symbol) ??
            null;

          const derivatives =
            derivativesMap.get(symbol) ??
            null;

          const liquidations =
            liquidationMap.get(symbol) ??
            null;

          const risk =
            riskMap.get(symbol) ??
            null;

          const volatility =
            volatilityMap.get(symbol) ??
            null;

          return {
            symbol,
            asset:
              spot?.asset ??
              derivatives?.asset ??
              liquidations?.asset ??
              risk?.asset ??
              volatility?.asset ??
              symbol,

            spot,
            derivatives,
            liquidations,
            risk,
            volatility,
          };
        },
      );
    },
    [
      spotRows,
      derivativesRows,
      liquidationRows,
      riskRows,
      volatilityRows,
    ],
  );


  // ==========================================================
  // DEFAULT SELECTION
  // ==========================================================

  const defaultSelectedSymbol = useMemo(
    () => {
      if (rows.length === 0) {
        return null;
      }

      const topRisk =
        [...rows]
          .filter(
            (row) =>
              row.risk?.risk_ready &&
              finite(
                row.risk
                  ?.provisional_risk_score,
              ),
          )
          .sort(
            (a, b) =>
              (
                b.risk
                  ?.provisional_risk_score ??
                -Infinity
              )
              -
              (
                a.risk
                  ?.provisional_risk_score ??
                -Infinity
              ),
          )[0];

      return (
        topRisk?.symbol ??
        rows[0].symbol
      );
    },
    [rows],
  );

  const effectiveSelectedSymbol =
    selectedSymbol ??
    defaultSelectedSymbol;


  // ==========================================================
  // SUMMARY
  // ==========================================================

  const topRisk = useMemo(
    () =>
      [...riskRows]
        .filter(
          (row) =>
            row.risk_ready &&
            finite(
              row.provisional_risk_score,
            ),
        )
        .sort(
          (a, b) =>
            (
              b.provisional_risk_score ??
              -Infinity
            )
            -
            (
              a.provisional_risk_score ??
              -Infinity
            ),
        )[0] ?? null,
    [riskRows],
  );

  const totalOpenInterest = useMemo(
    () =>
      derivativesRows.reduce(
        (
          total,
          row,
        ) =>
          total +
          (
            finite(
              row.total_open_interest,
            )
              ? row.total_open_interest
              : 0
          ),
        0,
      ),
    [derivativesRows],
  );

  const trackedLiquidations1h =
    useMemo(
      () =>
        liquidationRows.reduce(
          (
            total,
            row,
          ) =>
            total +
            (
              finite(
                row.total_liquidations_1h,
              )
                ? row.total_liquidations_1h
                : 0
            ),
          0,
        ),
      [liquidationRows],
    );

  const riskReadyCount = useMemo(
    () =>
      riskRows.filter(
        (row) =>
          row.risk_ready,
      ).length,
    [riskRows],
  );


  // ==========================================================
  // FILTER / SORT
  // ==========================================================

  const stateOptions = useMemo(
    () =>
      Array.from(
        new Set(
          riskRows
            .map(
              (row) =>
                row.primary_state,
            )
            .filter(
              (
                value,
              ): value is string =>
                Boolean(value),
            ),
        ),
      ).sort(),
    [riskRows],
  );

  const visibleRows = useMemo(
    () => {
      const query =
        search
          .trim()
          .toLowerCase();

      const filtered = rows.filter(
        (row) => {
          const matchesSearch =
            query.length === 0 ||
            row.symbol
              .toLowerCase()
              .includes(query) ||
            row.asset
              .toLowerCase()
              .includes(query);

          const matchesState =
            stateFilter === "ALL" ||
            row.risk
              ?.primary_state ===
              stateFilter;

          return (
            matchesSearch &&
            matchesState
          );
        },
      );

      return filtered.sort(
        (a, b) =>
          compareRows(
            a,
            b,
            sortKey,
            sortDirection,
          ),
      );
    },
    [
      rows,
      search,
      stateFilter,
      sortKey,
      sortDirection,
    ],
  );


  const selected =
    rows.find(
      (row) =>
        row.symbol ===
        effectiveSelectedSymbol,
    ) ??
    null;


  const pageStatus =
    degradedSources.length === 0
      ? (
        loading
          ? "LOADING"
          : "ONLINE"
      )
      : "DEGRADED";

  const sourceFreshness = marketSourceFreshness(spotRows, derivativesRows, liquidationRows, riskRows, volatilityRows);
  const sourceStale = finite(sourceFreshness.ageSeconds) && sourceFreshness.ageSeconds > 360;
  const navStatus = pageStatus === "ONLINE" && sourceStale ? "STALE" : pageStatus;


  return (
    <main className="dashboard-terminal min-h-screen bg-[#050505] text-[#f4f4f4]">
      {/* NAV */}
      <TerminalNav
        active="markets"
        status={navStatus}
        sourceAt={sourceFreshness.sourceAt}
        sourceAgeSeconds={sourceFreshness.ageSeconds}
        detail="OLDEST REQUIRED SOURCE"
      />


      {(degradedSources.length > 0 || sourceStale) && (
        <StatusBanner
          tone={degradedSources.length > 0 ? "error" : "warning"}
          title={degradedSources.length > 0 ? "DEGRADED MARKET DATA" : "STALE MARKET DATA"}
        >
          {degradedSources.length > 0
            ? `Refresh failed for: ${degradedSources.join(", ")}. Last successful rows are retained where available.`
            : `The oldest required market source is ${formatAgeSeconds(sourceFreshness.ageSeconds)} old. The explorer is showing the last successful snapshot.`}
        </StatusBanner>
      )}

      {/* SUMMARY */}
      <div className="grid grid-cols-2 border-b border-[#444] bg-[#0d0d0d] lg:grid-cols-5">

        <SummaryMetric
          label="TRACKED UNIVERSE"
          help="Fixed research universe used for all cross-sectional rankings and percentiles."
          value={`${rows.length || 20}`}
          sub="LIQUID CRYPTO ASSETS"
        />

        <SummaryMetric
          label="TOP CDRR"
          help="Highest current relative derivatives-stress score in the tracked universe. It is not a probability."
          value={
            finite(
              topRisk
                ?.provisional_risk_score,
            )
              ? (
                topRisk
                  ?.provisional_risk_score ??
                0
              ).toFixed(1)
              : "—"
          }
          sub={
            topRisk
              ? `#1 ${topRisk.symbol}`
              : "RISK SNAPSHOT"
          }
          valueClass="text-[#ffb000]"
        />

        <SummaryMetric
          label="TRACKED OPEN INTEREST"
          help="Clean derivatives open interest across the tracked assets after quality filters."
          value={
            derivativesRows.length > 0
              ? formatMoney(
                  totalOpenInterest,
                )
              : "—"
          }
          sub="CLEAN DERIVATIVES OI"
        />

        <SummaryMetric
          label="TRACKED 1H LIQUIDATIONS"
          help="One-hour liquidation notional aggregated across the tracked 20-asset universe."
          value={
            liquidationRows.length > 0
              ? formatMoney(
                  trackedLiquidations1h,
                )
              : "—"
          }
          sub="20-ASSET UNIVERSE"
        />

        <SummaryMetric
          label="RISK READINESS"
          help="Number of tracked assets with all five production risk components and state timing requirements available."
          value={
            riskRows.length > 0
              ? `${riskReadyCount}/${riskRows.length}`
              : "—"
          }
          sub={
            degradedSources.length === 0
              ? "CURRENT SNAPSHOT"
              : `DEGRADED: ${degradedSources.join(", ")}`
          }
          valueClass={
            degradedSources.length === 0
              ? "text-[#38d996]"
              : "text-[#ffb000]"
          }
        />

      </div>


      <div className="p-4 lg:p-5">

        {/* TITLE */}
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">

          <div>

            <div className="text-lg font-black tracking-wide text-[#f7f7f7]">
              MARKET EXPLORER
            </div>

            <div className="mt-1 text-xs tracking-[0.08em] text-[#a0a0a0]">
              SPOT · DERIVATIVES · VOLATILITY · LIQUIDATIONS · CDRR
            </div>

          </div>

          <div className="text-[10px] tracking-wide text-[#777]">
            CLICK ANY ROW TO INSPECT THE CURRENT CROSS-MARKET STATE
          </div>

        </div>


        {/* SELECTED ASSET */}
        <section className="mb-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">

          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#454545] bg-[#171717] px-4 py-3">

            <div>

              <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
                {selected
                  ? `${selected.symbol} · ${selected.asset}`
                  : "ASSET DETAIL"}
              </div>

              <div className="mt-1 text-xs text-[#949494]">
                CURRENT CROSS-MARKET SNAPSHOT
              </div>

            </div>

            {selected?.risk && (
              <div className="text-right">

                <div className="font-black tabular-nums text-[#ffb000]">
                  CDRR{" "}
                  {formatScore(
                    selected.risk
                      .provisional_risk_score,
                  )}
                </div>

                <div
                  className={`mt-1 text-[10px] font-bold ${stateColour(
                    selected.risk
                      .primary_state,
                  )}`}
                >
                  {selected.risk
                    .primary_state ??
                    "STATE UNAVAILABLE"}
                </div>

              </div>
            )}

          </div>

          {!selected && (
            <div className="px-4 py-8 text-sm text-[#888]">
              SELECT AN ASSET FROM THE TABLE
            </div>
          )}

          {selected && (
            <div className="grid gap-px bg-[#333] xl:grid-cols-4">

              <DetailGroup
                title="MARKET"
                items={[
                  [
                    "PRICE",
                    formatPrice(
                      selected.spot
                        ?.price ??
                        selected.volatility
                          ?.price ??
                        null,
                    ),
                  ],
                  [
                    "1H",
                    formatSignedPoints(
                      spotChange(
                        selected.spot,
                        "1h",
                      ),
                    ),
                    moveColour(
                      spotChange(
                        selected.spot,
                        "1h",
                      ),
                    ),
                  ],
                  [
                    "24H",
                    formatSignedPoints(
                      spotChange(
                        selected.spot,
                        "24h",
                      ),
                    ),
                    moveColour(
                      spotChange(
                        selected.spot,
                        "24h",
                      ),
                    ),
                  ],
                  [
                    "VOLUME 24H",
                    formatMoney(
                      selected.spot
                        ?.volume_24h ??
                        null,
                    ),
                  ],
                  [
                    "MARKET CAP",
                    formatMoney(
                      selected.spot
                        ?.market_cap ??
                        null,
                    ),
                  ],
                ]}
              />

              <DetailGroup
                title="DERIVATIVES"
                items={[
                  [
                    "OPEN INTEREST",
                    formatMoney(
                      selected.derivatives
                        ?.total_open_interest ??
                        null,
                    ),
                  ],
                  [
                    "COMMON OI 1H",
                    selected.derivatives
                      ?.common_oi_change_available_1h
                      ? formatSignedPercent(
                          selected.derivatives
                            .open_interest_change_common_1h,
                          2,
                        )
                      : "—",
                    changeColour(
                      selected.derivatives
                        ?.open_interest_change_common_1h ??
                        null,
                    ),
                  ],
                  [
                    "OI OVERLAP",
                    formatPercent(
                      selected.derivatives
                        ?.common_oi_overlap_min_share_1h ??
                        null,
                      1,
                    ),
                  ],
                  [
                    "MEDIAN FUNDING",
                    formatSignedPercent(
                      selected.derivatives
                        ?.median_funding_rate ??
                        null,
                      4,
                    ),
                    rateColour(
                      selected.derivatives
                        ?.median_funding_rate ??
                        null,
                    ),
                  ],
                  [
                    "MEDIAN BASIS",
                    formatSignedPercent(
                      selected.derivatives
                        ?.median_index_basis ??
                        null,
                      4,
                    ),
                    rateColour(
                      selected.derivatives
                        ?.median_index_basis ??
                        null,
                    ),
                  ],
                ]}
              />

              <DetailGroup
                title="STRESS"
                items={[
                  [
                    "LIQUIDATIONS 1H",
                    formatMoney(
                      selected.liquidations
                        ?.total_liquidations_1h ??
                        null,
                    ),
                  ],
                  [
                    "LIQ / OI 1H",
                    formatBasisPoints(
                      selected.liquidations
                        ?.liquidations_to_oi_1h ??
                        null,
                    ),
                  ],
                  [
                    "LIQ PCTL 1H",
                    formatPercentile(
                      selected.liquidations
                        ?.liquidation_percentile_1h ??
                        null,
                    ),
                  ],
                  [
                    "LONG LIQ SHARE",
                    formatPercent(
                      selected.liquidations
                        ?.long_liquidation_share_1h ??
                        null,
                      1,
                    ),
                  ],
                  [
                    "DIRECTION",
                    liquidationDirection(
                      selected.liquidations
                        ?.long_liquidation_share_1h ??
                        null,
                      selected.liquidations
                        ?.total_liquidations_1h ??
                        null,
                    ),
                    directionColour(
                      selected.liquidations
                        ?.long_liquidation_share_1h ??
                        null,
                    ),
                  ],
                ]}
              />

              <DetailGroup
                title="VOLATILITY"
                items={[
                  [
                    "RV 1H",
                    formatVolatility(
                      selected.volatility
                        ?.realized_vol_1h ??
                        null,
                    ),
                  ],
                  [
                    "RV 24H",
                    formatVolatility(
                      selected.volatility
                        ?.realized_vol_24h ??
                        null,
                    ),
                  ],
                  [
                    "24H PCTL",
                    formatPercentile(
                      selected.volatility
                        ?.vol_percentile_24h ??
                        null,
                    ),
                  ],
                  [
                    "PL 1H FWD",
                    formatVolatility(
                      selected.volatility
                        ?.power_law_vol_forecast ??
                        null,
                    ),
                    "text-[#49c6e5]",
                  ],
                  [
                    "MODEL SPREAD",
                    formatSignedPercent(
                      selected.volatility
                        ?.model_disagreement ??
                        null,
                      1,
                    ),
                    changeColour(
                      selected.volatility
                        ?.model_disagreement ??
                        null,
                    ),
                  ],
                ]}
              />

            </div>
          )}

          {selected?.risk && (
            <div className="grid gap-px border-t border-[#333] bg-[#333] md:grid-cols-5">

              <FactorCell
                label="VOL"
                value={
                  selected.risk
                    .volatility_component
                }
              />

              <FactorCell
                label="OI"
                value={
                  selected.risk
                    .leverage_component
                }
              />

              <FactorCell
                label="FUND"
                value={
                  selected.risk
                    .funding_component
                }
              />

              <FactorCell
                label="LIQ"
                value={
                  selected.risk
                    .liquidation_component
                }
              />

              <FactorCell
                label="CONC"
                value={
                  selected.risk
                    .market_structure_component
                }
              />

            </div>
          )}

        </section>


        {/* FILTER BAR */}
        <div className="mb-4 grid gap-3 border border-[#3f3f3f] bg-[#0d0d0d] p-3 lg:grid-cols-[1fr_280px_auto]">

          <input
            value={search}
            onChange={
              (event) =>
                setSearch(
                  event.target.value,
                )
            }
            placeholder="SEARCH SYMBOL OR ASSET..."
            className="border border-[#444] bg-[#080808] px-3 py-2 text-xs text-white outline-none placeholder:text-[#666] focus:border-[#ffb000]"
          />

          <select
            value={stateFilter}
            onChange={
              (event) =>
                setStateFilter(
                  event.target.value,
                )
            }
            className="border border-[#444] bg-[#080808] px-3 py-2 text-xs text-[#d0d0d0] outline-none focus:border-[#ffb000]"
          >
            <option value="ALL">
              ALL MARKET STATES
            </option>

            {stateOptions.map(
              (state) => (
                <option
                  key={state}
                  value={state}
                >
                  {state}
                </option>
              ),
            )}

          </select>

          <div className="flex items-center justify-end px-2 text-[10px] tracking-wide text-[#858585]">
            {visibleRows.length} / {rows.length} ASSETS
          </div>

        </div>


        {/* MARKET TABLE */}
        <section className="overflow-hidden border border-[#454545] bg-[#0d0d0d]">

          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#454545] bg-[#171717] px-4 py-3">

            <div>

              <div className="text-sm font-black tracking-[0.08em] text-[#f5f5f5]">
                CROSS-MARKET MONITOR
              </div>

              <div className="mt-1 text-xs tracking-wide text-[#949494]">
                CLICK HEADERS TO SORT · CLICK ROWS TO INSPECT
              </div>

            </div>

            <div className="text-right">

              <div
                className={
                  degradedSources.length === 0
                    ? "text-xs font-bold text-[#38d996]"
                    : "text-xs font-bold text-[#ffb000]"
                }
              >
                ● {navStatus}
              </div>

              <div className="mt-1 text-[10px] text-[#808080]">
                {latestSourceTimestamp(
                  spotRows,
                  derivativesRows,
                  liquidationRows,
                  riskRows,
                  volatilityRows,
                )}
              </div>

            </div>

          </div>

          {loading && rows.length === 0 && (
            <div className="px-4 py-8 text-sm text-[#888]">
              LOADING MARKET SURFACES...
            </div>
          )}

          {!loading &&
          rows.length === 0 && (
            <div className="px-4 py-8 text-sm text-[#888]">
              NO MARKET DATA
            </div>
          )}

          {rows.length > 0 && (
            <div className="max-h-[620px] overflow-auto">

              <table className="w-full min-w-[1580px] border-collapse text-xs">

                <thead className="sticky top-0 z-20">

                  <tr className="border-b border-[#4b4b4b] bg-[#141414] text-[#b8b8b8] shadow-[0_1px_0_#3b3b3b]">

                    <SortHeader
                      label="ASSET"
                      sort="symbol"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                    />

                    <SortHeader
                      label="PRICE"
                      sort="price"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="1H"
                      sort="change1h"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="24H"
                      sort="change24h"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="CDRR"
                      help="Relative 0–100 derivatives-stress score within the tracked universe; not a probability or price forecast."
                      sort="risk"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <Header help="Directional/regime classification from price, common-universe OI, volatility, funding, and liquidation context.">
                      PRIMARY STATE
                    </Header>

                    <SortHeader
                      label="OPEN INTEREST"
                      help="Clean tracked derivatives open interest after quality filters."
                      sort="oi"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="COMMON OI 1H"
                      help="One-hour OI change computed only on contracts valid both now and one hour ago."
                      sort="oi1h"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="FUNDING"
                      help="Median perpetual funding rate across valid tracked markets; not annualised."
                      sort="funding"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="BASIS"
                      help="Median index basis across valid tracked derivatives markets."
                      sort="basis"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="LIQ / OI 1H"
                      help="Current one-hour liquidation notional divided by clean tracked open interest."
                      sort="liqOi"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="RV 24H"
                      help="Twenty-four-hour realised volatility, displayed on an annualised basis."
                      sort="rv24h"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <Header
                      align="right"
                      help="Current risk/state readiness and source quality for the asset."
                      last
                    >
                      QUALITY
                    </Header>

                  </tr>

                </thead>

                <tbody>

                  {visibleRows.map(
                    (row) => {
                      const change1h =
                        spotChange(
                          row.spot,
                          "1h",
                        );

                      const change24h =
                        spotChange(
                          row.spot,
                          "24h",
                        );

                      const selectedRow =
                        row.symbol ===
                        effectiveSelectedSymbol;

                      return (
                        <tr
                          key={row.symbol}
                          onClick={
                            () =>
                              setSelectedSymbol(
                                row.symbol,
                              )
                          }
                          className={
                            selectedRow
                              ? "cursor-pointer border-b border-[#383838] bg-[#17140b]"
                              : "cursor-pointer border-b border-[#2d2d2d] transition hover:bg-[#151515]"
                          }
                        >

                          <td className="border-r border-[#303030] px-4 py-3">

                            <div className="font-black text-[#49c6e5]">
                              {row.symbol}
                            </div>

                            <div className="mt-1 text-[10px] text-[#8f8f8f]">
                              {row.asset}
                            </div>

                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#f1f1f1]">
                            {formatPrice(
                              row.spot
                                ?.price ??
                                row.volatility
                                  ?.price ??
                                null,
                            )}
                          </td>

                          <td
                            className={`border-r border-[#303030] px-4 py-3 text-right font-bold tabular-nums ${moveColour(
                              change1h,
                            )}`}
                          >
                            {formatSignedPoints(
                              change1h,
                            )}
                          </td>

                          <td
                            className={`border-r border-[#303030] px-4 py-3 text-right font-bold tabular-nums ${moveColour(
                              change24h,
                            )}`}
                          >
                            {formatSignedPoints(
                              change24h,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right">

                            <div className="font-black tabular-nums text-[#ffb000]">
                              {formatScore(
                                row.risk
                                  ?.provisional_risk_score ??
                                  null,
                              )}
                            </div>

                            <div className="mt-1 text-[9px] text-[#777]">
                              {row.risk
                                ?.risk_rank !== null &&
                              row.risk
                                ?.risk_rank !== undefined
                                ? `#${row.risk.risk_rank}`
                                : "—"}
                            </div>

                          </td>

                          <td className="border-r border-[#303030] px-4 py-3">

                            <span
                              className={`font-bold ${stateColour(
                                row.risk
                                  ?.primary_state ??
                                  null,
                              )}`}
                            >
                              {row.risk
                                ?.primary_state ??
                                "—"}
                            </span>

                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#e0e0e0]">
                            {formatMoney(
                              row.derivatives
                                ?.total_open_interest ??
                                null,
                            )}
                          </td>

                          <td
                            className={`border-r border-[#303030] px-4 py-3 text-right font-bold tabular-nums ${changeColour(
                              row.derivatives
                                ?.open_interest_change_common_1h ??
                                null,
                            )}`}
                          >
                            {row.derivatives
                              ?.common_oi_change_available_1h
                              ? formatSignedPercent(
                                  row.derivatives
                                    .open_interest_change_common_1h,
                                  2,
                                )
                              : "—"}
                          </td>

                          <td
                            className={`border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums ${rateColour(
                              row.derivatives
                                ?.median_funding_rate ??
                                null,
                            )}`}
                          >
                            {formatSignedPercent(
                              row.derivatives
                                ?.median_funding_rate ??
                                null,
                              4,
                            )}
                          </td>

                          <td
                            className={`border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums ${rateColour(
                              row.derivatives
                                ?.median_index_basis ??
                                null,
                            )}`}
                          >
                            {formatSignedPercent(
                              row.derivatives
                                ?.median_index_basis ??
                                null,
                              4,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#d0d0d0]">
                            {formatBasisPoints(
                              row.liquidations
                                ?.liquidations_to_oi_1h ??
                                null,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#d0d0d0]">
                            {formatVolatility(
                              row.volatility
                                ?.realized_vol_24h ??
                                null,
                            )}
                          </td>

                          <td className="px-4 py-3 text-right">

                            <span
                              className={
                                row.risk
                                  ?.risk_ready
                                  ? "font-bold text-[#38d996]"
                                  : "font-bold text-[#ffb000]"
                              }
                            >
                              {row.risk
                                ?.risk_ready
                                ? (
                                  row.risk
                                    ?.state_quality ??
                                  "READY"
                                )
                                : "BUILDING"}
                            </span>

                          </td>

                        </tr>
                      );
                    },
                  )}

                </tbody>

              </table>

            </div>
          )}

          <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-[#353535] bg-[#090909] px-4 py-2.5 text-[9px] tracking-wide text-[#707070]">

            <span>
              CDRR = RELATIVE STRESS MAGNITUDE
            </span>

            <span>
              COMMON OI = MATCHED CONTRACT UNIVERSE
            </span>

            <span>
              FUNDING NOT ANNUALISED
            </span>

            <span>
              LIQ/OI = CURRENT 1H LIQUIDATIONS / CLEAN OI
            </span>

            <span>
              RV = ANNUALISED REALISED VOLATILITY
            </span>

          </div>

        </section>

      </div>

    </main>
  );


  function handleSort(
    key: SortKey,
  ) {
    if (sortKey === key) {
      setSortDirection(
        (current) =>
          current === "asc"
            ? "desc"
            : "asc",
      );

      return;
    }

    setSortKey(
      key,
    );

    setSortDirection(
      key === "symbol" ||
      key === "risk"
        ? "asc"
        : "desc",
    );
  }
}


// ============================================================
// SUMMARY METRIC
// ============================================================

function SummaryMetric({
  label,
  value,
  sub,
  help,
  valueClass = "text-[#f7f7f7]",
}: {
  label: string;
  value: string;
  sub: string;
  help?: string;
  valueClass?: string;
}) {
  return (
    <div className="min-h-[98px] border-r border-[#3f3f3f] px-5 py-4">

      <div className="flex items-center text-[10px] font-semibold tracking-[0.12em] text-[#a2a2a2]">
        <span>{label}</span>
        {help && <InfoTip text={help} />}
      </div>

      <div
        className={`mt-1.5 text-2xl font-black tabular-nums ${valueClass}`}
      >
        {value}
      </div>

      <div className="mt-1.5 truncate text-[10px] font-medium tracking-wide text-[#929292]">
        {sub}
      </div>

    </div>
  );
}


// ============================================================
// DETAIL GROUP
// ============================================================

function DetailGroup({
  title,
  items,
}: {
  title: string;
  items: Array<
    [
      string,
      string,
      string?,
    ]
  >;
}) {
  return (
    <div className="bg-[#0d0d0d] p-4">

      <div className="mb-3 text-[10px] font-black tracking-[0.14em] text-[#8e8e8e]">
        {title}
      </div>

      <div className="space-y-2.5">

        {items.map(
          ([
            label,
            value,
            valueClass,
          ]) => (
            <div
              key={label}
              className="flex items-center justify-between gap-4 text-xs"
            >

              <span className="text-[#919191]">
                {label}
              </span>

              <span
                className={`text-right font-bold tabular-nums ${valueClass ?? "text-[#e3e3e3]"}`}
              >
                {value}
              </span>

            </div>
          ),
        )}

      </div>

    </div>
  );
}


// ============================================================
// FACTOR CELL
// ============================================================

function FactorCell({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  const percent =
    finite(value)
      ? Math.max(
          0,
          Math.min(
            100,
            value * 100,
          ),
        )
      : 0;

  return (
    <div className="bg-[#0b0b0b] px-4 py-3">

      <div className="flex items-center justify-between text-[10px]">

        <span className="font-bold text-[#929292]">
          {label}
        </span>

        <span className="font-black tabular-nums text-[#e8e8e8]">
          {finite(value)
            ? percent.toFixed(0)
            : "—"}
        </span>

      </div>

      <div className="mt-2 h-1.5 bg-[#282828]">

        <div
          className="h-full bg-[#ffb000]"
          style={{
            width: `${percent}%`,
          }}
        />

      </div>

    </div>
  );
}


// ============================================================
// TABLE HEADERS
// ============================================================

function Header({
  children,
  align = "left",
  help,
  last = false,
}: {
  children: React.ReactNode;
  align?: "left" | "right";
  help?: string;
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
      <span>{children}</span>
      {help && <InfoTip text={help} />}
    </th>
  );
}


function SortHeader({
  label,
  sort,
  current,
  direction,
  onSort,
  align = "left",
  help,
}: {
  label: string;
  sort: SortKey;
  current: SortKey;
  direction: "asc" | "desc";
  onSort: (
    key: SortKey,
  ) => void;
  align?: "left" | "right";
  help?: string;
}) {
  const active =
    current === sort;

  return (
    <th className="whitespace-nowrap border-r border-[#333] px-0 py-0">

      <button
        onClick={
          () =>
            onSort(
              sort,
            )
        }
        className={`
          flex
          w-full
          items-center
          gap-2
          px-4
          py-3
          font-bold
          tracking-wide
          transition
          hover:bg-[#1b1b1b]
          hover:text-white
          ${
            align === "right"
              ? "justify-end text-right"
              : "justify-start text-left"
          }
          ${
            active
              ? "text-[#ffb000]"
              : "text-[#b8b8b8]"
          }
        `}
      >
        <span>
          {label}
        </span>

        {help && <InfoTip text={help} />}

        {active && (
          <span className="text-[9px]">
            {direction === "asc"
              ? "▲"
              : "▼"}
          </span>
        )}

      </button>

    </th>
  );
}


// ============================================================
// SORTING
// ============================================================

function compareRows(
  a: MarketRow,
  b: MarketRow,
  key: SortKey,
  direction: "asc" | "desc",
) {
  const aValue =
    sortValue(
      a,
      key,
    );

  const bValue =
    sortValue(
      b,
      key,
    );

  if (
    aValue === null &&
    bValue === null
  ) {
    return a.symbol.localeCompare(
      b.symbol,
    );
  }

  if (aValue === null) {
    return 1;
  }

  if (bValue === null) {
    return -1;
  }

  let comparison = 0;

  if (
    typeof aValue === "string" &&
    typeof bValue === "string"
  ) {
    comparison =
      aValue.localeCompare(
        bValue,
      );
  } else if (
    typeof aValue === "number" &&
    typeof bValue === "number"
  ) {
    comparison =
      aValue - bValue;
  }

  return direction === "asc"
    ? comparison
    : -comparison;
}


function sortValue(
  row: MarketRow,
  key: SortKey,
): number | string | null {
  switch (key) {
    case "symbol":
      return row.symbol;

    case "risk":
      return row.risk
        ?.risk_rank ??
        null;

    case "price":
      return row.spot
        ?.price ??
        row.volatility
          ?.price ??
        null;

    case "change1h":
      return spotChange(
        row.spot,
        "1h",
      );

    case "change24h":
      return spotChange(
        row.spot,
        "24h",
      );

    case "oi":
      return row.derivatives
        ?.total_open_interest ??
        null;

    case "oi1h":
      return row.derivatives
        ?.open_interest_change_common_1h ??
        null;

    case "funding":
      return row.derivatives
        ?.median_funding_rate ??
        null;

    case "basis":
      return row.derivatives
        ?.median_index_basis ??
        null;

    case "liqOi":
      return row.liquidations
        ?.liquidations_to_oi_1h ??
        null;

    case "rv24h":
      return row.volatility
        ?.realized_vol_24h ??
        null;
  }
}


// ============================================================
// FORMATTERS / STATE
// ============================================================

function finite(
  value:
    number |
    null |
    undefined,
): value is number {
  return (
    value !== null &&
    value !== undefined &&
    Number.isFinite(value)
  );
}


function spotChange(
  row: SpotAsset | null,
  horizon: "1h" | "24h",
) {
  if (!row) {
    return null;
  }

  const processed =
    horizon === "1h"
      ? row.price_change_1h
      : row.price_change_24h;

  const raw =
    horizon === "1h"
      ? row.percent_change_1h
      : row.percent_change_24h;

  if (finite(processed)) {
    return processed * 100;
  }

  if (finite(raw)) {
    return raw;
  }

  return null;
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


function formatMoney(
  value: number | null,
) {
  if (!finite(value)) {
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

  if (
    Math.abs(value) >= 1e3
  ) {
    return `$${(
      value / 1e3
    ).toFixed(1)}K`;
  }

  return `$${value.toFixed(0)}`;
}


function formatScore(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return value.toFixed(1);
}


function formatSignedPoints(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  const sign =
    value > 0
      ? "+"
      : "";

  return `${sign}${value.toFixed(2)}%`;
}


function formatSignedPercent(
  value: number | null,
  decimals: number,
) {
  if (!finite(value)) {
    return "—";
  }

  const percent =
    value * 100;

  const sign =
    percent > 0
      ? "+"
      : "";

  return `${sign}${percent.toFixed(decimals)}%`;
}


function formatPercent(
  value: number | null,
  decimals: number,
) {
  if (!finite(value)) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(decimals)}%`;
}


function formatVolatility(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(1)}%`;
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


function formatBasisPoints(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return `${(
    value * 10_000
  ).toFixed(2)} bp`;
}


function moveColour(
  value: number | null,
) {
  if (!finite(value)) {
    return "text-[#aaa]";
  }

  if (value > 0) {
    return "text-[#38d996]";
  }

  if (value < 0) {
    return "text-[#ff6666]";
  }

  return "text-[#cfcfcf]";
}


function changeColour(
  value: number | null,
) {
  return moveColour(
    value,
  );
}


function rateColour(
  value: number | null,
) {
  if (!finite(value)) {
    return "text-[#999]";
  }

  if (value > 0) {
    return "text-[#ffb000]";
  }

  if (value < 0) {
    return "text-[#49c6e5]";
  }

  return "text-[#d0d0d0]";
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
    ) ||
    state.includes(
      "FORCED",
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


function liquidationDirection(
  longShare: number | null,
  total: number | null,
) {
  if (
    !finite(total) ||
    total <= 0 ||
    !finite(longShare)
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
  if (!finite(longShare)) {
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


function latestSourceTimestamp(
  spot: SpotAsset[],
  derivatives: DerivativesAsset[],
  liquidations: LiquidationAsset[],
  risk: RiskAsset[],
  volatility: VolatilityAsset[],
) {
  const timestamps: string[] = [];

  for (const row of spot) {
    const value =
      row.collected_at ??
      row.timestamp;

    if (value) {
      timestamps.push(value);
    }
  }

  for (const row of derivatives) {
    if (row.calculated_at) {
      timestamps.push(
        row.calculated_at,
      );
    }
  }

  for (const row of liquidations) {
    if (row.timestamp) {
      timestamps.push(
        row.timestamp,
      );
    }
  }

  for (const row of risk) {
    if (row.risk_source_at) {
      timestamps.push(
        row.risk_source_at,
      );
    }
  }

  for (const row of volatility) {
    const value =
      row.calculated_at ??
      row.timestamp;

    if (value) {
      timestamps.push(value);
    }
  }

  const latest =
    timestamps
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
        (a, b) =>
          a.getTime() -
          b.getTime(),
      )
      .at(-1);

  if (!latest) {
    return "—";
  }

  return `${latest
    .toISOString()
    .slice(11, 19)} UTC`;
}



function marketSourceFreshness(
  spotRows: SpotAsset[],
  derivativesRows: DerivativesAsset[],
  liquidationRows: LiquidationAsset[],
  riskRows: RiskAsset[],
  volatilityRows: VolatilityAsset[],
) {
  const latestPerSource = [
    latestDate(spotRows.map((row) => row.collected_at ?? row.timestamp ?? null)),
    latestDate(derivativesRows.map((row) => row.calculated_at)),
    latestDate(liquidationRows.map((row) => row.timestamp)),
    latestDate(riskRows.map((row) => row.risk_source_at)),
    latestDate(volatilityRows.map((row) => row.calculated_at ?? row.timestamp)),
  ].filter((value): value is Date => value !== null);

  if (latestPerSource.length === 0) return { sourceAt: null, ageSeconds: null };

  const oldestRequired = latestPerSource.sort((a, b) => a.getTime() - b.getTime())[0];
  return {
    sourceAt: oldestRequired.toISOString(),
    ageSeconds: Math.max(0, (Date.now() - oldestRequired.getTime()) / 1000),
  };
}

function latestDate(values: Array<string | null | undefined>) {
  const dates = values
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()))
    .sort((a, b) => a.getTime() - b.getTime());
  return dates.at(-1) ?? null;
}

function formatAgeSeconds(value: number | null) {
  if (!finite(value)) return "unknown";
  if (value < 60) return `${value.toFixed(0)}s`;
  if (value < 3600) return `${(value / 60).toFixed(1)}m`;
  return `${(value / 3600).toFixed(1)}h`;
}
