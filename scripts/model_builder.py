"""
QuantResearch Agent — Model Builder
=====================================
Módulo de construção de modelos quantitativos para trading.

Modelos disponíveis:
  1. XGBoost / LightGBM — Classificação (direção) e regressão (retorno)
  2. LSTM — Redes neurais recorrentes para séries temporais
  3. ARIMA / GARCH — Modelos clássicos (volatilidade, média condicional)
  4. Regime Detection — HMM (Hidden Markov Model) para regimes de mercado
  5. Feature Engineering — Cálculo automático de features técnicas + macro

Uso:
  python model_builder.py --model xgboost --symbol BTC-USD --target direction
  python model_builder.py --model regime --symbol SPY --n-regimes 3
  python model_builder.py --model garch --symbol BTC-USD --forecast 10
"""

import os
import json
import pickle
import logging
import argparse
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, classification_report,
    mean_absolute_error, mean_squared_error
)
from sklearn.ensemble import RandomForestClassifier

warnings.filterwarnings("ignore")
log = logging.getLogger("ModelBuilder")

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────

class FeatureEngineer:
    """
    Gera features técnicas e estatísticas automaticamente.
    Design: todas as features são calculadas com shift(1) para evitar look-ahead bias.
    """

    def create_features(self, df: pd.DataFrame,
                        include_volume: bool = True,
                        include_macro: bool = False) -> pd.DataFrame:
        """
        Gera conjunto completo de features a partir de OHLCV.

        Args:
            df: DataFrame com colunas open, high, low, close, volume
            include_volume: Incluir features de volume
            include_macro: Incluir features macro (requer coluna 'vix', etc.)
        """
        feat = pd.DataFrame(index=df.index)

        close = df["close"]
        high = df.get("high", close)
        low = df.get("low", close)
        volume = df.get("volume", pd.Series(1, index=df.index))

        # ── Retornos ──────────────────────────────
        for w in [1, 2, 3, 5, 10, 20, 60]:
            feat[f"ret_{w}d"] = close.pct_change(w)

        # ── Momentum ─────────────────────────────
        for w in [5, 10, 20, 60, 120]:
            feat[f"mom_{w}d"] = close / close.shift(w) - 1

        # ── Médias Móveis ────────────────────────
        for w in [5, 10, 20, 50, 100, 200]:
            sma = close.rolling(w).mean()
            feat[f"sma_{w}_ratio"] = close / sma - 1  # Distância da SMA

        # Cruzamentos de médias
        feat["sma_5_20_cross"] = (close.rolling(5).mean() > close.rolling(20).mean()).astype(int)
        feat["sma_20_50_cross"] = (close.rolling(20).mean() > close.rolling(50).mean()).astype(int)
        feat["golden_cross"] = (close.rolling(50).mean() > close.rolling(200).mean()).astype(int)

        # ── Volatilidade ──────────────────────────
        for w in [5, 10, 20, 60]:
            feat[f"vol_{w}d"] = close.pct_change().rolling(w).std() * np.sqrt(252)

        # Volatilidade realizada (Parkinson)
        if "high" in df.columns and "low" in df.columns:
            parkinson = np.sqrt(
                (np.log(df["high"] / df["low"]) ** 2).rolling(20).mean() / (4 * np.log(2))
            ) * np.sqrt(252)
            feat["vol_parkinson"] = parkinson

        # Volatility regime: vol atual vs. média histórica
        feat["vol_regime"] = (feat["vol_20d"] / feat["vol_20d"].rolling(252).mean())

        # ── RSI ──────────────────────────────────
        for w in [7, 14, 21]:
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(w).mean()
            loss = (-delta.clip(upper=0)).rolling(w).mean()
            rs = gain / loss.replace(0, np.nan)
            feat[f"rsi_{w}"] = 100 - (100 / (1 + rs))
            feat[f"rsi_{w}_zscore"] = (feat[f"rsi_{w}"] - feat[f"rsi_{w}"].rolling(252).mean()) / \
                                       feat[f"rsi_{w}"].rolling(252).std()

        # ── Bollinger Bands ───────────────────────
        for w in [20]:
            bb_mid = close.rolling(w).mean()
            bb_std = close.rolling(w).std()
            feat[f"bb_upper_dist"] = (close - (bb_mid + 2 * bb_std)) / close
            feat[f"bb_lower_dist"] = (close - (bb_mid - 2 * bb_std)) / close
            feat[f"bb_width"] = (4 * bb_std) / bb_mid
            feat[f"bb_position"] = (close - (bb_mid - 2 * bb_std)) / (4 * bb_std)

        # ── MACD ─────────────────────────────────
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        feat["macd"] = macd / close  # Normalizado pelo preço
        feat["macd_signal"] = signal / close
        feat["macd_hist"] = (macd - signal) / close
        feat["macd_cross"] = (macd > signal).astype(int)

        # ── ATR e Range ───────────────────────────
        if "high" in df.columns and "low" in df.columns:
            tr = pd.concat([
                df["high"] - df["low"],
                (df["high"] - close.shift(1)).abs(),
                (df["low"] - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            atr = tr.ewm(span=14, adjust=False).mean()
            feat["atr_ratio"] = atr / close
            feat["daily_range"] = (df["high"] - df["low"]) / close

        # ── Volume ────────────────────────────────
        if include_volume and "volume" in df.columns:
            vol_sma = volume.rolling(20).mean()
            feat["volume_ratio"] = volume / vol_sma
            feat["volume_trend"] = vol_sma / vol_sma.shift(10)

            # OBV simplificado
            direction = np.sign(close.pct_change())
            obv = (volume * direction).cumsum()
            feat["obv_slope"] = (obv / obv.shift(10) - 1)

        # ── Padrões de Candlestick ────────────────
        if "open" in df.columns:
            body = (close - df["open"]).abs() / close
            feat["doji"] = (body < 0.001).astype(int)
            feat["body_size"] = (close - df["open"]) / close
            feat["upper_shadow"] = (df["high"] - pd.concat([close, df["open"]], axis=1).max(axis=1)) / close
            feat["lower_shadow"] = (pd.concat([close, df["open"]], axis=1).min(axis=1) - df["low"]) / close

        # ── Sazonalidade ─────────────────────────
        feat["day_of_week"] = df.index.dayofweek
        feat["month"] = df.index.month
        feat["quarter"] = df.index.quarter

        # ── Shift para evitar look-ahead bias ────
        feat = feat.shift(1)

        return feat.replace([np.inf, -np.inf], np.nan)

    def create_targets(self, df: pd.DataFrame,
                       horizon: int = 1,
                       target_type: str = "direction") -> pd.Series:
        """
        Cria variável alvo.

        Args:
            horizon: Quantos períodos à frente prever
            target_type: 'direction' (0/1), 'return' (float), 'quantile' (0/1/2)
        """
        future_ret = df["close"].pct_change(horizon).shift(-horizon)

        if target_type == "direction":
            return (future_ret > 0).astype(int)
        elif target_type == "return":
            return future_ret
        elif target_type == "quantile":
            q33 = future_ret.quantile(0.33)
            q67 = future_ret.quantile(0.67)
            return pd.cut(future_ret, bins=[-np.inf, q33, q67, np.inf],
                          labels=[0, 1, 2]).astype(float)
        else:
            raise ValueError(f"target_type inválido: {target_type}")


# ─────────────────────────────────────────────
# MODELO XGBOOST / LIGHTGBM
# ─────────────────────────────────────────────

class GradientBoostingModel:
    """
    Modelo de gradient boosting para classificação/regressão.
    Usa XGBoost por padrão (LightGBM como alternativa).
    Validação com TimeSeriesSplit para respeitar ordem temporal.
    """

    def __init__(self, task: str = "classification",
                 model_type: str = "xgboost",
                 n_splits: int = 5):
        self.task = task
        self.model_type = model_type
        self.n_splits = n_splits
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.metrics: Dict = {}

    def _build_model(self, params: Dict = None):
        """Constrói o modelo com hiperparâmetros."""
        default_params = {
            "n_estimators": 500,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "n_jobs": -1,
        }
        if params:
            default_params.update(params)

        if self.model_type == "xgboost":
            try:
                from xgboost import XGBClassifier, XGBRegressor
                ModelClass = XGBClassifier if self.task == "classification" else XGBRegressor
                default_params["eval_metric"] = "logloss" if self.task == "classification" else "rmse"
                default_params["use_label_encoder"] = False
                return ModelClass(**default_params)
            except ImportError:
                log.warning("xgboost não instalado. Usando RandomForest.")
                return RandomForestClassifier(n_estimators=200, max_depth=4, random_state=42, n_jobs=-1)

        elif self.model_type == "lightgbm":
            try:
                from lightgbm import LGBMClassifier, LGBMRegressor
                ModelClass = LGBMClassifier if self.task == "classification" else LGBMRegressor
                default_params["verbose"] = -1
                return ModelClass(**default_params)
            except ImportError:
                log.warning("lightgbm não instalado. Usando RandomForest.")
                return RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)

    def fit(self, X: pd.DataFrame, y: pd.Series,
            params: Dict = None) -> Dict:
        """
        Treina com validação temporal walk-forward.

        Returns:
            Dict com métricas de validação
        """
        self.feature_names = list(X.columns)

        # Remove NaN
        mask = ~(X.isnull().any(axis=1) | y.isnull())
        X_clean = X[mask]
        y_clean = y[mask]

        log.info(f"Treinando {self.model_type} | {len(X_clean)} amostras | {len(self.feature_names)} features")

        # Walk-forward cross-validation
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        cv_scores = []

        for fold, (train_idx, test_idx) in enumerate(tscv.split(X_clean)):
            X_train, X_test = X_clean.iloc[train_idx], X_clean.iloc[test_idx]
            y_train, y_test = y_clean.iloc[train_idx], y_clean.iloc[test_idx]

            # Normaliza features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            model = self._build_model(params)
            model.fit(X_train_scaled, y_train)

            y_pred = model.predict(X_test_scaled)

            if self.task == "classification":
                score = accuracy_score(y_test, y_pred)
                cv_scores.append(score)
                log.info(f"  Fold {fold+1}: accuracy = {score:.3f}")
            else:
                score = mean_absolute_error(y_test, y_pred)
                cv_scores.append(-score)  # Negativo para consistência (maior = melhor)
                log.info(f"  Fold {fold+1}: MAE = {score:.5f}")

        # Treina modelo final em todos os dados
        X_scaled = self.scaler.fit_transform(X_clean)
        self.model = self._build_model(params)
        self.model.fit(X_scaled, y_clean)

        self.metrics = {
            "cv_scores": cv_scores,
            "cv_mean": np.mean(cv_scores),
            "cv_std": np.std(cv_scores),
            "n_samples": len(X_clean),
            "n_features": len(self.feature_names),
        }

        log.info(f"CV Score: {np.mean(cv_scores):.3f} ± {np.std(cv_scores):.3f}")
        return self.metrics

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Gera previsões para novos dados."""
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Probabilidades de classe (apenas classificação)."""
        if not hasattr(self.model, "predict_proba"):
            raise ValueError("Modelo não suporta probabilidades")
        X_scaled = self.scaler.transform(X[self.feature_names])
        return self.model.predict_proba(X_scaled)

    def get_feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """Retorna as features mais importantes."""
        if not hasattr(self.model, "feature_importances_"):
            return pd.DataFrame()

        importance = pd.DataFrame({
            "feature": self.feature_names,
            "importance": self.model.feature_importances_
        }).sort_values("importance", ascending=False)

        return importance.head(top_n)

    def save(self, path: Optional[Path] = None) -> Path:
        """Salva modelo em disco."""
        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = MODELS_DIR / f"gbm_{self.model_type}_{ts}.pkl"

        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler,
                         "features": self.feature_names, "metrics": self.metrics}, f)
        log.info(f"Modelo salvo: {path}")
        return path

    @classmethod
    def load(cls, path: Path) -> "GradientBoostingModel":
        """Carrega modelo do disco."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        instance = cls()
        instance.model = data["model"]
        instance.scaler = data["scaler"]
        instance.feature_names = data["features"]
        instance.metrics = data["metrics"]
        return instance


# ─────────────────────────────────────────────
# REGIME DETECTION (Hidden Markov Model)
# ─────────────────────────────────────────────

class RegimeDetector:
    """
    Detecta regimes de mercado usando Hidden Markov Model.
    Regimes típicos:
      - Bull/Crescimento: alto retorno, baixa volatilidade
      - Bear/Queda: baixo retorno, alta volatilidade
      - Sideways/Lateral: retorno próximo a zero, vol média
    """

    def __init__(self, n_regimes: int = 3):
        self.n_regimes = n_regimes
        self.model = None
        self.regime_stats = {}

    def fit(self, df: pd.DataFrame) -> pd.Series:
        """
        Treina HMM e retorna série de regimes detectados.

        Returns:
            pd.Series com label do regime (0, 1, 2, ...)
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            log.warning("hmmlearn não instalado. Usando K-Means como alternativa.")
            return self._fit_kmeans(df)

        # Features: retorno logarítmico e volatilidade realizada
        log_ret = np.log(df["close"] / df["close"].shift(1)).dropna()
        vol = log_ret.rolling(5).std()

        features = pd.concat([log_ret, vol], axis=1).dropna()
        features.columns = ["log_return", "volatility"]

        X = features.values
        X_scaled = (X - X.mean(axis=0)) / X.std(axis=0)

        self.model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=42
        )
        self.model.fit(X_scaled)

        hidden_states = pd.Series(
            self.model.predict(X_scaled),
            index=features.index,
            name="regime"
        )

        # Calcula estatísticas por regime
        for regime in range(self.n_regimes):
            mask = hidden_states == regime
            regime_rets = features.loc[mask, "log_return"]
            self.regime_stats[regime] = {
                "mean_return": regime_rets.mean() * 252,
                "volatility": regime_rets.std() * np.sqrt(252),
                "count": int(mask.sum()),
                "pct": round(mask.mean() * 100, 1)
            }

        self._label_regimes()
        log.info(f"Regimes detectados: {self.regime_stats}")
        return hidden_states

    def _fit_kmeans(self, df: pd.DataFrame) -> pd.Series:
        """Alternativa ao HMM usando K-Means."""
        from sklearn.cluster import KMeans

        log_ret = np.log(df["close"] / df["close"].shift(1))
        vol = log_ret.rolling(20).std()
        trend = (df["close"] / df["close"].rolling(50).mean() - 1)

        features = pd.concat([log_ret, vol, trend], axis=1).dropna()
        features.columns = ["return", "vol", "trend"]

        scaler = StandardScaler()
        X = scaler.fit_transform(features)

        km = KMeans(n_clusters=self.n_regimes, random_state=42, n_init=10)
        labels = pd.Series(km.fit_predict(X), index=features.index, name="regime")

        for regime in range(self.n_regimes):
            mask = labels == regime
            rets = features.loc[mask, "return"]
            self.regime_stats[regime] = {
                "mean_return": rets.mean() * 252,
                "volatility": rets.std() * np.sqrt(252),
                "count": int(mask.sum()),
                "pct": round(mask.mean() * 100, 1)
            }

        self.model = km
        self._label_regimes()
        return labels

    def _label_regimes(self):
        """Rotula regimes como bull/bear/sideways baseado nas estatísticas."""
        sorted_regimes = sorted(
            self.regime_stats.items(),
            key=lambda x: x[1]["mean_return"],
            reverse=True
        )
        labels = {
            0: ["bull 🐂", "neutral ↔", "bear 🐻"],
            1: ["bull 🐂", "sideways ↔", "bear 🐻"],
        }.get(self.n_regimes - 2, [str(i) for i in range(self.n_regimes)])

        for i, (regime, stats) in enumerate(sorted_regimes):
            self.regime_stats[regime]["label"] = labels[min(i, len(labels)-1)]

    def print_summary(self):
        """Imprime resumo dos regimes."""
        print("\n📊 REGIMES DE MERCADO DETECTADOS:")
        for regime, stats in sorted(self.regime_stats.items()):
            label = stats.get("label", str(regime))
            print(f"  Regime {regime} ({label}):")
            print(f"    Retorno anual médio: {stats['mean_return']*100:.1f}%")
            print(f"    Volatilidade:        {stats['volatility']*100:.1f}%")
            print(f"    Frequência:          {stats['pct']:.1f}% do tempo")


# ─────────────────────────────────────────────
# MODELOS DE VOLATILIDADE (GARCH)
# ─────────────────────────────────────────────

class VolatilityModel:
    """
    Modelos GARCH para previsão de volatilidade.
    Útil para: sizing de posições, precificação de opções, VaR dinâmico.
    """

    def __init__(self, p: int = 1, q: int = 1, dist: str = "normal"):
        self.p = p  # Ordem GARCH
        self.q = q  # Ordem ARCH
        self.dist = dist  # 'normal', 't', 'skewt'
        self.model = None
        self.fit_result = None

    def fit(self, returns: pd.Series) -> Dict:
        """Treina modelo GARCH."""
        try:
            from arch import arch_model
        except ImportError:
            log.error("arch não instalado. Execute: pip install arch")
            return {}

        log.info(f"Treinando GARCH({self.p},{self.q}) com distribuição {self.dist}")
        self.model = arch_model(
            returns * 100,  # em percentual para estabilidade numérica
            vol="GARCH",
            p=self.p, q=self.q,
            dist=self.dist
        )
        self.fit_result = self.model.fit(disp="off", show_warning=False)
        log.info(f"GARCH log-likelihood: {self.fit_result.loglikelihood:.2f}")
        return self.fit_result.summary().as_text()

    def forecast(self, horizon: int = 10) -> pd.DataFrame:
        """Prevê volatilidade para os próximos N períodos."""
        if not self.fit_result:
            raise ValueError("Execute fit() primeiro")

        fc = self.fit_result.forecast(horizon=horizon, reindex=False)
        vol_forecast = np.sqrt(fc.variance.dropna().values[-1]) / 100  # de volta para fração

        return pd.DataFrame({
            "horizon": range(1, horizon + 1),
            "volatility_daily": vol_forecast,
            "volatility_annual": vol_forecast * np.sqrt(252)
        })


# ─────────────────────────────────────────────
# PIPELINE COMPLETO
# ─────────────────────────────────────────────

class QuantModelPipeline:
    """
    Pipeline end-to-end: dados → features → modelo → previsão.
    Interface de alto nível para uso no agente.
    """

    def __init__(self, symbol: str, model_type: str = "xgboost",
                 target_type: str = "direction", horizon: int = 1):
        self.symbol = symbol
        self.model_type = model_type
        self.target_type = target_type
        self.horizon = horizon
        self.feature_engineer = FeatureEngineer()
        self.model = GradientBoostingModel(
            task="classification" if target_type == "direction" else "regression",
            model_type=model_type
        )

    def run(self, df: pd.DataFrame) -> Dict:
        """
        Executa pipeline completo.

        Returns:
            Dict com métricas, importância de features e previsão atual
        """
        log.info(f"Pipeline: {self.symbol} | {self.model_type} | target={self.target_type}")

        # 1. Feature engineering
        X = self.feature_engineer.create_features(df)
        y = self.feature_engineer.create_targets(df, self.horizon, self.target_type)

        # 2. Alinhamento e limpeza
        common_idx = X.dropna().index.intersection(y.dropna().index)
        X = X.loc[common_idx]
        y = y.loc[common_idx]

        # 3. Train/Test split temporal (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        # 4. Treina
        cv_metrics = self.model.fit(X_train, y_train)

        # 5. Avalia no test set
        y_pred = self.model.predict(X_test)
        test_metrics = {}
        if self.target_type == "direction":
            test_metrics["test_accuracy"] = round(accuracy_score(y_test, y_pred), 4)
            test_metrics["test_report"] = classification_report(y_test, y_pred, output_dict=True)
        else:
            test_metrics["test_mae"] = round(mean_absolute_error(y_test, y_pred), 6)
            test_metrics["test_rmse"] = round(np.sqrt(mean_squared_error(y_test, y_pred)), 6)

        # 6. Previsão para amanhã (última linha dos dados)
        last_features = X.iloc[[-1]]
        current_prediction = {
            "signal": int(self.model.predict(last_features)[0]),
            "date": str(X.index[-1])
        }
        if self.target_type == "direction":
            proba = self.model.predict_proba(last_features)[0]
            current_prediction["probability_up"] = round(float(proba[1]), 4)
            current_prediction["probability_down"] = round(float(proba[0]), 4)
            current_prediction["confidence"] = round(float(max(proba)), 4)

        # 7. Feature importance
        fi = self.model.get_feature_importance(20)

        # 8. Salva modelo
        save_path = self.model.save(
            MODELS_DIR / f"{self.symbol}_{self.model_type}_{datetime.now().strftime('%Y%m%d')}.pkl"
        )

        results = {
            "symbol": self.symbol,
            "model": self.model_type,
            "target": self.target_type,
            "horizon": self.horizon,
            "training": {
                "n_samples": len(X_train),
                "n_features": len(X.columns),
                **cv_metrics
            },
            "test": test_metrics,
            "current_signal": current_prediction,
            "top_features": fi.to_dict("records") if not fi.empty else [],
            "model_path": str(save_path)
        }

        self._print_results(results)
        return results

    def _print_results(self, results: Dict):
        p = results["current_signal"]
        t = results["test"]

        print("\n" + "="*55)
        print(f"  MODELO: {results['model']} | {results['symbol']}")
        print("="*55)
        if "test_accuracy" in t:
            print(f"  Acurácia (test set):  {t['test_accuracy']*100:.2f}%")
        if "test_mae" in t:
            print(f"  MAE (test set):       {t['test_mae']:.5f}")
        print(f"\n  📍 SINAL ATUAL ({p['date'][:10]}):")
        print(f"     Direção: {'↑ COMPRA' if p['signal'] == 1 else '↓ VENDA'}")
        if "confidence" in p:
            print(f"     Confiança: {p['confidence']*100:.1f}%")
        print("="*55 + "\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QuantResearch — Model Builder")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--period", default="5y")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--model", default="xgboost",
                        choices=["xgboost", "lightgbm", "regime", "garch"])
    parser.add_argument("--target", default="direction",
                        choices=["direction", "return", "quantile"])
    parser.add_argument("--horizon", type=int, default=1,
                        help="Horizonte de previsão em períodos")
    parser.add_argument("--n-regimes", type=int, default=3,
                        help="Número de regimes (apenas --model regime)")

    args = parser.parse_args()

    # Carrega dados
    sys.path.insert(0, str(Path(__file__).parent))
    from data_fetcher import YFinanceFetcher
    fetcher = YFinanceFetcher()
    df = fetcher.fetch(args.symbol, period=args.period, interval=args.interval)

    if args.model == "regime":
        detector = RegimeDetector(n_regimes=args.n_regimes)
        regimes = detector.fit(df)
        detector.print_summary()

        # Salva regimes
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = MODELS_DIR / f"{args.symbol}_regimes_{ts}.csv"
        regimes.to_csv(save_path)
        print(f"\n✅ Regimes salvos em: {save_path}")

    elif args.model == "garch":
        returns = df["close"].pct_change().dropna()
        vol_model = VolatilityModel()
        vol_model.fit(returns)
        fc = vol_model.forecast(horizon=10)
        print("\n📈 Previsão de Volatilidade (GARCH):")
        print(fc.to_string(index=False))

    else:
        import sys
        pipeline = QuantModelPipeline(
            symbol=args.symbol,
            model_type=args.model,
            target_type=args.target,
            horizon=args.horizon
        )
        results = pipeline.run(df)

        # Salva resultados
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = MODELS_DIR / f"{args.symbol}_{args.model}_{ts}_results.json"
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"📋 Resultados salvos em: {json_path}")


if __name__ == "__main__":
    import sys
    main()
