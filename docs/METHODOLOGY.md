# Methodology

## 1. Objective

Crypto Derivatives Risk Radar is designed to rank **derivatives-market stress**, not forecast the sign of future returns.

The core modelling objective is therefore:

$$ \text{estimate relative stress magnitude} \neq \text{predict price direction}. $$

Directional information is retained in market-state descriptors and supporting evidence, but the scalar CDRR score is direction-neutral.

---

## 2. Normalisation philosophy

The raw inputs have incompatible units:

- volatility;
- percentage OI changes;
- funding rates;
- dollar liquidations;
- concentration statistics.

Where possible, CDRR maps them into interpretable \([0,1]\) ranks or calibrated empirical percentiles.

Two comparison axes are used:

1. **own-history calibration** — is the current observation unusual for this asset?
2. **cross-sectional calibration** — is the current observation unusual compared with the other tracked assets?

This is particularly important in crypto because assets differ drastically in size, venue mix and baseline volatility.

---

## 3. Volatility subsystem

### Realised volatility

CDRR calculates annualised realised volatility over multiple horizons including 1h, 4h and 24h.

It also calculates a short-horizon volatility-expansion ratio such as:

$$ X_t = \frac{\sigma^{\text{realised}}_{1h,t}} {\sigma^{\text{realised}}_{24h,t}}. $$

The cross-sectional rank of this ratio identifies assets whose short-horizon volatility is currently expanding relative to their own recent 24h environment.

### Conditional variance model

The primary conditional variance model is a symmetric Student-\(t\) power-law memory model:

$$ \sigma_{t+1}^{2} = c + \beta \sum_{k=0}^{K-1} \frac{r_{t-k}^{2}} {(k+1)^{\alpha}}, $$

with:

$$ K=250. $$

The power-law kernel allows volatility memory to decay more flexibly than a single exponential half-life.

The implementation generates a 12-step forecast on 5-minute data to obtain a next-one-hour conditional variance:

$$ \widehat V_{t,t+1h} = \sum_{j=1}^{12} \widehat{\sigma}_{t+j|t}^{2}. $$

For presentation, this may be annualised as:

$$ \widehat{\sigma}_{\text{ann}} = \sqrt{ \widehat V_{t,t+1h} \times 8760 }. $$

This is a conditional volatility estimate, **not an expected price move**.

### Benchmarking

EWMA is retained as a secondary benchmark/model-spread diagnostic.

During development, four-fold walk-forward comparison found the power-law model had lower mean QLIKE than EWMA for 17 of the 20 tracked assets. HAC-adjusted comparisons produced five statistically significant power-law wins and no significant EWMA wins in that development sample.

These are model-development results rather than guarantees of future performance.

---

## 4. Derivatives data quality

Raw derivative-market records are not accepted blindly.

Processing includes:

- freshness checks;
- symbol consistency;
- contract deduplication;
- price and volume outlier handling;
- OI consistency checks;
- separation of field-level validity.

A bad price or volume field does not automatically invalidate an otherwise usable OI, funding or basis observation.

### Common-universe open interest

Naively comparing aggregate OI through time is vulnerable to changing venue/contract coverage.

CDRR therefore defines:

$$ I_{t,h} = S_t \cap S_{t-h}, $$

where \(S_t\) is the set of valid derivative contracts at time \(t\).

The common-universe change is:

$$ \Delta OI_{t,h}^{\text{common}} = \frac{ \sum_{m\in I_{t,h}} OI_{m,t} }{ \sum_{m\in I_{t,h}} OI_{m,t-h} } -1. $$

Contract identity is based on the asset, market and exchange identifiers.

Overlap diagnostics are retained so an OI change is not treated as high-quality when too little of the current/reference market universe overlaps.

The leverage component uses the **magnitude** of validated 1h common-universe OI change; its sign is handled by the state engine instead.

---

## 5. Funding calibration

Funding is not annualised in CDRR.

For each asset, robust venue aggregation produces a median funding rate plus dispersion information.

Funding calibration separates:

- signed position;
- absolute extremeness;
- long/short tail direction.

### Cross-sectional stage

The tracked universe is ranked by funding magnitude.

Directional tail probability is derived consistently with the sign of funding, preventing tiny negative values from being incorrectly treated as strongly crowded solely because their signed rank is extreme.

### Historical stage

Historical calibration uses **strictly prior observations** only.

Empirical percentiles use midrank tie handling:

$$ P(x_t) = \frac{\left|\{j \mid x_j < x_t\}\right| + \tfrac{1}{2}\left|\{j \mid x_j = x_t\}\right|}{N}. $$

A conservative confirmed historical signal requires both directional and magnitude evidence.

The operational history gate uses:

```text
history window          7 days
minimum history span    24 hours
minimum observations    120
minimum distinct values 8
```

Before this gate is ready, the production risk engine explicitly labels the funding source as cross-sectional warm-up.

---

## 6. Basis calibration

Basis is decomposed into two conceptually different signals.

### Central basis magnitude

$$ B_i = \left| \operatorname{median} (\text{index basis}_{i,\text{venues}}) \right|. $$

This measures how far the central derivative market is trading from the reference index, irrespective of premium/discount direction.

### Cross-venue dispersion

$$ D_i^{\text{basis}} = IQR (\text{index basis}_{i,\text{venues}}). $$

This measures fragmentation/dislocation across venues.

Each channel receives:

- a cross-sectional percentile;
- a prior-only historical empirical percentile;
- a conservative confirmed percentile once the history gate is ready.

Basis direction (`PREMIUM`, `DISCOUNT`, `FLAT`) remains descriptive and is not itself a risk magnitude.

### Production status

Basis is **not currently included in the production CDRR score**.

A research candidate is being evaluated:

$$ S_{\text{structure}}^{*} = 0.50C_{\text{OI}} + 0.25B_{\text{magnitude}} + 0.25B_{\text{dispersion}}. $$

It remains research-only until there is sufficient longitudinal evidence.

---

## 7. Liquidation calibration

Liquidations contain three separate concepts:

1. total activity;
2. materiality relative to derivatives exposure;
3. direction.

They are deliberately not collapsed blindly.

### Prior-only activity percentile

For each asset, the current liquidation observation is compared with a strict prior-only 24h baseline.

Midrank ties are used:

$$ P_t = \frac{ N_{<x_t} + \frac12N_{=x_t} }{ N }. $$

This matters because liquidation datasets often contain repeated zeros or repeated provider values.

### OI normalisation

Current activity is normalised by current tracked OI:

$$ L^{OI}_{i,t} = \frac{ \text{liquidations}_{i,t} }{ OI_{i,t} }. $$

The cross-sectional percentile of this quantity captures whether liquidations are economically material relative to the outstanding derivatives exposure.

### Conservative confirmation

The production liquidation factor is:

$$ Q_i = \min \left( P^{\text{temporal}}_{\text{liq},i}, P^{\text{cross}}_{\text{liq/OI},i} \right). $$

This prevents a large dollar liquidation print in a very large market from automatically dominating the ranking.

### Direction

Long-liquidation share is retained separately.

Directional imbalance can be represented as:

$$ I_{\text{dir}} = \left|2s_{\text{long}}-1\right|. $$

A perfectly one-sided but tiny liquidation event is therefore not automatically treated as severe stress.

### Exchange concentration

Exchange liquidation concentration is calculated from normalised exchange liquidation totals, ensuring the shares sum to one before computing:

$$ HHI = \sum_j s_j^2. $$

Provider-reported global shares are retained as diagnostics rather than assumed to form an exact probability distribution.

---

## 8. Cross-sectional features

The tracked universe is mapped to percentile ranks in \([0,1]\).

Ties receive average ranks.

Current features include:

$$ \begin{aligned} &\text{OI-change magnitude percentile}\\ &\text{liquidations/OI percentile}\\ &\text{funding magnitude percentile}\\ &\text{basis magnitude percentile}\\ &\text{OI concentration percentile}\\ &\text{volatility expansion percentile}\\ &\text{absolute price-move percentile}. \end{aligned} $$

These are descriptive features, not all production risk components.

---

## 9. Market states

The state engine combines price, common-universe OI, funding, liquidations and volatility context.

Representative logic includes regimes such as:

- falling price + falling OI -> `DELEVERAGING`;
- rising price + rising OI -> `OI BUILD INTO RALLY`;
- falling price + rising OI -> `OI BUILD INTO SELLOFF`;
- concentrated long liquidations -> `LONG LIQUIDATION STRESS`;
- concentrated short liquidations -> `SHORT LIQUIDATION STRESS`.

States are not intended to predict the next return. They describe the current derivatives regime.

State readiness requires synchronised source timestamps and validated OI inputs.

---

## 10. Production CDRR score

The current production version is:

```text
provisional_v1_equal_weight
```

with five components.

### Volatility

$$ V_i = \operatorname{mean\_available} \left( P^{\text{history}}_{\sigma,24h}, P^{\text{cross}}_{\text{vol expansion}} \right). $$

### Leverage

$$ L_i = P^{\text{cross}} \left( \left| \Delta OI^{\text{common}}_{1h} \right| \right). $$

### Funding

$$ C_i = \begin{cases} P^{\text{confirmed historical+cross}}_{\text{funding}}, & \text{history ready}\\ P^{\text{confirmed cross}}_{\text{funding}}, & \text{warm-up}. \end{cases} $$

The source is stored explicitly.

### Liquidations

$$ Q_i = P^{\text{confirmed}}_{\text{liquidations},1h}. $$

### Market structure

$$ D_i = P^{\text{cross}}_{HHI(OI)}. $$

### Aggregate

$$ \boxed{ R_i^{(0)} = 100 \left( 0.20V_i + 0.20L_i + 0.20C_i + 0.20Q_i + 0.20D_i \right) } $$

A score is emitted only when all five components and the underlying state are ready.

---

## 11. Why equal weights?

Equal weights are a deliberate provisional choice.

The project does not yet have enough longitudinal data to justify optimising weights without substantial overfitting risk.

The current design therefore prioritises:

- transparency;
- factor diversity;
- explainability;
- future empirical validation.

Weight optimisation, absolute risk bands and production inclusion of basis are deferred until the historical sample is sufficiently mature.

---

## 12. Missing data

CDRR avoids treating missing data as benign data.

A missing factor can prevent a production score from being marked ready. Warm-up states are exposed explicitly rather than silently replaced with arbitrary constants.

This is important for a live market-monitoring application because feed quality is part of model quality.

---

## 13. Scope

The methodology is intended as a **risk-monitoring and research system**.

It is not:

- investment advice;
- a trading signal guaranteeing positive expected returns;
- a liquidation-price engine;
- a portfolio optimiser;
- a directional forecasting model.
