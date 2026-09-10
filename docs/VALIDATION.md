# Validation

## Objective

The purpose of validation is to answer:

> **Does a higher current CDRR ranking correspond to greater subsequent realised market stress?**

This is intentionally different from asking whether CDRR predicts positive or negative returns.

---

## 1. Volatility-model validation

The conditional variance subsystem was developed using walk-forward comparison against an EWMA benchmark.

The primary loss is QLIKE, which is appropriate for variance-forecast comparison.

During development:

```text
Tracked assets                         20
Assets with lower mean QLIKE (PL)     17 / 20
HAC-significant PL wins                5
HAC-significant EWMA wins              0
```

Here `PL` refers to the Student-\(t\) power-law conditional variance model.

These results justify using the power-law model as the primary conditional volatility model while retaining EWMA as a secondary benchmark/spread diagnostic.

They do **not** imply that the model will outperform on every future period.

---

## 2. Data-quality validation

Several production safeguards are themselves validation mechanisms.

### Common-universe OI

Open-interest changes are calculated only over contracts present and valid at both timestamps.

Recent development checks showed very high 1h overlap across the tracked universe, including approximately:

```text
minimum overlap     ~0.99
median overlap      ~1.00
```

The exact value is expected to vary through time and remains available in processed diagnostics.

### Source synchronisation

State readiness requires the core source timestamps to be within the configured synchronisation tolerance.

This prevents a "current" state from mixing materially different market moments.

### Liquidation calibration

The current liquidation implementation was explicitly checked against repeated-zero/tied observations after replacing a naive `<= current` percentile with empirical midranks.

Exchange liquidation shares are also renormalised internally before HHI is calculated.

---

## 3. Market-structure research

The production fifth factor currently uses only OI concentration.

A separate research layer compares it with:

### Equal three-way formulation

\[
S_A
=
\frac{
C_{\text{OI}}
+
B_{\text{magnitude}}
+
B_{\text{dispersion}}
}{3}.
\]

### Concentration-led formulation

\[
S_B
=
0.50C_{\text{OI}}
+
0.25B_{\text{magnitude}}
+
0.25B_{\text{dispersion}}.
\]

Initial cross-sectional snapshots suggested the 50/25/25 candidate alters the production ranking less aggressively while adding information beyond OI concentration.

However, basis calibration was still in warm-up at the time of repository completion. Therefore:

```text
Production factor:
    OI concentration only

50/25/25 formulation:
    RESEARCH ONLY
```

`data/research/market_structure/history.parquet` is designed to accumulate the evidence needed for a later decision.

---

## 4. Forward-stress validation

The central validation framework is implemented in:

```text
backend/risk_radar/forward_validation.py
scripts/validate_forward_stress.py
```

The clean validation epoch is:

```text
2026-09-10 17:22 UTC
2026-09-10 18:22 BST
```

This epoch deliberately begins after the current liquidation calibration, basis research plumbing and production risk pipeline were operating together.

---

## 5. Forward targets

For each current risk snapshot \(t\), CDRR is evaluated against future outcomes over:

```text
1 hour
4 hours
24 hours
```

### A. Realised path volatility

\[
RV_{t,t+h}
=
100
\sqrt{
\sum_{j=t+1}^{t+h}
\left(
\ln
\frac{P_j}{P_{j-1}}
\right)^2
}.
\]

This captures realised path variability rather than endpoint direction.

### B. Maximum absolute move

\[
M_{t,t+h}
=
100
\max_{s\in[t,t+h]}
\left|
\frac{P_s}{P_t}-1
\right|.
\]

### C. Downside excursion

\[
DD_{t,t+h}
=
100
\max
\left(
0,
-\min_{s\in[t,t+h]}
\left(
\frac{P_s}{P_t}-1
\right)
\right).
\]

Downside excursion is retained as one stress diagnostic, but CDRR itself remains direction-neutral.

### D. Maximum future liquidation/OI stress

\[
L_{t,t+h}
=
\max_{s\in(t,t+h]}
\left(
\frac{
\text{1h liquidations}_s
}{
OI_s
}
\right).
\]

The maximum is used instead of summing observations because the source feature is itself a rolling one-hour quantity; summing neighbouring observations would double-count overlapping liquidation windows.

---

## 6. Horizon maturity

A target is not evaluated until the underlying source series has genuinely progressed to or beyond:

\[
t+h.
\]

Endpoint tolerance may handle irregular sampling around an already completed horizon, but it is not allowed to make a still-future horizon appear mature.

This avoids look-ahead / partial-window contamination.

---

## 7. Cross-sectional information coefficient

For every risk snapshot and horizon:

\[
IC_t^{(h)}
=
\rho_S
\left(
R_{i,t},
Y_{i,t\rightarrow t+h}
\right),
\]

where:

- \(R_{i,t}\) is the current CDRR score;
- \(Y_{i,t\rightarrow t+h}\) is a realised future-stress target;
- \(\rho_S\) is Spearman rank correlation across the tracked assets.

Interpretation:

```text
IC > 0
    Higher current CDRR ranks tended to experience
    greater subsequent stress.

IC ~ 0
    Little cross-sectional ranking relationship.

IC < 0
    Higher CDRR ranks tended to experience less
    subsequent stress in that snapshot.
```

IC is calculated **per timestamp**, rather than relying only on a single pooled correlation.

---

## 8. Risk-quintile test

Each 20-asset snapshot is split into five cross-sectional CDRR buckets:

```text
Q1 = lowest-risk assets
Q5 = highest-risk assets
```

For each forward target the validator records:

\[
E[Y|Q_5]-E[Y|Q_1]
\]

and, when defined,

\[
\frac{E[Y|Q_5]}{E[Y|Q_1]}.
\]

It also calculates the Spearman monotonicity of average forward stress from Q1 through Q5.

A useful risk score should eventually show a reasonably monotonic increase in realised stress as the current CDRR quintile rises.

---

## 9. Dependence and statistical inference

The validator intentionally warns against naive significance claims.

At a fast collection cadence, neighbouring observations overlap heavily.

For example, consecutive 4-hour targets share most of the same future path. Therefore rows are:

- serially dependent;
- cross-sectionally dependent;
- overlapping in their outcome windows.

Raw row count must not be interpreted as independent sample size.

Future statistical work should use approaches such as:

- non-overlapping evaluation timestamps;
- HAC/Newey-West inference;
- block bootstrap;
- day-level or regime-level aggregation.

---

## 10. Current status

At the point this documentation was prepared, the clean forward-validation sample had only just started accumulating.

Therefore the project makes **no claim of statistically established forward predictive performance yet**.

This is intentional.

The repository is already capable of collecting the evidence automatically, and the hackathon release distinguishes:

- implemented methodology;
- development diagnostics;
- provisional production assumptions;
- research hypotheses still awaiting sufficient history.

Recommended checkpoints:

```text
24 hours    pipeline / calibration sanity
72 hours    early rank persistence and turnover
7 days      first useful longitudinal comparison
14-30 days  stronger regime and significance analysis
```

The collector should ideally continue running beyond the hackathon submission.

---

## 11. Validation outputs

The validation script writes:

```text
data/research/forward_validation/
├── samples.parquet
├── snapshot_ic.parquet
├── metrics.parquet
├── quintiles.parquet
├── quintile_summary.parquet
└── status.parquet
```

These files are excluded from Git because they are generated research data.

---

## 12. What would invalidate the model?

The project should not promote the provisional score simply because it looks plausible.

Evidence against the model would include:

- persistently non-positive forward-stress IC;
- Q5 failing to exhibit more subsequent stress than Q1;
- severe rank instability unrelated to real market changes;
- one component dominating the score mechanically;
- high redundancy between supposedly distinct factors;
- material dependence on a single venue or unreliable data field.

If these occur, the correct action is to modify or reject the relevant factor rather than reinterpret the metric after the fact.
