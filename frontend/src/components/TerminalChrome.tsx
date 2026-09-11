import Link from "next/link";
import type { ReactNode } from "react";

export type TerminalSection =
  | "risk"
  | "markets"
  | "models"
  | "methodology";

type TerminalNavProps = {
  active: TerminalSection;
  status?: string;
  sourceAt?: string | null;
  sourceAgeSeconds?: number | null;
  detail?: string | null;
};

const NAV_ITEMS: Array<{
  section: TerminalSection;
  href: string;
  label: string;
}> = [
  { section: "risk", href: "/dashboard", label: "RISK RADAR" },
  { section: "markets", href: "/markets", label: "MARKETS" },
  { section: "models", href: "/models", label: "MODELS" },
  { section: "methodology", href: "/methodology", label: "METHODOLOGY" },
];

export function TerminalNav({
  active,
  status = "ONLINE",
  sourceAt = null,
  sourceAgeSeconds = null,
  detail = null,
}: TerminalNavProps) {
  const statusClass =
    status === "ONLINE" || status === "ACTIVE"
      ? "text-[#38d996]"
      : status === "STALE" || status === "DEGRADED"
        ? "text-[#ffb000]"
        : status === "ERROR" || status === "UNAVAILABLE"
          ? "text-[#ff6666]"
          : status === "REFERENCE"
            ? "text-[#49c6e5]"
            : "text-[#999]";

  const sourceLabel = sourceAt ? formatUtcTimestamp(sourceAt) : null;
  const ageLabel = finite(sourceAgeSeconds) ? formatAge(sourceAgeSeconds) : null;

  return (
    <header className="sticky top-0 z-50 flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-[#4a4a4a] bg-[#0d0d0d]/95 px-4 py-3 text-xs backdrop-blur md:px-5">
      <div className="flex w-full items-center justify-between gap-4 md:w-auto">
        <Link
          href="/"
          className="shrink-0 text-sm font-black tracking-[0.16em] text-[#ffb000]"
        >
          CDRR
        </Link>

        <div className="flex items-center gap-3 md:hidden">
          <span className={`whitespace-nowrap font-semibold ${statusClass}`}>
            ● {status}
          </span>
          {ageLabel && (
            <span className="whitespace-nowrap text-[9px] text-[#777]">
              {ageLabel}
            </span>
          )}
        </div>
      </div>

      <nav className="order-3 flex w-full items-center gap-5 overflow-x-auto whitespace-nowrap border-t border-[#262626] pt-2 text-[10px] font-semibold tracking-wide [scrollbar-width:none] [&::-webkit-scrollbar]:hidden md:order-none md:w-auto md:flex-1 md:border-t-0 md:pt-0">
        {NAV_ITEMS.map((item) => {
          const selected = item.section === active;
          return (
            <Link
              key={item.section}
              href={item.href}
              aria-current={selected ? "page" : undefined}
              className={
                selected
                  ? "border-b-2 border-[#ffb000] pb-1 text-white"
                  : "text-[#a0a0a0] transition hover:text-white"
              }
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto hidden items-center gap-4 md:flex">
        {detail && (
          <span className="whitespace-nowrap text-[9px] font-semibold tracking-wide text-[#777]">
            {detail}
          </span>
        )}
        <span className={`whitespace-nowrap font-semibold ${statusClass}`}>
          ● {status}
        </span>
        {(sourceLabel || ageLabel) && (
          <span className="whitespace-nowrap text-[10px] text-[#8a8a8a]">
            {sourceLabel ?? "SOURCE"}
            {sourceLabel && ageLabel ? " · " : ""}
            {ageLabel ?? ""}
          </span>
        )}
      </div>
    </header>
  );
}

export function InfoTip({ text }: { text: string }) {
  return (
    <span
      role="img"
      aria-label={text}
      title={text}
      className="ml-1 inline-flex h-4 w-4 cursor-help select-none items-center justify-center rounded-full border border-[#4a4a4a] align-middle text-[9px] font-black normal-case tracking-normal text-[#8b8b8b] transition hover:border-[#777] hover:text-white"
    >
      ?
    </span>
  );
}

export function StatusBanner({
  title,
  children,
  tone = "warning",
}: {
  title: string;
  children: ReactNode;
  tone?: "warning" | "error" | "info";
}) {
  const classes =
    tone === "error"
      ? "border-[#5a2c2c] bg-[#170b0b] text-[#ff8080]"
      : tone === "info"
        ? "border-[#234653] bg-[#071216] text-[#69c9df]"
        : "border-[#5b481a] bg-[#171207] text-[#e6b84d]";

  return (
    <div className={`border-b px-4 py-2.5 text-[10px] leading-5 tracking-wide ${classes}`}>
      <span className="font-black">{title}</span>
      <span className="ml-2 opacity-80">{children}</span>
    </div>
  );
}

function finite(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value);
}

function formatUtcTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "SOURCE —";
  return `${date.toISOString().slice(11, 19)} UTC`;
}

function formatAge(seconds: number) {
  if (seconds < 60) return `${Math.max(0, seconds).toFixed(0)}s old`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m old`;
  return `${(seconds / 3600).toFixed(1)}h old`;
}
