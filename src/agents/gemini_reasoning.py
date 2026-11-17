"""
Motor de Razonamiento e Inteligencia Artificial con Gemini (Gemini Flash con High Thinking).
Proporciona análisis cognitivo profundo para los agentes, evaluando contexto macro,
trampas de liquidez y validación de tesis de inversión antes de cualquier trade.
"""

import os
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class GeminiReasoningEngine:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.client = None
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[GEMINI] Error al inicializar cliente GenAI: {e}", flush=True)

    def is_available(self) -> bool:
        """Verifica si la API Key de Gemini está configurada."""
        return bool(self.api_key and self.client is not None)

    def analyze_opportunity_with_gemini(self, symbol: str, market_data: Dict[str, Any], technical_score: int) -> Dict[str, Any]:
        """
        Envía los datos de mercado cuantitativos a Gemini para un análisis profundo con Thinking Mode.
        """
        if not self.is_available():
            return {
                "ai_enabled": False,
                "reason": "GEMINI_API_KEY no configurada en .env. Usando motor cuantitativo puro.",
                "confidence": technical_score,
                "verdict": market_data.get("signal", "HOLD"),
                "reasoning": "Configura tu GEMINI_API_KEY en el archivo .env para activar el razonamiento cognitivo de Gemini."
            }

        prompt = f"""
Actúa como un Gestor Cuantitativo Senior de Fondos de Cobertura con Pensamiento Crítico Profundo (High Reasoning Mode).

Estás analizando en tiempo real el mercado {symbol}. A continuación tienes la radiografía matemática exacta extraída de MetaTrader 5:

DATOS EN VIVO:
- Símbolo: {symbol}
- Precio Actual: {market_data.get('current_price')}
- Spread actual: {market_data.get('spread_pips')} pips
- Tendencia Macro (H1): {market_data.get('macro_trend')}
- RSI (14): {market_data.get('rsi')}
- ATR (14): {market_data.get('atr')}
- Score Matemático Preliminar: {technical_score}/100
- Señal Preliminar de los Indicadores: {market_data.get('signal')}
- Factores Técnicos: {', '.join(market_data.get('reasons', []))}

TU TAREA:
1. Razona paso a paso sobre la estructura de mercado: ¿Es una tendencia genuina o una trampa de liquidez / fakeout de sesión?
2. Evalúa el riesgo contracorriente: ¿Qué podría invalidar esta operación?
3. Emite tu VEREDICTO FINAL: "BUY", "SELL" o "HOLD".
4. Asigna un Nivel de Convicción del 1 al 100.
5. Define niveles recomendados de Stop Loss y Take Profit asegurando un ratio Riesgo/Beneficio mínimo de 1:2.

RESPONDE ÚNICAMENTE CON UN OBJETO JSON VÁLIDO con la siguiente estructura:
{{
  "verdict": "BUY" | "SELL" | "HOLD",
  "ai_confidence_score": <numero de 1 a 100>,
  "thesis": "<explicación concisa y profesional de tu razonamiento de mercado>",
  "risk_warning": "<el mayor peligro que observas>",
  "recommended_sl": <precio stop loss numérico o null si HOLD>,
  "recommended_tp": <precio take profit numérico o null si HOLD>
}}
"""
        try:
            from google.genai import types
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Baja temperatura para máximo rigor analítico
                    response_mime_type="application/json"
                )
            )
            raw_text = response.text
            parsed = json.loads(raw_text)
            parsed["ai_enabled"] = True
            return parsed

        except Exception as e:
            return {
                "ai_enabled": False,
                "error": f"Fallo al consultar Gemini: {str(e)}",
                "verdict": market_data.get("signal", "HOLD"),
                "confidence": technical_score,
                "reasoning": "Error de comunicación con la API de Gemini."
            }

