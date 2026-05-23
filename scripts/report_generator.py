"""
QuantResearch Agent — Report Generator
=======================================
Gera relatórios estruturados em HTML, PDF e Markdown com base nos
resultados de backtests, modelos e análises de mercado.

Uso:
    python scripts/report_generator.py --type backtest --input backtests/result.json --format html
    python scripts/report_generator.py --type model --input models/pipeline_result.json --format html
    python scripts/report_generator.py --type market --asset BTC-USD --format markdown
"""

import os
import json
import argparse
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd
import numpy as np


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _color(value: float, positive_good: bool = True) -> str:
    """Retorna cor HTML para valores positivos/negativos."""
    if value > 0:
        return "#2ecc71" if positive_good else "#e74c3c"
    elif value < 0:
        return "#e74c3c" if positive_good else "#2ecc71"
    return "#95a5a6"


def _pct(value: float, decimals: int = 2) -> str:
    return f"{value * 100:.{decimals}f}%"


def _fmt(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def _currency(value: float) -> str:
    return f"${value:,.2f}"


# ─────────────────────────────────────────────
# CSS Base Template
# ─────────────────────────────────────────────

BASE_CSS = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: #0d1117;
    color: #e6edf3;
    padding: 2rem;
    line-height: 1.6;
  }
  h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #58a6ff; }
  h2 { font-size: 1.4rem; margin: 2rem 0 1rem; color: #79c0ff; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }
  h3 { font-size: 1.1rem; margin: 1.5rem 0 0.75rem; color: #a5d6ff; }
  .subtitle { color: #8b949e; font-size: 0.9rem; margin-bottom: 2rem; }
  .badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
    margin-right: 0.5rem;
  }
  .badge-green { background: #1a4731; color: #2ecc71; border: 1px solid #2ecc71; }
  .badge-red { background: #4d1f1f; color: #e74c3c; border: 1px solid #e74c3c; }
  .badge-blue { background: #1c2f4d; color: #58a6ff; border: 1px solid #58a6ff; }
  .badge-yellow { background: #3d2f00; color: #f39c12; border: 1px solid #f39c12; }
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
    margin: 1.5rem 0;
  }
  .metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
  }
  .metric-label { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
  .metric-value { font-size: 1.6rem; font-weight: bold; margin: 0.3rem 0; }
  .metric-sub { font-size: 0.75rem; color: #8b949e; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.875rem;
  }
  th {
    text-align: left;
    padding: 0.6rem 0.8rem;
    background: #161b22;
    color: #8b949e;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #30363d;
  }
  td {
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid #21262d;
    color: #e6edf3;
  }
  tr:hover td { background: #1c2128; }
  .chart-placeholder {
    background: #161b22;
    border: 1px dashed #30363d;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    color: #8b949e;
    margin: 1rem 0;
    font-size: 0.875rem;
  }
  .warning-box {
    background: #3d2f00;
    border: 1px solid #f39c12;
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
    font-size: 0.875rem;
  }
  .info-box {
    background: #1c2f4d;
    border: 1px solid #58a6ff;
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
    font-size: 0.875rem;
  }
  footer { margin-top: 3rem; color: #8b949e; font-size: 0.75rem; text-align: center; }
  code {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 0.1rem 0.4rem;
    font-family: monospace;
    font-size: 0.85em;
    color: #f0883e;
  }
  pre {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    font-size: 0.8rem;
    line-height: 1.5;
  }
</style>
"""


# ─────────────────────────────────────────────
# Backtest Report
# ─────────────────────────────────────────────

class BacktestReportGenerator:
    """Gera relatório HTML de backtest."""

    def generate(self, metrics: Dict, config: Dict, trades: Optional[List] = None,
                 equity_curve_path: Optional[str] = None) -> str:
        """
        Parâmetros:
            metrics (dict): Resultado de BacktestEngine._calculate_metrics()
            config (dict): BacktestConfig como dicionário
            trades (list): Lista de trades individuais
            equity_curve_path (str): Caminho para imagem da equity curve
        """
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        strategy = config.get("strategy", "N/A")
        asset = config.get("asset", "N/A")
        period = config.get("period", "N/A")

        total_return = metrics.get("total_return", 0)
        cagr = metrics.get("cagr", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        sortino = metrics.get("sortino_ratio", 0)
        calmar = metrics.get("calmar_ratio", 0)
        max_dd = metrics.get("max_drawdown", 0)
        win_rate = metrics.get("win_rate", 0)
        profit_factor = metrics.get("profit_factor", 0)
        total_trades = metrics.get("total_trades", 0)
        var_95 = metrics.get("var_95", 0)
        cvar_95 = metrics.get("cvar_95", 0)
        benchmark_return = metrics.get("benchmark_return", 0)
        alpha = metrics.get("alpha", 0)
        beta = metrics.get("beta", 0)
        initial_capital = config.get("initial_capital", 100000)
        final_value = initial_capital * (1 + total_return)

        # Badge de resultado geral
        if sharpe > 1.5 and max_dd > -0.20:
            quality_badge = '<span class="badge badge-green">✅ Robusto</span>'
        elif sharpe > 1.0:
            quality_badge = '<span class="badge badge-blue">📊 Razoável</span>'
        elif sharpe > 0:
            quality_badge = '<span class="badge badge-yellow">⚠️ Marginal</span>'
        else:
            quality_badge = '<span class="badge badge-red">❌ Negativo</span>'

        # Métricas principais
        metrics_html = f"""
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">Retorno Total</div>
            <div class="metric-value" style="color:{_color(total_return)}">{_pct(total_return)}</div>
            <div class="metric-sub">Capital final: {_currency(final_value)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">CAGR</div>
            <div class="metric-value" style="color:{_color(cagr)}">{_pct(cagr)}</div>
            <div class="metric-sub">Benchmark: {_pct(benchmark_return)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-value" style="color:{_color(sharpe)}">{_fmt(sharpe)}</div>
            <div class="metric-sub">Sortino: {_fmt(sortino)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Max Drawdown</div>
            <div class="metric-value" style="color:{_color(max_dd, positive_good=False)}">{_pct(max_dd)}</div>
            <div class="metric-sub">Calmar: {_fmt(calmar)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value" style="color:{_color(win_rate - 0.5)}">{_pct(win_rate)}</div>
            <div class="metric-sub">{total_trades} trades</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Profit Factor</div>
            <div class="metric-value" style="color:{_color(profit_factor - 1.0)}">{_fmt(profit_factor)}</div>
            <div class="metric-sub">Alpha: {_pct(alpha)} | Beta: {_fmt(beta)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">VaR 95%</div>
            <div class="metric-value" style="color:#e74c3c">{_pct(var_95)}</div>
            <div class="metric-sub">CVaR: {_pct(cvar_95)}</div>
          </div>
        </div>
        """

        # Tabela de trades (se disponível)
        trades_html = ""
        if trades:
            rows = ""
            for t in trades[:50]:  # Mostrar até 50 trades
                pnl = t.get("pnl_pct", 0)
                color = _color(pnl)
                rows += f"""
                <tr>
                  <td>{t.get('entry_date', '')}</td>
                  <td>{t.get('exit_date', '')}</td>
                  <td>{t.get('side', 'long').upper()}</td>
                  <td>{_currency(t.get('entry_price', 0))}</td>
                  <td>{_currency(t.get('exit_price', 0))}</td>
                  <td style="color:{color}">{_pct(pnl)}</td>
                  <td style="color:{color}">{_currency(t.get('pnl_abs', 0))}</td>
                  <td>{t.get('duration_bars', 0)} bars</td>
                </tr>"""

            trades_html = f"""
            <h2>📋 Trades Individuais</h2>
            <p class="subtitle">Mostrando até 50 trades. Total: {len(trades)} trades.</p>
            <table>
              <thead>
                <tr>
                  <th>Entrada</th><th>Saída</th><th>Direção</th>
                  <th>Preço Entrada</th><th>Preço Saída</th>
                  <th>Retorno %</th><th>PnL $</th><th>Duração</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table>
            """

        # Configuração do backtest
        config_html = f"""
        <h2>⚙️ Configuração</h2>
        <table>
          <tr><th>Parâmetro</th><th>Valor</th></tr>
          <tr><td>Capital Inicial</td><td>{_currency(config.get('initial_capital', 100000))}</td></tr>
          <tr><td>Comissão</td><td>{_pct(config.get('commission', 0.001))}</td></tr>
          <tr><td>Slippage</td><td>{_pct(config.get('slippage', 0.0005))}</td></tr>
          <tr><td>Tamanho da Posição</td><td>{_pct(config.get('position_size', 1.0))}</td></tr>
          <tr><td>Stop Loss</td><td>{config.get('stop_loss', 'N/A')}</td></tr>
          <tr><td>Take Profit</td><td>{config.get('take_profit', 'N/A')}</td></tr>
          <tr><td>Risk Free Rate</td><td>{_pct(config.get('risk_free_rate', 0.05))}</td></tr>
        </table>
        """

        # Imagem da equity curve (se disponível)
        chart_html = ""
        if equity_curve_path and Path(equity_curve_path).exists():
            chart_html = f'<img src="{equity_curve_path}" style="width:100%;border-radius:8px;margin:1rem 0;" alt="Equity Curve">'
        else:
            chart_html = '<div class="chart-placeholder">📈 Equity curve disponível ao executar com plot=True em BacktestEngine</div>'

        # Aviso de limitações
        warnings_html = f"""
        <div class="warning-box">
          ⚠️ <strong>Limitações e Avisos:</strong><br>
          • Backtests históricos não garantem resultados futuros.<br>
          • Slippage real pode ser maior que {_pct(config.get('slippage', 0.0005))} em ativos ilíquidos.<br>
          • Não inclui impacto de mercado (market impact) para posições grandes.<br>
          • Impostos sobre ganhos de capital não foram considerados.
        </div>
        """

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Backtest Report — {strategy} | {asset}</title>
  {BASE_CSS}
</head>
<body>
  <h1>📊 Backtest Report</h1>
  <p class="subtitle">
    Estratégia: <strong>{strategy}</strong> · Ativo: <strong>{asset}</strong> · Período: <strong>{period}</strong>
    &nbsp;{quality_badge}
    <br>Gerado em {ts} · QuantResearch Agent
  </p>

  <h2>📈 Métricas de Performance</h2>
  {metrics_html}

  <h2>📉 Equity Curve</h2>
  {chart_html}

  {config_html}
  {trades_html}
  {warnings_html}

  <footer>QuantResearch Agent · Relatório gerado automaticamente · {ts}</footer>
</body>
</html>"""
        return html


# ─────────────────────────────────────────────
# Model Report
# ─────────────────────────────────────────────

class ModelReportGenerator:
    """Gera relatório HTML de resultados de modelos ML."""

    def generate(self, results: Dict) -> str:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        asset = results.get("asset", "N/A")
        model_type = results.get("model_type", "N/A")
        target_type = results.get("target_type", "N/A")
        horizon = results.get("horizon", "N/A")

        # Métricas de avaliação
        eval_metrics = results.get("evaluation", {})
        cv_mean = eval_metrics.get("cv_mean_score", 0)
        cv_std = eval_metrics.get("cv_std_score", 0)
        test_score = eval_metrics.get("test_score", 0)
        n_features = eval_metrics.get("n_features", 0)
        top_features = eval_metrics.get("top_features", [])

        # Métricas de classificação vs regressão
        if target_type == "direction":
            score_label = "Acurácia"
            score_color = _color(test_score - 0.5)
        else:
            score_label = "R² Score"
            score_color = _color(test_score)

        metrics_html = f"""
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">Test {score_label}</div>
            <div class="metric-value" style="color:{score_color}">{_fmt(test_score, 4)}</div>
            <div class="metric-sub">Alvo: {target_type} | H={horizon}d</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">CV Score (Walk-Forward)</div>
            <div class="metric-value">{_fmt(cv_mean, 4)}</div>
            <div class="metric-sub">Std: ±{_fmt(cv_std, 4)}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Features Usadas</div>
            <div class="metric-value">{n_features}</div>
            <div class="metric-sub">TimeSeriesSplit CV</div>
          </div>
        </div>
        """

        # Feature importance
        features_html = ""
        if top_features:
            rows = ""
            for i, (feat, imp) in enumerate(top_features[:20], 1):
                bar_width = int(imp / max(v for _, v in top_features) * 100)
                rows += f"""<tr>
                  <td>#{i}</td><td><code>{feat}</code></td>
                  <td>{_fmt(imp, 4)}</td>
                  <td><div style="background:#58a6ff;height:8px;width:{bar_width}%;border-radius:4px;"></div></td>
                </tr>"""

            features_html = f"""
            <h2>🔍 Feature Importance (Top 20)</h2>
            <table>
              <thead><tr><th>#</th><th>Feature</th><th>Importância</th><th>Barra</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
            """

        info = f"""
        <div class="info-box">
          ℹ️ <strong>Notas de Validação:</strong><br>
          • TimeSeriesSplit com {eval_metrics.get('n_splits', 5)} folds (sem vazamento temporal)<br>
          • Features com shift(1) para evitar look-ahead bias<br>
          • Split treino/teste: 80%/20% temporal (não aleatório)<br>
          • Modelo salvo em: <code>models/{asset}_{model_type}_{target_type}.pkl</code>
        </div>
        """

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Model Report — {model_type} | {asset}</title>
  {BASE_CSS}
</head>
<body>
  <h1>🤖 Model Report</h1>
  <p class="subtitle">
    Modelo: <strong>{model_type}</strong> · Ativo: <strong>{asset}</strong> ·
    Target: <strong>{target_type}</strong> · Horizonte: <strong>{horizon} dias</strong>
    <br>Gerado em {ts} · QuantResearch Agent
  </p>

  <h2>📊 Métricas de Avaliação</h2>
  {metrics_html}

  {features_html}
  {info}

  <footer>QuantResearch Agent · Relatório gerado automaticamente · {ts}</footer>
</body>
</html>"""
        return html


# ─────────────────────────────────────────────
# Market Overview Report
# ─────────────────────────────────────────────

class MarketReportGenerator:
    """Gera relatório de visão geral de mercado."""

    def generate_markdown(self, asset: str, df: pd.DataFrame, indicators: Dict) -> str:
        """Gera relatório em Markdown a partir de um DataFrame com indicadores."""
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        last = df.iloc[-1]
        first = df.iloc[0]

        period_return = (last["close"] / first["close"]) - 1
        volatility = df["close"].pct_change().std() * np.sqrt(252)

        md = f"""# 📊 Market Overview — {asset}
> Gerado em {ts} · QuantResearch Agent

## Resumo Executivo
- **Último preço:** ${last['close']:,.2f}
- **Variação no período:** {'▲' if period_return > 0 else '▼'} {_pct(period_return)} ({df.index[0].date()} → {df.index[-1].date()})
- **Volatilidade Anualizada:** {_pct(volatility)}
- **Observações:** {len(df):,} candles

## Indicadores Técnicos (Último Bar)
| Indicador | Valor | Interpretação |
|---|---|---|
| RSI (14) | {indicators.get('rsi', 'N/A')} | {'Sobrecomprado' if (indicators.get('rsi') or 50) > 70 else 'Sobrevendido' if (indicators.get('rsi') or 50) < 30 else 'Neutro'} |
| MACD Signal | {indicators.get('macd_signal', 'N/A')} | {'Alta' if (indicators.get('macd_signal') or 0) > 0 else 'Baixa'} |
| SMA 50 | {indicators.get('sma_50', 'N/A')} | {'Acima SMA50' if last['close'] > (indicators.get('sma_50') or last['close']) else 'Abaixo SMA50'} |
| SMA 200 | {indicators.get('sma_200', 'N/A')} | {'Acima SMA200 (bull)' if last['close'] > (indicators.get('sma_200') or last['close']) else 'Abaixo SMA200 (bear)'} |

## Estatísticas do Período
| Métrica | Valor |
|---|---|
| Máxima | ${df['close'].max():,.2f} |
| Mínima | ${df['close'].min():,.2f} |
| Média | ${df['close'].mean():,.2f} |
| Vol. Diária Média | {df.get('volume', pd.Series([0])).mean():,.0f} |

## Distribuição de Retornos
- **Retorno Médio Diário:** {_pct(df['close'].pct_change().mean())}
- **Desvio Padrão Diário:** {_pct(df['close'].pct_change().std())}
- **Skewness:** {df['close'].pct_change().skew():.3f}
- **Kurtosis:** {df['close'].pct_change().kurt():.3f}

## ⚠️ Limitações
- Análise baseada em dados históricos; não constitui recomendação de investimento
- Indicadores técnicos têm limitações em mercados de baixa liquidez

---
*Fonte: QuantResearch Agent | {ts}*
"""
        return md


# ─────────────────────────────────────────────
# Main Report Orchestrator
# ─────────────────────────────────────────────

class ReportGenerator:
    """Orquestrador principal de relatórios."""

    def __init__(self):
        self.backtest_gen = BacktestReportGenerator()
        self.model_gen = ModelReportGenerator()
        self.market_gen = MarketReportGenerator()
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

    def generate_backtest_report(
        self,
        metrics: Dict,
        config: Dict,
        trades: Optional[List] = None,
        equity_curve_path: Optional[str] = None,
        fmt: str = "html"
    ) -> str:
        """Gera e salva relatório de backtest."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy = config.get("strategy", "backtest")
        asset = config.get("asset", "unknown").replace("/", "-")

        if fmt == "html":
            content = self.backtest_gen.generate(metrics, config, trades, equity_curve_path)
            filename = self.reports_dir / f"backtest_{strategy}_{asset}_{ts}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Relatório de backtest salvo em: {filename}")
            return str(filename)

        elif fmt == "markdown":
            # Versão simplificada em Markdown
            total_return = metrics.get("total_return", 0)
            sharpe = metrics.get("sharpe_ratio", 0)
            max_dd = metrics.get("max_drawdown", 0)
            cagr = metrics.get("cagr", 0)
            win_rate = metrics.get("win_rate", 0)

            md = f"""# 📊 Backtest Report — {strategy} | {asset}

## Resumo Executivo
- **Retorno Total:** {_pct(total_return)}
- **CAGR:** {_pct(cagr)}
- **Sharpe Ratio:** {_fmt(sharpe)}
- **Max Drawdown:** {_pct(max_dd)}
- **Win Rate:** {_pct(win_rate)}
- **Total Trades:** {metrics.get('total_trades', 0)}

## Configuração
- Capital inicial: {_currency(config.get('initial_capital', 100000))}
- Comissão: {_pct(config.get('commission', 0.001))}
- Slippage: {_pct(config.get('slippage', 0.0005))}

*Gerado por QuantResearch Agent em {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
            filename = self.reports_dir / f"backtest_{strategy}_{asset}_{ts}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"✅ Relatório Markdown salvo em: {filename}")
            return str(filename)

        else:
            raise ValueError(f"Formato '{fmt}' não suportado. Use 'html' ou 'markdown'.")

    def generate_model_report(self, results: Dict, fmt: str = "html") -> str:
        """Gera e salva relatório de modelo ML."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        asset = results.get("asset", "unknown").replace("/", "-")
        model_type = results.get("model_type", "model")

        if fmt == "html":
            content = self.model_gen.generate(results)
            filename = self.reports_dir / f"model_{model_type}_{asset}_{ts}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Relatório de modelo salvo em: {filename}")
            return str(filename)
        else:
            raise ValueError(f"Formato '{fmt}' não suportado para model report.")

    def generate_market_report(
        self,
        asset: str,
        df: pd.DataFrame,
        indicators: Optional[Dict] = None,
        fmt: str = "markdown"
    ) -> str:
        """Gera e salva relatório de visão geral de mercado."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        asset_safe = asset.replace("/", "-")
        indicators = indicators or {}

        if fmt == "markdown":
            content = self.market_gen.generate_markdown(asset, df, indicators)
            filename = self.reports_dir / f"market_{asset_safe}_{ts}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Relatório de mercado salvo em: {filename}")
            return str(filename)
        else:
            raise ValueError("Market report suporta apenas formato 'markdown' por enquanto.")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="QuantResearch Agent — Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/report_generator.py --type backtest --input backtests/result.json --format html
  python scripts/report_generator.py --type model --input models/result.json --format html
  python scripts/report_generator.py --type market --asset BTC-USD --input data/crypto/BTC-USD.parquet --format markdown
        """
    )
    parser.add_argument("--type", choices=["backtest", "model", "market"], required=True)
    parser.add_argument("--input", help="Arquivo JSON de resultados ou Parquet de dados")
    parser.add_argument("--asset", help="Símbolo do ativo (para market report)")
    parser.add_argument("--format", default="html", choices=["html", "markdown", "pdf"])

    args = parser.parse_args()
    gen = ReportGenerator()

    if args.type == "backtest":
        if not args.input or not Path(args.input).exists():
            print("❌ Forneça --input com caminho para um arquivo JSON de resultado de backtest")
            return
        with open(args.input) as f:
            data = json.load(f)
        metrics = data.get("metrics", {})
        config = data.get("config", {})
        trades = data.get("trades", [])
        out = gen.generate_backtest_report(metrics, config, trades, fmt=args.format)
        print(f"📁 Relatório: {out}")

    elif args.type == "model":
        if not args.input or not Path(args.input).exists():
            print("❌ Forneça --input com caminho para um arquivo JSON de resultado de modelo")
            return
        with open(args.input) as f:
            results = json.load(f)
        out = gen.generate_model_report(results, fmt=args.format)
        print(f"📁 Relatório: {out}")

    elif args.type == "market":
        if not args.asset:
            print("❌ Forneça --asset (ex: BTC-USD)")
            return
        if args.input and Path(args.input).exists():
            df = pd.read_parquet(args.input)
        else:
            print(f"⚠️  Arquivo de dados não encontrado. Use /quant fetch {args.asset} primeiro.")
            return
        out = gen.generate_market_report(args.asset, df, fmt=args.format)
        print(f"📁 Relatório: {out}")


if __name__ == "__main__":
    main()
