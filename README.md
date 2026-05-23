# 🔬 QuantResearch Agent

Agente de pesquisa quantitativa para mercados financeiros, criptoativos e mercados de predição — powered by Claude (Anthropic API).

## Estrutura

```
quant-research-agent/
├── run_agent.py          ← Entry point principal (CLI + interativo)
├── SKILL.md              ← Definição do agente (Cowork Skill)
├── requirements.txt      ← Dependências Python
├── .env.example          ← Template de variáveis de ambiente
├── Makefile              ← Atalhos de execução
├── .vscode/
│   └── launch.json       ← Configurações de run/debug para VS Code
├── references/
│   └── data_sources.md   ← Guia de fontes de dados
├── scripts/
│   ├── data_fetcher.py   ← Coleta de dados (Yahoo, CCXT, Kalshi, Polymarket)
│   ├── backtest_engine.py← Backtesting vetorizado
│   ├── model_builder.py  ← Modelos ML (XGBoost, HMM, RandomForest)
│   └── report_generator.py← Relatórios HTML dark-theme
├── data/                 ← Dados gerados (Parquet, modelos .pkl)
└── reports/              ← Relatórios HTML gerados
```

## Setup rápido

### 1. Clonar o repositório
```bash
git clone https://github.com/guimeister/quant-research-agent.git
cd quant-research-agent
```

### 2. Configurar ambiente
```bash
# Via Makefile (recomendado)
make setup

# Ou manualmente
python3 -m venv .venv
source .venv/bin/activate       # Linux/Mac
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### 3. Configurar variáveis
```bash
cp .env.example .env
# Edite .env e adicione sua ANTHROPIC_API_KEY
```

Mínimo necessário em `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Executar

**Modo interativo:**
```bash
python run_agent.py
# ou
make run
```

**Query direta:**
```bash
python run_agent.py "analise BTC/USDT nos últimos 90 dias"
make run-query Q="backtest momentum AAPL 2023"
```

**De arquivo:**
```bash
python run_agent.py --file queries/morning_brief.txt
```

## Uso no VS Code / Cursor

1. Abra a pasta do projeto no VS Code
2. Instale a extensão **Python** (ms-python.python)
3. Selecione o interpretador: `.venv/bin/python` (Ctrl+Shift+P → "Python: Select Interpreter")
4. Vá em **Run and Debug** (Ctrl+Shift+D)
5. Escolha uma configuração:
   - **QuantResearch Agent — Interativo**: abre o chat no terminal integrado
   - **QuantResearch Agent — Query rápida**: pede uma query e executa
   - **Fetch/Backtest/Model Builder**: executa cada script individualmente para debug

## Modelos suportados

Configure via `.env` ou flag `--model`:
```env
QUANT_MODEL=claude-opus-4-5        # padrão (mais capaz)
QUANT_MODEL=claude-sonnet-4-5      # mais rápido e econômico
```

## Ferramentas disponíveis (tool_use)

| Ferramenta | Descrição |
|------------|-----------|
| `fetch_market_data` | Dados de ações, crypto, Kalshi, Polymarket |
| `run_backtest` | Backtest vetorizado com métricas |
| `build_model` | Treinamento ML com walk-forward CV |
| `generate_report` | Relatório HTML dark-theme |
| `run_script` | Execução direta de scripts |
| `read_file` | Leitura de dados/resultados |
| `list_files` | Listagem de arquivos gerados |

## Exemplos de queries

```
analise BTC/USDT nos últimos 90 dias e identifique os melhores momentos de entrada

faça backtest de estratégia mean_reversion para AAPL com janela de 20 dias

treine um modelo de gradient boosting para prever direção do mercado de ETH

compare contratos Kalshi vs Polymarket para eleições de 2024

gere relatório completo de análise quantitativa para um portfólio de tech stocks
```

## Fontes de dados configuradas

| Fonte | Asset class | Gratuita |
|-------|-------------|----------|
| Yahoo Finance (yfinance) | Ações, ETFs, Forex, Índices | ✅ |
| Binance via CCXT | Criptoativos (500+ pares) | ✅ |
| Kalshi API v2 | Mercados de predição (EUA) | ✅* |
| Polymarket (Gamma + CLOB) | Mercados de predição (DeFi) | ✅ |
| FRED (Federal Reserve) | Macro: juros, inflação, PIB | ✅ |

*Kalshi requer conta gratuita para API key

## Licença

MIT — uso livre para fins educacionais e de pesquisa.
