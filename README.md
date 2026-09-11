# Crypto Derivatives Risk Radar

**Crypto Derivatives Risk Radar (CDRR)** is a quantitative crypto-derivatives stress monitor built for the **2026 CoinMarketCap Build with CMC API Hackathon**.

**Track:** Data and Visualisation  
**Live demo:** https://cdrr.duckdns.org  
**Repository:** https://github.com/callumconnel1/crypto-derivatives-risk-radar

Rather than predicting whether a cryptocurrency will go up or down, CDRR asks a different question:

> **Where is derivatives-market stress concentrated right now, how unusual is it, and what is driving it?**

The system continuously collects CoinMarketCap market and derivatives data, builds calibrated risk features for a tracked crypto universe, classifies market states, and ranks assets with a transparent multi-factor risk score.

---

## What CDRR measures

CDRR combines five distinct sources of derivatives stress:

1. **Volatility stress** — own-history realised volatility plus cross-sectional volatility expansion.
2. **Leverage stress** — magnitude of validated common-universe open-interest changes.
3. **Funding crowding** — unusually one-sided perpetual positioning inferred from robust funding-rate calibration.
4. **Liquidation stress** — unusual liquidation activity confirmed by liquidation-to-open-interest materiality.
5. **Concentration** — cross-exchange open-interest concentration.

Direction is deliberately kept separate from stress magnitude. A high CDRR score does **not** mean "price will fall"; it means the asset currently exhibits a comparatively elevated combination of derivatives-market stress signals.

The current production score is $R_i^{(0)} = 100\left(0.2V_i + 0.2L_i + 0.2C_i + 0.2Q_i + 0.2D_i\right)$, where every component is normalised to $[0,1]$.

The production model is explicitly versioned as:

```text
provisional_v1_equal_weight
```

Absolute labels such as "low", "medium" and "high" are intentionally avoided at this stage. The score is a **relative, provisional stress ranking** across the tracked universe.

---

## Live dashboard

The Bloomberg-terminal-inspired Next.js frontend shows:

- live CDRR rankings;
- component-level stress drivers;
- spot-market context;
- realised and conditional volatility;
- common-universe open-interest changes;
- funding and basis information;
- liquidation activity and direction;
- market-state classifications;
- data-quality and freshness context.

The deployed application is available at:

```text
https://cdrr.duckdns.org
```

The browser never receives the CoinMarketCap API key. The Next.js server proxies `/api/*` requests to the internal FastAPI service, while the collector and API remain private on the host.

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

Production deployment:

```text
Internet
   |
   v
Caddy :443 (HTTPS)
   |
   v
Next.js :3000
   |
   +---- /api/* ----> FastAPI :8000
                         |
                         v
                 Persistent Parquet data
                         ^
                         |
                  CMC collector service
```

The collector, API and frontend run as separate `systemd` services on the production VPS.

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

Generated market-data and research Parquet files are intentionally excluded from Git.

---

## CoinMarketCap API usage

CoinMarketCap is the primary market-data source for CDRR.

The production collector uses these CMC Pro API endpoints:

```text
GET /v3/cryptocurrency/quotes/latest
GET /v5/cryptocurrency/derivatives/market-pairs/list/latest
GET /v5/derivatives/liquidations/cryptocurrency/list/latest
GET /v5/derivatives/liquidations/quotes/latest
GET /v5/derivatives/liquidations/exchange/list/latest
GET /v5/exchange/derivatives/list
GET /v1/key/info
```

They provide the raw spot, derivatives, funding, basis, open-interest, liquidation, exchange and API-plan data from which CDRR builds its processed features.

The API key is read server-side and is never exposed through the frontend or committed to Git.

Market-data attribution: **CoinMarketCap API**. Use of CoinMarketCap data remains subject to CoinMarketCap's applicable API terms and licence.

### Evidence of a real API call

A production collector request looks like:

```http
GET https://pro-api.coinmarketcap.com/v5/cryptocurrency/derivatives/market-pairs/list/latest?crypto_id=1&start=1&limit=250&category=all&convert=USD
X-CMC_PRO_API_KEY: <server-side key>
```

A real response contains per-market fields used directly by the pipeline, including:

```json
{
  "market_pair_symbol": "BTC/USDT",
  "category": "perpetual",
  "exchange": {
    "exchange_name": "Binance"
  },
  "exchange_reported_quotes": [
    {
      "convert_symbol": "USD",
      "open_interest": 8343305358.9912,
      "index_price": 79052.78993047,
      "index_basis": -0.00008660793202,
      "funding_rate": 0.00006587
    }
  ]
}
```

The collector validates freshness, identity and provider exclusions before those fields are allowed into the production feature pipeline.

---

## What the CMC API made possible

CDRR depends on being able to observe spot prices, derivative contracts, venue-level open interest, funding, basis and liquidation activity through one data provider.

That made it practical to build a cross-venue stress monitor rather than a single-exchange dashboard. In particular, the derivative market-pair responses expose the fields needed to compare leverage, crowding and venue concentration across a common asset universe.

The API also exposed several implementation challenges that shaped the project:

- derivative contract coverage can change between observations, so CDRR computes **common-universe OI changes** instead of blindly differencing aggregate OI;
- provider freshness, exclusions and occasional incomplete fields require explicit data-quality gates;
- funding and basis vary materially across venues, so CDRR uses robust aggregation and historical calibration rather than a single contract;
- API credits are finite, so the production collector reads `/v1/key/info` and adapts its polling interval to the remaining monthly budget and rate limit;
- some research questions require longitudinal history that must accumulate during operation, so experimental signals remain outside the production score until enough evidence exists.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/callumconnel1/crypto-derivatives-risk-radar.git
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

Create a root `.env` containing your CoinMarketCap API key:

```env
CMC_API_KEY=your_key_here
```

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

```env
API_INTERNAL_URL=http://127.0.0.1:8000
```

The frontend proxies `/api/*` through the Next.js server, so the internal FastAPI address is not exposed to the browser.

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

From the repository root:

```bash
uvicorn backend.app:app \
  --host 127.0.0.1 \
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
http://localhost:3000
```

---

## Local API endpoints

The FastAPI service exposes processed snapshots including:

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

- a Student-$t$ power-law conditional variance model;
- walk-forward volatility-model comparison against EWMA;
- common-universe OI changes to prevent changing contract coverage from masquerading as leverage changes;
- prior-only empirical midrank calibration for funding, basis and liquidations;
- conservative confirmation rules requiring stress to be unusual in more than one sense;
- explicit source freshness and synchronisation checks;
- direction-free risk magnitude with separate state classification.

Full details are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

---

## Forward validation

CDRR includes a forward-stress validation framework rather than relying only on contemporaneous plausibility.

Current CDRR scores are evaluated against subsequent:

- realised path volatility;
- maximum absolute price excursion;
- downside excursion;
- maximum future 1h liquidations / OI.

For each timestamp and horizon, the research pipeline calculates the cross-sectional Spearman information coefficient $IC_t^{(h)} = \rho_S\left(R_{i,t}, Y_{i,t\rightarrow t+h}\right)$.

It also compares forward stress across CDRR risk quintiles.

The clean validation epoch begins on **10 September 2026 at 17:22 UTC (18:22 BST)**. Early 1h and 4h observations show positive cross-sectional stress-ranking behaviour, and the first mature 24h observations are directionally encouraging for realised volatility, downside excursion and maximum absolute movement.

These observations remain heavily overlapping and serially dependent. They are treated as early model diagnostics, **not as statistical proof and not as justification for optimising production weights**.

See [docs/VALIDATION.md](docs/VALIDATION.md).

---

## Research-only market-structure candidate

The production fifth factor is **open-interest concentration**.

A separate research pipeline is collecting evidence for the richer candidate $S_{\text{structure}}^{*} = 0.50C_{\text{OI}} + 0.25B_{\text{magnitude}} + 0.25B_{\text{dispersion}}$, where:

- $C_{\text{OI}}$ is the OI-concentration percentile;
- $B_{\text{magnitude}}$ is calibrated absolute central basis;
- $B_{\text{dispersion}}$ is calibrated cross-venue basis dispersion.

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

CDRR is a **live deployed hackathon build**.

The production system currently includes:

- continuous CoinMarketCap ingestion;
- persistent raw and processed Parquet history;
- adaptive API-credit management;
- derivatives data-quality filtering;
- conditional-volatility modelling;
- funding, basis and liquidation calibration;
- common-universe OI measurement;
- market-state classification;
- the provisional equal-weight CDRR production score;
- forward-stress validation infrastructure;
- FastAPI processed-data endpoints;
- a public Next.js dashboard served over HTTPS.

Historical calibration and forward validation continue to accumulate automatically. The repository deliberately distinguishes between production functionality, provisional modelling assumptions, research candidates and results that still require more longitudinal data.

---

## Licence

See [LICENSE](LICENSE).
