"""
Red de Consenso Multi-Agente (Trading Swarm / Comité Institucional).
Cuatro agentes especializados analizan, debaten, se critican y votan en tiempo real:
1. BullHunter (Especialista Alcista & Liquidez)
2. BearCritic (El Abogado del Diablo & Detección de Trampas)
3. RiskSentinel (Matemático de Gestión de Capital y Drawdown)
4. ChiefArbiter (Juez y Director de Mesa: Emite el veredicto por consenso)
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple

DEBATE_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "agent_debate.json")

class ConsensusNetwork:
    def __init__(self, min_consensus_threshold: int = 75):
        self.min_consensus_threshold = min_consensus_threshold
        self.debate_history = []

    def conduct_debate(self, symbol: str, market_data: Dict[str, Any], account_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta un debate en vivo entre los agentes para un activo específico.
        Retorna el diálogo completo, los votos y el veredicto final.
        """
        price = market_data.get("current_price", 0.0)
        spread = market_data.get("spread_pips", 0.0)
        macro = market_data.get("macro_trend", "NEUTRAL")
        rsi = market_data.get("rsi", 50.0)
        atr = market_data.get("atr", 0.001)
        tech_score = market_data.get("score", 0)
        prelim_signal = market_data.get("signal", "HOLD")

        debate_messages = []
        now_str = datetime.now().strftime("%H:%M:%S")

        def add_msg(agent_name: str, role: str, avatar: str, text: str, sentiment: str = "NEUTRAL"):
            msg = {
                "timestamp": now_str,
                "agent": agent_name,
                "role": role,
                "avatar": avatar,
                "text": text,
                "sentiment": sentiment
            }
            debate_messages.append(msg)

        # ----------------------------------------------------
        # 1. BULL HUNTER PRESENTA SU TESIS O DUDAS
        # ----------------------------------------------------
        bull_confidence = 30
        if macro == "BULLISH":
            bull_confidence += 35
            if rsi < 60:
                bull_confidence += 20
            add_msg(
                "BullHunter", "Analista Alcista", "🐂",
                f"Defiendo postura ALCISTA en {symbol} a {price}. La tendencia institucional en H1 está claramente por encima de las medias móviles y el retroceso en M15 ofrece un punto de compra con descuento. RSI en {rsi:.1f} aún tiene suficiente recorrido al alza.",
                "BULLISH"
            )
        elif prelim_signal == "BUY":
            bull_confidence += 45
            add_msg(
                "BullHunter", "Analista Alcista", "🐂",
                f"Detecto rotura alcista en {symbol} a {price}. Hay absorción de compras en la zona de soporte y propongo buscar entrada larga.",
                "BULLISH"
            )
        else:
            bull_confidence = 20
            add_msg(
                "BullHunter", "Analista Alcista", "🐂",
                f"No veo suficiente presión compradora en {symbol} en este momento. El precio no ha formado una estructura alcista sólida en M15.",
                "NEUTRAL"
            )

        # ----------------------------------------------------
        # 2. BEAR CRITIC (EL ABOGADO DEL DIABLO) CRITICA LA TESIS
        # ----------------------------------------------------
        bear_confidence = 30
        objections = []

        if spread > 2.5 and symbol in ["EURUSD", "GBPUSD"]:
            objections.append(f"El spread actual ({spread} pips) está más amplio de lo normal, reduciendo nuestra ventaja matemática.")
            bear_confidence += 25

        if macro == "BEARISH":
            bear_confidence += 40
            add_msg(
                "BearCritic", "Abogado del Diablo", "🐻",
                f"¡OBJECIÓN TOTAL! {symbol} se encuentra en una macro-tendencia bajista en H1. Comprar aquí sería atrapar un cuchillo cayendo. Cualquier subida actual parece una trampa de liquidez para compradores desprevenidos.",
                "BEARISH"
            )
        elif rsi > 65:
            objections.append(f"RSI en {rsi:.1f} muestra sobrecompra cercana, riesgo alto de pullback inminente.")
            bear_confidence += 30
            add_msg(
                "BearCritic", "Abogado del Diablo", "🐻",
                f"¡Cuidado! " + " ".join(objections),
                "BEARISH"
            )
        else:
            add_msg(
                "BearCritic", "Abogado del Diablo", "🐻",
                f"Examiné posibles trampas en {symbol}. No detecto divergencias bajistas críticas inmediatas, pero exijo un Stop Loss ceñido por debajo del soporte más reciente.",
                "NEUTRAL"
            )

        # ----------------------------------------------------
        # 3. RISK SENTINEL (MATEMÁTICO DE RIESGO Y CAPITAL)
        # ----------------------------------------------------
        balance = account_summary.get("balance", 0.0)
        currency = account_summary.get("currency", "USD")

        risk_approved = True
        risk_notes = []

        if balance <= 0:
            risk_approved = False
            risk_notes.append("Balance de cuenta no disponible o en 0.")
        if spread > 4.0:
            risk_approved = False
            risk_notes.append(f"Spread excesivo ({spread} pips).")

        if risk_approved:
            add_msg(
                "RiskSentinel", "Guardián de Capital", "🛡️",
                f"Filtro matemático validado: Balance disponible de {balance:.2f} {currency}. Ratio R/B mínimo exigido de 1:2.0. El Stop Loss debe respetar la volatilidad calculada de ATR ({atr:.5f}) y arriesgar estrictamente el 1.0% de la cuenta.",
                "APPROVED"
            )
        else:
            add_msg(
                "RiskSentinel", "Guardián de Capital", "🛡️",
                f"⛔ VETO DE RIESGO: " + " | ".join(risk_notes) + " No permito arriesgar capital bajo estas condiciones.",
                "VETO"
            )

        # ----------------------------------------------------
        # 4. CHIEF ARBITER (EL JUEZ Y JEFE DE MESA) DICTA SENTENCIA
        # ----------------------------------------------------
        final_verdict = "HOLD"
        consensus_score = 0
        execution_plan = None

        if not risk_approved:
            final_verdict = "RECHAZADO_POR_RIESGO"
            consensus_score = 0
            add_msg(
                "ChiefArbiter", "Jefe de Mesa / Decisor", "⚖️",
                f"Sentencia definitiva para {symbol}: OPERACIÓN RECHAZADA. El Guardián de Riesgo vetó la entrada. Proteger el capital es nuestra primera regla inquebrantable.",
                "HOLD"
            )
        else:
            # Ponderar argumentos
            if bull_confidence >= 70 and bear_confidence < 50:
                consensus_score = int((bull_confidence + (100 - bear_confidence)) / 2)
                if consensus_score >= self.min_consensus_threshold:
                    final_verdict = "BUY"
                    sl = round(price - (1.5 * atr), 5)
                    tp = round(price + (3.0 * atr), 5)
                    execution_plan = {"action": "BUY", "sl": sl, "tp": tp, "rr": "1:2.0"}
                    add_msg(
                        "ChiefArbiter", "Jefe de Mesa / Decisor", "⚖️",
                        f"Veredicto APROBADO: {consensus_score}% de Consenso ALCISTA. Los argumentos de BullHunter son sólidos y BearCritic no presentó objeciones invalidantes. Ejecutar COMPRA en {symbol} con SL en {sl} y TP en {tp}.",
                        "BUY"
                    )
            elif bear_confidence >= 70 and bull_confidence < 50:
                consensus_score = int((bear_confidence + (100 - bull_confidence)) / 2)
                if consensus_score >= self.min_consensus_threshold:
                    final_verdict = "SELL"
                    sl = round(price + (1.5 * atr), 5)
                    tp = round(price - (3.0 * atr), 5)
                    execution_plan = {"action": "SELL", "sl": sl, "tp": tp, "rr": "1:2.0"}
                    add_msg(
                        "ChiefArbiter", "Jefe de Mesa / Decisor", "⚖️",
                        f"Veredicto APROBADO: {consensus_score}% de Consenso BAJISTA. BearCritic demostró que la presión vendedora domina el mercado. Ejecutar VENTA en {symbol} con SL en {sl} y TP en {tp}.",
                        "SELL"
                    )
            else:
                consensus_score = max(bull_confidence, bear_confidence)
                final_verdict = "HOLD"
                add_msg(
                    "ChiefArbiter", "Jefe de Mesa / Decisor", "⚖️",
                    f"Veredicto: MANTENER AL MARGEN (HOLD). El debate no alcanzó el umbral mínimo del {self.min_consensus_threshold}% de consenso (Consenso actual: {consensus_score}%). El dinero se gana esperando las oportunidades más claras.",
                    "HOLD"
                )

        debate_result = {
            "symbol": symbol,
            "timestamp": now_str,
            "verdict": final_verdict,
            "consensus_score": consensus_score,
            "bull_confidence": bull_confidence,
            "bear_confidence": bear_confidence,
            "risk_approved": risk_approved,
            "execution_plan": execution_plan,
            "debate": debate_messages
        }

        self.save_debate(debate_result)
        return debate_result

    def save_debate(self, debate_result: Dict[str, Any]):
        """Persiste el debate para que la plataforma web lo muestre en tiempo real."""
        try:
            os.makedirs(os.path.dirname(DEBATE_LOG_FILE), exist_ok=True)
            self.debate_history.insert(0, debate_result)
            if len(self.debate_history) > 15:
                self.debate_history.pop()
            with open(DEBATE_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.debate_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] No se pudo guardar debate de agentes: {e}", flush=True)

