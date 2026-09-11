"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import DerivativesPanel from "@/components/DerivativesPanel";
import LiquidationsPanel from "@/components/LiquidationsPanel";
import MarketTable from "@/components/MarketTable";
import RiskRadarPanel from "@/components/RiskRadarPanel";
import VolatilityPanel from "@/components/VolatilityPanel";
import { InfoTip, StatusBanner, TerminalNav } from "@/components/TerminalChrome";


const REFRESH_INTERVAL = 15_000;

type DerivativesAsset = {
  symbol: string;
  asset: string;
  total_open_interest: number | null;
  median_funding_rate: number | null;
  calculated_at: string | null;
};

type GlobalLiquidations = {
  total_liquidations_24h: number | null;
  long_liquidation_share_24h: number | null;
  collected_at?: string | null;
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

type StateAsset = {
  symbol: string;
  volatility_state: string | null;
  vol_ratio_1h_vs_24h: number | null;
  state_ready_1h: boolean;
  state_quality: string | null;
  state_source_at: string | null;
};

type SnapshotHealth = {
  available: boolean;
  rows: number | null;
  modified_at: string | null;
  age_seconds: number | null;
  error: string | null;
};

type HealthResponse = {
  status: "healthy" | "degraded" | string;
  service: string;
  version: string;
  checked_at: string;
  snapshots: Record<string, SnapshotHealth>;
};

async function fetchDataArray<T>(endpoint: string): Promise<T[]> {
  const response = await fetch(`${endpoint}?t=${Date.now()}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`${endpoint} returned HTTP ${response.status}`);
  }

  const payload = await response.json();

  if (!Array.isArray(payload.data)) {
    throw new Error(`${endpoint} did not return a data array`);
  }

  return payload.data as T[];
}

async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`/api/health?t=${Date.now()}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`/api/health returned HTTP ${response.status}`);
  }

  return response.json();
}

export default function Dashboard() {
  const [derivatives, setDerivatives] = useState<DerivativesAsset[]>([]);
  const [globalLiquidations, setGlobalLiquidations] =
    useState<GlobalLiquidations | null>(null);
  const [riskRows, setRiskRows] = useState<RiskAsset[]>([]);
  const [stateRows, setStateRows] = useState<StateAsset[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const [summaryError, setSummaryError] = useState(false);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [riskLoading, setRiskLoading] = useState(true);

  // ============================================================
  // LOAD DASHBOARD SUMMARY DATA
  // ============================================================

  useEffect(() => {
    let mounted = true;

    async function loadSummary() {
      const results = await Promise.allSettled([
        fetchDataArray<DerivativesAsset>("/api/derivatives/latest"),
        fetchDataArray<GlobalLiquidations>("/api/liquidations/global"),
        fetchDataArray<RiskAsset>("/api/risk/latest"),
        fetchDataArray<StateAsset>("/api/states/latest"),
        fetchHealth(),
      ]);

      if (!mounted) {
        return;
      }

      let anyError = false;

      const derivativesResult = results[0];

      if (derivativesResult.status === "fulfilled") {
        setDerivatives(derivativesResult.value);
      } else {
        anyError = true;
      }

      const liquidationsResult = results[1];

      if (liquidationsResult.status === "fulfilled") {
        setGlobalLiquidations(liquidationsResult.value[0] ?? null);
      } else {
        anyError = true;
      }

      const riskResult = results[2];

      if (riskResult.status === "fulfilled") {
        setRiskRows(riskResult.value);
        setRiskError(null);
      } else {
        anyError = true;

        setRiskError(
          riskResult.reason instanceof Error
            ? riskResult.reason.message
            : "RISK DATA UNAVAILABLE",
        );
      }

      setRiskLoading(false);

      const statesResult = results[3];

      if (statesResult.status === "fulfilled") {
        setStateRows(statesResult.value);
      } else {
        anyError = true;
      }

      const healthResult = results[4];

      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value);
      } else {
        anyError = true;
      }

      setSummaryError(anyError);
    }

    loadSummary();

    const interval = window.setInterval(loadSummary, REFRESH_INTERVAL);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  // ============================================================
  // SUMMARY METRICS
  // ============================================================

  const totalOpenInterest = useMemo(
    () =>
      derivatives.reduce((total, asset) => {
        const value = asset.total_open_interest;

        if (value === null || !Number.isFinite(value)) {
          return total;
        }

        return total + value;
      }, 0),
    [derivatives],
  );

  const medianFunding = useMemo(() => {
    const values = derivatives
      .map((asset) => asset.median_funding_rate)
      .filter(
        (value): value is number =>
          value !== null && Number.isFinite(value),
      )
      .sort((a, b) => a - b);

    if (values.length === 0) {
      return null;
    }

    const midpoint = Math.floor(values.length / 2);

    if (values.length % 2 === 0) {
      return (values[midpoint - 1] + values[midpoint]) / 2;
    }

    return values[midpoint];
  }, [derivatives]);

  const readyRiskRows = useMemo(
    () =>
      riskRows
        .filter(
          (row) =>
            row.risk_ready && finite(row.provisional_risk_score),
        )
        .sort(
          (a, b) =>
            (b.provisional_risk_score ?? -Infinity) -
            (a.provisional_risk_score ?? -Infinity),
        ),
    [riskRows],
  );

  const topRisk = readyRiskRows[0] ?? null;

  const volatilityBreadth = useMemo(() => {
    const valid = stateRows.filter(
      (row) =>
        row.state_ready_1h &&
        (row.volatility_state === "EXPANDING" ||
          finite(row.vol_ratio_1h_vs_24h)),
    );

    if (valid.length === 0) {
      return null;
    }

    const expanding = valid.filter(
      (row) =>
        row.volatility_state === "EXPANDING" ||
        (finite(row.vol_ratio_1h_vs_24h) &&
          (row.vol_ratio_1h_vs_24h ?? 0) > 1),
    );

    return expanding.length / valid.length;
  }, [stateRows]);

  const apiStatus =
    health === null
      ? summaryError
        ? "ERROR"
        : "LOADING"
      : health.status === "healthy"
        ? "ONLINE"
        : "DEGRADED";

  const riskSnapshotAge = health?.snapshots.risk?.age_seconds ?? null;
  const riskSnapshotAt = health?.snapshots.risk?.modified_at ?? null;
  const riskSnapshotStale = finite(riskSnapshotAge) && riskSnapshotAge > 360;
  const navStatus = apiStatus === "ONLINE" && riskSnapshotStale ? "STALE" : apiStatus;

  return (
    <main className="dashboard-terminal min-h-screen bg-[#050505] text-[#f4f4f4]">
      {/* NAV */}
      <TerminalNav
        active="risk"
        status={navStatus}
        sourceAt={riskSnapshotAt}
        sourceAgeSeconds={riskSnapshotAge}
        detail="RISK SNAPSHOT"
      />

      {(summaryError || riskSnapshotStale) && (
        <StatusBanner
          tone={summaryError ? "error" : "warning"}
          title={summaryError ? "DEGRADED DATA" : "STALE RISK SNAPSHOT"}
        >
          {summaryError
            ? "One or more dashboard sources failed to refresh. Last successful values are retained where available."
            : `The primary risk snapshot is ${snapshotAge(health, "risk") ?? "older than expected"}. The terminal is displaying the last successful result.`}
        </StatusBanner>
      )}

      {/* SUMMARY METRICS */}
      <div className="grid grid-cols-2 border-b border-[#444] bg-[#0d0d0d] lg:grid-cols-5">
        <Metric
          label="TOP CDRR RISK"
          help="Highest current relative stress score in the tracked 20-asset universe. The score is not a crash probability."
          value={
            finite(topRisk?.provisional_risk_score)
              ? (topRisk?.provisional_risk_score ?? 0).toFixed(1)
              : "—"
          }
          sub={
            topRisk
              ? `#1 ${topRisk.symbol} · PROVISIONAL`
              : riskError
                ? "RISK API OFFLINE"
                : "LOADING"
          }
          valueClass="text-[#ffb000]"
        />

        <Metric
          label="TRACKED OPEN INTEREST"
          help="Clean derivatives open interest retained after freshness, identity, outlier, and venue-consistency checks."
          value={
            derivatives.length > 0
              ? formatMoney(totalOpenInterest)
              : "—"
          }
          sub={
            derivatives.length > 0
              ? `${derivatives.length} ASSETS · CLEAN OI`
              : "LOADING"
          }
        />

        <Metric
          label="GLOBAL 24H LIQUIDATIONS"
          help="CoinMarketCap global 24-hour liquidation notional. This is market-wide context and is separate from the tracked 20-asset CDRR universe."
          value={
            finite(globalLiquidations?.total_liquidations_24h)
              ? formatMoney(
                  globalLiquidations?.total_liquidations_24h ?? 0,
                )
              : "—"
          }
          sub={
            finite(globalLiquidations?.long_liquidation_share_24h)
              ? `${(
                  (globalLiquidations?.long_liquidation_share_24h ?? 0) *
                  100
                ).toFixed(1)}% LONG`
              : "LOADING"
          }
        />

        <Metric
          label="MEDIAN FUNDING"
          help="Cross-asset median perpetual funding rate. Funding is displayed as observed and is not annualised."
          value={
            medianFunding !== null
              ? formatSignedPercent(medianFunding)
              : "—"
          }
          sub={
            derivatives.length > 0
              ? "CROSS-ASSET MEDIAN"
              : "LOADING"
          }
          valueClass={fundingColour(medianFunding)}
        />

        <Metric
          label="VOLATILITY BREADTH"
          help="Share of state-ready assets whose 1-hour volatility is expanding relative to the 24-hour baseline."
          value={
            volatilityBreadth !== null
              ? `${(volatilityBreadth * 100).toFixed(0)}%`
              : "—"
          }
          sub={
            volatilityBreadth !== null
              ? "1H VOL EXPANDING"
              : "LOADING"
          }
        />
      </div>

      <div className="p-4 lg:p-5">
        {/* TITLE */}
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-lg font-black tracking-wide text-[#f7f7f7]">
              DERIVATIVES RISK RADAR
            </div>

            <div className="mt-1 text-xs tracking-[0.08em] text-[#a0a0a0]">
              LIVE PROCESSED MARKET STATE · 20-ASSET RESEARCH UNIVERSE
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => window.location.reload()}
              className="border border-[#555] bg-[#111] px-4 py-2 text-xs font-semibold text-[#c8c8c8] transition hover:border-[#888] hover:text-white"
            >
              REFRESH
            </button>
          </div>
        </div>

        {/* PRIMARY RISK RANKING */}
        <RiskRadarPanel
          rows={riskRows}
          loading={riskLoading}
          error={riskError}
        />

        {/* OVERVIEW PANELS */}
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <TerminalPanel title="TOP RISK NAMES">
            <div>
              {readyRiskRows.slice(0, 5).map((row) => (
                <RiskNameRow
                  key={row.symbol}
                  rank={row.risk_rank}
                  asset={row.symbol}
                  score={row.provisional_risk_score}
                  state={row.primary_state}
                />
              ))}

              {readyRiskRows.length === 0 && (
                <div className="py-3 text-xs text-[#989898]">
                  RISK SNAPSHOT UNAVAILABLE
                </div>
              )}
            </div>
          </TerminalPanel>

          <TerminalPanel
            title={
              topRisk
                ? `#1 RISK DRIVERS · ${topRisk.symbol}`
                : "#1 RISK DRIVERS"
            }
          >
            <div className="space-y-5">
              <RiskBar
                label="VOLATILITY"
                value={topRisk?.volatility_component ?? null}
              />

              <RiskBar
                label="LEVERAGE / OI"
                value={topRisk?.leverage_component ?? null}
              />

              <RiskBar
                label="FUNDING"
                value={topRisk?.funding_component ?? null}
              />

              <RiskBar
                label="LIQUIDATIONS"
                value={topRisk?.liquidation_component ?? null}
              />

              <RiskBar
                label="CONCENTRATION"
                value={topRisk?.market_structure_component ?? null}
              />
            </div>

            <div className="mt-4 border-t border-[#333] pt-3 text-[10px] leading-relaxed text-[#9a9a9a]">
              FACTOR LOADS FOR THE CURRENT #1 RANKED ASSET. THE TOTAL
              SCORE REMAINS PROVISIONAL AND RELATIVE TO THE TRACKED
              UNIVERSE.
            </div>
          </TerminalPanel>

          <TerminalPanel title="SYSTEM">
            <SystemRow
              name="API SERVER"
              status={apiStatus}
              detail={health ? `v${health.version}` : null}
            />

            <SystemRow
              name="SPOT SNAPSHOT"
              status={snapshotStatus(health, "spot")}
              detail={snapshotAge(health, "spot")}
            />

            <SystemRow
              name="VOL ENGINE"
              status={snapshotStatus(health, "volatility")}
              detail={snapshotAge(health, "volatility")}
            />

            <SystemRow
              name="DERIVATIVES ENGINE"
              status={snapshotStatus(health, "derivatives")}
              detail={snapshotAge(health, "derivatives")}
            />

            <SystemRow
              name="STATE ENGINE"
              status={snapshotStatus(health, "states")}
              detail={snapshotAge(health, "states")}
            />

            <SystemRow
              name="RISK ENGINE"
              status={snapshotStatus(health, "risk")}
              detail={snapshotAge(health, "risk")}
            />
          </TerminalPanel>
        </div>

        {/* LIVE SPOT MARKET */}
        <div className="mt-6">
          <MarketTable />
        </div>

        {/* VOLATILITY ENGINE */}
        <div className="mt-5">
          <VolatilityPanel />
        </div>

        {/* DERIVATIVES ENGINE */}
        <div className="mt-5">
          <DerivativesPanel />
        </div>

        {/* LIQUIDATIONS */}
        <div className="mt-5">
          <LiquidationsPanel />
        </div>
      </div>
    </main>
  );
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
// TERMINAL PANEL
// ============================================================

function TerminalPanel({
  title,
  children,
}: {
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="border border-[#454545] bg-[#0d0d0d]">
      <div className="border-b border-[#454545] bg-[#181818] px-4 py-3 text-xs font-black tracking-[0.08em] text-[#ffb000]">
        {title}
      </div>

      <div className="p-4">{children}</div>
    </section>
  );
}

// ============================================================
// TOP-RISK ROW
// ============================================================

function RiskNameRow({
  rank,
  asset,
  score,
  state,
}: {
  rank: number | null;
  asset: string;
  score: number | null;
  state: string | null;
}) {
  return (
    <div className="grid grid-cols-[34px_52px_64px_1fr] items-center gap-2 border-b border-[#303030] py-3 text-xs last:border-0">
      <span className="tabular-nums text-[#989898]">
        {rank !== null ? `#${rank}` : "—"}
      </span>

      <span className="font-black text-[#49c6e5]">{asset}</span>

      <span className="font-black tabular-nums text-[#ffb000]">
        {finite(score) ? score.toFixed(1) : "—"}
      </span>

      <span className="truncate text-right text-[10px] font-medium text-[#bdbdbd]">
        {state ?? "—"}
      </span>
    </div>
  );
}

// ============================================================
// FACTOR BAR
// ============================================================

function RiskBar({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  const percent = finite(value)
    ? Math.max(0, Math.min(100, value * 100))
    : 0;

  return (
    <div>
      <div className="mb-2 flex justify-between text-xs">
        <span className="font-semibold text-[#b5b5b5]">
          {label}
        </span>

        <span className="font-black tabular-nums text-[#f4f4f4]">
          {finite(value) ? percent.toFixed(0) : "—"}
        </span>
      </div>

      <div className="h-2 bg-[#282828]">
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
// SYSTEM ROW
// ============================================================

function SystemRow({
  name,
  status,
  detail,
}: {
  name: string;
  status: string;
  detail: string | null;
}) {
  const statusClass =
    status === "ONLINE" || status === "ACTIVE"
      ? "text-[#38d996]"
      : status === "DEGRADED"
        ? "text-[#ffb000]"
        : status === "LOADING"
          ? "text-[#999]"
          : "text-[#ff6666]";

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-b border-[#303030] py-3 text-xs last:border-0">
      <div>
        <div className="font-semibold text-[#b3b3b3]">
          {name}
        </div>

        {detail && (
          <div className="mt-1 text-[10px] text-[#8e8e8e]">
            {detail}
          </div>
        )}
      </div>

      <span className={`font-bold ${statusClass}`}>
        {status}
      </span>
    </div>
  );
}

// ============================================================
// HELPERS
// ============================================================

function finite(
  value: number | null | undefined,
): value is number {
  return (
    value !== null &&
    value !== undefined &&
    Number.isFinite(value)
  );
}

function formatMoney(value: number) {
  if (!Number.isFinite(value)) {
    return "—";
  }

  if (Math.abs(value) >= 1e12) {
    return `$${(value / 1e12).toFixed(2)}T`;
  }

  if (Math.abs(value) >= 1e9) {
    return `$${(value / 1e9).toFixed(1)}B`;
  }

  if (Math.abs(value) >= 1e6) {
    return `$${(value / 1e6).toFixed(1)}M`;
  }

  return `$${value.toLocaleString()}`;
}

function formatSignedPercent(value: number) {
  const percent = value * 100;
  const sign = percent > 0 ? "+" : "";

  return `${sign}${percent.toFixed(4)}%`;
}

function fundingColour(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "text-[#f5f5f5]";
  }

  if (value > 0) {
    return "text-[#ffb000]";
  }

  if (value < 0) {
    return "text-[#49c6e5]";
  }

  return "text-[#f5f5f5]";
}

function snapshotStatus(
  health: HealthResponse | null,
  name: string,
) {
  if (!health) {
    return "LOADING";
  }

  return health.snapshots[name]?.available
    ? "ACTIVE"
    : "UNAVAILABLE";
}

function snapshotAge(
  health: HealthResponse | null,
  name: string,
) {
  const seconds = health?.snapshots[name]?.age_seconds;

  if (!finite(seconds)) {
    return null;
  }

  if (seconds < 60) {
    return `${seconds.toFixed(0)}s old`;
  }

  if (seconds < 3600) {
    return `${(seconds / 60).toFixed(1)}m old`;
  }

  return `${(seconds / 3600).toFixed(1)}h old`;
}
