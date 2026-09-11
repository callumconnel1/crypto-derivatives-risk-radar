# CDRR terminology

This file defines the canonical user-facing terminology for Crypto Derivatives Risk Radar. Internal field names may remain unchanged for API compatibility.

## Score and state

- **CDRR score / stress score**: a relative **stress-magnitude** score on a 0–100 scale within the tracked universe.
- The score is **not** a crash probability, return forecast, price target, or trade signal.
- **Primary state / state engine**: directional and regime context kept separate from the stress score.
- Avoid absolute labels such as *low risk*, *medium risk*, or *high risk* unless a validated absolute calibration is introduced later.

## Universe

- **Tracked universe**: the fixed 20-asset CDRR research universe.
- **Top CDRR asset**: the highest-ranked asset in the tracked universe, not the whole crypto market.
- **Tracked open interest**: cleaned OI retained across valid tracked derivatives markets. Do not call this global OI.
- **Common-universe OI change**: OI change calculated only on contracts valid both now and at the lag horizon.

## Liquidations

- **Tracked 1H liquidations**: liquidations aggregated across the 20 tracked assets.
- **Global 24H liquidations**: CoinMarketCap's market-wide global liquidation snapshot.
- Always distinguish these two concepts in labels and help text.
- **LIQ/OI**: liquidation notional divided by cleaned tracked open interest.

## Funding

- **Funding**: observed perpetual funding rate. It is **not annualised** in CDRR.
- **Cross-asset median funding**: median funding across the tracked asset universe.
- **Funding crowding**: the production stress component based on confirmed funding-tail magnitude.
- **HIST + X-SEC**: historical and cross-sectional confirmation are both available.
- **X-SEC WARMUP**: historical calibration is not yet ready, so only the cross-section is available.

## Volatility

- **RV 1H / 4H / 24H**: realised volatility over the named return window; displayed annualised.
- **PL 1H FWD**: next-one-hour conditional volatility forecast from the Student-t power-law model; displayed annualised.
- **EWMA 1H FWD**: next-one-hour EWMA conditional volatility forecast; displayed annualised.
- **1H sigma**: the one-hour standard deviation implied by the annualised conditional volatility. Do not describe the annualised forecast itself as a one-hour expected price move.
- **Model spread**: `(power-law forecast - EWMA forecast) / EWMA forecast`.

## Production factors

Production `provisional_v1_equal_weight` uses five 20% factors:

- **VOL** — volatility stress.
- **OI** — leverage / common-universe OI-change magnitude.
- **FUND** — funding crowding.
- **LIQ** — confirmed liquidation stress.
- **CONC** — open-interest venue concentration.

The API field `market_structure_component` is retained for compatibility, but the current production value is **concentration only**. User-facing production labels should therefore use **CONC** or **CONCENTRATION**, not generic **STRUCT**.

## Basis and market-structure research

- **Basis level** and **basis dispersion** are research-only channels.
- They are not part of the production CDRR score.
- The `50/25/25` structure candidate means 50% OI concentration, 25% confirmed basis magnitude, and 25% confirmed basis dispersion.
- Always label this candidate **RESEARCH ONLY** until longitudinal validation supports promotion.
