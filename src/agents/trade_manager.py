"""
Agente Gestor de Operaciones y Protección de Ganancias (Trade Manager).
Implementa la regla de oro solicitada por el usuario:
- El Stop Loss NO se toca hasta que la operación alcance un ratio de 1 a 2 (1:2) de ganancia.
- Al tocar 1:2, el Stop Loss se mueve inmediatamente para CUBRIR GANANCIAS (asegura +1R de beneficio).
- A partir de ese punto, el trade es 100% ganador y se deja correr hacia el Take Profit con Trailing Stop.
"""

import json
import os
from typing import Dict, Any, List

MANAGED_POS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "managed_positions.json")

class TradeManager:
    def __init__(self, target_rr_trigger: float = 2.0, secure_profit_ratio: float = 1.0):
        """
        :param target_rr_trigger: Ratio R/B requerido para mover el SL (por defecto 2.0 -> Ratio 1 a 2).
        :param secure_profit_ratio: Cuánto beneficio asegurar al mover el SL (1.0 = asegurar +1R de ganancia limpia).
        """
        self.target_rr_trigger = target_rr_trigger
        self.secure_profit_ratio = secure_profit_ratio
        self.managed_positions = self.load_managed_positions()

    def load_managed_positions(self) -> Dict[str, Any]:
        try:
            if os.path.exists(MANAGED_POS_FILE):
                with open(MANAGED_POS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_managed_positions(self):
        try:
            os.makedirs(os.path.dirname(MANAGED_POS_FILE), exist_ok=True)
            with open(MANAGED_POS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.managed_positions, f, indent=2)
        except Exception:
            pass

    def monitor_and_manage(self, connector) -> List[str]:
        """
        Revisa todas las posiciones abiertas en MT5:
        Si alguna posición alcanza el 1:2 de beneficio, mueve el SL a zona de ganancias aseguradas (+1R)
        y la deja correr libre de riesgo.
        """
        actions = []
        positions = connector.get_open_positions()
        if not positions:
            return actions

        active_tickets = {str(p["ticket"]) for p in positions}

        # Limpiar posiciones que ya fueron cerradas
        for old_ticket in list(self.managed_positions.keys()):
            if old_ticket not in active_tickets:
                del self.managed_positions[old_ticket]
        self.save_managed_positions()

        for pos in positions:
            ticket = str(pos["ticket"])
            symbol = pos["symbol"]
            pos_type = pos["type"]
            price_open = pos["price_open"]
            current_price = pos["current_price"]
            current_sl = pos["sl"]
            current_tp = pos["tp"]

            tick_info = connector.get_symbol_tick(symbol)
            if not tick_info:
                continue

            # Registrar posición si es nueva
            if ticket not in self.managed_positions:
                self.managed_positions[ticket] = {
                    "symbol": symbol,
                    "type": pos_type,
                    "initial_sl": current_sl,
                    "price_open": price_open,
                    "protected_at_1_to_2": False,
                    "trailing_active": False
                }

            meta = self.managed_positions[ticket]
            initial_sl = meta.get("initial_sl", current_sl)

            if initial_sl <= 0:
                continue

            initial_risk = abs(price_open - initial_sl)
            if initial_risk <= 0:
                continue

            # ========================================================
            # REGLA: AL ALCANZAR EL 1 A 2 -> MOVER SL PARA CUBRIR GANANCIAS
            # ========================================================
            if not meta.get("protected_at_1_to_2"):
                # Para COMPRA (BUY)
                if pos_type == "BUY":
                    current_gain = current_price - price_open
                    gain_rr = current_gain / initial_risk

                    # ¿Alcanzó el ratio 1:2?
                    if gain_rr >= self.target_rr_trigger:
                        # Nuevo SL: precio de entrada + 1R de ganancia asegurada
                        new_sl = round(price_open + (initial_risk * self.secure_profit_ratio), tick_info["digits"])
                        if new_sl > current_sl:
                            success = connector.modify_position(int(ticket), sl=new_sl, tp=current_tp)
                            if success:
                                meta["protected_at_1_to_2"] = True
                                meta["trailing_active"] = True
                                actions.append(
                                    f"🎯 [GANANCIA ASEGURADA 1:2] Posición #{ticket} en {symbol} alcanzó ratio 1:{gain_rr:.1f}. "
                                    f"Stop Loss movido a {new_sl} asegurando +1R de beneficio. ¡Dejando correr el trade al TP!"
                                )

                # Para VENTA (SELL)
                elif pos_type == "SELL":
                    current_gain = price_open - current_price
                    gain_rr = current_gain / initial_risk

                    # ¿Alcanzó el ratio 1:2?
                    if gain_rr >= self.target_rr_trigger:
                        # Nuevo SL: precio de entrada - 1R de ganancia asegurada
                        new_sl = round(price_open - (initial_risk * self.secure_profit_ratio), tick_info["digits"])
                        if current_sl == 0 or new_sl < current_sl:
                            success = connector.modify_position(int(ticket), sl=new_sl, tp=current_tp)
                            if success:
                                meta["protected_at_1_to_2"] = True
                                meta["trailing_active"] = True
                                actions.append(
                                    f"🎯 [GANANCIA ASEGURADA 1:2] Posición #{ticket} en {symbol} alcanzó ratio 1:{gain_rr:.1f}. "
                                    f"Stop Loss movido a {new_sl} asegurando +1R de beneficio. ¡Dejando correr el trade al TP!"
                                )

            # ========================================================
            # TRAILING DINÁMICO: SI SIGUE SUBIENDO MÁS ALLÁ DEL 1:2.5
            # ========================================================
            elif meta.get("trailing_active"):
                if pos_type == "BUY":
                    current_gain = current_price - price_open
                    gain_rr = current_gain / initial_risk
                    if gain_rr >= 2.5:
                        trailing_sl = round(current_price - (1.2 * initial_risk), tick_info["digits"])
                        if trailing_sl > current_sl:
                            if connector.modify_position(int(ticket), sl=trailing_sl, tp=current_tp):
                                actions.append(f"📈 [TRAILING STOP] Subiendo SL de #{ticket} a {trailing_sl} (asegurando más beneficio).")

                elif pos_type == "SELL":
                    current_gain = price_open - current_price
                    gain_rr = current_gain / initial_risk
                    if gain_rr >= 2.5:
                        trailing_sl = round(current_price + (1.2 * initial_risk), tick_info["digits"])
                        if current_sl == 0 or trailing_sl < current_sl:
                            if connector.modify_position(int(ticket), sl=trailing_sl, tp=current_tp):
                                actions.append(f"📉 [TRAILING STOP] Bajando SL de #{ticket} a {trailing_sl} (asegurando más beneficio).")

        self.save_managed_positions()
        return actions
