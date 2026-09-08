import Link from "next/link";

const assets = [
  {
    symbol: "ETH",
    name: "Ethereum",
    price: "$3,842.19",
    change: "+2.14%",
    risk: 87,
    vol: "4.91%",
    funding: "+0.048%",
    oi: "$18.4B",
    liquidations: "$218M",
    state: "CROWDED LONG",
  },
  {
    symbol: "SOL",
    name: "Solana",
    price: "$184.31",
    change: "+1.02%",
    risk: 78,
    vol: "6.42%",
    funding: "+0.031%",
    oi: "$6.7B",
    liquidations: "$71M",
    state: "VOL EXPANSION",
  },
  {
    symbol: "BTC",
    name: "Bitcoin",
    price: "$79,115.84",
    change: "-1.42%",
    risk: 61,
    vol: "3.12%",
    funding: "+0.012%",
    oi: "$31.2B",
    liquidations: "$84M",
    state: "ELEVATED",
  },
  {
    symbol: "XRP",
    name: "XRP",
    price: "$2.48",
    change: "-0.38%",
    risk: 43,
    vol: "4.18%",
    funding: "-0.004%",
    oi: "$2.4B",
    liquidations: "$19M",
    state: "NORMAL",
  },
  {
    symbol: "DOGE",
    name: "Dogecoin",
    price: "$0.218",
    change: "+0.71%",
    risk: 39,
    vol: "5.43%",
    funding: "+0.006%",
    oi: "$1.8B",
    liquidations: "$14M",
    state: "NORMAL",
  },
];

function riskColour(risk: number) {
  if (risk >= 85) return "text-[#ff5c5c]";
  if (risk >= 70) return "text-[#ffb000]";
  if (risk >= 50) return "text-[#ffd166]";
  return "text-[#38d996]";
}

function changeColour(change: string) {
  return change.startsWith("+")
    ? "text-[#38d996]"
    : "text-[#ff5c5c]";
}

export default function Dashboard() {
  return (
    <main className="min-h-screen bg-[#050505] text-[#f2f2f2]">

      {/* NAV */}
      <header className="flex items-center justify-between border-b border-[#3a3a3a] bg-[#0d0d0d] px-5 py-2 text-xs">

        <div className="flex items-center gap-6">

          <Link
            href="/"
            className="font-bold text-[#ffb000]"
          >
            CDRR
          </Link>

          <span className="border-b border-[#ffb000] pb-1 text-white">
            RISK RADAR
          </span>

          <span className="text-[#8a8a8a]">
            MARKETS
          </span>

          <span className="text-[#8a8a8a]">
            MODELS
          </span>

          <span className="text-[#8a8a8a]">
            METHODOLOGY
          </span>

        </div>

        <div className="flex gap-5">

          <span className="text-[#38d996]">
            ● LIVE
          </span>

          <span className="text-[#8a8a8a]">
            UTC
          </span>

        </div>

      </header>

      {/* SUMMARY METRICS */}
      <div className="grid grid-cols-2 border-b border-[#3a3a3a] bg-[#0d0d0d] md:grid-cols-5">

        <Metric
          label="GLOBAL RISK"
          value="72"
          sub="HIGH ↑"
          valueClass="text-[#ffb000]"
        />

        <Metric
          label="TOTAL OPEN INTEREST"
          value="$68.4B"
          sub="+2.8% 24H"
        />

        <Metric
          label="24H LIQUIDATIONS"
          value="$512M"
          sub="LONG BIAS"
        />

        <Metric
          label="MEDIAN FUNDING"
          value="+0.014%"
          sub="POSITIVE"
        />

        <Metric
          label="VOLATILITY BREADTH"
          value="68%"
          sub="EXPANDING"
        />

      </div>

      <div className="p-4">

        {/* TITLE */}
        <div className="mb-4 flex items-center justify-between">

          <div>

            <div className="text-sm font-bold text-[#f5f5f5]">
              DERIVATIVES RISK RADAR
            </div>

            <div className="mt-1 text-[10px] tracking-wide text-[#8a8a8a]">
              RANKED BY COMPOSITE DERIVATIVES RISK SCORE
            </div>

          </div>

          <div className="flex gap-2">

            <button className="border border-[#4a4a4a] bg-[#111] px-3 py-1.5 text-[10px] text-[#b5b5b5] transition hover:border-[#777] hover:text-white">
              FILTER
            </button>

            <button className="border border-[#4a4a4a] bg-[#111] px-3 py-1.5 text-[10px] text-[#b5b5b5] transition hover:border-[#777] hover:text-white">
              REFRESH
            </button>

          </div>

        </div>

        {/* TABLE */}
        <div className="overflow-x-auto border border-[#3a3a3a]">

          <table className="w-full border-collapse text-xs">

            <thead>

              <tr className="bg-[#171717] text-left text-[#b5b5b5]">

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  ASSET
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  PRICE
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  24H
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  RISK
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  FCAST VOL
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  FUNDING
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  OPEN INT.
                </th>

                <th className="border-r border-[#3a3a3a] px-3 py-2">
                  LIQUIDATIONS
                </th>

                <th className="px-3 py-2">
                  STATE
                </th>

              </tr>

            </thead>

            <tbody>

              {assets.map((asset) => (

                <tr
                  key={asset.symbol}
                  className="border-t border-[#333] bg-[#0b0b0b] transition hover:bg-[#161616]"
                >

                  <td className="border-r border-[#333] px-3 py-3">

                    <div className="font-bold text-[#f5f5f5]">
                      {asset.symbol}
                    </div>

                    <div className="mt-1 text-[10px] text-[#7a7a7a]">
                      {asset.name}
                    </div>

                  </td>

                  <td className="border-r border-[#333] px-3 py-3 text-[#e0e0e0]">
                    {asset.price}
                  </td>

                  <td
                    className={`border-r border-[#333] px-3 py-3 ${changeColour(
                      asset.change
                    )}`}
                  >
                    {asset.change}
                  </td>

                  <td
                    className={`border-r border-[#333] px-3 py-3 text-lg font-bold ${riskColour(
                      asset.risk
                    )}`}
                  >
                    {asset.risk}
                  </td>

                  <td className="border-r border-[#333] px-3 py-3 text-[#d3d3d3]">
                    {asset.vol}
                  </td>

                  <td className="border-r border-[#333] px-3 py-3 text-[#d3d3d3]">
                    {asset.funding}
                  </td>

                  <td className="border-r border-[#333] px-3 py-3 text-[#d3d3d3]">
                    {asset.oi}
                  </td>

                  <td className="border-r border-[#333] px-3 py-3 text-[#d3d3d3]">
                    {asset.liquidations}
                  </td>

                  <td className="px-3 py-3 text-[#ffb000]">
                    {asset.state}
                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

        {/* LOWER PANELS */}
        <div className="mt-4 grid gap-4 lg:grid-cols-3">

          <TerminalPanel title="RISK EVENTS">

            <Event
              time="18:42"
              asset="ETH"
              text="Risk score crossed 85"
              type="HIGH"
            />

            <Event
              time="18:30"
              asset="SOL"
              text="Volatility regime expansion"
              type="WARN"
            />

            <Event
              time="17:55"
              asset="BTC"
              text="Open interest +4.2%"
              type="INFO"
            />

          </TerminalPanel>

          <TerminalPanel title="MARKET STATE">

            <div className="space-y-4">

              <RiskBar label="VOLATILITY" value={81} />

              <RiskBar label="LEVERAGE" value={76} />

              <RiskBar label="CROWDING" value={69} />

              <RiskBar label="LIQUIDATIONS" value={73} />

              <RiskBar label="FRAGMENTATION" value={61} />

            </div>

          </TerminalPanel>

          <TerminalPanel title="SYSTEM">

            <SystemRow
              name="CMC REST API"
              status="ONLINE"
            />

            <SystemRow
              name="WEBSOCKET"
              status="ONLINE"
            />

            <SystemRow
              name="VOL ENGINE"
              status="ACTIVE"
            />

            <SystemRow
              name="RISK ENGINE"
              status="ACTIVE"
            />

            <SystemRow
              name="LAST UPDATE"
              status="18:44:12 UTC"
            />

          </TerminalPanel>

        </div>

      </div>

    </main>
  );
}

function Metric({
  label,
  value,
  sub,
  valueClass = "text-[#f5f5f5]",
}: {
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="border-r border-[#3a3a3a] px-4 py-3">

      <div className="text-[9px] tracking-wider text-[#969696]">
        {label}
      </div>

      <div
        className={`mt-1 text-xl font-bold ${valueClass}`}
      >
        {value}
      </div>

      <div className="mt-1 text-[9px] text-[#858585]">
        {sub}
      </div>

    </div>
  );
}

function TerminalPanel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-[#3a3a3a] bg-[#0d0d0d]">

      <div className="border-b border-[#3a3a3a] bg-[#161616] px-3 py-2 text-[10px] font-bold text-[#ffb000]">
        {title}
      </div>

      <div className="p-3">
        {children}
      </div>

    </section>
  );
}

function Event({
  time,
  asset,
  text,
  type,
}: {
  time: string;
  asset: string;
  text: string;
  type: string;
}) {
  return (
    <div className="grid grid-cols-[45px_40px_1fr_45px] border-b border-[#303030] py-2 text-[10px] last:border-0">

      <span className="text-[#7d7d7d]">
        {time}
      </span>

      <span className="font-bold text-[#49c6e5]">
        {asset}
      </span>

      <span className="text-[#b5b5b5]">
        {text}
      </span>

      <span className="text-right text-[#ffb000]">
        {type}
      </span>

    </div>
  );
}

function RiskBar({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div>

      <div className="mb-1 flex justify-between text-[10px]">

        <span className="text-[#9b9b9b]">
          {label}
        </span>

        <span className="text-[#f4f4f4]">
          {value}
        </span>

      </div>

      <div className="h-1.5 bg-[#2a2a2a]">

        <div
          className="h-full bg-[#ffb000]"
          style={{
            width: `${value}%`,
          }}
        />

      </div>

    </div>
  );
}

function SystemRow({
  name,
  status,
}: {
  name: string;
  status: string;
}) {
  return (
    <div className="flex justify-between border-b border-[#303030] py-2 text-[10px] last:border-0">

      <span className="text-[#949494]">
        {name}
      </span>

      <span className="text-[#38d996]">
        {status}
      </span>

    </div>
  );
}