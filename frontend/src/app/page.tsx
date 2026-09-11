import Link from "next/link";

const metrics = [
  {
    label: "ASSETS MONITORED",
    value: "20",
    sub: "LIQUID CRYPTO UNIVERSE",
  },
  {
    label: "PRODUCTION FACTORS",
    value: "5",
    sub: "EQUAL-WEIGHT · PROVISIONAL v1",
  },
  {
    label: "DATA CYCLE",
    value: "~2 MIN",
    sub: "ADAPTIVE CMC COLLECTION",
  },
  {
    label: "MODEL OUTPUT",
    value: "0–100",
    sub: "RELATIVE STRESS SCORE",
  },
];

const productLinks = [
  {
    number: "01",
    title: "RISK RADAR",
    href: "/dashboard",
    description:
      "Live CDRR ranking, factor decomposition, system health, spot state, derivatives, volatility, and liquidations.",
  },
  {
    number: "02",
    title: "MARKETS",
    href: "/markets",
    description:
      "Cross-market explorer combining price, open interest, funding, basis, liquidation stress, volatility, and CDRR state.",
  },
  {
    number: "03",
    title: "MODELS",
    href: "/models",
    description:
      "Power-law and EWMA volatility diagnostics, fitted parameters, factor matrix, model spread, and research status.",
  },
  {
    number: "04",
    title: "METHODOLOGY",
    href: "/methodology",
    description:
      "Production score construction, common-universe OI, historical calibration, state logic, data quality, and limitations.",
  },
];

const factors = [
  {
    number: "01",
    symbol: "V",
    title: "VOLATILITY",
    description:
      "Historical volatility percentile and current volatility expansion.",
  },
  {
    number: "02",
    symbol: "L",
    title: "LEVERAGE",
    description:
      "Magnitude of common-universe open-interest change.",
  },
  {
    number: "03",
    symbol: "C",
    title: "CROWDING",
    description:
      "Confirmed funding-tail stress across history and the cross-section.",
  },
  {
    number: "04",
    symbol: "Q",
    title: "LIQUIDATIONS",
    description:
      "Confirmed forced-position stress normalised through time and by OI.",
  },
  {
    number: "05",
    symbol: "D",
    title: "CONCENTRATION",
    description:
      "Cross-sectional venue concentration of cleaned derivatives open interest.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#050505] text-[#f2f2f2]">
      {/* TOP BAR */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#3a3a3a] bg-[#0d0d0d] px-5 py-3 text-xs">
        <div className="flex items-center gap-6">
          <span className="font-black tracking-[0.16em] text-[#ffb000]">
            CDRR
          </span>

          <span className="hidden text-[#a3a3a3] sm:inline">
            CRYPTO DERIVATIVES RISK RADAR
          </span>
        </div>

        <nav className="flex flex-wrap items-center gap-5 text-[10px] font-semibold tracking-wide">
          <Link
            href="/dashboard"
            className="text-[#a0a0a0] transition hover:text-white"
          >
            RISK RADAR
          </Link>

          <Link
            href="/markets"
            className="text-[#a0a0a0] transition hover:text-white"
          >
            MARKETS
          </Link>

          <Link
            href="/models"
            className="text-[#a0a0a0] transition hover:text-white"
          >
            MODELS
          </Link>

          <Link
            href="/methodology"
            className="text-[#a0a0a0] transition hover:text-white"
          >
            METHODOLOGY
          </Link>
        </nav>
      </header>

      {/* HERO */}
      <section className="mx-auto max-w-[1500px] px-5 py-16 md:py-24 lg:px-8">
        <div className="grid gap-12 xl:grid-cols-[1.15fr_0.85fr] xl:items-end">
          <div>
            <div className="mb-5 text-[10px] font-black tracking-[0.28em] text-[#ffb000]">
              QUANTITATIVE DERIVATIVES INTELLIGENCE
            </div>

            <h1 className="max-w-5xl text-5xl font-black leading-[1.02] tracking-tight text-[#f4f4f4] md:text-7xl">
              KNOW WHERE
              <br />
              <span className="text-[#ffb000]">
                DERIVATIVES STRESS
              </span>
              <br />
              IS BUILDING.
            </h1>

            <p className="mt-8 max-w-3xl text-sm leading-7 text-[#aaa] md:text-base">
              Crypto Derivatives Risk Radar combines conditional volatility,
              common-universe open-interest dynamics, funding crowding,
              liquidation stress, and venue concentration to rank abnormal
              derivatives risk across a fixed 20-asset universe.
            </p>

            <p className="mt-4 max-w-3xl text-xs leading-6 text-[#777]">
              CDRR measures stress magnitude. Market direction and regime are
              reported separately by the state engine. The system does not
              produce price targets or directional return forecasts.
            </p>

            <div className="mt-9 flex flex-wrap gap-3">
              <Link
                href="/dashboard"
                className="border border-[#ffb000] bg-[#ffb000] px-5 py-3 text-xs font-black tracking-wide text-black transition hover:bg-transparent hover:text-[#ffb000]"
              >
                OPEN TERMINAL →
              </Link>

              <Link
                href="/methodology"
                className="border border-[#4a4a4a] bg-[#0d0d0d] px-5 py-3 text-xs font-bold tracking-wide text-[#c0c0c0] transition hover:border-[#777] hover:text-white"
              >
                READ METHODOLOGY
              </Link>
            </div>
          </div>

          <div className="border border-[#3d3d3d] bg-[#0b0b0b]">
            <div className="border-b border-[#3d3d3d] bg-[#151515] px-4 py-3">
              <div className="text-[10px] font-black tracking-[0.12em] text-[#ffb000]">
                PRODUCTION MODEL
              </div>

              <div className="mt-1 text-[10px] text-[#777]">
                provisional_v1_equal_weight
              </div>
            </div>

            <div className="p-5">
              <div className="text-[9px] font-bold tracking-[0.14em] text-[#777]">
                SCORE
              </div>

              <div className="mt-4 overflow-x-auto border border-[#333] bg-[#070707] px-4 py-5 text-center text-base text-[#f1f1f1]">
                <div
                  aria-label="R equals 100 times the equal-weight sum of the five CDRR stress factors"
                  dangerouslySetInnerHTML={{
                    __html: String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <mi>R</mi>
                    <mo>=</mo>
                    <mn>100</mn>
                    <mo>⁢</mo>
                    <mo>(</mo>
                    <mn>0.20</mn>
                    <mi>V</mi>
                    <mo>+</mo>
                    <mn>0.20</mn>
                    <mi>L</mi>
                    <mo>+</mo>
                    <mn>0.20</mn>
                    <mi>C</mi>
                    <mo>+</mo>
                    <mn>0.20</mn>
                    <mi>Q</mi>
                    <mo>+</mo>
                    <mn>0.20</mn>
                    <mi>D</mi>
                    <mo>)</mo>
                  </mrow>
                </math>`,
                  }}
                />
              </div>

              <div className="mt-5 grid grid-cols-5 gap-px bg-[#333]">
                {[
                  ["V", "VOL"],
                  ["L", "OI"],
                  ["C", "FUND"],
                  ["Q", "LIQ"],
                  ["D", "CONC"],
                ].map(([symbol, label]) => (
                  <div
                    key={symbol}
                    className="bg-[#0d0d0d] px-2 py-3 text-center"
                  >
                    <div className="text-sm font-black text-[#ffb000]">
                      {symbol}
                    </div>

                    <div className="mt-1 text-[8px] font-bold tracking-wide text-[#777]">
                      {label}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* METRICS */}
        <div className="mt-16 grid grid-cols-2 border border-[#3a3a3a] bg-[#0d0d0d] md:grid-cols-4">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="border-b border-r border-[#3a3a3a] p-5 md:border-b-0"
            >
              <div className="text-[9px] font-bold tracking-[0.12em] text-[#858585]">
                {metric.label}
              </div>

              <div className="mt-2 text-2xl font-black text-[#f5f5f5]">
                {metric.value}
              </div>

              <div className="mt-1 text-[9px] tracking-wide text-[#717171]">
                {metric.sub}
              </div>
            </div>
          ))}
        </div>

        {/* PRODUCT SURFACES */}
        <section className="mt-16">
          <div className="mb-5 text-[10px] font-black tracking-[0.16em] text-[#ffb000]">
            [ PRODUCT SURFACES ]
          </div>

          <div className="grid gap-px border border-[#3a3a3a] bg-[#3a3a3a] md:grid-cols-2 xl:grid-cols-4">
            {productLinks.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="group bg-[#0d0d0d] p-5 transition hover:bg-[#141414]"
              >
                <div className="text-[9px] font-bold text-[#666]">
                  {item.number}
                </div>

                <div className="mt-7 flex items-center justify-between gap-4">
                  <div className="text-sm font-black tracking-[0.08em] text-[#f1f1f1]">
                    {item.title}
                  </div>

                  <span className="text-[#555] transition group-hover:text-[#ffb000]">
                    →
                  </span>
                </div>

                <p className="mt-3 text-[11px] leading-5 text-[#929292]">
                  {item.description}
                </p>
              </Link>
            ))}
          </div>
        </section>

        {/* FACTORS */}
        <section className="mt-16">
          <div className="mb-5 text-[10px] font-black tracking-[0.16em] text-[#ffb000]">
            [ PRODUCTION FACTORS ]
          </div>

          <div className="grid gap-px border border-[#3a3a3a] bg-[#3a3a3a] md:grid-cols-5">
            {factors.map((factor) => (
              <div
                key={factor.number}
                className="bg-[#0d0d0d] p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <span className="text-[9px] text-[#666]">
                    {factor.number}
                  </span>

                  <span className="text-lg font-black text-[#ffb000]">
                    {factor.symbol}
                  </span>
                </div>

                <div className="mt-7 text-xs font-black tracking-[0.08em] text-[#f1f1f1]">
                  {factor.title}
                </div>

                <p className="mt-3 text-[11px] leading-5 text-[#909090]">
                  {factor.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* DESIGN PRINCIPLES */}
        <section className="mt-16 grid gap-4 xl:grid-cols-3">
          <Principle
            title="MAGNITUDE ≠ DIRECTION"
            body="The CDRR score describes stress magnitude. Rally, selloff, leverage-build, and deleveraging states are kept outside the score."
          />

          <Principle
            title="CONFIRM BEFORE ESCALATING"
            body="Funding and liquidation channels combine complementary normalisations so one isolated extreme does not automatically dominate the production score."
          />

          <Principle
            title="RESEARCH STAYS RESEARCH"
            body="Basis magnitude and basis dispersion are monitored in the 50/25/25 structure candidate but remain outside production until longitudinal validation supports promotion."
          />
        </section>
      </section>

      <footer className="border-t border-[#333] bg-[#090909] px-5 py-5 text-[9px] tracking-wide text-[#666] lg:px-8">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3">
          <span>
            CDRR · CRYPTO DERIVATIVES RISK RADAR
          </span>

          <span>
            DATA VIA COINMARKETCAP API · QUANTITATIVE RESEARCH PROTOTYPE
          </span>
        </div>
      </footer>
    </main>
  );
}

function Principle({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <article className="border border-[#3d3d3d] bg-[#0d0d0d] p-5">
      <div className="text-[10px] font-black tracking-[0.1em] text-[#ffb000]">
        {title}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-[#929292]">
        {body}
      </p>
    </article>
  );
}
