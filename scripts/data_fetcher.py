"""
QuantResearch Agent — Data Fetcher
===================================
Módulo central de coleta de dados para múltiplos mercados:
  - Mercados de capitais: ações, ETFs, futuros, forex (yfinance, Polygon.io)
  - Criptoativos: spot e derivativos (Binance via CCXT)
  - Mercados de predição: Kalshi e Polymarket
  - Dados macro: FRED (Federal Reserve)

Uso via CLI:
  python data_fetcher.py --source yfinance --symbol AAPL --period 2y --interval 1d
  python data_fetcher.py --source binance --symbol BTC/USDT --period 30d --interval 15m
  python data_fetcher.py --source kalshi --market PRES-2028 --period all
  python data_fetcher.py --source polymarket --topic crypto --period 7d
  python data_fetcher.py --test  # testa todas as conexões
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data_fetcher.log")
    ]
)
log = logging.getLogger("DataFetcher")

# Diretórios de saída
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# ─────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────

def parse_period(period: str) -> tuple[datetime, datetime]:
    """Converte strings como '2y', '6mo', '30d' em datas."""
    end = datetime.now()
    unit = period[-1].lower()
    n = int(period[:-1]) if period[:-1].isdigit() else 1

    if unit == 'd':
        start = end - timedelta(days=n)
    elif unit == 'w':
        start = end - timedelta(weeks=n)
    elif unit in ('m', 'mo'):
        start = end - timedelta(days=n * 30)
    elif unit == 'y':
        start = end - timedelta(days=n * 365)
    else:
        raise ValueError(f"Período inválido: {period}. Use: 30d, 6mo, 2y, etc.")

    return start, end


def save_data(df: pd.DataFrame, market: str, symbol: str,
              period: str, interval: str) -> Path:
    """Salva DataFrame em Parquet com metadados."""
    folder = DATA_DIR / market
    folder.mkdir(parents=True, exist_ok=True)

    # Sanitiza o nome do arquivo
    clean_symbol = symbol.replace("/", "-").replace(":", "_")
    filename = f"{clean_symbol}_{period}_{interval}.parquet"
    filepath = folder / filename

    df.to_parquet(filepath, compression="snappy")
    log.info(f"Dados salvos: {filepath} ({len(df)} linhas)")
    return filepath


def describe_data(df: pd.DataFrame, symbol: str) -> Dict:
    """Retorna resumo estatístico do DataFrame."""
    return {
        "symbol": symbol,
        "shape": df.shape,
        "date_range": {
            "start": str(df.index.min()) if hasattr(df.index, 'min') else "N/A",
            "end": str(df.index.max()) if hasattr(df.index, 'max') else "N/A"
        },
        "missing_values": int(df.isnull().sum().sum()),
        "missing_pct": round(df.isnull().mean().mean() * 100, 2),
        "columns": list(df.columns),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
        "tail": df.tail(3).to_dict()
    }


# ─────────────────────────────────────────────
# YFINANCE — Ações, ETFs, Futuros, Forex
# ─────────────────────────────────────────────

class YFinanceFetcher:
    """
    Coleta dados via Yahoo Finance (yfinance).
    Gratuito, sem API key. Cobre ações, ETFs, futuros, forex, índices.

    Intervalos disponíveis:
      Intraday: 1m, 2m, 5m, 15m, 30m, 60m, 90m (máx 60 dias para <1d)
      Daily+: 1d, 5d, 1wk, 1mo, 3mo

    Período máximo por intervalo:
      1m  → 7 dias
      2m/5m/15m/30m/90m → 60 dias
      60m → 730 dias
      1d+ → histórico completo
    """

    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            log.info("yfinance carregado com sucesso")
        except ImportError:
            log.error("yfinance não instalado. Execute: pip install yfinance")
            raise

    def fetch(self, symbol: str, period: str = "1y", interval: str = "1d",
              start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        """
        Baixa OHLCV + Volume + Dividends + Splits.

        Args:
            symbol: Ticker no formato Yahoo (AAPL, BTC-USD, ES=F, EURUSD=X)
            period: '1d','5d','1mo','3mo','6mo','1y','2y','5y','10y','ytd','max'
            interval: '1m','2m','5m','15m','30m','60m','90m','1h','1d','5d','1wk','1mo','3mo'
            start/end: Datas alternativas no formato 'YYYY-MM-DD'
        """
        log.info(f"yfinance: baixando {symbol} | período={period} | intervalo={interval}")

        ticker = self.yf.Ticker(symbol)

        kwargs = {"interval": interval, "auto_adjust": True, "progress": False}
        if start and end:
            kwargs["start"] = start
            kwargs["end"] = end
        else:
            kwargs["period"] = period

        df = ticker.history(**kwargs)

        if df.empty:
            raise ValueError(f"Nenhum dado retornado para {symbol}. Verifique o ticker.")

        # Padroniza colunas
        df.index.name = "datetime"
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()

        # Remove duplicatas e NaN
        df = df.dropna()
        df = df[~df.index.duplicated(keep='last')]

        log.info(f"yfinance: {len(df)} candles carregados para {symbol}")
        return df

    def fetch_multiple(self, symbols: List[str], period: str = "1y",
                       interval: str = "1d") -> Dict[str, pd.DataFrame]:
        """Baixa múltiplos ativos em paralelo."""
        log.info(f"yfinance: baixando {len(symbols)} ativos...")
        raw = self.yf.download(
            symbols, period=period, interval=interval,
            auto_adjust=True, progress=False
        )
        result = {}
        for sym in symbols:
            try:
                df = raw.xs(sym, axis=1, level=1) if len(symbols) > 1 else raw
                df.columns = [c.lower() for c in df.columns]
                df = df.dropna()
                result[sym] = df
            except Exception as e:
                log.warning(f"Erro ao processar {sym}: {e}")
        return result

    def get_info(self, symbol: str) -> Dict:
        """Retorna metadados do ativo (setor, mercado, moeda, etc.)"""
        ticker = self.yf.Ticker(symbol)
        info = ticker.info
        return {
            "name": info.get("longName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "currency": info.get("currency", ""),
            "exchange": info.get("exchange", ""),
            "market_cap": info.get("marketCap"),
            "country": info.get("country", "")
        }


# ─────────────────────────────────────────────
# CCXT / BINANCE — Criptoativos
# ─────────────────────────────────────────────

class CryptoFetcher:
    """
    Coleta dados de criptoativos via CCXT (suporte a 100+ exchanges).
    Configuração padrão: Binance (maior liquidez, dados históricos extensos).

    API pública: sem autenticação para dados históricos OHLCV.
    API privada: necessária para ordens, saldo e dados em tempo real.
    """

    SUPPORTED_EXCHANGES = ["binance", "bybit", "okx", "kraken", "coinbase"]

    def __init__(self, exchange_id: str = "binance",
                 api_key: Optional[str] = None,
                 secret: Optional[str] = None):
        try:
            import ccxt
            self.ccxt = ccxt
        except ImportError:
            log.error("ccxt não instalado. Execute: pip install ccxt")
            raise

        exchange_class = getattr(self.ccxt, exchange_id)
        params = {"enableRateLimit": True}
        if api_key:
            params["apiKey"] = api_key
        if secret:
            params["secret"] = secret

        self.exchange = exchange_class(params)
        log.info(f"CCXT: conectado à {exchange_id}")

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1d",
                    since: Optional[int] = None, limit: int = 1000,
                    paginate: bool = True) -> pd.DataFrame:
        """
        Baixa OHLCV com paginação automática para histórico longo.

        Args:
            symbol: Par no formato CCXT (BTC/USDT, ETH/BTC, BTC/USDT:USDT para futuros)
            timeframe: '1m','5m','15m','30m','1h','4h','1d','1w'
            since: Timestamp Unix em ms (None = máximo disponível)
            limit: Candles por requisição (máx 1000 na Binance)
            paginate: Se True, busca todo o histórico automaticamente
        """
        log.info(f"CCXT: baixando {symbol} | timeframe={timeframe}")
        all_ohlcv = []

        if since is None:
            # Busca desde o início disponível (geralmente 2017 para BTC)
            since = self.exchange.parse8601("2017-01-01T00:00:00Z")

        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol, timeframe, since=since, limit=limit
                )
            except self.ccxt.RateLimitExceeded:
                log.warning("Rate limit atingido. Aguardando 30s...")
                time.sleep(30)
                continue

            if not ohlcv:
                break

            all_ohlcv.extend(ohlcv)

            if not paginate or len(ohlcv) < limit:
                break

            since = ohlcv[-1][0] + 1  # próximo candle
            time.sleep(self.exchange.rateLimit / 1000)  # respeita rate limit

        if not all_ohlcv:
            raise ValueError(f"Nenhum dado para {symbol}")

        df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("datetime").drop("timestamp", axis=1)
        df = df[~df.index.duplicated(keep='last')].sort_index()

        log.info(f"CCXT: {len(df)} candles carregados para {symbol}")
        return df

    def fetch_funding_rate(self, symbol: str, limit: int = 500) -> pd.DataFrame:
        """Baixa funding rate histórico (apenas futuros perpétuos)."""
        try:
            funding = self.exchange.fetch_funding_rate_history(symbol, limit=limit)
            df = pd.DataFrame(funding)
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df.set_index("datetime")[["fundingRate", "fundingTimestamp"]]
        except Exception as e:
            log.warning(f"Funding rate não disponível para {symbol}: {e}")
            return pd.DataFrame()

    def get_markets(self, quote: str = "USDT") -> List[str]:
        """Lista todos os mercados disponíveis para uma moeda de cotação."""
        markets = self.exchange.load_markets()
        return [s for s in markets if s.endswith(f"/{quote}") and markets[s]["active"]]


# ─────────────────────────────────────────────
# KALSHI — Mercado de Predição (EUA)
# ─────────────────────────────────────────────

class KalshiFetcher:
    """
    Acessa dados do Kalshi — exchange regulada de mercados de predição (CFTC).
    API v2: https://trading-api.kalshi.com/trade-api/v2

    Endpoints públicos (sem auth): mercados, preços atuais
    Endpoints privados (com auth): histórico de trades, portfólio

    Documentação: https://trading-api.kalshi.com/trade-api/v2/docs
    """

    BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"
    DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"  # Para testes

    def __init__(self, api_key: Optional[str] = None, use_demo: bool = False):
        self.api_key = api_key or os.getenv("KALSHI_API_KEY")
        self.base_url = self.DEMO_URL if use_demo else self.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "QuantResearch/1.0"
        })
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"
            log.info("Kalshi: autenticado com API key")
        else:
            log.info("Kalshi: modo público (dados limitados)")

    def get_markets(self, series_ticker: Optional[str] = None,
                    status: str = "open", limit: int = 100) -> pd.DataFrame:
        """
        Lista mercados disponíveis no Kalshi.

        Args:
            series_ticker: Filtro por série (ex: 'PRES', 'FED', 'INFL')
            status: 'open', 'closed', 'settled', 'all'
            limit: Número de mercados a retornar
        """
        params = {"limit": limit, "status": status}
        if series_ticker:
            params["series_ticker"] = series_ticker

        resp = self.session.get(f"{self.base_url}/markets", params=params)
        resp.raise_for_status()
        data = resp.json()

        markets = data.get("markets", [])
        if not markets:
            return pd.DataFrame()

        df = pd.DataFrame(markets)
        log.info(f"Kalshi: {len(df)} mercados carregados")
        return df

    def get_market_history(self, ticker: str, limit: int = 1000) -> pd.DataFrame:
        """
        Histórico de preços de um mercado específico.
        Retorna série temporal de yes_price, no_price e volume.
        """
        resp = self.session.get(
            f"{self.base_url}/markets/{ticker}/history",
            params={"limit": limit}
        )

        if resp.status_code == 404:
            raise ValueError(f"Mercado não encontrado: {ticker}")
        resp.raise_for_status()

        history = resp.json().get("history", [])
        if not history:
            return pd.DataFrame()

        df = pd.DataFrame(history)
        if "ts" in df.columns:
            df["datetime"] = pd.to_datetime(df["ts"], unit="s")
            df = df.set_index("datetime")

        # Normaliza para probabilidades (0-100 → 0-1)
        for col in ["yes_price", "no_price"]:
            if col in df.columns:
                df[col] = df[col] / 100.0

        log.info(f"Kalshi: {len(df)} pontos de histórico para {ticker}")
        return df

    def get_orderbook(self, ticker: str) -> Dict:
        """Retorna o order book atual de um mercado."""
        resp = self.session.get(f"{self.base_url}/markets/{ticker}/orderbook")
        resp.raise_for_status()
        return resp.json()

    def search_markets(self, query: str) -> pd.DataFrame:
        """Busca mercados por palavra-chave."""
        resp = self.session.get(
            f"{self.base_url}/markets",
            params={"search": query, "limit": 100}
        )
        resp.raise_for_status()
        markets = resp.json().get("markets", [])
        return pd.DataFrame(markets) if markets else pd.DataFrame()


# ─────────────────────────────────────────────
# POLYMARKET — Mercado de Predição (Descentralizado)
# ─────────────────────────────────────────────

class PolymarketFetcher:
    """
    Acessa dados do Polymarket — mercado de predição descentralizado em Polygon.
    Gamma API: https://gamma-api.polymarket.com (dados públicos, sem auth)
    CLOB API: https://clob.polymarket.com (order book e trades)

    Documentação: https://docs.polymarket.com
    """

    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "QuantResearch/1.0"})
        log.info("Polymarket: conectado (modo público)")

    def get_markets(self, active: bool = True, limit: int = 100,
                    offset: int = 0, tag: Optional[str] = None) -> pd.DataFrame:
        """
        Lista mercados ativos no Polymarket.

        Args:
            active: Se True, retorna apenas mercados abertos
            limit: Quantidade de resultados
            offset: Paginação
            tag: Filtrar por tag (ex: 'crypto', 'politics', 'sports')
        """
        params = {"limit": limit, "offset": offset, "active": active}
        if tag:
            params["tag"] = tag

        resp = self.session.get(f"{self.GAMMA_URL}/markets", params=params)
        resp.raise_for_status()
        markets = resp.json()

        if not markets:
            return pd.DataFrame()

        df = pd.DataFrame(markets)
        log.info(f"Polymarket: {len(df)} mercados carregados")
        return df

    def get_market_prices(self, condition_id: str) -> pd.DataFrame:
        """
        Histórico de preços de um mercado específico.
        Os preços representam probabilidades implícitas (0 a 1).
        """
        resp = self.session.get(
            f"{self.CLOB_URL}/prices-history",
            params={"market": condition_id, "interval": "1d", "fidelity": 60}
        )

        if resp.status_code != 200:
            log.warning(f"Polymarket: não foi possível obter histórico para {condition_id}")
            return pd.DataFrame()

        data = resp.json()
        history = data.get("history", [])
        if not history:
            return pd.DataFrame()

        df = pd.DataFrame(history)
        if "t" in df.columns:
            df["datetime"] = pd.to_datetime(df["t"], unit="s")
            df = df.set_index("datetime")
        if "p" in df.columns:
            df = df.rename(columns={"p": "probability"})

        log.info(f"Polymarket: {len(df)} preços carregados para {condition_id}")
        return df

    def get_trades(self, condition_id: str, limit: int = 500) -> pd.DataFrame:
        """Retorna trades recentes de um mercado."""
        resp = self.session.get(
            f"{self.CLOB_URL}/trades",
            params={"market": condition_id, "limit": limit}
        )
        resp.raise_for_status()
        trades = resp.json()
        return pd.DataFrame(trades) if trades else pd.DataFrame()

    def search_markets(self, query: str) -> pd.DataFrame:
        """Busca mercados por palavra-chave."""
        resp = self.session.get(
            f"{self.GAMMA_URL}/markets",
            params={"search": query, "limit": 50}
        )
        resp.raise_for_status()
        markets = resp.json()
        return pd.DataFrame(markets) if markets else pd.DataFrame()


# ─────────────────────────────────────────────
# FRED — Dados Macroeconômicos
# ─────────────────────────────────────────────

class FREDFetcher:
    """
    Federal Reserve Economic Data — banco central de dados macro dos EUA.
    Requer API key gratuita: https://fred.stlouisfed.org/docs/api/api_key.html

    Séries úteis para trading:
      DFF     → Fed Funds Rate (diário)
      T10YIE  → Breakeven 10y (inflação implícita)
      VIXCLS  → VIX
      DTWEXBGS → DXY (índice do dólar)
      BAMLH0A0HYM2 → High Yield Spread
    """

    BASE_URL = "https://api.stlouisfed.org/fred"
    USEFUL_SERIES = {
        "fed_funds_rate": "DFF",
        "inflation_breakeven_10y": "T10YIE",
        "vix": "VIXCLS",
        "dollar_index": "DTWEXBGS",
        "hy_spread": "BAMLH0A0HYM2",
        "unemployment": "UNRATE",
        "cpi": "CPIAUCSL",
        "yield_10y": "DGS10",
        "yield_2y": "DGS2",
        "yield_curve_2_10": "T10Y2Y",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            log.warning("FRED: sem API key. Obtenha gratuitamente em fred.stlouisfed.org")

    def fetch_series(self, series_id: str, start: Optional[str] = None,
                     end: Optional[str] = None) -> pd.DataFrame:
        """Baixa uma série temporal do FRED."""
        if not self.api_key:
            raise ValueError("FRED_API_KEY não configurada")

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end

        resp = requests.get(f"{self.BASE_URL}/series/observations", params=params)
        resp.raise_for_status()

        obs = resp.json().get("observations", [])
        df = pd.DataFrame(obs)[["date", "value"]]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df.columns = [series_id.lower()]

        return df.dropna()

    def fetch_macro_dashboard(self, start: str = "2020-01-01") -> pd.DataFrame:
        """Baixa todas as séries macro úteis de uma vez."""
        dfs = []
        for name, series_id in self.USEFUL_SERIES.items():
            try:
                df = self.fetch_series(series_id, start=start)
                df.columns = [name]
                dfs.append(df)
                time.sleep(0.1)  # Respeita rate limit
            except Exception as e:
                log.warning(f"FRED: erro ao baixar {name} ({series_id}): {e}")

        if dfs:
            return pd.concat(dfs, axis=1).sort_index()
        return pd.DataFrame()


# ─────────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL
# ─────────────────────────────────────────────

class DataFetcher:
    """
    Orquestrador que seleciona automaticamente a fonte correta
    e normaliza a saída em um formato padrão.
    """

    def __init__(self):
        self.yfinance = None
        self.crypto = None
        self.kalshi = None
        self.polymarket = None
        self.fred = None

    def _get_yfinance(self):
        if not self.yfinance:
            self.yfinance = YFinanceFetcher()
        return self.yfinance

    def _get_crypto(self):
        if not self.crypto:
            self.crypto = CryptoFetcher(
                exchange_id="binance",
                api_key=os.getenv("BINANCE_API_KEY"),
                secret=os.getenv("BINANCE_SECRET")
            )
        return self.crypto

    def _get_kalshi(self):
        if not self.kalshi:
            self.kalshi = KalshiFetcher()
        return self.kalshi

    def _get_polymarket(self):
        if not self.polymarket:
            self.polymarket = PolymarketFetcher()
        return self.polymarket

    def _get_fred(self):
        if not self.fred:
            self.fred = FREDFetcher()
        return self.fred

    def fetch(self, source: str, symbol: str, period: str = "1y",
              interval: str = "1d", **kwargs) -> pd.DataFrame:
        """
        Interface unificada de coleta de dados.

        Args:
            source: 'yfinance', 'binance', 'kalshi', 'polymarket', 'fred', 'auto'
            symbol: Símbolo do ativo
            period: Período histórico
            interval: Granularidade temporal
        """
        log.info(f"DataFetcher: [{source}] {symbol} | {period} @ {interval}")

        if source == "auto":
            source = self._detect_source(symbol)

        if source == "yfinance":
            df = self._get_yfinance().fetch(symbol, period=period, interval=interval)
            save_data(df, "equities", symbol, period, interval)

        elif source in ["binance", "ccxt", "crypto"]:
            # Converte período para timestamp
            start_dt, _ = parse_period(period)
            since_ms = int(start_dt.timestamp() * 1000)
            df = self._get_crypto().fetch_ohlcv(
                symbol, timeframe=interval, since=since_ms
            )
            save_data(df, "crypto", symbol, period, interval)

        elif source == "kalshi":
            df = self._get_kalshi().get_market_history(symbol)
            save_data(df, "prediction/kalshi", symbol, period, "tick")

        elif source == "polymarket":
            df = self._get_polymarket().get_market_prices(symbol)
            save_data(df, "prediction/polymarket", symbol, period, "1d")

        elif source == "fred":
            start_dt, end_dt = parse_period(period)
            df = self._get_fred().fetch_series(
                symbol,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d")
            )
            save_data(df, "macro", symbol, period, interval)

        else:
            raise ValueError(f"Fonte desconhecida: {source}. Use: yfinance, binance, kalshi, polymarket, fred")

        # Exibe resumo
        summary = describe_data(df, symbol)
        log.info(f"Resumo: {json.dumps(summary, default=str, indent=2)}")
        return df

    def _detect_source(self, symbol: str) -> str:
        """Detecta automaticamente a fonte com base no formato do símbolo."""
        if "/" in symbol and any(c in symbol for c in ["BTC", "ETH", "USDT", "BNB"]):
            return "binance"
        elif symbol.startswith("kalshi:"):
            return "kalshi"
        elif symbol.startswith("polymarket:"):
            return "polymarket"
        else:
            return "yfinance"

    def test_connections(self) -> Dict[str, bool]:
        """Testa a conectividade com todas as fontes disponíveis."""
        results = {}

        # yfinance
        try:
            df = YFinanceFetcher().fetch("SPY", period="5d", interval="1d")
            results["yfinance"] = len(df) > 0
        except Exception as e:
            results["yfinance"] = False
            log.error(f"yfinance FALHOU: {e}")

        # Binance/CCXT
        try:
            crypto = CryptoFetcher()
            df = crypto.fetch_ohlcv("BTC/USDT", timeframe="1d",
                                    since=int((datetime.now() - timedelta(days=7)).timestamp() * 1000),
                                    paginate=False, limit=7)
            results["binance"] = len(df) > 0
        except Exception as e:
            results["binance"] = False
            log.error(f"Binance FALHOU: {e}")

        # Kalshi
        try:
            kalshi = KalshiFetcher()
            df = kalshi.get_markets(limit=5)
            results["kalshi"] = len(df) > 0
        except Exception as e:
            results["kalshi"] = False
            log.error(f"Kalshi FALHOU: {e}")

        # Polymarket
        try:
            poly = PolymarketFetcher()
            df = poly.get_markets(limit=5)
            results["polymarket"] = len(df) > 0
        except Exception as e:
            results["polymarket"] = False
            log.error(f"Polymarket FALHOU: {e}")

        print("\n" + "="*40)
        print("TESTE DE CONEXÕES:")
        for source, ok in results.items():
            status = "✅ OK" if ok else "❌ FALHOU"
            print(f"  {source:20s} {status}")
        print("="*40 + "\n")

        return results


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="QuantResearch Agent — Data Fetcher",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", default="auto",
                        choices=["auto", "yfinance", "binance", "kalshi", "polymarket", "fred"],
                        help="Fonte de dados")
    parser.add_argument("--symbol", help="Símbolo do ativo (ex: AAPL, BTC/USDT)")
    parser.add_argument("--period", default="1y",
                        help="Período (ex: 30d, 6mo, 2y, max)")
    parser.add_argument("--interval", default="1d",
                        help="Granularidade (ex: 1m, 15m, 1h, 1d)")
    parser.add_argument("--test", action="store_true",
                        help="Testa conectividade com todas as fontes")
    parser.add_argument("--list-crypto-markets", action="store_true",
                        help="Lista pares disponíveis na Binance")
    parser.add_argument("--search-kalshi", metavar="QUERY",
                        help="Busca mercados no Kalshi")
    parser.add_argument("--search-polymarket", metavar="QUERY",
                        help="Busca mercados no Polymarket")

    args = parser.parse_args()
    fetcher = DataFetcher()

    if args.test:
        fetcher.test_connections()
        return

    if args.list_crypto_markets:
        markets = fetcher._get_crypto().get_markets("USDT")
        print(f"\n{len(markets)} pares USDT na Binance:")
        for m in markets[:50]:
            print(f"  {m}")
        return

    if args.search_kalshi:
        df = fetcher._get_kalshi().search_markets(args.search_kalshi)
        print(df[["ticker", "title", "yes_bid", "yes_ask", "volume"]].to_string())
        return

    if args.search_polymarket:
        df = fetcher._get_polymarket().search_markets(args.search_polymarket)
        print(df[["question", "conditionId", "volume"]].to_string() if not df.empty else "Nenhum resultado")
        return

    if not args.symbol:
        parser.error("--symbol é obrigatório (exceto com --test)")

    df = fetcher.fetch(args.source, args.symbol, args.period, args.interval)
    print(f"\n✅ {len(df)} registros baixados para {args.symbol}")
    print(df.tail())


if __name__ == "__main__":
    main()
