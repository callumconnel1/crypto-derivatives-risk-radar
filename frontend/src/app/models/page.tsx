"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";
import { InfoTip, StatusBanner, TerminalNav } from "@/components/TerminalChrome";


const REFRESH_INTERVAL = 15_000;

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

  power_law_alpha: number | null;
  power_law_beta: number | null;
  power_law_nu: number | null;

  ewma_lambda: number | null;

  calculated_at?: string | null;
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

type ModelRow = {
  symbol: string;
  asset: string;

  volatility: VolatilityAsset | null;
  risk: RiskAsset | null;
};

type SortKey =
  | "symbol"
  | "pl"
  | "ewma"
  | "spread"
  | "rv24h"
  | "volPctl"
  | "risk";

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

  const payload =
    await response.json();

  if (!Array.isArray(payload.data)) {
    throw new Error(
      `${endpoint} did not return a data array`,
    );
  }

  return payload.data as T[];
}

export default function ModelsPage() {
  const [
    volatilityRows,
    setVolatilityRows,
  ] = useState<VolatilityAsset[]>([]);

  const [
    riskRows,
    setRiskRows,
  ] = useState<RiskAsset[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    errors,
    setErrors,
  ] = useState<string[]>([]);

  const [
    selectedSymbol,
    setSelectedSymbol,
  ] = useState<string | null>(null);

  const [
    sortKey,
    setSortKey,
  ] = useState<SortKey>("spread");

  const [
    sortDirection,
    setSortDirection,
  ] = useState<"asc" | "desc">("desc");

  const [
    search,
    setSearch,
  ] = useState("");

  // ==========================================================
  // LOAD MODEL SURFACES
  // ==========================================================

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      const results =
        await Promise.allSettled([
          fetchDataArray<VolatilityAsset>(
            "/api/volatility/latest",
          ),
          fetchDataArray<RiskAsset>(
            "/api/risk/latest",
          ),
        ]);

      if (!mounted) {
        return;
      }

      const failed: string[] = [];

      const volatilityResult =
        results[0];

      if (
        volatilityResult.status ===
        "fulfilled"
      ) {
        setVolatilityRows(
          volatilityResult.value,
        );
      } else {
        failed.push(
          "VOLATILITY",
        );
      }

      const riskResult =
        results[1];

      if (
        riskResult.status ===
        "fulfilled"
      ) {
        setRiskRows(
          riskResult.value,
        );
      } else {
        failed.push(
          "RISK",
        );
      }

      setErrors(
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
      const symbols =
        new Set<string>();

      for (
        const row of volatilityRows
      ) {
        symbols.add(
          row.symbol,
        );
      }

      for (
        const row of riskRows
      ) {
        symbols.add(
          row.symbol,
        );
      }

      const volatilityMap =
        new Map(
          volatilityRows.map(
            (row) => [
              row.symbol,
              row,
            ],
          ),
        );

      const riskMap =
        new Map(
          riskRows.map(
            (row) => [
              row.symbol,
              row,
            ],
          ),
        );

      return Array.from(
        symbols,
      ).map(
        (symbol): ModelRow => {
          const volatility =
            volatilityMap.get(
              symbol,
            ) ??
            null;

          const risk =
            riskMap.get(
              symbol,
            ) ??
            null;

          return {
            symbol,
            asset:
              volatility?.asset ??
              risk?.asset ??
              symbol,
            volatility,
            risk,
          };
        },
      );
    },
    [
      volatilityRows,
      riskRows,
    ],
  );

  // ==========================================================
  // DEFAULT SELECTED ASSET
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
  // SUMMARY METRICS
  // ==========================================================

  const medianSpread =
    useMemo(
      () =>
        median(
          volatilityRows
            .map(
              (row) =>
                row.model_disagreement,
            )
            .filter(
              (
                value,
              ): value is number =>
                finite(value),
            ),
        ),
      [volatilityRows],
    );

  const powerLawAbove =
    useMemo(
      () =>
        volatilityRows.filter(
          (row) =>
            finite(
              row.model_disagreement,
            ) &&
            (
              row.model_disagreement ??
              0
            ) > 0,
        ).length,
      [volatilityRows],
    );

  const highVolCount =
    useMemo(
      () =>
        volatilityRows.filter(
          (row) =>
            finite(
              row.vol_percentile_24h,
            ) &&
            (
              row.vol_percentile_24h ??
              0
            ) >= 0.8,
        ).length,
      [volatilityRows],
    );

  const riskReadyCount =
    useMemo(
      () =>
        riskRows.filter(
          (row) =>
            row.risk_ready,
        ).length,
      [riskRows],
    );

  // ==========================================================
  // TABLE
  // ==========================================================

  const visibleRows =
    useMemo(
      () => {
        const query =
          search
            .trim()
            .toLowerCase();

        const filtered =
          rows.filter(
            (row) =>
              query.length === 0 ||
              row.symbol
                .toLowerCase()
                .includes(query) ||
              row.asset
                .toLowerCase()
                .includes(query),
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
    errors.length === 0
      ? (
        loading
          ? "LOADING"
          : "ONLINE"
      )
      : "DEGRADED";

  const sourceFreshness = modelSourceFreshness(volatilityRows, riskRows);
  const sourceStale = finite(sourceFreshness.ageSeconds) && sourceFreshness.ageSeconds > 360;
  const navStatus = pageStatus === "ONLINE" && sourceStale ? "STALE" : pageStatus;

  return (
    <main className="dashboard-terminal min-h-screen bg-[#050505] text-[#f4f4f4]">
      {/* NAV */}
      <TerminalNav
        active="models"
        status={navStatus}
        sourceAt={sourceFreshness.sourceAt}
        sourceAgeSeconds={sourceFreshness.ageSeconds}
        detail="OLDEST REQUIRED SOURCE"
      />

      {(errors.length > 0 || sourceStale) && (
        <StatusBanner
          tone={errors.length > 0 ? "error" : "warning"}
          title={errors.length > 0 ? "DEGRADED MODEL DATA" : "STALE MODEL DATA"}
        >
          {errors.length > 0
            ? `Refresh failed for: ${errors.join(", ")}. Last successful model outputs are retained where available.`
            : `The oldest required model source is ${formatAgeSeconds(sourceFreshness.ageSeconds)} old. The monitor is showing the last successful snapshot.`}
        </StatusBanner>
      )}

      {/* SUMMARY */}
      <div className="grid grid-cols-2 border-b border-[#444] bg-[#0d0d0d] lg:grid-cols-5">

        <Metric
          label="PRIMARY VOL MODEL"
          help="Primary next-one-hour conditional volatility model: Student-t power-law memory over five-minute returns."
          value="POWER-LAW"
          sub="STUDENT-t · 1H CONDITIONAL"
          valueClass="text-[#49c6e5]"
        />

        <Metric
          label="MEDIAN MODEL SPREAD"
          help="Median current disagreement between power-law and EWMA forecasts: (PL − EWMA) / EWMA."
          value={
            finite(
              medianSpread,
            )
              ? formatSignedPercent(
                  medianSpread,
                  1,
                )
              : "—"
          }
          sub="PL VS EWMA"
          valueClass={
            spreadColour(
              medianSpread,
            )
          }
        />

        <Metric
          label="PL ABOVE EWMA"
          help="Number of assets where the primary power-law forecast currently exceeds the EWMA forecast."
          value={`${powerLawAbove}/${volatilityRows.length || 20}`}
          sub="CURRENT SNAPSHOT"
        />

        <Metric
          label="HIGH VOL NAMES"
          help="Assets whose current 24-hour realised volatility sits at or above the 80th percentile of their own recent history."
          value={`${highVolCount}/${volatilityRows.length || 20}`}
          sub="24H VOL ≥ 80P"
          valueClass={
            highVolCount > 0
              ? "text-[#ffb000]"
              : "text-[#f7f7f7]"
          }
        />

        <Metric
          label="RISK MODEL READY"
          help="Assets with all five provisional production factors and timing/state requirements available."
          value={`${riskReadyCount}/${riskRows.length || 20}`}
          sub="PROVISIONAL v1 · EQUAL WEIGHT"
          valueClass={
            riskReadyCount ===
            riskRows.length &&
            riskRows.length > 0
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
              MODEL MONITOR
            </div>

            <div className="mt-1 text-xs tracking-[0.08em] text-[#a0a0a0]">
              VOLATILITY FORECASTING · FACTOR DECOMPOSITION · RESEARCH STATUS
            </div>

          </div>

          <div className="text-[10px] tracking-wide text-[#777]">
            LIVE MODEL OUTPUTS · STATIC RESEARCH VALIDATION LABELLED SEPARATELY
          </div>

        </div>

        {/* MODEL ARCHITECTURE */}
        <div className="grid gap-4 xl:grid-cols-4">

          <ModelCard
            number="01"
            title="POWER-LAW VOL"
            tag="PRIMARY"
            tagClass="text-[#49c6e5]"
            body="Student-t conditional variance model with power-law memory. Twelve 5-minute variance forecasts are aggregated into the next 1-hour conditional volatility estimate."
          />

          <ModelCard
            number="02"
            title="EWMA VOL"
            tag="SECONDARY"
            tagClass="text-[#bdbdbd]"
            body="Tuned exponentially weighted variance model used as a secondary benchmark. The live model spread measures disagreement against the primary power-law forecast."
          />

          <ModelCard
            number="03"
            title="CDRR v1"
            tag="PRODUCTION"
            tagClass="text-[#38d996]"
            body="Provisional equal-weight stress score: volatility, leverage/open interest, funding crowding, liquidations, and concentration. Direction is kept separate in the state engine."
          />

          <ModelCard
            number="04"
            title="STRUCTURE v2"
            tag="RESEARCH ONLY"
            tagClass="text-[#ffb000]"
            body="Candidate structure channel: 50% OI concentration, 25% confirmed basis magnitude, 25% confirmed basis dispersion. It is not used in the production score."
          />

        </div>

        {/* OFFLINE VALIDATION */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">

          <div className="border-b border-[#454545] bg-[#171717] px-4 py-3">

            <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
              OFFLINE VOLATILITY VALIDATION
            </div>

            <div className="mt-1 text-xs text-[#949494]">
              WALK-FORWARD RESEARCH · NOT A LIVE PERFORMANCE METRIC
            </div>

          </div>

          <div className="grid gap-px bg-[#333] md:grid-cols-4">

            <ValidationCell
              label="LOWER MEAN QLIKE"
              value="17 / 20"
              sub="POWER-LAW VS EWMA"
            />

            <ValidationCell
              label="SIGNIFICANT PL WINS"
              value="5"
              sub="HAC-ROBUST TEST"
            />

            <ValidationCell
              label="SIGNIFICANT EWMA WINS"
              value="0"
              sub="HAC-ROBUST TEST"
            />

            <ValidationCell
              label="FORECAST HORIZON"
              value="1H"
              sub="12 × 5-MIN STEPS"
            />

          </div>

        </section>

        {/* SELECTED ASSET */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">

          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#454545] bg-[#171717] px-4 py-3">

            <div>

              <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
                {selected
                  ? `${selected.symbol} · MODEL DETAIL`
                  : "MODEL DETAIL"}
              </div>

              <div className="mt-1 text-xs text-[#949494]">
                CURRENT VOLATILITY OUTPUTS AND CDRR FACTOR LOADS
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
            <>
              <div className="grid gap-px bg-[#333] xl:grid-cols-4">

                <DetailGroup
                  title="REALIZED VOL"
                  items={[
                    [
                      "RV 1H",
                      formatVol(
                        selected.volatility
                          ?.realized_vol_1h ??
                          null,
                      ),
                    ],
                    [
                      "RV 4H",
                      formatVol(
                        selected.volatility
                          ?.realized_vol_4h ??
                          null,
                      ),
                    ],
                    [
                      "RV 24H",
                      formatVol(
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
                      "4H / 24H",
                      formatRatio(
                        selected.volatility
                          ?.vol_ratio_4h_vs_24h ??
                          null,
                      ),
                    ],
                  ]}
                />

                <DetailGroup
                  title="FORECASTS"
                  items={[
                    [
                      "PL 1H FWD",
                      formatVol(
                        selected.volatility
                          ?.power_law_vol_forecast ??
                          null,
                      ),
                      "text-[#49c6e5]",
                    ],
                    [
                      "PL 1H σ",
                      formatOneHourSigma(
                        selected.volatility
                          ?.power_law_vol_forecast ??
                          null,
                      ),
                    ],
                    [
                      "EWMA 1H FWD",
                      formatVol(
                        selected.volatility
                          ?.ewma_vol_forecast ??
                          null,
                      ),
                    ],
                    [
                      "EWMA 1H σ",
                      formatOneHourSigma(
                        selected.volatility
                          ?.ewma_vol_forecast ??
                          null,
                      ),
                    ],
                    [
                      "MODEL SPREAD",
                      formatSignedPercent(
                        selected.volatility
                          ?.model_disagreement ??
                          null,
                        1,
                      ),
                      spreadColour(
                        selected.volatility
                          ?.model_disagreement ??
                          null,
                      ),
                    ],
                  ]}
                />

                <DetailGroup
                  title="POWER-LAW PARAMS"
                  items={[
                    [
                      "ALPHA",
                      formatParameter(
                        selected.volatility
                          ?.power_law_alpha ??
                          null,
                        4,
                      ),
                    ],
                    [
                      "BETA",
                      formatParameter(
                        selected.volatility
                          ?.power_law_beta ??
                          null,
                        6,
                      ),
                    ],
                    [
                      "NU",
                      formatParameter(
                        selected.volatility
                          ?.power_law_nu ??
                          null,
                        3,
                      ),
                    ],
                    [
                      "EWMA LAMBDA",
                      formatParameter(
                        selected.volatility
                          ?.ewma_lambda ??
                          null,
                        5,
                      ),
                    ],
                    [
                      "PRIMARY",
                      "POWER-LAW",
                      "text-[#49c6e5]",
                    ],
                  ]}
                />

                <DetailGroup
                  title="RISK STATUS"
                  items={[
                    [
                      "RANK",
                      selected.risk
                        ?.risk_rank !== null &&
                      selected.risk
                        ?.risk_rank !== undefined
                        ? `#${selected.risk.risk_rank}`
                        : "—",
                    ],
                    [
                      "X-SEC PCTL",
                      formatPercentile(
                        selected.risk
                          ?.risk_cross_percentile ??
                          null,
                      ),
                    ],
                    [
                      "READY",
                      selected.risk
                        ?.risk_ready
                        ? "YES"
                        : "NO",
                      selected.risk
                        ?.risk_ready
                        ? "text-[#38d996]"
                        : "text-[#ffb000]",
                    ],
                    [
                      "STATE QUALITY",
                      selected.risk
                        ?.state_quality ??
                        "—",
                    ],
                    [
                      "FUND SOURCE",
                      shortFundingSource(
                        selected.risk
                          ?.funding_component_source ??
                          null,
                      ),
                    ],
                  ]}
                />

              </div>

              {selected.risk && (
                <div className="grid gap-px border-t border-[#333] bg-[#333] md:grid-cols-5">

                  <FactorCell
                    label="VOLATILITY"
                    value={
                      selected.risk
                        .volatility_component
                    }
                  />

                  <FactorCell
                    label="LEVERAGE / OI"
                    value={
                      selected.risk
                        .leverage_component
                    }
                  />

                  <FactorCell
                    label="FUNDING"
                    value={
                      selected.risk
                        .funding_component
                    }
                  />

                  <FactorCell
                    label="LIQUIDATIONS"
                    value={
                      selected.risk
                        .liquidation_component
                    }
                  />

                  <FactorCell
                    label="CONCENTRATION"
                    value={
                      selected.risk
                        .market_structure_component
                    }
                  />

                </div>
              )}
            </>
          )}

        </section>

        {/* SEARCH */}
        <div className="mt-4 grid gap-3 border border-[#3f3f3f] bg-[#0d0d0d] p-3 lg:grid-cols-[1fr_auto]">

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

          <div className="flex items-center justify-end px-2 text-[10px] tracking-wide text-[#858585]">
            {visibleRows.length} / {rows.length} ASSETS
          </div>

        </div>

        {/* LIVE VOL TABLE */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">

          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#454545] bg-[#171717] px-4 py-3">

            <div>

              <div className="text-sm font-black tracking-[0.08em] text-[#f5f5f5]">
                LIVE VOLATILITY MODEL MONITOR
              </div>

              <div className="mt-1 text-xs tracking-wide text-[#949494]">
                REALISED VOL · CONDITIONAL FORECASTS · MODEL DISAGREEMENT
              </div>

            </div>

            <div className="text-right">

              <div
                className={
                  errors.length === 0
                    ? "text-xs font-bold text-[#38d996]"
                    : "text-xs font-bold text-[#ffb000]"
                }
              >
                ● {navStatus}
              </div>

              <div className="mt-1 text-[10px] text-[#808080]">
                {latestTimestamp(
                  volatilityRows,
                  riskRows,
                )}
              </div>

            </div>

          </div>

          {loading && rows.length === 0 && (
            <div className="px-4 py-8 text-sm text-[#888]">
              LOADING MODEL OUTPUTS...
            </div>
          )}

          {rows.length > 0 && (
            <div className="max-h-[620px] overflow-auto">

              <table className="w-full min-w-[1350px] border-collapse text-xs">

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
                      label="CDRR"
                      help="Relative 0–100 derivatives-stress score within the tracked universe."
                      sort="risk"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <Header help="Directional/regime classification from the state engine; kept separate from stress magnitude.">
                      STATE
                    </Header>

                    <SortHeader
                      label="RV 24H"
                      help="Twenty-four-hour realised volatility, annualised."
                      sort="rv24h"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="24H PCTL"
                      help="Current 24-hour realised-volatility percentile versus the asset's own recent history."
                      sort="volPctl"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="PL 1H FWD"
                      help="Primary next-one-hour conditional volatility forecast from the Student-t power-law model, annualised."
                      sort="pl"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="EWMA 1H FWD"
                      help="Secondary next-one-hour EWMA conditional volatility forecast, annualised."
                      sort="ewma"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <SortHeader
                      label="MODEL SPREAD"
                      help="Forecast disagreement defined as (PL − EWMA) / EWMA. Sorting uses absolute disagreement magnitude."
                      sort="spread"
                      current={sortKey}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="right"
                    />

                    <Header
                      align="right"
                      help="Power-law memory exponent α. Larger values make distant squared returns decay more quickly."
                    >
                      ALPHA
                    </Header>

                    <Header
                      align="right"
                      help="Power-law variance-memory scale coefficient β."
                    >
                      BETA
                    </Header>

                    <Header
                      align="right"
                      help="Student-t degrees of freedom ν. Lower values imply heavier residual tails."
                    >
                      NU
                    </Header>

                    <Header
                      align="right"
                      help="EWMA decay parameter λ controlling how quickly older squared returns lose weight."
                      last
                    >
                      EWMA λ
                    </Header>

                  </tr>

                </thead>

                <tbody>

                  {visibleRows.map(
                    (row) => {
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

                          <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#d8d8d8]">
                            {formatVol(
                              row.volatility
                                ?.realized_vol_24h ??
                                null,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right font-semibold tabular-nums text-[#d8d8d8]">
                            {formatPercentile(
                              row.volatility
                                ?.vol_percentile_24h ??
                                null,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right">

                            <div className="font-black tabular-nums text-[#49c6e5]">
                              {formatVol(
                                row.volatility
                                  ?.power_law_vol_forecast ??
                                  null,
                              )}
                            </div>

                            <div className="mt-1 text-[9px] text-[#777]">
                              1H σ{" "}
                              {formatOneHourSigma(
                                row.volatility
                                  ?.power_law_vol_forecast ??
                                  null,
                              )}
                            </div>

                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right">

                            <div className="font-semibold tabular-nums text-[#d8d8d8]">
                              {formatVol(
                                row.volatility
                                  ?.ewma_vol_forecast ??
                                  null,
                              )}
                            </div>

                            <div className="mt-1 text-[9px] text-[#777]">
                              1H σ{" "}
                              {formatOneHourSigma(
                                row.volatility
                                  ?.ewma_vol_forecast ??
                                  null,
                              )}
                            </div>

                          </td>

                          <td
                            className={`border-r border-[#303030] px-4 py-3 text-right font-black tabular-nums ${spreadColour(
                              row.volatility
                                ?.model_disagreement ??
                                null,
                            )}`}
                          >
                            {formatSignedPercent(
                              row.volatility
                                ?.model_disagreement ??
                                null,
                              1,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#bdbdbd]">
                            {formatParameter(
                              row.volatility
                                ?.power_law_alpha ??
                                null,
                              4,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#bdbdbd]">
                            {formatParameter(
                              row.volatility
                                ?.power_law_beta ??
                                null,
                              6,
                            )}
                          </td>

                          <td className="border-r border-[#303030] px-4 py-3 text-right tabular-nums text-[#bdbdbd]">
                            {formatParameter(
                              row.volatility
                                ?.power_law_nu ??
                                null,
                              3,
                            )}
                          </td>

                          <td className="px-4 py-3 text-right tabular-nums text-[#bdbdbd]">
                            {formatParameter(
                              row.volatility
                                ?.ewma_lambda ??
                                null,
                              5,
                            )}
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
              PL = POWER-LAW STUDENT-t MODEL
            </span>

            <span>
              EWMA = SECONDARY BENCHMARK
            </span>

            <span>
              FORECAST FIGURES ARE ANNUALISED VOLATILITY
            </span>

            <span>
              1H σ = IMPLIED ONE-HOUR STANDARD DEVIATION
            </span>

            <span>
              MODEL SPREAD = (PL − EWMA) / EWMA
            </span>

          </div>

        </section>

        {/* FACTOR MATRIX */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">

          <div className="border-b border-[#454545] bg-[#171717] px-4 py-3">

            <div className="text-sm font-black tracking-[0.08em] text-[#f5f5f5]">
              CDRR FACTOR MATRIX
            </div>

            <div className="mt-1 text-xs tracking-wide text-[#949494]">
              PROVISIONAL v1 · EQUAL-WEIGHT 5-FACTOR STRESS MAGNITUDE
            </div>

          </div>

          <div className="max-h-[560px] overflow-auto">

            <table className="w-full min-w-[1100px] border-collapse text-xs">

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
                    CONC
                  </Header>

                  <Header>
                    FUND SOURCE
                  </Header>

                  <Header last>
                    STATE
                  </Header>

                </tr>

              </thead>

              <tbody>

                {[...riskRows]
                  .sort(
                    (a, b) =>
                      (
                        a.risk_rank ??
                        Infinity
                      )
                      -
                      (
                        b.risk_rank ??
                        Infinity
                      ),
                  )
                  .map(
                    (row) => (
                      <tr
                        key={row.symbol}
                        onClick={
                          () =>
                            setSelectedSymbol(
                              row.symbol,
                            )
                        }
                        className="cursor-pointer border-b border-[#2d2d2d] transition hover:bg-[#151515]"
                      >

                        <td className="border-r border-[#303030] px-4 py-3 font-bold tabular-nums text-[#999]">
                          {row.risk_rank !== null
                            ? `#${row.risk_rank}`
                            : "—"}
                        </td>

                        <td className="border-r border-[#303030] px-4 py-3 font-black text-[#49c6e5]">
                          {row.symbol}
                        </td>

                        <td className="border-r border-[#303030] px-4 py-3 text-right font-black tabular-nums text-[#ffb000]">
                          {formatScore(
                            row.provisional_risk_score,
                          )}
                        </td>

                        <FactorTableCell
                          value={
                            row.volatility_component
                          }
                        />

                        <FactorTableCell
                          value={
                            row.leverage_component
                          }
                        />

                        <FactorTableCell
                          value={
                            row.funding_component
                          }
                        />

                        <FactorTableCell
                          value={
                            row.liquidation_component
                          }
                        />

                        <FactorTableCell
                          value={
                            row.market_structure_component
                          }
                        />

                        <td className="border-r border-[#303030] px-4 py-3 text-[10px] font-semibold text-[#aaa]">
                          {shortFundingSource(
                            row.funding_component_source,
                          )}
                        </td>

                        <td className="px-4 py-3">
                          <span
                            className={`font-bold ${stateColour(
                              row.primary_state,
                            )}`}
                          >
                            {row.primary_state ?? "—"}
                          </span>
                        </td>

                      </tr>
                    ),
                  )}

              </tbody>

            </table>

          </div>

          <div className="border-t border-[#353535] bg-[#090909] px-4 py-2.5 text-[9px] leading-relaxed tracking-wide text-[#707070]">
            PRODUCTION FACTOR D = OI CONCENTRATION ONLY. BASIS LEVEL AND BASIS DISPERSION REMAIN RESEARCH-ONLY UNTIL LONGITUDINAL VALIDATION SUPPORTS PROMOTION.
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

function Metric({
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

      <div className="mt-1.5 text-[10px] font-medium tracking-wide text-[#929292]">
        {sub}
      </div>

    </div>
  );
}

// ============================================================
// MODEL CARD
// ============================================================

function ModelCard({
  number,
  title,
  tag,
  tagClass,
  body,
}: {
  number: string;
  title: string;
  tag: string;
  tagClass: string;
  body: string;
}) {
  return (
    <section className="border border-[#454545] bg-[#0d0d0d] p-4">

      <div className="flex items-start justify-between gap-4">

        <span className="text-[10px] font-bold text-[#666]">
          {number}
        </span>

        <span
          className={`text-[9px] font-black tracking-[0.12em] ${tagClass}`}
        >
          {tag}
        </span>

      </div>

      <div className="mt-5 text-sm font-black tracking-[0.08em] text-[#f1f1f1]">
        {title}
      </div>

      <p className="mt-3 text-xs leading-5 text-[#999]">
        {body}
      </p>

    </section>
  );
}

// ============================================================
// VALIDATION CELL
// ============================================================

function ValidationCell({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="bg-[#0b0b0b] px-4 py-4">

      <div className="text-[10px] font-bold tracking-[0.1em] text-[#888]">
        {label}
      </div>

      <div className="mt-2 text-2xl font-black tabular-nums text-[#f4f4f4]">
        {value}
      </div>

      <div className="mt-1 text-[9px] tracking-wide text-[#777]">
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
// FACTOR CELLS
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

function FactorTableCell({
  value,
}: {
  value: number | null;
}) {
  const percent =
    finite(value)
      ? value * 100
      : null;

  return (
    <td className="border-r border-[#303030] px-4 py-3 text-right">

      <div className="font-bold tabular-nums text-[#d6d6d6]">
        {percent !== null
          ? percent.toFixed(0)
          : "—"}
      </div>

      <div className="ml-auto mt-1 h-1 w-12 bg-[#2d2d2d]">

        <div
          className="h-full bg-[#ffb000]"
          style={{
            width: `${Math.max(
              0,
              Math.min(
                100,
                percent ?? 0,
              ),
            )}%`,
          }}
        />

      </div>

    </td>
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
// SORT
// ============================================================

function compareRows(
  a: ModelRow,
  b: ModelRow,
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
  row: ModelRow,
  key: SortKey,
): number | string | null {
  switch (key) {
    case "symbol":
      return row.symbol;

    case "risk":
      return row.risk
        ?.risk_rank ??
        null;

    case "pl":
      return row.volatility
        ?.power_law_vol_forecast ??
        null;

    case "ewma":
      return row.volatility
        ?.ewma_vol_forecast ??
        null;

    case "spread":
      return finite(
        row.volatility
          ?.model_disagreement,
      )
        ? Math.abs(
            row.volatility
              ?.model_disagreement ??
              0,
          )
        : null;

    case "rv24h":
      return row.volatility
        ?.realized_vol_24h ??
        null;

    case "volPctl":
      return row.volatility
        ?.vol_percentile_24h ??
        null;
  }
}

// ============================================================
// FORMATTERS
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

function median(
  values: number[],
) {
  if (
    values.length === 0
  ) {
    return null;
  }

  const sorted =
    [...values].sort(
      (a, b) =>
        a - b,
    );

  const middle =
    Math.floor(
      sorted.length / 2,
    );

  if (
    sorted.length % 2 === 0
  ) {
    return (
      sorted[middle - 1] +
      sorted[middle]
    ) / 2;
  }

  return sorted[middle];
}

function formatVol(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return `${(
    value * 100
  ).toFixed(1)}%`;
}

function formatOneHourSigma(
  annualizedVol: number | null,
) {
  if (
    !finite(
      annualizedVol,
    )
  ) {
    return "—";
  }

  const oneHourSigma =
    annualizedVol /
    Math.sqrt(
      365 * 24,
    );

  return `${(
    oneHourSigma * 100
  ).toFixed(2)}%`;
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

function formatRatio(
  value: number | null,
) {
  if (!finite(value)) {
    return "—";
  }

  return `${value.toFixed(2)}×`;
}

function formatParameter(
  value: number | null,
  decimals: number,
) {
  if (!finite(value)) {
    return "—";
  }

  return value.toFixed(
    decimals,
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

function spreadColour(
  value: number | null,
) {
  if (!finite(value)) {
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

function latestTimestamp(
  volatilityRows: VolatilityAsset[],
  riskRows: RiskAsset[],
) {
  const values: string[] = [];

  for (
    const row of volatilityRows
  ) {
    const value =
      row.calculated_at ??
      row.timestamp;

    if (value) {
      values.push(
        value,
      );
    }
  }

  for (
    const row of riskRows
  ) {
    if (
      row.risk_source_at
    ) {
      values.push(
        row.risk_source_at,
      );
    }
  }

  const latest =
    values
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


function modelSourceFreshness(
  volatilityRows: VolatilityAsset[],
  riskRows: RiskAsset[],
) {
  const latestPerSource = [
    latestDate(volatilityRows.map((row) => row.calculated_at ?? row.timestamp)),
    latestDate(riskRows.map((row) => row.risk_source_at)),
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
