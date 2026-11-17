"""
Agente Scout (Explorador de Mercado Cuantitativo).
Analiza múltiples activos en paralelo con Análisis Multi-Temporal (Macro H1 + Micro M15),
calculando confluencias matemáticas de alta probabilidad y Stop Loss / Take Profit dinámicos con ATR.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import ta

class ScoutAgent:
    def __init__(self, symbols: Optional[List[str]] = None, min_confluence_score: int = 75):
        self.symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]
        self.min_confluence_score = min_confluence_score

    def analyze_symbol(self, connector, symbol: str) -> Dict[str, Any]:
        """
        Realiza un análisis multi-temporal completo de un símbolo.
        Retorna la señal, puntaje de confluencia y niveles calculados de entrada, SL y TP.
        """
        tick = connector.get_symbol_tick(symbol)
        if not tick:
            return {"symbol": symbol, "status": "ERROR", "reason": "No se pudo obtener tick en vivo"}

        # 1. Análisis Macro (H1) para determinar la dirección institucional
        df_h1 = connector.get_ohlcv(symbol, timeframe="H1", count=100)
        if df_h1 is None or len(df_h1) < 50:
            return {"symbol": symbol, "status": "WAITING_DATA", "reason": "Datos insuficientes en H1"}

        ema50_h1 = ta.trend.ema_indicator(df_h1['close'], window=50).iloc[-1]
        ema200_h1 = ta.trend.ema_indicator(df_h1['close'], window=200 if len(df_h1) >= 200 else 50).iloc[-1]
        last_h1_close = df_h1['close'].iloc[-1]

        macro_trend = "NEUTRAL"
        if last_h1_close > ema50_h1 and ema50_h1 >= ema200_h1:
            macro_trend = "BULLISH"
        elif last_h1_close < ema50_h1 and ema50_h1 <= ema200_h1:
            macro_trend = "BEARISH"

        # 2. Análisis Micro (M15) para el punto óptimo de entrada y gatillo
        df_m15 = connector.get_ohlcv(symbol, timeframe="M15", count=100)
        if df_m15 is None or len(df_m15) < 35:
            return {"symbol": symbol, "status": "WAITING_DATA", "reason": "Datos insuficientes en M15"}

        close_series = df_m15['close']
        high_series = df_m15['high']
        low_series = df_m15['low']

        ema21 = ta.trend.ema_indicator(close_series, window=21).iloc[-1]
        ema50 = ta.trend.ema_indicator(close_series, window=50).iloc[-1]
        rsi = ta.momentum.rsi(close_series, window=14).iloc[-1]
        
        # MACD
        macd_line = ta.trend.macd(close_series).iloc[-1]
        macd_signal = ta.trend.macd_signal(close_series).iloc[-1]
        macd_diff = ta.trend.macd_diff(close_series).iloc[-1]

        # ATR para volatilidad y cálculo de SL dinámico
        atr = ta.volatility.average_true_range(high_series, low_series, close_series, window=14).iloc[-1]

        current_price = tick["bid"] if macro_trend == "BEARISH" else tick["ask"]
        recent_low = low_series.iloc[-10:].min()
        recent_high = high_series.iloc[-10:].max()

        score = 0
        reasons = []
        signal = "HOLD"
        entry_price = current_price
        sl_price = 0.0
        tp_price = 0.0

        # === EVALUACIÓN DE COMPRA (BUY) ===
        if macro_trend == "BULLISH":
            score += 30
            reasons.append("Tendencia Macro H1 Alcista (+30)")

            # Pullback a zona de valor (cerca de EMA 21 o EMA 50)
            dist_to_ema21 = abs(current_price - ema21)
            if dist_to_ema21 <= (1.2 * atr):
                score += 25
                reasons.append("Precio en zona de valor / retroceso EMA21 (+25)")

            # RSI en zona de impulso saliendo de sobreventa o neutral alcista (40 - 62)
            if 38 <= rsi <= 62:
                score += 20
                reasons.append(f"RSI saludable ({rsi:.1f}) con espacio para subir (+20)")

            # MACD con momentum positivo o cruzando al alza
            if macd_diff > 0:
                score += 15
                reasons.append("MACD histograma positivo (+15)")

            # Vela reciente M15 alcista
            if close_series.iloc[-1] >= df_m15['open'].iloc[-1]:
                score += 10
                reasons.append("Vela de confirmación alcista (+10)")

            if score >= self.min_confluence_score:
                signal = "BUY"
                # Stop Loss por debajo del mínimo reciente con margen de ATR
                sl_distance = max((current_price - recent_low) + (0.5 * atr), 1.5 * atr)
                sl_price = current_price - sl_distance
                # Take Profit 1:2
                tp_price = current_price + (2.0 * sl_distance)

        # === EVALUACIÓN DE VENTA (SELL) ===
        elif macro_trend == "BEARISH":
            score += 30
            reasons.append("Tendencia Macro H1 Bajista (+30)")

            # Retroceso a zona de resistencia dinámica (EMA 21 / EMA 50)
            dist_to_ema21 = abs(current_price - ema21)
            if dist_to_ema21 <= (1.2 * atr):
                score += 25
                reasons.append("Precio en retroceso hacia EMA21 (+25)")

            # RSI en zona neutral bajista (38 - 62)
            if 38 <= rsi <= 62:
                score += 20
                reasons.append(f"RSI saludable ({rsi:.1f}) con espacio para caer (+20)")

            # MACD con momentum negativo
            if macd_diff < 0:
                score += 15
                reasons.append("MACD histograma negativo (+15)")

            # Vela reciente M15 bajista
            if close_series.iloc[-1] <= df_m15['open'].iloc[-1]:
                score += 10
                reasons.append("Vela de confirmación bajista (+10)")

            if score >= self.min_confluence_score:
                signal = "SELL"
                # Stop Loss por encima del máximo reciente con margen de ATR
                sl_distance = max((recent_high - current_price) + (0.5 * atr), 1.5 * atr)
                sl_price = current_price + sl_distance
                # Take Profit 1:2
                tp_price = current_price - (2.0 * sl_distance)

        else:
            reasons.append("Mercado H1 en rango o consolidación neutral (esperando dirección clara)")

        return {
            "symbol": symbol,
            "status": "SCANNED",
            "signal": signal,
            "score": score,
            "macro_trend": macro_trend,
            "current_price": round(current_price, tick["digits"]),
            "entry_price": round(entry_price, tick["digits"]),
            "sl_price": round(sl_price, tick["digits"]) if sl_price > 0 else None,
            "tp_price": round(tp_price, tick["digits"]) if tp_price > 0 else None,
            "rsi": round(rsi, 1),
            "atr": round(atr, tick["digits"]),
            "spread_pips": tick["spread_pips"],
            "reasons": reasons,
            "tick_info": tick
        }

    def scan_all(self, connector) -> List[Dict[str, Any]]:
        """Escanea todos los símbolos de la lista de vigilancia."""
        results = []
        for symbol in self.symbols:
            res = self.analyze_symbol(connector, symbol)
            results.append(res)
        return results

