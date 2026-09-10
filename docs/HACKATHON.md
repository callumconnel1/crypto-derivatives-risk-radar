# Hackathon Submission Notes

## Project name

**Crypto Derivatives Risk Radar (CDRR)**

---

## One-line description

A live quantitative risk radar that uses CoinMarketCap market and derivatives data to rank where crypto derivatives stress is concentrated and explain what is driving it.

---

## Short submission description

Crypto Derivatives Risk Radar is a live derivatives-market monitoring platform built on the CoinMarketCap API.

Instead of trying to predict whether a token will rise or fall, CDRR measures the **current magnitude and structure of derivatives stress** across a tracked crypto universe.

The system continuously combines conditional volatility, validated open-interest changes, funding crowding, liquidation pressure and exchange concentration into an explainable risk ranking. A separate state engine describes regimes such as deleveraging, OI build into rallies/selloffs and long/short liquidation stress.

The stack includes a Python/Polars research backend, FastAPI service and a Next.js/TypeScript terminal-style dashboard.

CDRR also includes forward-validation infrastructure so the risk ranking can be tested against subsequent realised volatility, price excursions and liquidation/OI stress rather than judged only by visual plausibility.

---

## Problem

Crypto derivatives risk is fragmented across several data channels:

- leverage builds through open interest;
- funding reflects positioning pressure;
- liquidations reveal forced flows;
- volatility changes the probability and size of forced unwinds;
- derivatives exposure is distributed unevenly across exchanges.

Looking at any one metric in isolation can be misleading.

A large liquidation print may be routine for BTC but extreme for a smaller market. Aggregate OI may appear to change simply because contract coverage changed. Funding sign alone does not tell us whether positioning is genuinely crowded.

CDRR combines these signals into a single explainable monitoring framework while preserving their individual diagnostics.

---

## Solution

For each tracked asset, CDRR builds five risk components:

```text
Volatility
Leverage / OI
Funding crowding
Liquidation stress
Market structure
```

Each component is mapped to a comparable \([0,1]\) scale and the current production model applies transparent equal weights.

The dashboard then shows:

- the total relative risk score;
- each component contribution;
- the current market-state label;
- the underlying data needed to understand why the score is elevated.

CDRR is deliberately **not** a black-box directional prediction model.

---

## How CoinMarketCap is used

CoinMarketCap is the primary live data source.

The application uses CMC API functionality for:

- latest cryptocurrency quotes;
- derivative market pairs;
- asset liquidation snapshots;
- global liquidation activity;
- exchange liquidation activity;
- derivatives exchange summaries;
- API credit / rate-limit information.

CMC data powers both the live dashboard and the historical research/calibration pipeline.

The collector dynamically adapts its polling interval to live API-plan usage so the project can run continuously without blindly exhausting its monthly allocation.

---

## Technical highlights

### Common-universe OI

OI changes are calculated only over contracts that exist at both the current and reference timestamp:

$$ \Delta OI_h^{common} = \frac{ \sum_{m\in I}OI_{m,t} }{ \sum_{m\in I}OI_{m,t-h} } -1. $$

This reduces false leverage signals caused by changing contract coverage.

### Conditional volatility

A Student-\(t\) power-law memory model forecasts conditional variance from 5-minute returns:

$$ \sigma_{t+1}^{2} = c + \beta \sum_{k=0}^{K-1} \frac{r_{t-k}^{2}} {(k+1)^\alpha}. $$

The model was compared with EWMA in walk-forward testing.

### Robust calibration

Funding, basis and liquidations use prior-only empirical midrank percentiles:

$$ P(x_t) = \frac{\#\{j : x_j < x_t\} + \tfrac{1}{2}\#\{j : x_j = x_t\}}{N}. $$

This is particularly useful for tied and zero-heavy liquidation data.

### Explainable state engine

The scalar score is direction-neutral, while a separate state engine identifies regimes such as:

```text
DELEVERAGING
OI BUILD INTO RALLY
OI BUILD INTO SELLOFF
LONG LIQUIDATION STRESS
SHORT LIQUIDATION STRESS
```

### Forward validation

The repository already includes a framework for testing whether high current CDRR rankings correspond to greater subsequent realised stress at 1h, 4h and 24h horizons.

---

## Innovation

The main innovation is not a single exotic formula. It is the way the system makes heterogeneous derivatives data comparable while preserving data quality and economic meaning.

Key examples:

- common-universe rather than naive aggregate OI changes;
- liquidation stress confirmed by both own-history activity and liquidation/OI materiality;
- funding sign separated from crowding magnitude;
- basis magnitude separated from cross-venue dispersion;
- production factors kept separate from research-only candidates;
- explicit model warm-up and source-quality states;
- no directional claim attached to the risk score.

---

## Current production score

$$ R_i^{(0)} = 100 \left( 0.2V_i + 0.2L_i + 0.2C_i + 0.2Q_i + 0.2D_i \right). $$

Version:

```text
provisional_v1_equal_weight
```

The word **provisional** is intentional. The project does not optimise weights on a tiny historical sample merely to produce a more impressive backtest.

---

## Research extension

A richer market-structure factor is being collected as a research candidate:

$$ S_{\text{structure}}^{*} = 0.50C_{\text{OI}} + 0.25B_{\text{magnitude}} + 0.25B_{\text{dispersion}}. $$

It is not promoted into production until historical calibration and longitudinal validation are sufficiently mature.

---

## Demo flow

A concise demo can be delivered in roughly two minutes.

### 0:00-0:20 — Problem

"Crypto derivatives risk is not one number. Leverage, funding, volatility, liquidations and exchange structure can all deteriorate differently. CDRR brings those signals together."

### 0:20-0:45 — Risk ranking

Show the CDRR table.

"The score is relative and direction-neutral. The highest asset is the market where the current combination of derivatives-risk factors is most elevated, not the asset we think will fall the most."

### 0:45-1:15 — Explain one asset

Open the component view for a high-ranked asset.

"Here we can see exactly which factors are driving the score: volatility, leverage, funding, liquidations and market structure."

Point to the primary state.

"The state engine separately tells us whether this is deleveraging, OI build, or liquidation stress."

### 1:15-1:35 — Data-quality innovation

Show common OI overlap / funding source / liquidation normalisation.

"We do not simply trust raw aggregate changes. OI uses a common contract universe, funding has explicit warm-up calibration, and liquidation activity is normalised by OI."

### 1:35-1:55 — Research and validation

"The system also stores research history and tests today's risk ranking against future realised volatility, price excursions and liquidation stress."

### 1:55-2:00 — Close

"CDRR turns CoinMarketCap derivatives data into an explainable live risk-monitoring system rather than another price-prediction dashboard."

---

## Suggested judging points

### Usefulness

A trader, researcher or risk manager can immediately see where derivatives-market stress is concentrated and inspect the cause.

### Technical depth

The project includes:

- continuous API ingestion;
- adaptive API-budget control;
- data-quality validation;
- conditional volatility modelling;
- cross-sectional feature engineering;
- historical empirical calibration;
- state classification;
- explainable multi-factor scoring;
- forward validation;
- full-stack delivery.

### Responsible modelling

The application avoids claiming certainty or directional predictive power that has not been demonstrated.

Experimental factors are labelled as research rather than quietly inserted into production.

---

## Limitations to state openly

- The tracked universe contains 20 selected liquid assets rather than the entire crypto market.
- The current production weights are provisional equal weights.
- Funding and basis historical calibration require sufficient live history.
- The forward-validation sample is still accumulating.
- API data quality and venue coverage can vary.
- CDRR is a relative monitoring tool, not investment advice.

These limitations are strengths of the submission when presented correctly because they show that the model distinguishes implemented functionality from claims that still require evidence.

---

## Submission checklist

Before submission:

```text
[ ] README renders correctly on GitHub
[ ] Mermaid architecture renders
[ ] No .env or .env.local committed
[ ] No API keys in notebooks or source
[ ] No raw/processed/research Parquet data committed
[ ] frontend npm run lint passes
[ ] frontend npm run build passes
[ ] FastAPI starts from clean environment
[ ] collector --once completes
[ ] /api/health responds
[ ] /api/risk/latest responds
[ ] dashboard loads
[ ] GitHub repository is public if required by hackathon rules
[ ] demo link / video added if required
```
