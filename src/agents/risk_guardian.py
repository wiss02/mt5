"""
Agente Guardián de Riesgo (Risk Guardian).
Este agente es el filtro supremo e infranqueable del sistema.
Ninguna operación entra al mercado sin su estricta aprobación.
"""

from typing import Dict, Any, Tuple
from datetime import datetime

class RiskGuardian:
    def __init__(
        self,
        risk_per_trade_pct: float = 1.0,     # Máximo 1% del balance por trade
        max_daily_loss_pct: float = 3.0,      # Kill-switch: pérdida máxima del 3% diaria
        min_risk_reward_ratio: float = 2.0,   # Mínimo ratio 1:2 (beneficio / riesgo)
        max_open_positions: int = 3,          # Máximo 3 posiciones simultáneas
    ):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_open_positions = max_open_positions

        # Filtro de spread máximo permitido (en pips)
        self.max_spread_rules = {
            "EURUSD": 2.5,
            "GBPUSD": 3.0,
            "USDJPY": 2.5,
            "AUDUSD": 3.0,
            "USDCAD": 3.0,
            "XAUUSD": 35.0,
            "BTCUSD": 85.0
        }

        self.daily_start_equity = None
        self.daily_date = None

    def update_daily_baseline(self, current_equity: float):
        """Actualiza el balance base del día para calcular el drawdown diario."""
        today = datetime.now().date()
        if self.daily_date != today or self.daily_start_equity is None:
            self.daily_date = today
            self.daily_start_equity = current_equity

    def validate_opportunity(
        self,
        symbol: str,
        signal_type: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        account_summary: Dict[str, Any],
        open_positions: list,
        current_spread_pips: float,
        tick_info: Dict[str, Any]
    ) -> Tuple[bool, str, float]:
        """
        Valida una oportunidad generada por los Scouts.
        Retorna: (aprobado: bool, razon: str, lotaje_aprobado: float)
        """
        balance = account_summary.get("balance", 0.0)
        equity = account_summary.get("equity", 0.0)

        if balance <= 0 or equity <= 0:
            return False, "Balance o equidad insuficiente o nula.", 0.0

        self.update_daily_baseline(equity)

        # 1. Kill-Switch de Pérdida Diaria
        daily_drawdown_pct = ((self.daily_start_equity - equity) / self.daily_start_equity) * 100.0
        if daily_drawdown_pct >= self.max_daily_loss_pct:
            return False, f"KILL-SWITCH ACTIVO: Drawdown diario alcanzó {daily_drawdown_pct:.2f}% (Máx: {self.max_daily_loss_pct}%). Operaciones bloqueadas.", 0.0

        # 2. Límite de Posiciones Abiertas Simultáneas
        if len(open_positions) >= self.max_open_positions:
            return False, f"Límite de posiciones abiertas alcanzado ({len(open_positions)}/{self.max_open_positions}).", 0.0

        # 3. Evitar duplicar posición en el mismo símbolo
        for pos in open_positions:
            if pos.get("symbol") == symbol:
                return False, f"Ya existe una posición abierta en {symbol}.", 0.0

        # 4. Filtro de Spread
        max_allowed_spread = self.max_spread_rules.get(symbol, 4.0)
        if current_spread_pips > max_allowed_spread:
            return False, f"Spread muy alto ({current_spread_pips:.1f} pips > límite de {max_allowed_spread} pips en {symbol}).", 0.0

        # 5. Validación del Ratio Riesgo / Beneficio (Mínimo 1:2)
        risk_distance = abs(entry_price - sl_price)
        reward_distance = abs(tp_price - entry_price)

        if risk_distance <= 0:
            return False, "Distancia de Stop Loss inválida (0 o negativa).", 0.0

        rr_ratio = reward_distance / risk_distance
        if rr_ratio < (self.min_risk_reward_ratio - 0.05):
            return False, f"Ratio R/B insuficiente ({rr_ratio:.2f} < mínimo requerido {self.min_risk_reward_ratio}).", 0.0

        # 6. Cálculo Matemático de Tamaño de Lote según Riesgo
        risk_amount_currency = balance * (self.risk_per_trade_pct / 100.0)
        point = tick_info.get("point", 0.00001)
        digits = tick_info.get("digits", 5)
        trade_tick_value = tick_info.get("trade_tick_value", 1.0)
        vol_min = tick_info.get("volume_min", 0.01)
        vol_max = tick_info.get("volume_max", 100.0)
        vol_step = tick_info.get("volume_step", 0.01)

        # Distancia en puntos
        sl_points = risk_distance / point
        if sl_points <= 0:
            sl_points = 1.0

        # Costo de 1 lote para la distancia del SL
        risk_per_1_lot = sl_points * trade_tick_value
        if risk_per_1_lot <= 0:
            calculated_lot = vol_min
        else:
            raw_lot = risk_amount_currency / risk_per_1_lot
            # Ajustar al paso permitido (ej. 0.01)
            calculated_lot = round(raw_lot / vol_step) * vol_step
            calculated_lot = round(calculated_lot, 2)

        # Restringir a límites de la cuenta
        lot = max(vol_min, min(vol_max, calculated_lot))

        return True, f"Riesgo validado con éxito. Lote: {lot} (Riesgo estimado: ~{risk_amount_currency:.2f} {account_summary.get('currency', '')}, RR 1:{rr_ratio:.1f})", lot

