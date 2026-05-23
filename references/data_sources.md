# 📡 Guia de Fontes de Dados — QuantResearch Agent

> **Última atualização:** Maio 2026  
> **Formato:** Fonte · Cobertura · Planos · Preço · Tier Gratuito · Cupons/Descontos

---

## 🏛️ MERCADOS DE CAPITAIS (Ações, ETFs, Futuros, Forex)

### 1. yfinance (Yahoo Finance) — ⭐ Principal Fonte Gratuita
| Item | Detalhe |
|------|---------|
| **URL** | https://pypi.org/project/yfinance/ |
| **Cobertura** | 70.000+ ativos: ações globais, ETFs, futuros, forex, índices |
| **Granularidade** | 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo |
| **Histórico** | Até 1m: 7 dias · Até 1h: 730 dias · Diário: 1950+ |
| **Preço** | **100% GRATUITO** |
| **Limitações** | Dados de 1min limitados a 7 dias; sem orderbook; sem tick; dados podem ter gaps |
| **Uso** | `pip install yfinance` · sem API key necessária |
| **Ideal para** | Research de posição, backtests diários, screening de ativos |

**⚠️ Atenção:** yfinance é scraping não oficial. Para uso em produção, prefira fontes com API oficial.

---

### 2. Polygon.io — ⭐ Melhor Custo-Benefício Pro
| Item | Detalhe |
|------|---------|
| **URL** | https://polygon.io |
| **Cobertura** | Ações US, opções, forex, criptoativos, índices |
| **Granularidade** | Tick, segundo, minuto, hora, dia |
| **Histórico** | 10+ anos de dados históricos (planos pagos) |
| **Preço Gratuito** | EOD apenas, 5 req/min, sem WebSocket |
| **Preço Pago** | Starter: $29/mo · Stocks Developer: $79/mo · Stocks Advanced: $199/mo |
| **Diferencial** | API REST + WebSocket + WebSocket para streaming; dados oficiais SIP |
| **Ideal para** | Intraday e swing trading, opções, backtests de alta qualidade |

**💰 Cupons e Descontos disponíveis:**
- **Estudantes:** 20% off via [StudentBeans](https://www.studentbeans.com/student-discount/us/polygon-io)
- **Cupom genérico:** Até 50% off em promoções — verifique https://couponsum.com/polygon-io
- **Tip:** O plano Starter ($29/mo) já inclui dados históricos de 2 anos com 1min de granularidade

---

### 3. Alpaca Markets — ⭐ Melhor para Paper Trading Gratuito
| Item | Detalhe |
|------|---------|
| **URL** | https://alpaca.markets/data |
| **Cobertura** | Ações US (NYSE, NASDAQ, AMEX), ETFs, criptoativos |
| **Granularidade** | 1min, 5min, 15min, 1h, 1d |
| **Histórico** | 10 anos de dados de 1min — **100% GRATUITO** para contas abertas |
| **Preço Gratuito** | Conta gratuita (paper ou live) inclui dados históricos via IEX |
| **Preço Pago** | Unlimited Plan: $49/mo (SIP tape completo, sem limites) |
| **Diferencial** | Conta free já tem 10 anos de dados de 1min; integração com brokerage nativa |
| **Ideal para** | Backtests de swing intraday, daytrade research, integração com execução |

**💡 Dica:** Abra uma conta gratuita em alpaca.markets — sem necessidade de depósito para obter acesso aos dados históricos.

---

### 4. Tiingo — ⭐ Melhor para Research de Longo Prazo
| Item | Detalhe |
|------|---------|
| **URL** | https://www.tiingo.com |
| **Cobertura** | 65.000+ US stocks, ETFs, fundos mútuos, ADRs; ações chinesas; crypto |
| **Granularidade** | EOD (gratuito) e intraday 1min (pago) |
| **Histórico** | 30+ anos histórico; até 50+ anos para alguns ativos |
| **Preço Gratuito** | Tier gratuito: 50 símbolos/hora, EOD data |
| **Preço Pago** | Individual: $10/mo (Basic), $30/mo (Plus), $50/mo (Advanced) |
| **Diferencial** | Melhor custo para pesquisa macro de longo prazo; dados ajustados por splits/dividendos |
| **Ideal para** | Modelos ML (backtests 10+ anos), research macro, análise fundamentalista |

---

### 5. Databento — ⭐ Melhor para Tick Data e Futuros
| Item | Detalhe |
|------|---------|
| **URL** | https://databento.com |
| **Cobertura** | 70+ venues globais; CME/CBOT/NYMEX/COMEX; 15 bolsas US de ações |
| **Granularidade** | Tick (MBO), top-of-book (MBP-1), depth-10 (MBP-10), segundos, minutos |
| **Histórico** | 16 PB de dados históricos tick com precisão de nanosegundos |
| **Preço Gratuito** | **$125 em créditos grátis** ao criar conta |
| **Preço Pago** | Standard CME: $179/mo · Equities US: $199/mo · Pay-as-you-go histórico |
| **Diferencial** | Nanosegundo timestamps; orderbook completo; dados tick de alta qualidade |
| **Ideal para** | Daytrade research, HFT, backtests com tick data, futuros CME |

**💰 Desconto:**
- **Free credits:** $125 de créditos ao registrar-se — suficiente para testes extensivos
- Dados históricos são pay-as-you-go; modelo de custo antes de se comprometer

---

### 6. Interactive Brokers — Melhor para Dados + Execução
| Item | Detalhe |
|------|---------|
| **URL** | https://www.interactivebrokers.com |
| **Cobertura** | Global: ações, futuros, opções, forex, bonds, cripto |
| **Granularidade** | Tick, 1s, 5s, 15s, 1min, 5min, 15min, 1h, 1d |
| **Histórico** | 15+ anos para a maioria dos instrumentos |
| **Preço** | Dados gratuitos para clientes com conta ativa; data feed especializado: $10-15/mo |
| **Acesso via Python** | `ib_insync` (pip install ib_insync) via TWS ou IB Gateway |
| **Ideal para** | Live trading + backtesting integrado, futuros, opções, forex |

---

### 7. FRED (Federal Reserve) — ⭐ Melhor para Dados Macro
| Item | Detalhe |
|------|---------|
| **URL** | https://fred.stlouisfed.org |
| **Cobertura** | 840.000+ séries: GDP, CPI, taxas de juros, desemprego, yields, spreads |
| **Granularidade** | Diário, semanal, mensal, trimestral, anual |
| **Histórico** | Décadas a séculos de dados macroeconômicos |
| **Preço** | **100% GRATUITO** — API key gratuita em fred.stlouisfed.org/api_key |
| **Uso** | `pip install fredapi` · `FRED_API_KEY` no `.env` |
| **Ideal para** | Modelos macro, análise de regimes com VIX/DXY/yields, research de longo prazo |

---

## ₿ MERCADOS DE CRIPTOATIVOS

### 8. CCXT + Binance — ⭐ Principal Fonte Cripto Gratuita
| Item | Detalhe |
|------|---------|
| **URL** | https://github.com/ccxt/ccxt · https://binance.com |
| **Cobertura** | 100+ exchanges; 30.000+ pares de trading |
| **Granularidade** | 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M |
| **Histórico** | Binance: desde 2017 · Exchange-específico |
| **Preço** | **GRATUITO** para dados públicos sem autenticação |
| **Com API Key** | Gratuito (higher rate limits); trading requer conta Binance |
| **Ideal para** | Spot trading, perpetuals, funding rates, cripto OHLCV |

**💡 Exchanges com bons dados históricos via CCXT:**
- Binance (maior volume, melhor histórico)
- OKX (alternativa robusta)
- Bybit (perpetuals, 2019+)
- Kraken (US-friendly, 2014+)

---

### 9. CoinGecko API — ⭐ Melhor Cobertura de Tokens/DeFi
| Item | Detalhe |
|------|---------|
| **URL** | https://www.coingecko.com/en/api |
| **Cobertura** | 17.000+ tokens; preços, market cap, volume, DeFi, NFTs |
| **Granularidade** | Horária (curto prazo) e diária (histórico longo) |
| **Histórico** | Completo desde listing de cada token |
| **Preço Gratuito** | Demo API: 30 req/min, sem autenticação |
| **Preço Pago** | Basic: $35/mo · Analyst: $129/mo (500k calls) · Pro: $499/mo · Enterprise: $999/mo+ |
| **Ideal para** | Screening de tokens, DeFi research, dados de on-chain price |

**💰 Desconto:**
- **15% OFF** em qualquer plano: https://www.coingecko.com/en/candy/rewards/coingecko-api-plans-15-for-any-coingecko-api-subscription
- Demo API gratuita suficiente para pesquisa

---

### 10. CoinMarketCap API — Alternativa ao CoinGecko
| Item | Detalhe |
|------|---------|
| **URL** | https://coinmarketcap.com/api |
| **Cobertura** | 20.000+ criptoativos; dados de exchanges, DeFi, NFT |
| **Preço Gratuito** | Basic: 10.000 calls/mês gratuito |
| **Preço Pago** | Hobbyist: $29/mo · Startup: $79/mo · Standard: $299/mo |
| **Ideal para** | Market cap research, dominância, dados de exchanges |

---

### 11. Glassnode — On-Chain Analytics Premium
| Item | Detalhe |
|------|---------|
| **URL** | https://glassnode.com |
| **Cobertura** | BTC, ETH, on-chain metrics: endereços ativos, flows, MVRV, SOPR, LTH/STH |
| **Preço Gratuito** | ❌ Sem tier gratuito para API |
| **Preço** | Studio Basic: $39/mo (UI apenas) · Advanced: $99/mo · Professional: $799/mo · API add-on: contato comercial (≈$200+/mo adicional) |
| **Ideal para** | Research avançado de BTC/ETH, análise de ciclos, smart money tracking |

**💡 Alternativa gratuita:** Dune Analytics (https://dune.com) oferece queries on-chain gratuitas para ETH e outras chains EVM.

---

### 12. Kaiko — Dados Institucionais de Cripto
| Item | Detalhe |
|------|---------|
| **URL** | https://www.kaiko.com |
| **Cobertura** | 4.000+ CEX coins; 30.000+ DEX tokens; 100+ exchanges; Level 2 orderbook |
| **Preço** | ❌ Enterprise apenas — planos a partir de ~$2.000+/mo; requer contato comercial |
| **Ideal para** | Fundos quant, pesquisa institucional, backtest com orderbook completo |
| **Alternativa** | Para uso individual, prefira Databento (cripto) ou CoinGecko (preços) |

---

## 🎲 MERCADOS DE PREDIÇÃO

### 13. Kalshi — ⭐ Principal Mercado de Predição US (CFTC Regulado)
| Item | Detalhe |
|------|---------|
| **URL** | https://kalshi.com · https://trading-api.kalshi.com/trade-api/v2 |
| **Documentação** | https://docs.kalshi.com |
| **Cobertura** | 1.000+ mercados: eleições, clima, Fed, econômicos, esportes |
| **Granularidade** | Por trade (tick-level), histórico de preços por série |
| **Histórico** | Completo desde 2021; todos os mercados fechados disponíveis |
| **Preço** | **100% GRATUITO** para dados públicos (sem autenticação) |
| **Autenticação** | API key necessária para trading e rate limits maiores |
| **Endpoints chave** | `GET /markets/{ticker}/history` · `GET /series` · `GET /markets` |
| **Ideal para** | Research de probabilidades implícitas, correlação com ativos financeiros |

**Endpoints de dados históricos:**
```python
# Histórico de preços de um contrato
GET https://trading-api.kalshi.com/trade-api/v2/markets/{ticker}/history

# Listar todos os mercados (incluindo fechados)
GET https://trading-api.kalshi.com/trade-api/v2/markets?status=closed&limit=200

# Séries (grupos de mercados relacionados)
GET https://trading-api.kalshi.com/trade-api/v2/series
```

**Fontes alternativas/complementares:**
- **Lychee Data** (https://lycheedata.com/guides/kalshi-historical-data): Ferramentas pagas para download em bulk
- **PredictionData.dev** (https://predictiondata.dev): API agregada para Kalshi + Polymarket (~$50-200/mo)
- **FinFeedAPI** (https://www.finfeedapi.com/products/prediction-markets-api): API de dados de predição com planos acessíveis

---

### 14. Polymarket — Maior Mercado de Predição Descentralizado
| Item | Detalhe |
|------|---------|
| **URL** | https://polymarket.com · https://docs.polymarket.com |
| **Rede** | Polygon (MATIC) — descentralizado |
| **Cobertura** | 1.000+ mercados: política, cripto, esportes, economia |
| **Preço** | **100% GRATUITO** — sem autenticação necessária para leitura |
| **Ideal para** | Research descentralizado, correlação com cripto, eventos políticos globais |

**APIs disponíveis (todas gratuitas):**
| API | URL Base | Uso |
|-----|----------|-----|
| Gamma API | `https://gamma-api.polymarket.com` | Descoberta de mercados, eventos, metadados |
| CLOB API | `https://clob.polymarket.com` | Preços, orderbook, histórico de séries temporais |
| Data API | `https://data-api.polymarket.com` | Posições, trades, leaderboard |
| WebSocket | `wss://ws-subscriptions-clob.polymarket.com` | Streaming em tempo real |

**Endpoints úteis:**
```python
# Histórico de preços por condição (CLOB)
GET https://clob.polymarket.com/prices-history?conditionId={id}&resolution=1min

# Listar todos os mercados (Gamma)
GET https://gamma-api.polymarket.com/markets?limit=100&active=false

# Orderbook em tempo real
GET https://clob.polymarket.com/book?token_id={token_id}
```

---

## 📊 DADOS ALTERNATIVOS E ESPECIALIZADOS

### 15. Quandl / Nasdaq Data Link — Dados Alternativos
| Item | Detalhe |
|------|---------|
| **URL** | https://data.nasdaq.com |
| **Cobertura** | Futuros CFTC, dados macro, fundamentos, commodities, imobiliário |
| **Preço Gratuito** | Muitas bases públicas gratuitas (CFTC COT, FRED mirror, etc.) |
| **Preço Pago** | Por dataset; bundles a partir de $99/mo |
| **Ideal para** | COT data, commodities, alternative data research |

---

### 16. Dune Analytics — On-Chain Gratuito
| Item | Detalhe |
|------|---------|
| **URL** | https://dune.com |
| **Cobertura** | Ethereum, Polygon, Arbitrum, Optimism, BSC e + |
| **Preço Gratuito** | Queries gratuitas com limite de execuções |
| **Preço Pago** | Free: 0 · Basic: $349/mo · Plus: $649/mo · Enterprise: custom |
| **Ideal para** | DEX analytics, DeFi TVL, on-chain flows, whale tracking |

---

### 17. Alternative.me — Fear & Greed Index (Gratuito)
| Item | Detalhe |
|------|---------|
| **URL** | https://alternative.me/crypto/fear-and-greed-index/ |
| **API** | `https://api.alternative.me/fng/?limit=365` |
| **Preço** | **100% GRATUITO** |
| **Ideal para** | Feature de sentimento para modelos ML; regime de mercado cripto |

---

## 📋 TABELA RESUMO: FONTES POR CASO DE USO

| Caso de Uso | Fonte Gratuita | Fonte Paga Recomendada | Custo Estimado |
|---|---|---|---|
| **Backtesting diário ações US** | yfinance / Alpaca (free) | Tiingo ($10/mo) | $0-10/mo |
| **Backtesting intraday ações** | Alpaca (free, 10 anos 1min) | Polygon.io ($79/mo) | $0-79/mo |
| **Tick data / HFT research** | — | Databento ($125 créditos grátis → $179/mo) | $125 free → $179/mo |
| **Futuros CME** | yfinance (limitado) | Databento CME ($179/mo) | $179/mo |
| **Forex** | yfinance (EURUSD=X) | Interactive Brokers (conta) | $0 com conta IB |
| **Dados macro** | FRED (gratuito) | Quandl premium | $0+ |
| **Cripto OHLCV** | CCXT/Binance (gratuito) | — | $0 |
| **Cripto screening/tokens** | CoinGecko Demo | CoinGecko Basic ($35/mo, -15%) | $0-30/mo |
| **On-chain cripto** | Dune Analytics | Glassnode Pro ($799/mo) | $0+ |
| **Kalshi prediction markets** | Kalshi API (gratuito) | PredictionData.dev ($50-200/mo) | $0+ |
| **Polymarket prediction markets** | Polymarket Gamma+CLOB (gratuito) | — | $0 |
| **Dados fundamentalistas** | yfinance (limitado) | Tiingo Plus ($30/mo) | $30/mo |

---

## 🔑 CONFIGURAÇÃO DE API KEYS

Adicione ao arquivo `.env` na raiz do projeto:

```bash
# === AÇÕES E FUTUROS ===
# Alpaca (criar conta grátis em alpaca.markets)
ALPACA_API_KEY=
ALPACA_SECRET_KEY=

# Polygon.io (criar conta em polygon.io)
POLYGON_API_KEY=

# Tiingo (criar conta em tiingo.com)
TIINGO_API_KEY=

# Databento (criar conta em databento.com — $125 créditos grátis)
DATABENTO_API_KEY=

# === MACRO ===
# FRED (gratuito em fred.stlouisfed.org/api_key)
FRED_API_KEY=

# === CRIPTO ===
# Binance (criar conta em binance.com)
BINANCE_API_KEY=
BINANCE_SECRET=

# CoinGecko (criar conta em coingecko.com/en/api — tier gratuito disponível)
COINGECKO_API_KEY=

# === MERCADOS DE PREDIÇÃO ===
# Kalshi (criar conta em kalshi.com — gratuito)
KALSHI_API_KEY=
KALSHI_EMAIL=
KALSHI_PASSWORD=

# Polymarket (sem autenticação para leitura — opcional para trading)
POLYMARKET_API_KEY=
POLYMARKET_PRIVATE_KEY=
```

---

## 💰 RESUMO DE DESCONTOS E CUPONS ATIVOS (Maio 2026)

| Provedor | Desconto | Link / Como Usar |
|---|---|---|
| **Polygon.io** | 20% para estudantes | https://www.studentbeans.com/student-discount/us/polygon-io |
| **Polygon.io** | Até 50% off promoções | https://couponsum.com/polygon-io |
| **Databento** | $125 créditos grátis | Automático ao criar conta em databento.com |
| **CoinGecko API** | 15% off qualquer plano | https://www.coingecko.com/en/candy/rewards/coingecko-api-plans-15-for-any-coingecko-api-subscription |
| **CoinDesk (ex-CryptoCompare)** | 250.000 calls free trial | Criar conta em developers.coindesk.com |
| **Alpaca** | Dados históricos 10 anos GRÁTIS | Abrir conta gratuita em alpaca.markets |
| **Kalshi** | API pública gratuita | Registrar em kalshi.com (sem custo para leitura) |
| **Polymarket** | API totalmente gratuita | Sem registro necessário para leitura |
| **FRED** | 100% gratuito | https://fred.stlouisfed.org/api_key |

---

## 📚 REFERÊNCIAS

- [Databento vs Polygon 2026 — AI Fin Hub](https://aifinhub.io/articles/market-data-apis-compared-2026/)
- [Alpaca Market Data API](https://alpaca.markets/data)
- [CoinGecko API Pricing](https://www.coingecko.com/en/api/pricing)
- [Kalshi Quick Start](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Polymarket API Guide 2026](https://pm.wiki/learn/polymarket-api)
- [Databento Pricing](https://databento.com/pricing)
- [FRED API Documentation](https://fred.stlouisfed.org/docs/api/fred/)
- [Best Prediction Market APIs 2026](https://www.predictionhunt.com/blog/best-api-for-prediction-markets)
- [Polygon.io Coupons](https://couponsum.com/polygon-io)
- [Tiingo Review 2026](https://www.findmymoat.com/tools/tiingo)
