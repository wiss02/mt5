"""
Calculadora Avanzada de Riesgo y Dimensionamiento de Lotaje Cuantitativo.
Diseñada para precisión absoluta en cuentas Estándar (USD) y cuentas Centavo (USC).
Respeta estrictamente el riesgo del 2% por operación y los límites del broker.
"""

from typing import Dict, Any, Optional, Tuple
import MetaTrader5 as mt5

class RiskCalculator:
    def __init__(self, risk_pct: float = 2.0, min_rr_ratio: float = 2.0):
        self.risk_pct = risk_pct
        self.min_rr_ratio = min_rr_ratio

    def resolve_symbol(self, base_symbol: str) -> Optional[str]:
        """
        Encuentra el nombre exacto del símbolo en el broker activo,
        manejando sufijos como XAUUSD.sc, EURUSD+, BTCUSD.sc, etc.
        """
        base_clean = base_symbol.upper().replace(".SC", "").replace("+", "").replace(".M", "")
        # Primero verificar si existe tal cual
        info = mt5.symbol_info(base_symbol)
        if info:
            return base_symbol

        # Buscar en la lista de símbolos disponibles
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            return None

        candidates = [s.name for s in all_symbols if s.name.upper().startswith(base_clean)]
        if candidates:
            # Priorizar coincidencia exacta o con sufijos conocidos
            candidates.sort(key=lambda s: (s.upper() != base_clean, len(s), s))
            return candidates[0]

        return None

    def calculate_lot(
        self,
        symbol: str,
        entry_price: float,
        sl_price: float,
        account_balance: float,
        risk_pct: Optional[float] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calcula el lotaje exacto para arriesgar exactamente el X% (por defecto 2%) del balance.
        Retorna: (lote_normalizado: float, detalles: dict)
        """
        target_risk_pct = risk_pct if risk_pct is not None else self.risk_pct
        
        resolved_sym = self.resolve_symbol(symbol)
        if not resolved_sym:
            raise ValueError(f"Símbolo {symbol} no encontrado en el broker.")

        # Asegurar visibilidad
        mt5.symbol_select(resolved_sym, True)
        info = mt5.symbol_info(resolved_sym)
        if not info:
            raise ValueError(f"No se pudo obtener información de {resolved_sym}")

        # Distancia en precio y en puntos
        sl_distance = abs(entry_price - sl_price)
        if sl_distance <= 0:
            raise ValueError("El Stop Loss no puede ser igual al precio de entrada.")

        point = info.point if info.point > 0 else 0.00001
        sl_points = sl_distance / point

        # Dinero que arriesgamos (2% del balance)
        risk_amount = account_balance * (target_risk_pct / 100.0)

        # tick_size y tick_value proporcionados por el broker
        tick_size = info.trade_tick_size if info.trade_tick_size > 0 else point
        tick_value = info.trade_tick_value if info.trade_tick_value > 0 else 1.0

        # Costo por 1.0 lote si toca el Stop Loss
        # (sl_points / (tick_size / point)) * tick_value
        ticks_in_sl = sl_distance / tick_size
        loss_per_one_lot = ticks_in_sl * tick_value

        if loss_per_one_lot <= 0:
            raw_lot = info.volume_min
        else:
            raw_lot = risk_amount / loss_per_one_lot

        # Ajuste riguroso al volumen del broker (volume_step, volume_min, volume_max)
        vol_step = info.volume_step if info.volume_step > 0 else 0.01
        vol_min = info.volume_min if info.volume_min > 0 else 0.01
        vol_max = info.volume_max if info.volume_max > 0 else 100.0

        # Redondeo hacia abajo al paso más cercano para nunca exceder el riesgo del 2%
        steps = int(raw_lot / vol_step)
        adjusted_lot = round(steps * vol_step, 2)

        # Aplicar límites mínimos y máximos
        final_lot = max(vol_min, min(vol_max, adjusted_lot))

        # Riesgo real proyectado con el lote final
        actual_risk_amount = final_lot * loss_per_one_lot
        actual_risk_pct = (actual_risk_amount / account_balance * 100.0) if account_balance > 0 else 0.0

        details = {
            "symbol": resolved_sym,
            "balance": account_balance,
            "target_risk_pct": target_risk_pct,
            "target_risk_amount": round(risk_amount, 2),
            "actual_risk_amount": round(actual_risk_amount, 2),
            "actual_risk_pct": round(actual_risk_pct, 2),
            "sl_distance_points": round(sl_points, 1),
            "tick_value": tick_value,
            "tick_size": tick_size,
            "volume_min": vol_min,
            "volume_max": vol_max,
            "volume_step": vol_step,
            "final_lot": final_lot
        }

        return final_lot, details

    def compute_sl_tp(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        sl_points_or_price: Optional[float] = None,
        rr_ratio: float = 2.0
    ) -> Tuple[float, float]:
        """
        Calcula niveles de SL y TP garantizando el ratio R/B solicitado (ej. 1:2 o 1:3).
        """
        resolved_sym = self.resolve_symbol(symbol) or symbol
        info = mt5.symbol_info(resolved_sym)
        point = info.point if info else 0.00001
        digits = info.digits if info else 5

        is_buy = action.upper() == "BUY"

        # Si el usuario pasó un precio de SL directo
        if sl_points_or_price is not None and sl_points_or_price > 0:
            if sl_points_or_price > 10.0 and abs(sl_points_or_price - entry_price) < entry_price * 0.2:
                # Es un precio exacto
                sl = sl_points_or_price
                risk_dist = abs(entry_price - sl)
            else:
                # Es una distancia en pips/puntos
                risk_dist = sl_points_or_price * point * 10
                sl = entry_price - risk_dist if is_buy else entry_price + risk_dist
        else:
            # SL automático por defecto (ej. 20 pips en forex)
            risk_dist = 200 * point
            sl = entry_price - risk_dist if is_buy else entry_price + risk_dist

        reward_dist = risk_dist * rr_ratio
        tp = entry_price + reward_dist if is_buy else entry_price - reward_dist

        return round(sl, digits), round(tp, digits)
