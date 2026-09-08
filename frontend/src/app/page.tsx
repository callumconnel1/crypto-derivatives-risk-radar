import Link from "next/link";

const metrics = [
  {
    label: "ASSETS MONITORED",
    value: "20",
  },
  {
    label: "RISK FACTORS",
    value: "5",
  },
  {
    label: "UPDATE FREQUENCY",
    value: "15M",
  },
  {
    label: "MARKET STATUS",
    value: "LIVE",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#050505] text-[#f2f2f2]">

      {/* TOP BAR */}
      <header className="flex items-center justify-between border-b border-[#3a3a3a] bg-[#0d0d0d] px-6 py-3 text-xs">

        <div className="flex items-center gap-6">
          <span className="font-bold text-[#ffb000]">
            CDRR
          </span>

          <span className="text-[#a3a3a3]">
            CRYPTO DERIVATIVES RISK RADAR
          </span>
        </div>

        <div className="flex items-center gap-6">
          <span className="text-[#38d996]">
            ● SYSTEM ONLINE
          </span>

          <span className="text-[#8a8a8a]">
            CMC DATA
          </span>
        </div>

      </header>

      <section className="mx-auto max-w-7xl px-6 py-24">

        {/* HERO */}
        <div className="max-w-4xl">

          <div className="mb-5 text-xs tracking-[0.32em] text-[#ffb000]">
            QUANTITATIVE DERIVATIVES INTELLIGENCE
          </div>

          <h1 className="mb-8 text-5xl font-bold leading-[1.12] tracking-tight text-[#f4f4f4] md:text-7xl">

            KNOW WHERE THE

            <br />

            <span className="text-[#ffb000]">
              LEVERAGE RISK
            </span>

            <br />

            IS BUILDING.

          </h1>

          <p className="max-w-2xl text-base leading-8 text-[#b8b8b8]">
            Crypto Derivatives Risk Radar combines conditional volatility
            forecasting, derivatives positioning, liquidation activity, and
            cross-exchange dislocations to identify abnormal market risk.
          </p>

          <div className="mt-10 flex gap-4">

            <Link
              href="/dashboard"
              className="border border-[#ffb000] bg-[#ffb000] px-6 py-3 text-sm font-bold text-black transition hover:bg-transparent hover:text-[#ffb000]"
            >
              OPEN TERMINAL →
            </Link>

            <a
              href="#methodology"
              className="border border-[#4a4a4a] bg-[#0d0d0d] px-6 py-3 text-sm text-[#c0c0c0] transition hover:border-[#777] hover:text-white"
            >
              METHODOLOGY
            </a>

          </div>

        </div>

        {/* METRICS */}
        <div className="mt-24 grid grid-cols-2 border border-[#3a3a3a] bg-[#0d0d0d] md:grid-cols-4">

          {metrics.map((metric, index) => (
            <div
              key={metric.label}
              className={`p-5 ${
                index !== metrics.length - 1
                  ? "border-r border-[#3a3a3a]"
                  : ""
              }`}
            >

              <div className="mb-2 text-[10px] tracking-widest text-[#8f8f8f]">
                {metric.label}
              </div>

              <div className="text-2xl font-bold text-[#f5f5f5]">
                {metric.value}
              </div>

            </div>
          ))}

        </div>

        {/* METHODOLOGY */}
        <section
          id="methodology"
          className="mt-20 border-t border-[#3a3a3a] pt-10"
        >

          <div className="mb-8 text-xs text-[#ffb000]">
            [ SYSTEM MODEL ]
          </div>

          <div className="grid gap-px bg-[#3a3a3a] md:grid-cols-5">

            {[
              ["01", "VOLATILITY", "Conditional volatility forecasting"],
              ["02", "LEVERAGE", "Open interest and leverage intensity"],
              ["03", "CROWDING", "Funding and directional positioning"],
              ["04", "LIQUIDATIONS", "Forced-position stress"],
              ["05", "FRAGMENTATION", "Cross-exchange dislocation"],
            ].map(([number, title, description]) => (

              <div
                key={number}
                className="bg-[#0d0d0d] p-5"
              >

                <div className="mb-6 text-xs text-[#707070]">
                  {number}
                </div>

                <div className="mb-2 text-sm font-bold text-[#ffb000]">
                  {title}
                </div>

                <p className="text-xs leading-5 text-[#a0a0a0]">
                  {description}
                </p>

              </div>

            ))}

          </div>

        </section>

      </section>

    </main>
  );
}