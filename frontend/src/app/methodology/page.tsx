import Link from "next/link";
import type { ReactNode } from "react";
import { TerminalNav } from "@/components/TerminalChrome";

const FACTORS = [
  {
    key: "V",
    number: "01",
    title: "VOLATILITY",
    weight: "20%",
    colour: "text-[#49c6e5]",
    summary:
      "How elevated and how rapidly expanding realised volatility is.",
    signal:
      "Available mean of the asset's 24H historical volatility percentile and its current cross-sectional volatility-expansion percentile.",
    interpretation:
      "Higher values indicate an asset is already volatile relative to its own recent history, the current universe, or both.",
  },
  {
    key: "L",
    number: "02",
    title: "LEVERAGE / OI",
    weight: "20%",
    colour: "text-[#f4f4f4]",
    summary:
      "The magnitude of current leverage build-up or contraction.",
    signal:
      "Cross-sectional percentile of the absolute 1H common-universe open-interest change.",
    interpretation:
      "The component measures leverage movement magnitude. Direction is handled separately by the state engine.",
  },
  {
    key: "C",
    number: "03",
    title: "FUNDING CROWDING",
    weight: "20%",
    colour: "text-[#ffb000]",
    summary:
      "How unusually one-sided perpetual positioning appears through funding.",
    signal:
      "Confirmed funding-tail percentile using cross-sectional and prior historical calibration once the history gate is ready.",
    interpretation:
      "The factor is based on crowding magnitude; the sign of funding remains descriptive context rather than score direction.",
  },
  {
    key: "Q",
    number: "04",
    title: "LIQUIDATIONS",
    weight: "20%",
    colour: "text-[#ff6666]",
    summary:
      "Current forced-position stress relative to both time and the cross-section.",
    signal:
      "Conservative confirmation of the temporal 1H liquidation percentile with the cross-sectional percentile of 1H liquidations divided by clean open interest.",
    interpretation:
      "A high value requires liquidation activity to look abnormal through more than one normalisation.",
  },
  {
    key: "D",
    number: "05",
    title: "CONCENTRATION",
    weight: "20%",
    colour: "text-[#d8d8d8]",
    summary:
      "How concentrated tracked derivatives open interest is across venues.",
    signal:
      "Cross-sectional percentile of the clean open-interest Herfindahl-Hirschman Index.",
    interpretation:
      "More concentrated venue exposure receives a higher concentration component.",
  },
] as const;

const STATES = [
  {
    state: "OI BUILD INTO RALLY",
    meaning:
      "Price is rising while common-universe open interest is expanding.",
    colour: "text-[#49c6e5]",
  },
  {
    state: "OI BUILD INTO SELLOFF",
    meaning:
      "Price is falling while common-universe open interest is expanding.",
    colour: "text-[#ffb000]",
  },
  {
    state: "DELEVERAGING",
    meaning:
      "Open interest is contracting materially as positions are reduced.",
    colour: "text-[#d8d8d8]",
  },
  {
    state: "LONG LIQUIDATION STRESS",
    meaning:
      "Forced liquidations are elevated and dominated by long positions.",
    colour: "text-[#ff6666]",
  },
  {
    state: "SHORT LIQUIDATION STRESS",
    meaning:
      "Forced liquidations are elevated and dominated by short positions.",
    colour: "text-[#38d996]",
  },
  {
    state: "FORCED DELEVERAGING",
    meaning:
      "Liquidation stress and open-interest contraction coincide.",
    colour: "text-[#ff6666]",
  },
] as const;

export default function MethodologyPage() {
  return (
    <main className="dashboard-terminal min-h-screen bg-[#050505] text-[#f4f4f4]">
      {/* NAV */}
      <TerminalNav
        active="methodology"
        status="REFERENCE"
        detail="PROVISIONAL v1 · 20-ASSET UNIVERSE"
      />

      {/* HERO */}
      <section className="border-b border-[#444] bg-[#0d0d0d] px-5 py-10 lg:px-8">
        <div className="mx-auto max-w-[1500px]">
          <div className="text-[10px] font-black tracking-[0.22em] text-[#ffb000]">
            [ SYSTEM METHODOLOGY ]
          </div>

          <div className="mt-4 grid gap-8 xl:grid-cols-[1.25fr_0.75fr]">
            <div>
              <h1 className="max-w-4xl text-3xl font-black leading-tight tracking-tight text-[#f5f5f5] md:text-5xl">
                A RELATIVE STRESS RADAR FOR
                <span className="text-[#ffb000]">
                  {" "}CRYPTO DERIVATIVES.
                </span>
              </h1>

              <p className="mt-6 max-w-3xl text-sm leading-7 text-[#aaa]">
                CDRR ranks a fixed 20-asset universe by current derivatives
                stress. It combines volatility, leverage movement, funding
                crowding, liquidations, and venue concentration into one
                cross-sectional score while keeping market direction in a
                separate state engine.
              </p>
            </div>

            <div className="grid gap-px border border-[#3d3d3d] bg-[#3d3d3d] sm:grid-cols-2">
              <HeroMetric
                label="OUTPUT"
                value="0–100"
                sub="RELATIVE STRESS SCORE"
              />

              <HeroMetric
                label="FACTORS"
                value="5"
                sub="EQUAL WEIGHT · v1"
              />

              <HeroMetric
                label="DIRECTION"
                value="SEPARATE"
                sub="STATE ENGINE"
              />

              <HeroMetric
                label="PRICE TARGET"
                value="NONE"
                sub="NOT A DIRECTIONAL FORECAST"
              />
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="border border-[#ffb000] bg-[#ffb000] px-4 py-2 text-xs font-black text-black transition hover:bg-transparent hover:text-[#ffb000]"
            >
              OPEN RISK RADAR →
            </Link>

            <Link
              href="/models"
              className="border border-[#555] bg-[#111] px-4 py-2 text-xs font-bold text-[#d0d0d0] transition hover:border-[#888] hover:text-white"
            >
              VIEW MODEL MONITOR
            </Link>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-[1500px] p-4 lg:p-5">
        {/* OBJECTIVE / BOUNDARY */}
        <div className="grid gap-4 xl:grid-cols-2">
          <TerminalPanel
            title="WHAT CDRR MEASURES"
            eyebrow="SYSTEM OBJECTIVE"
          >
            <p className="text-sm leading-7 text-[#aaa]">
              The score is designed to answer a narrow question:
              <span className="font-bold text-[#f1f1f1]">
                {" "}where is derivatives stress currently concentrated
                within the tracked universe?
              </span>
              {" "}It is therefore a ranking and monitoring system, not a
              return-prediction model.
            </p>

            <div className="mt-5 grid gap-px bg-[#333] sm:grid-cols-3">
              <StatusCell
                label="HIGH SCORE"
                value="MORE STRESS"
                detail="Relative to tracked assets"
              />

              <StatusCell
                label="LOW SCORE"
                value="LESS STRESS"
                detail="Relative to tracked assets"
              />

              <StatusCell
                label="DIRECTION"
                value="NOT IMPLIED"
                detail="Read the state separately"
              />
            </div>
          </TerminalPanel>

          <TerminalPanel
            title="WHAT CDRR DOES NOT CLAIM"
            eyebrow="INTERPRETATION BOUNDARY"
          >
            <div className="space-y-3">
              <BoundaryRow>
                A score of 80 does not mean an 80% probability of a crash.
              </BoundaryRow>

              <BoundaryRow>
                Higher stress does not mechanically imply negative future
                returns.
              </BoundaryRow>

              <BoundaryRow>
                There are no fixed low / medium / high absolute risk bands in
                provisional v1.
              </BoundaryRow>

              <BoundaryRow>
                The score is cross-sectional and depends on the current
                20-asset research universe.
              </BoundaryRow>
            </div>
          </TerminalPanel>
        </div>

        {/* SCORE FORMULA */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="PRODUCTION RISK SCORE"
            subtitle="PROVISIONAL v1 · EQUAL-WEIGHT STRESS MAGNITUDE"
          />

          <div className="grid gap-px bg-[#333] xl:grid-cols-[0.8fr_1.2fr]">
            <div className="bg-[#0b0b0b] p-5">
              <div className="text-[10px] font-black tracking-[0.14em] text-[#888]">
                SCORE DEFINITION
              </div>

              <MathPanel
                ariaLabel="R equals 100 times the weighted sum of volatility, leverage, crowding, liquidations, and concentration"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <mi>R</mi>
                    <mo>=</mo>
                    <mn>100</mn>
                    <mo></mo>
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
                </math>`}
              />

              <p className="mt-4 text-xs leading-6 text-[#969696]">
                Each component is normalised to the interval [0, 1].
                Production v1 deliberately uses simple equal weights while
                longer forward-stress history is collected.
              </p>
            </div>

            <div className="grid gap-px bg-[#333] sm:grid-cols-5">
              {FACTORS.map((factor) => (
                <FactorKey
                  key={factor.key}
                  symbol={factor.key}
                  title={factor.title}
                  weight={factor.weight}
                  colour={factor.colour}
                />
              ))}
            </div>
          </div>
        </section>

        {/* FACTORS */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="THE FIVE PRODUCTION FACTORS"
            subtitle="ALL FACTORS MEASURE STRESS MAGNITUDE · DIRECTION REMAINS SEPARATE"
          />

          <div className="grid gap-px bg-[#333] lg:grid-cols-2 xl:grid-cols-5">
            {FACTORS.map((factor) => (
              <FactorCard
                key={factor.key}
                symbol={factor.key}
                number={factor.number}
                title={factor.title}
                weight={factor.weight}
                colour={factor.colour}
                summary={factor.summary}
                signal={factor.signal}
                interpretation={factor.interpretation}
              />
            ))}
          </div>
        </section>

        {/* VOLATILITY MODEL */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="VOLATILITY ENGINE"
            subtitle="POWER-LAW STUDENT-t PRIMARY · EWMA SECONDARY"
          />

          <div className="grid gap-px bg-[#333] xl:grid-cols-3">
            <MethodBlock
              title="PRIMARY MODEL"
              tag="POWER-LAW"
              tagClass="text-[#49c6e5]"
            >
              <p>
                Conditional variance uses a finite power-law memory over the
                latest 250 five-minute squared returns:
              </p>

              <MathPanel
                ariaLabel="Conditional variance equals c plus beta times a finite power-law weighted sum of past squared returns"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <msubsup>
                      <mi>σ</mi>
                      <mrow>
                        <mi>t</mi>
                        <mo>+</mo>
                        <mn>1</mn>
                      </mrow>
                      <mn>2</mn>
                    </msubsup>
                    <mo>=</mo>
                    <mi>c</mi>
                    <mo>+</mo>
                    <mi>β</mi>
                    <munderover>
                      <mo>∑</mo>
                      <mrow>
                        <mi>k</mi>
                        <mo>=</mo>
                        <mn>0</mn>
                      </mrow>
                      <mrow>
                        <mi>K</mi>
                        <mo>−</mo>
                        <mn>1</mn>
                      </mrow>
                    </munderover>
                    <mfrac>
                      <msup>
                        <msub>
                          <mi>r</mi>
                          <mrow>
                            <mi>t</mi>
                            <mo>−</mo>
                            <mi>k</mi>
                          </mrow>
                        </msub>
                        <mn>2</mn>
                      </msup>
                      <msup>
                        <mrow>
                          <mo>(</mo>
                          <mi>k</mi>
                          <mo>+</mo>
                          <mn>1</mn>
                          <mo>)</mo>
                        </mrow>
                        <mi>α</mi>
                      </msup>
                    </mfrac>
                  </mrow>
                </math>`}
              />

              <p>
                Student-t residuals allow heavier tails than a Gaussian
                specification.
              </p>
            </MethodBlock>

            <MethodBlock
              title="FORECAST HORIZON"
              tag="NEXT 1H"
              tagClass="text-[#ffb000]"
            >
              <p>
                Twelve five-minute conditional variance steps are aggregated
                to form the next-one-hour forecast. The terminal displays the
                result as annualised volatility and also reports the implied
                one-hour sigma.
              </p>

              <MathPanel
                ariaLabel="One-hour sigma equals annualised volatility divided by the square root of 365 times 24"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <msub>
                      <mi>σ</mi>
                      <mrow>
                        <mn>1</mn>
                        <mi>h</mi>
                      </mrow>
                    </msub>
                    <mo>=</mo>
                    <mfrac>
                      <msub>
                        <mi>σ</mi>
                        <mi>ann</mi>
                      </msub>
                      <msqrt>
                        <mrow>
                          <mn>365</mn>
                          <mo>×</mo>
                          <mn>24</mn>
                        </mrow>
                      </msqrt>
                    </mfrac>
                  </mrow>
                </math>`}
              />
            </MethodBlock>

            <MethodBlock
              title="SECONDARY MODEL"
              tag="EWMA"
              tagClass="text-[#bdbdbd]"
            >
              <p>
                A tuned exponentially weighted variance model runs beside the
                primary forecast.
              </p>

              <MathPanel
                ariaLabel="Model disagreement equals power-law volatility minus EWMA volatility, divided by EWMA volatility"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <mi>D</mi>
                    <mo>=</mo>
                    <mfrac>
                      <mrow>
                        <msub>
                          <mi>σ</mi>
                          <mi>PL</mi>
                        </msub>
                        <mo>−</mo>
                        <msub>
                          <mi>σ</mi>
                          <mi>EWMA</mi>
                        </msub>
                      </mrow>
                      <msub>
                        <mi>σ</mi>
                        <mi>EWMA</mi>
                      </msub>
                    </mfrac>
                  </mrow>
                </math>`}
              />

              <p>
                The spread is a model-disagreement diagnostic, not an
                additional production risk factor.
              </p>
            </MethodBlock>
          </div>

          <div className="grid gap-px border-t border-[#333] bg-[#333] md:grid-cols-4">
            <ValidationCell
              label="WALK-FORWARD"
              value="4 FOLDS"
              sub="OFFLINE RESEARCH"
            />

            <ValidationCell
              label="LOWER MEAN QLIKE"
              value="17 / 20"
              sub="POWER-LAW VS EWMA"
            />

            <ValidationCell
              label="HAC-SIGNIFICANT PL WINS"
              value="5"
              sub="EWMA WINS: 0"
            />

            <ValidationCell
              label="STATUS"
              value="PRIMARY"
              sub="POWER-LAW MODEL"
              valueClass="text-[#49c6e5]"
            />
          </div>
        </section>

        {/* LEVERAGE + COMMON UNIVERSE */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="COMMON-UNIVERSE OPEN INTEREST"
            subtitle="CONTRACT MATCHING PREVENTS COVERAGE CHANGES FROM MASQUERADING AS LEVERAGE CHANGES"
          />

          <div className="grid gap-px bg-[#333] xl:grid-cols-[1fr_1fr_1fr]">
            <MethodBlock
              title="MATCHED UNIVERSE"
              tag="CURRENT ∩ LAG"
              tagClass="text-[#38d996]"
            >
              <p>
                OI change is calculated only on contracts that are valid both
                now and at the comparison horizon.
              </p>

              <MathPanel
                ariaLabel="The common contract universe at horizon h is the intersection of the current and lagged valid contract sets"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <msub>
                      <mi>I</mi>
                      <mi>h</mi>
                    </msub>
                    <mo>=</mo>
                    <msub>
                      <mi>S</mi>
                      <mi>t</mi>
                    </msub>
                    <mo>∩</mo>
                    <msub>
                      <mi>S</mi>
                      <mrow>
                        <mi>t</mi>
                        <mo>−</mo>
                        <mi>h</mi>
                      </mrow>
                    </msub>
                  </mrow>
                </math>`}
              />

              <p>
                Contract identity uses symbol, market identifier, and exchange
                identifier.
              </p>
            </MethodBlock>

            <MethodBlock
              title="OI CHANGE"
              tag="1H PRIMARY"
              tagClass="text-[#ffb000]"
            >
              <MathPanel
                ariaLabel="Common-universe open-interest change equals current matched open interest divided by lagged matched open interest, minus one"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <msubsup>
                      <mi>ΔOI</mi>
                      <mi>h</mi>
                      <mi>common</mi>
                    </msubsup>
                    <mo>=</mo>
                    <mfrac>
                      <mrow>
                        <munderover>
                          <mo>∑</mo>
                          <mrow>
                            <mi>m</mi>
                            <mo>∈</mo>
                            <msub>
                              <mi>I</mi>
                              <mi>h</mi>
                            </msub>
                          </mrow>
                          <mrow />
                        </munderover>
                        <msub>
                          <mi>OI</mi>
                          <mrow>
                            <mi>m</mi>
                            <mo>,</mo>
                            <mi>t</mi>
                          </mrow>
                        </msub>
                      </mrow>
                      <mrow>
                        <munderover>
                          <mo>∑</mo>
                          <mrow>
                            <mi>m</mi>
                            <mo>∈</mo>
                            <msub>
                              <mi>I</mi>
                              <mi>h</mi>
                            </msub>
                          </mrow>
                          <mrow />
                        </munderover>
                        <msub>
                          <mi>OI</mi>
                          <mrow>
                            <mi>m</mi>
                            <mo>,</mo>
                            <mi>t</mi>
                            <mo>−</mo>
                            <mi>h</mi>
                          </mrow>
                        </msub>
                      </mrow>
                    </mfrac>
                    <mo>−</mo>
                    <mn>1</mn>
                  </mrow>
                </math>`}
              />

              <p>
                Production leverage stress uses the cross-sectional percentile
                of the absolute one-hour change.
              </p>
            </MethodBlock>

            <MethodBlock
              title="WHY IT MATTERS"
              tag="DATA QUALITY"
              tagClass="text-[#bdbdbd]"
            >
              <p>
                A provider adding or dropping contracts can move raw aggregate
                OI even when the actual positions in comparable contracts have
                not changed. Common-universe matching removes that coverage
                contamination.
              </p>
            </MethodBlock>
          </div>
        </section>

        {/* CONFIRMATION */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="CONFIRMATION AND HISTORICAL CALIBRATION"
            subtitle="CONSERVATIVE SIGNAL DESIGN · STRICTLY PRIOR HISTORY"
          />

          <div className="grid gap-px bg-[#333] xl:grid-cols-3">
            <MethodBlock
              title="EMPIRICAL MIDRANK"
              tag="PRIOR-ONLY"
              tagClass="text-[#49c6e5]"
            >
              <p>
                Historical percentiles use a midrank empirical CDF so ties are
                handled symmetrically.
              </p>

              <MathPanel
                ariaLabel="Empirical midrank percentile equals the count strictly below x plus half the count tied at x, divided by the total count"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <mover>
                      <mi>F</mi>
                      <mo>^</mo>
                    </mover>
                    <mo>(</mo>
                    <mi>x</mi>
                    <mo>)</mo>
                    <mo>=</mo>
                    <mfrac>
                      <mrow>
                        <msub>
                          <mi>N</mi>
                          <mrow>
                            <mo>&lt;</mo>
                            <mi>x</mi>
                          </mrow>
                        </msub>
                        <mo>+</mo>
                        <mfrac>
                          <mn>1</mn>
                          <mn>2</mn>
                        </mfrac>
                        <msub>
                          <mi>N</mi>
                          <mrow>
                            <mo>=</mo>
                            <mi>x</mi>
                          </mrow>
                        </msub>
                      </mrow>
                      <mi>N</mi>
                    </mfrac>
                  </mrow>
                </math>`}
              />

              <p>
                The current observation is not allowed to calibrate its own
                historical percentile.
              </p>
            </MethodBlock>

            <MethodBlock
              title="FUNDING"
              tag="CONFIRMED"
              tagClass="text-[#ffb000]"
            >
              <p>
                Funding crowding is calibrated against both the current
                cross-section and the asset&apos;s prior history. Once the history
                gate is ready, the production signal keeps the more
                conservative confirmation.
              </p>

              <MathPanel
                ariaLabel="Confirmed funding crowding equals the minimum of the cross-sectional and historical crowding percentiles"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <msub>
                      <mi>C</mi>
                      <mi>fund</mi>
                    </msub>
                    <mo>=</mo>
                    <mi>min</mi>
                    <mo>(</mo>
                    <msub>
                      <mi>C</mi>
                      <mi>cross</mi>
                    </msub>
                    <mo>,</mo>
                    <msub>
                      <mi>C</mi>
                      <mi>hist</mi>
                    </msub>
                    <mo>)</mo>
                  </mrow>
                </math>`}
              />

              <p>
                Funding rates are not annualised in the terminal.
              </p>
            </MethodBlock>

            <MethodBlock
              title="LIQUIDATIONS"
              tag="CONFIRMED"
              tagClass="text-[#ff6666]"
            >
              <p>
                Production liquidation stress combines abnormal activity
                through time with current liquidations relative to open
                interest across assets.
              </p>

              <MathPanel
                ariaLabel="Confirmed liquidation stress equals the minimum of the temporal liquidation percentile and the cross-sectional liquidations-to-open-interest percentile"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <mi>Q</mi>
                    <mo>=</mo>
                    <mi>min</mi>
                    <mo>(</mo>
                    <msub>
                      <mi>P</mi>
                      <mi>temporal</mi>
                    </msub>
                    <mo>,</mo>
                    <msub>
                      <mi>P</mi>
                      <mrow>
                        <mi>LIQ</mi>
                        <mo>/</mo>
                        <mi>OI</mi>
                      </mrow>
                    </msub>
                    <mo>)</mo>
                  </mrow>
                </math>`}
              />
            </MethodBlock>
          </div>

          <div className="border-t border-[#333] bg-[#090909] px-4 py-3 text-[10px] leading-5 tracking-wide text-[#777]">
            FUNDING AND BASIS HISTORICAL CALIBRATION REQUIRE AT LEAST 24 HOURS
            OF SPAN, 120 OBSERVATIONS, AND 8 DISTINCT VALUES BEFORE THE
            HISTORICAL CHANNEL IS CONSIDERED READY.
          </div>
        </section>

        {/* STATE ENGINE */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="STATE ENGINE"
            subtitle="DIRECTION AND REGIME ARE DESCRIPTIVE CONTEXT · THEY DO NOT CHANGE THE CDRR SCORE SIGN"
          />

          <div className="grid gap-px bg-[#333] md:grid-cols-2 xl:grid-cols-3">
            {STATES.map((item) => (
              <StateCard
                key={item.state}
                {...item}
              />
            ))}
          </div>

          <div className="grid gap-px border-t border-[#333] bg-[#333] lg:grid-cols-3">
            <InterpretationCard
              title="HIGH SCORE + RALLY"
              body="Stress is elevated while leverage is building into positive price action. The system does not convert that combination into a bearish prediction."
            />

            <InterpretationCard
              title="HIGH SCORE + SELLOFF"
              body="Stress is elevated while price weakness and leverage dynamics point to a more defensive or forced-risk regime."
            />

            <InterpretationCard
              title="HIGH SCORE + DELEVERAGING"
              body="The market remains stressed, but leverage is being removed rather than added. That is a different regime from fresh leveraged build-up."
            />
          </div>
        </section>

        {/* DATA QUALITY */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="DERIVATIVES DATA QUALITY"
            subtitle="CLEAN BEFORE AGGREGATION"
          />

          <div className="grid gap-px bg-[#333] md:grid-cols-2 xl:grid-cols-4">
            <QualityCard
              number="01"
              title="FRESHNESS"
              body="Provider market observations older than 15 minutes are rejected from the current derivatives snapshot."
            />

            <QualityCard
              number="02"
              title="IDENTITY"
              body="The contract base symbol must match the tracked asset, and duplicate symbol / market pairs are reduced to the newest observation."
            />

            <QualityCard
              number="03"
              title="OUTLIERS"
              body="CMC market-pair outliers are rejected. Price or volume exclusion does not automatically invalidate otherwise usable OI, funding, or basis fields."
            />

            <QualityCard
              number="04"
              title="OI CONSISTENCY"
              body="Tracked market-pair OI is checked against exchange-wide derivatives OI when that reference is available. Missing exchange-wide OI is allowed but marked unverified."
            />
          </div>
        </section>

        {/* PIPELINE */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="PIPELINE"
            subtitle="RAW CMC DATA → CLEAN FEATURES → STATE → RISK"
          />

          <div className="overflow-x-auto bg-[#0b0b0b] p-5">
            <div className="flex min-w-[980px] items-stretch">
              <PipelineNode
                index="01"
                title="CMC API"
                body="Spot · derivatives · liquidations"
              />

              <PipelineArrow />

              <PipelineNode
                index="02"
                title="QUALITY FILTERS"
                body="Freshness · identity · outliers"
              />

              <PipelineArrow />

              <PipelineNode
                index="03"
                title="FEATURE ENGINES"
                body="Vol · OI · funding · basis · liq"
              />

              <PipelineArrow />

              <PipelineNode
                index="04"
                title="STATE ENGINE"
                body="Directional / regime context"
              />

              <PipelineArrow />

              <PipelineNode
                index="05"
                title="CDRR"
                body="Relative stress ranking"
              />
            </div>
          </div>
        </section>

        {/* RESEARCH VS PRODUCTION */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="PRODUCTION VS RESEARCH"
            subtitle="EXPERIMENTAL SIGNALS ARE NOT SILENTLY PROMOTED INTO THE LIVE SCORE"
          />

          <div className="grid gap-px bg-[#333] xl:grid-cols-2">
            <div className="bg-[#0b0b0b] p-5">
              <Badge
                text="PRODUCTION · provisional_v1_equal_weight"
                className="text-[#38d996]"
              />

              <div className="mt-5 text-sm font-black text-[#f1f1f1]">
                CONCENTRATION = OI CONCENTRATION
              </div>

              <p className="mt-3 text-xs leading-6 text-[#999]">
                The live fifth factor currently uses the cross-sectional OI
                concentration percentile. This keeps the production score
                stable while the newer market-structure channels accumulate
                longitudinal evidence.
              </p>
            </div>

            <div className="bg-[#0b0b0b] p-5">
              <Badge
                text="RESEARCH ONLY"
                className="text-[#ffb000]"
              />

              <div className="mt-5 text-sm font-black text-[#f1f1f1]">
                CANDIDATE STRUCTURE = 50 / 25 / 25
              </div>

              <MathPanel
                ariaLabel="Research structure candidate equals fifty percent open-interest concentration, twenty-five percent basis level, and twenty-five percent basis dispersion"
                markup={String.raw`<math
                  xmlns="http://www.w3.org/1998/Math/MathML"
                  display="block"
                >
                  <mrow>
                    <msub>
                      <mi>S</mi>
                      <mi>B</mi>
                    </msub>
                    <mo>=</mo>
                    <mn>0.50</mn>
                    <msub>
                      <mi>C</mi>
                      <mi>OI</mi>
                    </msub>
                    <mo>+</mo>
                    <mn>0.25</mn>
                    <msub>
                      <mi>B</mi>
                      <mi>level</mi>
                    </msub>
                    <mo>+</mo>
                    <mn>0.25</mn>
                    <msub>
                      <mi>B</mi>
                      <mi>disp</mi>
                    </msub>
                  </mrow>
                </math>`}
              />

              <p className="mt-3 text-xs leading-6 text-[#999]">
                Basis magnitude and cross-venue basis dispersion are now
                historically calibrated, but the candidate remains outside the
                production score until sufficient forward-stress and
                longitudinal history supports promotion.
              </p>
            </div>
          </div>
        </section>

        {/* LIMITATIONS */}
        <section className="mt-4 overflow-hidden border border-[#454545] bg-[#0d0d0d]">
          <SectionHeader
            title="CURRENT LIMITATIONS"
            subtitle="IMPORTANT WHEN READING THE TERMINAL"
          />

          <div className="grid gap-px bg-[#333] md:grid-cols-2 xl:grid-cols-4">
            <Limitation
              title="RELATIVE UNIVERSE"
              body="Ranks are only relative to the 20 tracked assets. They are not a statement about the entire crypto market."
            />

            <Limitation
              title="SHORT LIVE HISTORY"
              body="Several calibration and forward-validation datasets are still accumulating. Production weights are intentionally conservative while that history grows."
            />

            <Limitation
              title="OVERLAPPING TARGETS"
              body="High-frequency forward-validation snapshots overlap heavily, so a large snapshot count does not imply the same number of independent statistical observations."
            />

            <Limitation
              title="NO PRICE FORECAST"
              body="CDRR estimates stress magnitude and market regime. It does not produce expected returns, price targets, or trade instructions."
            />
          </div>
        </section>

        {/* FOOTER */}
        <footer className="mt-6 border-t border-[#333] py-6 text-[10px] leading-5 tracking-wide text-[#707070]">
          CDRR · CRYPTO DERIVATIVES RISK RADAR · QUANTITATIVE RESEARCH
          PROTOTYPE · DATA SOURCED THROUGH COINMARKETCAP API · SCORE VERSION:
          provisional_v1_equal_weight
        </footer>
      </div>
    </main>
  );
}

// ============================================================
// SHARED PRESENTATION COMPONENTS
// ============================================================

function HeroMetric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="bg-[#0a0a0a] p-4">
      <div className="text-[9px] font-bold tracking-[0.12em] text-[#777]">
        {label}
      </div>

      <div className="mt-2 text-xl font-black text-[#f4f4f4]">
        {value}
      </div>

      <div className="mt-1 text-[9px] tracking-wide text-[#777]">
        {sub}
      </div>
    </div>
  );
}

function TerminalPanel({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: ReactNode;
}) {
  return (
    <section className="border border-[#454545] bg-[#0d0d0d]">
      <div className="border-b border-[#454545] bg-[#171717] px-4 py-3">
        <div className="text-[9px] font-bold tracking-[0.14em] text-[#777]">
          {eyebrow}
        </div>

        <div className="mt-1 text-sm font-black tracking-[0.08em] text-[#ffb000]">
          {title}
        </div>
      </div>

      <div className="p-4">
        {children}
      </div>
    </section>
  );
}

function SectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="border-b border-[#454545] bg-[#171717] px-4 py-3">
      <div className="text-sm font-black tracking-[0.08em] text-[#ffb000]">
        {title}
      </div>

      <div className="mt-1 text-xs tracking-wide text-[#949494]">
        {subtitle}
      </div>
    </div>
  );
}

function StatusCell({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="bg-[#090909] p-3">
      <div className="text-[9px] font-bold tracking-[0.1em] text-[#777]">
        {label}
      </div>

      <div className="mt-2 text-xs font-black text-[#f1f1f1]">
        {value}
      </div>

      <div className="mt-1 text-[9px] text-[#777]">
        {detail}
      </div>
    </div>
  );
}

function BoundaryRow({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[18px_1fr] gap-3 border-b border-[#2d2d2d] pb-3 text-xs leading-6 text-[#aaa] last:border-0 last:pb-0">
      <span className="font-black text-[#ff6666]">×</span>
      <div>{children}</div>
    </div>
  );
}

function FactorKey({
  symbol,
  title,
  weight,
  colour,
}: {
  symbol: string;
  title: string;
  weight: string;
  colour: string;
}) {
  return (
    <div className="bg-[#0b0b0b] p-4 text-center">
      <div className={`text-2xl font-black ${colour}`}>
        {symbol}
      </div>

      <div className="mt-2 text-[9px] font-black tracking-[0.08em] text-[#d0d0d0]">
        {title}
      </div>

      <div className="mt-1 text-[9px] text-[#777]">
        {weight}
      </div>
    </div>
  );
}

function FactorCard({
  symbol,
  number,
  title,
  weight,
  colour,
  summary,
  signal,
  interpretation,
}: {
  symbol: string;
  number: string;
  title: string;
  weight: string;
  colour: string;
  summary: string;
  signal: string;
  interpretation: string;
}) {
  return (
    <article className="bg-[#0b0b0b] p-4">
      <div className="flex items-start justify-between gap-4">
        <span className="text-[9px] font-bold text-[#666]">
          {number}
        </span>

        <span className="text-[9px] font-black text-[#777]">
          {weight}
        </span>
      </div>

      <div className={`mt-5 text-2xl font-black ${colour}`}>
        {symbol}
      </div>

      <div className="mt-2 text-xs font-black tracking-[0.08em] text-[#f1f1f1]">
        {title}
      </div>

      <p className="mt-4 text-xs leading-5 text-[#aaa]">
        {summary}
      </p>

      <div className="mt-4 border-t border-[#303030] pt-4">
        <div className="text-[9px] font-black tracking-[0.1em] text-[#707070]">
          SIGNAL
        </div>

        <p className="mt-2 text-[11px] leading-5 text-[#929292]">
          {signal}
        </p>
      </div>

      <div className="mt-4 border-t border-[#303030] pt-4">
        <div className="text-[9px] font-black tracking-[0.1em] text-[#707070]">
          INTERPRETATION
        </div>

        <p className="mt-2 text-[11px] leading-5 text-[#929292]">
          {interpretation}
        </p>
      </div>
    </article>
  );
}

function MethodBlock({
  title,
  tag,
  tagClass,
  children,
}: {
  title: string;
  tag: string;
  tagClass: string;
  children: ReactNode;
}) {
  return (
    <div className="bg-[#0b0b0b] p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="text-xs font-black tracking-[0.08em] text-[#f1f1f1]">
          {title}
        </div>

        <span
          className={`text-[9px] font-black tracking-[0.12em] ${tagClass}`}
        >
          {tag}
        </span>
      </div>

      <div className="mt-4 space-y-4 text-xs leading-6 text-[#999]">
        {children}
      </div>
    </div>
  );
}

function MathPanel({
  markup,
  ariaLabel,
}: {
  markup: string;
  ariaLabel: string;
}) {
  return (
    <div
      role="math"
      aria-label={ariaLabel}
      className="overflow-x-auto border border-[#3a3a3a] bg-[#070707] px-4 py-4 text-center text-[17px] text-[#f0f0f0] md:text-[19px] [&_math]:mx-auto [&_math]:min-w-max [&_math]:font-serif"
      dangerouslySetInnerHTML={{ __html: markup }}
    />
  );
}

function ValidationCell({
  label,
  value,
  sub,
  valueClass = "text-[#f4f4f4]",
}: {
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="bg-[#0b0b0b] px-4 py-4">
      <div className="text-[9px] font-bold tracking-[0.1em] text-[#777]">
        {label}
      </div>

      <div className={`mt-2 text-xl font-black tabular-nums ${valueClass}`}>
        {value}
      </div>

      <div className="mt-1 text-[9px] tracking-wide text-[#777]">
        {sub}
      </div>
    </div>
  );
}

function StateCard({
  state,
  meaning,
  colour,
}: {
  state: string;
  meaning: string;
  colour: string;
}) {
  return (
    <article className="bg-[#0b0b0b] p-4">
      <div className={`text-xs font-black tracking-[0.06em] ${colour}`}>
        {state}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-[#999]">
        {meaning}
      </p>
    </article>
  );
}

function InterpretationCard({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="bg-[#090909] p-4">
      <div className="text-[10px] font-black tracking-[0.08em] text-[#d8d8d8]">
        {title}
      </div>

      <p className="mt-2 text-[11px] leading-5 text-[#8f8f8f]">
        {body}
      </p>
    </div>
  );
}

function QualityCard({
  number,
  title,
  body,
}: {
  number: string;
  title: string;
  body: string;
}) {
  return (
    <article className="bg-[#0b0b0b] p-4">
      <div className="text-[9px] font-bold text-[#666]">
        {number}
      </div>

      <div className="mt-5 text-xs font-black tracking-[0.08em] text-[#f1f1f1]">
        {title}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-[#999]">
        {body}
      </p>
    </article>
  );
}

function PipelineNode({
  index,
  title,
  body,
}: {
  index: string;
  title: string;
  body: string;
}) {
  return (
    <div className="min-w-[160px] flex-1 border border-[#393939] bg-[#101010] p-4">
      <div className="text-[9px] font-bold text-[#666]">
        {index}
      </div>

      <div className="mt-4 text-xs font-black tracking-[0.08em] text-[#ffb000]">
        {title}
      </div>

      <div className="mt-2 text-[10px] leading-5 text-[#888]">
        {body}
      </div>
    </div>
  );
}

function PipelineArrow() {
  return (
    <div className="flex w-10 shrink-0 items-center justify-center text-lg font-black text-[#555]">
      →
    </div>
  );
}

function Badge({
  text,
  className,
}: {
  text: string;
  className: string;
}) {
  return (
    <div className={`text-[9px] font-black tracking-[0.14em] ${className}`}>
      {text}
    </div>
  );
}

function Limitation({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <article className="bg-[#0b0b0b] p-4">
      <div className="text-[10px] font-black tracking-[0.08em] text-[#ffb000]">
        {title}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-[#999]">
        {body}
      </p>
    </article>
  );
}
