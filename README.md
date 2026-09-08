# Crypto Derivatives Risk Radar

A quantitative cryptocurrency derivatives risk-monitoring platform built for the
2026 CoinMarketCap Build with CMC API Hackathon.

## Objective

Identify markets where volatility, leverage, positioning, liquidation activity,
and cross-exchange dislocations are combining to create elevated derivatives risk.

## Core Risk Components

1. Conditional volatility
2. Leverage / open interest
3. Funding and positioning crowding
4. Liquidation pressure
5. Cross-exchange fragmentation

## Planned Architecture

CoinMarketCap API
        |
        v
Data ingestion
        |
        v
Historical database
        |
        +--> Volatility forecasting
        |
        +--> Derivatives feature engine
        |
        v
Risk scoring engine
        |
        v
FastAPI
        |
        v
Next.js dashboard

## Status

Initial development.
