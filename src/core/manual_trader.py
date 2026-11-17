"""
Módulo de Ejecución de Operaciones Manuales Inteligentes.
Permite abrir trades con un clic o comando calculando automáticamente:
1. Lotaje exacto según el 2% estricto del balance.
2. Stop Loss y Take Profit optimizados (Ratio 1:3 para dejar correr).
3. Enlace automático con el Trade Manager para mover a ganancias al alcanzar 1:2.
"""

from typing import Dict, Any, Optional
from src.core.mt5_connector import MT5Connector
from src.core.risk_calculator import RiskCalculator

class ManualTrader:
    def __init__(self, connector: Optional[MT5Connector] = None, risk_pct: float = 2.0):
        self.connector = connector or MT5Connector()
        self.calculator = RiskCalculator(risk_pct=risk_pct)

    def execute_order(
        self,
        symbol: str,
        action: str,
        sl_price: Optional[float] = None,
        sl_pips: Optional[float] = None,
        tp_ratio: float = 3.0,
        risk_pct: Optional[float] = None,
        comment: str = "Manual-2pct"
    ) -> Dict[str, Any]:
        """
        Ejecuta una orden a mercado con cálculo de lotaje automático al 2% de riesgo.
        """
        action = action.upper()
        if action not in ["BUY", "SELL"]:
            return {"success": False, "error": f"Acción '{action}' inválida. Debe ser BUY o SELL."}

        if not self.connector.is_connected:
            if not self.connector.connect():
                return {"success": False, "error": "No se pudo conectar a la terminal MT5 activa."}

        account = self.connector.get_account_summary()
        balance = account.get("balance", 0.0)
        currency = account.get("currency", "")

        if balance <= 0:
            return {"success": False, "error": f"Balance de cuenta insuficiente ({balance} {currency})."}

        resolved_symbol = self.calculator.resolve_symbol(symbol)
        if not resolved_symbol:
            return {"success": False, "error": f"Símbolo '{symbol}' no encontrado en el broker."}

        tick = self.connector.get_symbol_tick(resolved_symbol)
        if not tick:
            return {"success": False, "error": f"No se pudo obtener cotización de {resolved_symbol}."}

        is_buy = action == "BUY"
        entry_price = tick["ask"] if is_buy else tick["bid"]
        point = tick["point"]
        digits = tick["digits"]

        # Determinar Stop Loss
        if sl_price is not None and sl_price > 0:
            calculated_sl = sl_price
        elif sl_pips is not None and sl_pips > 0:
            pips_dist = sl_pips * (point * (10 if digits in [3, 5] else 1))
            calculated_sl = entry_price - pips_dist if is_buy else entry_price + pips_dist
        else:
            # SL por defecto inteligente si no se especifica (ej. 25 pips)
            default_pips = 25.0 if "USD" in resolved_symbol and "XAU" not in resolved_symbol else 50.0
            pips_dist = default_pips * (point * (10 if digits in [3, 5] else 1))
            calculated_sl = entry_price - pips_dist if is_buy else entry_price + pips_dist

        calculated_sl = round(calculated_sl, digits)

        # Validación básica de dirección del SL
        if is_buy and calculated_sl >= entry_price:
            return {"success": False, "error": "Para BUY, el Stop Loss debe ser menor al precio de entrada."}
        if not is_buy and calculated_sl <= entry_price:
            return {"success": False, "error": "Para SELL, el Stop Loss debe ser mayor al precio de entrada."}

        # Calcular Take Profit (1:3 para dejar correr después de que proteja al 1:2)
        risk_dist = abs(entry_price - calculated_sl)
        reward_dist = risk_dist * tp_ratio
        calculated_tp = round(entry_price + reward_dist if is_buy else entry_price - reward_dist, digits)

        # ---------------------------------------------------------
        # CÁLCULO ESTRICTO DE LOTAJE AL 2%
        # ---------------------------------------------------------
        try:
            lot, details = self.calculator.calculate_lot(
                symbol=resolved_symbol,
                entry_price=entry_price,
                sl_price=calculated_sl,
                account_balance=balance,
                risk_pct=risk_pct
            )
        except Exception as e:
            return {"success": False, "error": f"Error calculando lotaje: {str(e)}"}

        # ---------------------------------------------------------
        # ENVIAR ORDEN A MT5
        # ---------------------------------------------------------
        order_res = self.connector.open_order(
            symbol=resolved_symbol,
            order_type=action,
            volume=lot,
            sl=calculated_sl,
            tp=calculated_tp,
            comment=comment
        )

        if not order_res.get("success"):
            return {
                "success": False,
                "error": order_res.get("error", "Fallo al enviar orden a MT5"),
                "calculation_details": details
            }

        return {
            "success": True,
            "ticket": order_res["ticket"],
            "symbol": resolved_symbol,
            "action": action,
            "volume": lot,
            "entry_price": entry_price,
            "sl": calculated_sl,
            "tp": calculated_tp,
            "risk_amount": details["actual_risk_amount"],
            "risk_pct": details["actual_risk_pct"],
            "currency": currency,
            "tp_ratio": f"1:{tp_ratio}",
            "protection_rule": "Al alcanzar 1:2, el Stop Loss se moverá a ganancias (+1R) automáticamente dejando correr el resto."
        }
