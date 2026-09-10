# Crypto Derivatives Risk Radar

**Crypto Derivatives Risk Radar (CDRR)** is a quantitative derivatives-market stress monitor built for the **2026 CoinMarketCap Build with CMC API Hackathon**.

Rather than predicting whether a cryptocurrency will go up or down, CDRR asks a different question:

> **Where is derivatives-market stress concentrated right now, how unusual is it, and what is driving it?**

The system continuously collects CoinMarketCap market and derivatives data, builds calibrated risk features for a tracked crypto universe, classifies market states, and ranks assets with a transparent multi-factor risk score.

---

## What CDRR measures

CDRR combines five distinct sources of derivatives risk:

1. **Volatility stress** — own-history realised volatility plus cross-sectional volatility expansion.
2. **Leverage stress** — magnitude of validated common-universe open-interest changes.
3. **Funding crowding** — extreme long/short positioning inferred from robust funding-rate calibration.
4. **Liquidation stress** — unusual liquidation activity confirmed by liquidation-to-open-interest materiality.
5. **Market structure** — cross-exchange open-interest concentration.

Direction is deliberately kept separate from stress magnitude. A high CDRR score does **not** mean "price will fall"; it means the asset currently exhibits a comparatively elevated combination of derivatives-market risk signals.

The current production score is:

\[
R_i^{(0)}
=
100\left(
0.2V_i
+
0.2L_i
+
0.2C_i
+
0.2Q_i
+
0.2D_i
\right),
\]

where every component is normalised to \([0,1]\).

The production model is explicitly versioned as:

```text
provisional_v1_equal_weight
```

Absolute labels such as "low", "medium" and "high" are intentionally avoided at this stage. The score is a **relative, provisional risk ranking** across the tracked universe.

---

## Dashboard

The frontend is a Bloomberg-terminal-inspired Next.js dashboard showing:

- live CDRR rankings;
- component-level risk drivers;
- spot-market context;
- realised and conditional volatility;
- common-universe open-interest changes;
- funding and basis information;
- liquidation activity and direction;
- market-state classifications;
- data quality and freshness context.

The dashboard consumes the local FastAPI service rather than calling CoinMarketCap directly from the browser, keeping the API key server-side.

---

## Architecture

```text
                         CoinMarketCap API
                                |
                                v
                    Continuous Python Collector
                                |
              +-----------------+-----------------+
              |                                   |
              v                                   v
       Raw Parquet snapshots                Usage / budget guard
              |
              v
     +--------+---------+----------+-----------+-------------+
     |                  |          |           |             |
     v                  v          v           v             v
   Spot            Volatility  Derivatives   Funding    Liquidations
     |                  |          |           |             |
     |                  |          +-----> Basis calibration |
     |                  |                                |    |
     +------------------+---------------+----------------+----+
                                        |
                                        v
                              Cross-sectional features
                                        |
                                        v
                                  Market states
                                        |
                                        v
                                 CDRR risk score
                                        |
                          +-------------+-------------+
                          |                           |
                          v                           v
                       FastAPI                 Research pipelines
                          |                 - market structure
                          |                 - forward validation
                          v
                    Next.js dashboard
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the detailed data flow.

---

## Repository structure

```text
.
├── backend/
│   ├── app.py
│   └── risk_radar/
│       ├── basis.py
│       ├── cross_section.py
│       ├── derivatives.py
│       ├── forward_validation.py
│       ├── funding.py
│       ├── liquidations.py
│       ├── market_structure_research.py
│       ├── risk.py
│       ├── spot.py
│       ├── states.py
│       └── volatility.py
├── docs/
├── frontend/
│   └── src/
│       ├── app/
│       └── components/
├── research/
├── scripts/
│   ├── collect_data.py
│   ├── fit_volatility_models.py
│   ├── update_basis.py
│   ├── update_derivatives.py
│   ├── update_funding.py
│   ├── update_liquidations.py
│   ├── update_risk.py
│   ├── update_spot.py
│   ├── update_states.py
│   ├── update_volatility.py
│   ├── analyse_market_structure.py
│   └── validate_forward_stress.py
└── pyproject.toml
```

Generated market data and research Parquet files are intentionally excluded from Git.

---

## CoinMarketCap usage

CDRR uses CoinMarketCap as its primary market-data source. The collector uses API functionality for:

- latest cryptocurrency quotes;
- derivative market pairs;
- cryptocurrency liquidation snapshots;
- global liquidation snapshots;
- exchange liquidation snapshots;
- derivatives exchange summaries;
- API usage / plan information.

The API key is read server-side and must never be exposed through the frontend or committed to Git.

Market data attribution: **CoinMarketCap API**. Use of CoinMarketCap data remains subject to CoinMarketCap's applicable API terms and licence.

---

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd crypto-derivatives-risk-radar
```

### 2. Python environment

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e .
```

Create a root `.env` containing the CoinMarketCap API key expected by `scripts/get_data.py`.

Do **not** commit `.env`.

### 3. Frontend

```bash
cd frontend
npm install
```

Create:

```text
frontend/.env.local
```

with:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

For access from another machine on the same network, replace `127.0.0.1` with the backend machine's LAN IP.

---

## Running the project

### Start the data collector

From the repository root:

```bash
source .venv/bin/activate
python scripts/collect_data.py
```

Run one cycle only:

```bash
python scripts/collect_data.py --once
```

The collector includes a lock file to prevent accidental duplicate processes and dynamically adjusts its polling interval using live CoinMarketCap credit and rate-limit information.

### Start the API

```bash
uvicorn backend.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

### Start the frontend

In another terminal:

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:3000/dashboard
```

---

## API endpoints

The FastAPI service exposes local processed snapshots including:

```text
GET /api/health
GET /api/market/latest
GET /api/volatility/latest
GET /api/derivatives/latest
GET /api/liquidations/latest
GET /api/liquidations/global
GET /api/liquidations/exchanges
GET /api/states/latest
GET /api/risk/latest
```

`/api/health` reports snapshot availability, row counts, modification time, age and read errors.

---

## Quantitative methodology

The project does not simply sum raw API fields. Each subsystem includes validation and calibration designed to make heterogeneous derivatives data more comparable.

Highlights include:

- a Student-\(t\) power-law conditional variance model;
- walk-forward volatility-model comparison against EWMA;
- common-universe OI changes to prevent changing contract coverage from masquerading as leverage changes;
- prior-only empirical midrank calibration for funding, basis and liquidations;
- conservative confirmation rules requiring stress to be unusual in more than one sense;
- explicit source freshness and synchronisation checks;
- direction-free risk magnitude with separate state classification.

Full details are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

---

## Validation

CDRR includes a forward-stress validation framework rather than relying only on contemporaneous plausibility.

Current CDRR scores are evaluated against subsequent:

- realised path volatility;
- maximum absolute price excursion;
- downside excursion;
- maximum future 1h liquidations / OI.

For each timestamp and horizon, the research pipeline calculates a cross-sectional Spearman information coefficient:

\[
IC_t^{(h)}
=
\rho_S
\left(
R_{i,t},
Y_{i,t\rightarrow t+h}
\right).
\]

It also compares forward stress across CDRR risk quintiles.

The clean validation epoch begins on **10 September 2026 at 17:22 UTC (18:22 BST)**. At repository completion, the longitudinal sample is still accumulating, so early forward-validation results must not be interpreted as statistically significant.

See [docs/VALIDATION.md](docs/VALIDATION.md).

---

## Research-only market-structure candidate

The production fifth factor currently uses open-interest concentration only.

A research pipeline is collecting evidence for a richer candidate:

\[
S_{\text{structure}}^{*}
=
0.50C_{\text{OI}}
+
0.25B_{\text{magnitude}}
+
0.25B_{\text{dispersion}},
\]

where:

- \(C_{\text{OI}}\) is the OI-concentration percentile;
- \(B_{\text{magnitude}}\) is calibrated absolute central basis;
- \(B_{\text{dispersion}}\) is calibrated cross-venue basis dispersion.

This formulation is **not** used in the production CDRR score. It is being evaluated longitudinally before any promotion to a future model version.

---

## Current tracked universe

The default collector tracks 20 liquid crypto assets:

```text
BTC ETH SOL XRP BNB DOGE ADA LINK AVAX SUI
TRX DOT LTC BCH UNI APT NEAR ETC ICP FIL
```

The tracked universe is configurable through the collector's `--ids` argument.

---

## Design principles

CDRR follows several rules throughout the project:

- **No directional price prediction.**
- **No hidden black-box score.**
- **Do not confuse data absence with zero risk.**
- **Use prior-only history when calibrating current observations.**
- **Preserve direction separately from stress magnitude.**
- **Expose data quality and model warm-up states.**
- **Keep experimental factors out of production until validated.**

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Methodology](docs/METHODOLOGY.md)
- [Validation](docs/VALIDATION.md)
- [Hackathon submission notes](docs/HACKATHON.md)

---

## Status

The project is a **hackathon release candidate**.

The ingestion, processing, API, dashboard, provisional CDRR model, market-structure research and forward-validation infrastructure are implemented. Historical calibration and forward validation continue to accumulate automatically, so the repository distinguishes clearly between:

- production functionality;
- provisional modelling assumptions;
- research candidates;
- results that require more longitudinal data.

---

## Licence

See [LICENSE](LICENSE).
