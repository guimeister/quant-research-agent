# QuantResearch Agent — Makefile
# Uso: make <comando>

.PHONY: help setup run run-query fetch backtest model report clean

PYTHON  := python3
SCRIPT  := run_agent.py
VENV    := .venv

help:
	@echo ""
	@echo "  QuantResearch Agent"
	@echo "  ─────────────────────────────────────────"
	@echo "  make setup        Cria venv e instala dependências"
	@echo "  make run          Inicia o agente em modo interativo"
	@echo "  make run-query Q='...'  Executa uma query direta"
	@echo "  make fetch        Baixa dados de exemplo (BTC/USDT 90d)"
	@echo "  make backtest     Backtest momentum em dados de exemplo"
	@echo "  make model        Treina modelo GB nos dados de exemplo"
	@echo "  make report       Gera relatório de exemplo"
	@echo "  make clean        Remove dados e relatórios gerados"
	@echo ""

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	@echo ""
	@echo "✅ Ambiente pronto! Agora:"
	@echo "   1. Copie .env.example → .env"
	@echo "   2. Adicione sua ANTHROPIC_API_KEY em .env"
	@echo "   3. Execute: make run"

run:
	$(PYTHON) $(SCRIPT)

run-query:
	$(PYTHON) $(SCRIPT) "$(Q)"

fetch:
	$(PYTHON) scripts/data_fetcher.py \
		--symbol BTC/USDT --source ccxt --days 90 --interval 1d \
		--output data/BTCUSDT_90d.parquet

backtest:
	$(PYTHON) scripts/backtest_engine.py \
		--data data/BTCUSDT_90d.parquet \
		--strategy momentum \
		--output reports/backtest_example.html

model:
	$(PYTHON) scripts/model_builder.py \
		--data data/BTCUSDT_90d.parquet \
		--algorithm gradient_boosting \
		--output data/model_btc.pkl

report:
	$(PYTHON) scripts/report_generator.py \
		--title "Análise BTC/USDT" \
		--data data/BTCUSDT_90d.parquet \
		--output reports/report_example.html

clean:
	rm -f data/*.parquet data/*.pkl data/*.csv
	rm -f reports/*.html reports/*.json
	@echo "Dados e relatórios removidos."
