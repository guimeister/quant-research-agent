"""
QuantResearch Agent — Backtest Engine
=======================================
Motor de backtesting vetorizado para múltiplas estratégias e mercados.

Estratégias incluídas:
  - Momentum / Trend Following
  - Mean Reversion
  - Breakout
  - Dual Momentum (cross-asset)
  - Prediction Market Sentiment (Kalshi/Polymarket → sinal de equity)

Métricas calculadas:
  Retorno, CAGR, Sharpe, Sortino, Calmar, Max Drawdown,
  Win Rate, Profit Factor, VaR 95%, CVaR 95%

Uso:
  python backtest_engine.py --symbol BTC-USD --period 2y --strategy momentum
  python backtest_engine.py --symbol SPY --period 5y --strategy mean-reversion
  python backtest_engine.py --symbol AAPL --period 3y --strategy breakout
"""

import os
import json
import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Sem GUI — compatível com servidor
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats

log = logging.getLogger("BacktestEngine")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "backtests"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

@dataclass
class BacktestConfig:
    """Parâmetros globais do backtest."""
    symbol: str
    strategy_name: str
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001     # 0.1% por trade (realista para cripto)
    slippage_pct: float = 0.0005      # 0.05% de slippage
    position_size: float = 1.0        # Fração do capital por trade (1.0 = 100%)
    stop_loss_pct: Optional[float] = None   # Ex: 0.05 = 5%
    take_profit_pct: Optional[float] = None
    benchmark: str = "buy_and_hold"
    risk_free_rate: float = 0.05      # 5% ao ano (Selic aproximada)
    params: Dict = field(default_factory=dict)


# ─────────────────────────────────────────────
# INDICADORES TÉCNICOS
# ─────────────────────────────────────────────

class Indicators:
    """Biblioteca de indicadores técnicos vetorizados."""

    @staticmethod
    def sma(series: pd.Series, window: int) -> pd.Series:
        return series.rolling(window).mean()

    @staticmethod
    def ema(series: pd.Series, window: int) -> pd.Series:
        return series.ewm(span=window, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, window: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(window).mean()
        loss = (-delta.clip(upper=0)).rolling(window).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26,
             signal: int = 9) -> pd.DataFrame:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return pd.DataFrame({
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        })

    @staticmethod
    def bollinger_bands(series: pd.Series, window: int = 20,
                        num_std: float = 2.0) -> pd.DataFrame:
        mid = series.rolling(window).mean()
        std = series.rolling(window).std()
        return pd.DataFrame({
            "upper": mid + num_std * std,
            "mid": mid,
            "lower": mid - num_std * std,
            "bandwidth": (2 * num_std * std) / mid
        })

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series,
            window: int = 14) -> pd.Series:
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        return tr.ewm(span=window, adjust=False).mean()

    @staticmethod
    def momentum(series: pd.Series, window: int = 20) -> pd.Series:
        return series / series.shift(window) - 1

    @staticmethod
    def volume_sma(volume: pd.Series, window: int = 20) -> pd.Series:
        return volume.rolling(window).mean()


# ─────────────────────────────────────────────
# ESTRATÉGIAS
# ─────────────────────────────────────────────

class Strategies:
    """Biblioteca de estratégias de trading."""

    @staticmethod
    def momentum(df: pd.DataFrame, params: Dict) -> pd.Series:
        """
        Momentum: compra quando retorno de N dias é positivo.
        Variante com filtro de tendência (SMA200).
        """
        lookback = params.get("lookback", 20)
        trend_filter = params.get("trend_filter", True)
        trend_period = params.get("trend_period", 200)

        signal = pd.Series(0, index=df.index)
        mom = Indicators.momentum(df["close"], lookback)

        # Sinal base: long quando momentum positivo
        signal[mom > 0] = 1
        signal[mom < 0] = -1

        # Filtro de tendência: só compra acima da SMA200
        if trend_filter and len(df) > trend_period:
            sma200 = Indicators.sma(df["close"], trend_period)
            signal[df["close"] < sma200] = 0

        return signal

    @staticmethod
    def mean_reversion(df: pd.DataFrame, params: Dict) -> pd.Series:
        """
        Mean Reversion via Bollinger Bands.
        Compra quando preço toca banda inferior, vende na superior.
        """
        window = params.get("window", 20)
        num_std = params.get("num_std", 2.0)
        rsi_filter = params.get("rsi_filter", True)

        bb = Indicators.bollinger_bands(df["close"], window, num_std)
        signal = pd.Series(0, index=df.index)

        # Sinal base
        signal[df["close"] < bb["lower"]] = 1   # oversold → long
        signal[df["close"] > bb["upper"]] = -1  # overbought → short

        # Filtro RSI
        if rsi_filter:
            rsi = Indicators.rsi(df["close"])
            signal[(signal == 1) & (rsi > 40)] = 0   # só entra se RSI < 40
            signal[(signal == -1) & (rsi < 60)] = 0  # só short se RSI > 60

        return signal

    @staticmethod
    def breakout(df: pd.DataFrame, params: Dict) -> pd.Series:
        """
        Breakout: compra na máxima de N dias (Donchian Channel).
        """
        channel_period = params.get("channel_period", 20)
        exit_period = params.get("exit_period", 10)
        atr_filter = params.get("atr_filter", True)

        upper = df["high"].rolling(channel_period).max().shift(1)
        lower = df["low"].rolling(exit_period).min().shift(1)

        signal = pd.Series(0, index=df.index)
        position = 0

        for i in range(len(df)):
            if df["close"].iloc[i] > upper.iloc[i]:
                position = 1
            elif df["close"].iloc[i] < lower.iloc[i]:
                position = 0
            signal.iloc[i] = position

        # Filtro ATR: só entra em breakouts com volatilidade acima da média
        if atr_filter:
            atr = Indicators.atr(df["high"], df["low"], df["close"])
            atr_mean = atr.rolling(100).mean()
            signal[atr < atr_mean * 0.8] = 0

        return signal

    @staticmethod
    def macd_crossover(df: pd.DataFrame, params: Dict) -> pd.Series:
        """Sinal baseado no cruzamento MACD."""
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        sig = params.get("signal", 9)

        macd_df = Indicators.macd(df["close"], fast, slow, sig)
        signal = pd.Series(0, index=df.index)

        # Cruzamento bullish
        signal[
            (macd_df["macd"] > macd_df["signal"]) &
            (macd_df["macd"].shift(1) <= macd_df["signal"].shift(1))
        ] = 1
        # Cruzamento bearish
        signal[
            (macd_df["macd"] < macd_df["signal"]) &
            (macd_df["macd"].shift(1) >= macd_df["signal"].shift(1))
        ] = -1

        return signal.replace(0, np.nan).ffill().fillna(0)

    @staticmethod
    def dual_momentum(df: pd.DataFrame, params: Dict) -> pd.Series:
        """
        Dual Momentum (Gary Antonacci):
        - Momentum absoluto: compara ativo vs. T-Bills
        - Momentum relativo: compara dois ativos (ex: SPY vs. EFA)
        Requer coluna 'benchmark_close' no DataFrame.
        """
        lookback = params.get("lookback", 252)  # 12 meses
        signal = pd.Series(0, index=df.index)

        asset_mom = Indicators.momentum(df["close"], lookback)

        # Apenas momentum absoluto se não há benchmark
        if "benchmark_close" in df.columns:
            bench_mom = Indicators.momentum(df["benchmark_close"], lookback)
            signal[(asset_mom > 0) & (asset_mom > bench_mom)] = 1
        else:
            signal[asset_mom > 0] = 1

        return signal


# ─────────────────────────────────────────────
# MOTOR DE BACKTEST
# ─────────────────────────────────────────────

class BacktestEngine:
    """Motor vetorizado de backtesting."""

    STRATEGIES = {
        "momentum": Strategies.momentum,
        "mean-reversion": Strategies.mean_reversion,
        "breakout": Strategies.breakout,
        "macd": Strategies.macd_crossover,
        "dual-momentum": Strategies.dual_momentum,
    }

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.results: Dict = {}

    def run(self, df: pd.DataFrame,
            signal_func: Optional[Callable] = None) -> Dict:
        """
        Executa o backtest completo.

        Args:
            df: DataFrame com OHLCV (index DatetimeIndex)
            signal_func: Função personalizada de geração de sinal.
                         Se None, usa a estratégia do config.

        Returns:
            Dict com equity curve, trades e métricas
        """
        df = df.copy()

        # 1. Gera sinais
        if signal_func:
            signals = signal_func(df, self.config.params)
        else:
            strategy_fn = self.STRATEGIES.get(self.config.strategy_name)
            if not strategy_fn:
                raise ValueError(f"Estratégia desconhecida: {self.config.strategy_name}")
            signals = strategy_fn(df, self.config.params)

        df["signal"] = signals

        # 2. Posição efetiva (delay de 1 barra para evitar look-ahead bias)
        df["position"] = df["signal"].shift(1).fillna(0)

        # 3. Retornos do ativo
        df["returns"] = df["close"].pct_change()

        # 4. Retornos da estratégia com custos de transação
        df["position_change"] = df["position"].diff().abs()
        costs = df["position_change"] * (self.config.commission_pct + self.config.slippage_pct)
        df["strategy_returns"] = df["position"] * df["returns"] - costs
        df["strategy_returns"] = df["strategy_returns"].fillna(0)

        # 5. Equity curve
        df["equity"] = self.config.initial_capital * (1 + df["strategy_returns"]).cumprod()
        df["bh_equity"] = self.config.initial_capital * (1 + df["returns"]).cumprod()

        # 6. Stop loss / Take profit
        if self.config.stop_loss_pct or self.config.take_profit_pct:
            df = self._apply_sl_tp(df)

        # 7. Métricas
        metrics = self._calculate_metrics(df)

        # 8. Análise de trades
        trades = self._extract_trades(df)

        self.results = {
            "config": self.config.__dict__,
            "data": df,
            "metrics": metrics,
            "trades": trades,
            "run_date": datetime.now().isoformat()
        }

        return self.results

    def _apply_sl_tp(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica stop loss e take profit na equity curve."""
        # Implementação simplificada — ajuste conforme necessidade
        peak = df["equity"].expanding().max()
        drawdown = (df["equity"] - peak) / peak

        if self.config.stop_loss_pct:
            # Sai quando drawdown excede o stop
            df.loc[drawdown < -self.config.stop_loss_pct, "position"] = 0

        return df

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calcula métricas completas de performance."""
        rets = df["strategy_returns"].dropna()
        bh_rets = df["returns"].dropna()
        equity = df["equity"].dropna()

        # Detecta frequência dos dados
        freq = self._detect_frequency(df.index)
        annual_factor = self._annual_factor(freq)

        # Retorno total
        total_return = (equity.iloc[-1] / self.config.initial_capital) - 1

        # CAGR
        years = len(df) / annual_factor
        cagr = (equity.iloc[-1] / self.config.initial_capital) ** (1 / years) - 1 if years > 0 else 0

        # Volatilidade anualizada
        vol = rets.std() * np.sqrt(annual_factor)

        # Sharpe Ratio
        rf_daily = self.config.risk_free_rate / annual_factor
        excess_returns = rets - rf_daily
        sharpe = (excess_returns.mean() / rets.std()) * np.sqrt(annual_factor) if rets.std() > 0 else 0

        # Sortino Ratio (penaliza apenas retornos negativos)
        downside = rets[rets < 0].std()
        sortino = (excess_returns.mean() / downside) * np.sqrt(annual_factor) if downside > 0 else 0

        # Maximum Drawdown
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max
        max_dd = drawdown.min()

        # Calmar Ratio
        calmar = cagr / abs(max_dd) if max_dd != 0 else 0

        # Win Rate e Profit Factor
        daily_pnl = rets * self.config.initial_capital
        wins = daily_pnl[daily_pnl > 0]
        losses = daily_pnl[daily_pnl < 0]
        win_rate = len(wins) / len(daily_pnl[daily_pnl != 0]) if len(daily_pnl[daily_pnl != 0]) > 0 else 0
        profit_factor = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf

        # VaR e CVaR (95%)
        var_95 = np.percentile(rets, 5)
        cvar_95 = rets[rets <= var_95].mean()

        # Benchmark (buy & hold)
        bh_total = (1 + bh_rets).prod() - 1
        bh_cagr = (1 + bh_total) ** (1 / years) - 1 if years > 0 else 0

        # Alpha e Beta
        if len(rets) > 30:
            slope, intercept, r, p, se = stats.linregress(bh_rets, rets)
            beta = slope
            alpha_annual = (intercept * annual_factor)
        else:
            beta, alpha_annual = 0, 0

        return {
            "symbol": self.config.symbol,
            "strategy": self.config.strategy_name,
            "period": {
                "start": str(df.index.min()),
                "end": str(df.index.max()),
                "years": round(years, 2)
            },
            "performance": {
                "total_return": round(total_return * 100, 2),
                "cagr": round(cagr * 100, 2),
                "volatility_annual": round(vol * 100, 2),
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "calmar_ratio": round(calmar, 3),
                "max_drawdown": round(max_dd * 100, 2),
                "win_rate": round(win_rate * 100, 2),
                "profit_factor": round(profit_factor, 3),
                "var_95_daily": round(var_95 * 100, 3),
                "cvar_95_daily": round(cvar_95 * 100, 3),
            },
            "benchmark": {
                "total_return": round(bh_total * 100, 2),
                "cagr": round(bh_cagr * 100, 2),
            },
            "risk_adjusted": {
                "alpha_annual": round(alpha_annual * 100, 2),
                "beta": round(beta, 3),
                "excess_return": round((cagr - bh_cagr) * 100, 2)
            }
        }

    def _extract_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extrai lista de trades individuais."""
        trades = []
        entry_price = None
        entry_date = None
        position = 0

        for date, row in df.iterrows():
            if row["position"] != position:
                if position != 0 and entry_price is not None:
                    # Fecha trade anterior
                    pnl_pct = (row["close"] - entry_price) / entry_price * position
                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": date,
                        "direction": "long" if position > 0 else "short",
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(row["close"], 6),
                        "pnl_pct": round(pnl_pct * 100, 3),
                        "duration_days": (date - entry_date).days
                    })

                if row["position"] != 0:
                    entry_price = row["close"]
                    entry_date = date

                position = row["position"]

        return pd.DataFrame(trades) if trades else pd.DataFrame()

    def _detect_frequency(self, index: pd.DatetimeIndex) -> str:
        if len(index) < 2:
            return "D"
        diff = (index[1] - index[0]).total_seconds()
        if diff < 3600:
            return "min"
        elif diff < 86400:
            return "H"
        else:
            return "D"

    def _annual_factor(self, freq: str) -> int:
        return {"min": 252 * 390, "H": 252 * 24, "D": 252}.get(freq, 252)

    def plot(self, save_path: Optional[Path] = None) -> str:
        """Gera gráfico completo de 4 painéis."""
        if not self.results:
            raise ValueError("Execute run() antes de chamar plot()")

        df = self.results["data"]
        metrics = self.results["metrics"]

        fig = plt.figure(figsize=(16, 12))
        fig.suptitle(
            f"{self.config.symbol} — {self.config.strategy_name.upper()} Backtest",
            fontsize=14, fontweight="bold"
        )
        gs = gridspec.GridSpec(4, 1, hspace=0.4)

        # Painel 1: Preço + Sinais
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(df.index, df["close"], linewidth=1, label="Preço", color="#333")
        longs = df[df["position"] > 0]["close"]
        shorts = df[df["position"] < 0]["close"]
        ax1.fill_between(df.index, df["close"].min(), df["close"],
                         where=df["position"] > 0, alpha=0.15, color="green", label="Long")
        ax1.fill_between(df.index, df["close"].min(), df["close"],
                         where=df["position"] < 0, alpha=0.15, color="red", label="Short")
        ax1.set_title("Preço e Posições")
        ax1.legend(loc="upper left", fontsize=8)
        ax1.set_ylabel("Preço")

        # Painel 2: Equity Curve
        ax2 = fig.add_subplot(gs[1])
        ax2.plot(df.index, df["equity"], linewidth=1.5, label="Estratégia", color="blue")
        ax2.plot(df.index, df["bh_equity"], linewidth=1, label="Buy & Hold",
                 color="gray", linestyle="--", alpha=0.7)
        ax2.set_title(f"Equity Curve | CAGR: {metrics['performance']['cagr']}% | Sharpe: {metrics['performance']['sharpe_ratio']}")
        ax2.legend(loc="upper left", fontsize=8)
        ax2.set_ylabel("Capital (R$)")

        # Painel 3: Drawdown
        ax3 = fig.add_subplot(gs[2])
        rolling_max = df["equity"].expanding().max()
        drawdown = (df["equity"] - rolling_max) / rolling_max * 100
        ax3.fill_between(df.index, drawdown, 0, alpha=0.5, color="red")
        ax3.plot(df.index, drawdown, linewidth=0.8, color="darkred")
        ax3.set_title(f"Drawdown | Máx: {metrics['performance']['max_drawdown']}%")
        ax3.set_ylabel("Drawdown (%)")

        # Painel 4: Retornos diários (distribuição)
        ax4 = fig.add_subplot(gs[3])
        daily_rets = df["strategy_returns"].dropna() * 100
        ax4.hist(daily_rets, bins=60, color="steelblue", alpha=0.7, edgecolor="none")
        ax4.axvline(daily_rets.mean(), color="green", linewidth=1.5, label=f"Média: {daily_rets.mean():.3f}%")
        ax4.axvline(np.percentile(daily_rets, 5), color="red", linewidth=1.5,
                    linestyle="--", label=f"VaR 95%: {np.percentile(daily_rets, 5):.3f}%")
        ax4.set_title("Distribuição de Retornos Diários")
        ax4.set_xlabel("Retorno Diário (%)")
        ax4.legend(fontsize=8)

        plt.tight_layout()

        if save_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = RESULTS_DIR / f"{self.config.symbol}_{self.config.strategy_name}_{ts}.png"

        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        log.info(f"Gráfico salvo: {save_path}")
        return str(save_path)

    def print_report(self):
        """Imprime relatório formatado no terminal."""
        if not self.results:
            raise ValueError("Execute run() primeiro")

        m = self.results["metrics"]
        p = m["performance"]
        b = m["benchmark"]
        r = m["risk_adjusted"]

        print("\n" + "="*60)
        print(f"  BACKTEST: {m['symbol']} | {m['strategy']}")
        print(f"  Período: {m['period']['start'][:10]} → {m['period']['end'][:10]} ({m['period']['years']} anos)")
        print("="*60)
        print(f"\n  📈 PERFORMANCE")
        print(f"     Retorno Total:     {p['total_return']:>8.2f}%    (BH: {b['total_return']:.2f}%)")
        print(f"     CAGR:              {p['cagr']:>8.2f}%    (BH: {b['cagr']:.2f}%)")
        print(f"     Alpha Anual:       {r['alpha_annual']:>8.2f}%    (Beta: {r['beta']:.3f})")
        print(f"\n  📊 RISCO")
        print(f"     Volatilidade:      {p['volatility_annual']:>8.2f}%")
        print(f"     Max Drawdown:      {p['max_drawdown']:>8.2f}%")
        print(f"     VaR 95% (diário):  {p['var_95_daily']:>8.3f}%")
        print(f"     CVaR 95% (diário): {p['cvar_95_daily']:>8.3f}%")
        print(f"\n  🎯 QUALIDADE")
        print(f"     Sharpe Ratio:      {p['sharpe_ratio']:>8.3f}")
        print(f"     Sortino Ratio:     {p['sortino_ratio']:>8.3f}")
        print(f"     Calmar Ratio:      {p['calmar_ratio']:>8.3f}")
        print(f"     Win Rate:          {p['win_rate']:>8.2f}%")
        print(f"     Profit Factor:     {p['profit_factor']:>8.3f}")
        print("="*60 + "\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QuantResearch — Backtest Engine")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--strategy", default="momentum",
                        choices=["momentum", "mean-reversion", "breakout", "macd", "dual-momentum"])
    parser.add_argument("--capital", type=float, default=100000)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--no-plot", action="store_true")

    args = parser.parse_args()

    # Carrega dados
    try:
        from data_fetcher import YFinanceFetcher
        fetcher = YFinanceFetcher()
        df = fetcher.fetch(args.symbol, period=args.period, interval=args.interval)
    except Exception as e:
        log.error(f"Erro ao carregar dados: {e}")
        return

    # Configura e executa backtest
    config = BacktestConfig(
        symbol=args.symbol,
        strategy_name=args.strategy,
        initial_capital=args.capital,
        commission_pct=args.commission
    )

    engine = BacktestEngine(config)
    results = engine.run(df)
    engine.print_report()

    if not args.no_plot:
        plot_path = engine.plot()
        print(f"📊 Gráfico salvo em: {plot_path}")

    # Salva métricas em JSON
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"{args.symbol}_{args.strategy}_{ts}.json"
    with open(json_path, "w") as f:
        json.dump(results["metrics"], f, indent=2, default=str)
    print(f"📋 Métricas salvas em: {json_path}")


if __name__ == "__main__":
    main()
