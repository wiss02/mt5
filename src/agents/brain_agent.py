"""
Agente Cerebro (Brain / Orquestador Central con Red de Consenso Multi-Agente).
Coordina los agentes Scout, Risk Guardian, Trade Manager y la Red de Debate de 4 Agentes.
Ejecuta el ciclo de análisis en tiempo real y persiste el estado completo en data/live_state.json
para que el panel web de ChatGPT lo visualice al instante.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.core.mt5_connector import MT5Connector
from src.agents.scout_agent import ScoutAgent
from src.agents.risk_guardian import RiskGuardian
from src.agents.trade_manager import TradeManager
from src.agents.consensus_network import ConsensusNetwork

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "live_state.json")

class BrainAgent:
    def __init__(self, default_mode: str = "DEMO", symbols: Optional[List[str]] = None, auto_trade: bool = False):
        self.connector = MT5Connector(active_mode=default_mode)
        self.scout = ScoutAgent(symbols=symbols)
        self.risk_guardian = RiskGuardian()
        self.trade_manager = TradeManager()
        self.consensus_network = ConsensusNetwork()
        self.auto_trade = auto_trade
        self.logs = []
        self.is_running = False

    def log(self, message: str, level: str = "INFO"):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.insert(0, entry)
        if len(self.logs) > 60:
            self.logs.pop()
        print(f"[{entry['timestamp']}] [{level}] {message}", flush=True)

    def initialize(self) -> bool:
        """Inicializa la conexión con la terminal MT5 configurada."""
        success = self.connector.connect()
        if success:
            acc = self.connector.get_account_summary()
            self.log(f"Cerebro conectado a terminal MT5 en modo {acc.get('mode')} (Cuenta {acc.get('login')} - {acc.get('server')}).")
            self.log("Red de Consenso Multi-Agente ACTIVADA (BullHunter, BearCritic, RiskSentinel, ChiefArbiter).")
        else:
            self.log("Fallo al conectar con terminal MT5.", level="ERROR")
        return success

    def run_cycle(self) -> Dict[str, Any]:
        """
        Ejecuta un ciclo completo de monitoreo, debate entre agentes y gestión:
        1. Obtener estado de la cuenta.
        2. Monitorear posiciones abiertas (Breakeven/Trailing Stop).
        3. Escanear todos los mercados con los Scouts.
        4. Abrir debate entre los 4 agentes para cada activo con potencial.
        5. Validar con Risk Sentinel y ejecutar si auto_trade está activo y hay consenso >= 75%.
        6. Guardar estado en data/live_state.json para el Dashboard de ChatGPT.
        """
        if not self.connector.is_connected:
            self.connector.connect()

        # 1. Estado de la cuenta y posiciones
        account = self.connector.get_account_summary()
        positions = self.connector.get_open_positions()

        # 2. Gestión de operaciones vivas
        manage_actions = self.trade_manager.monitor_and_manage(self.connector)
        for act in manage_actions:
            self.log(act, level="ACTION")

        # 3. Escaneo de mercados con los Scouts
        scanned_markets = self.scout.scan_all(self.connector)

        # 4. Debates del Comité de Agentes
        debates_by_symbol = {}
        decision_events = []

        for opp in scanned_markets:
            symbol = opp.get("symbol")
            
            # El comité debate el activo
            debate_res = self.consensus_network.conduct_debate(symbol, opp, account)
            debates_by_symbol[symbol] = debate_res
            opp["debate"] = debate_res

            verdict = debate_res.get("verdict")
            consensus_score = debate_res.get("consensus_score", 0)

            if verdict in ["BUY", "SELL"] and consensus_score >= 75:
                self.log(f"🏛️ [COMITÉ CONSENSO] {symbol} {verdict} con {consensus_score}% de acuerdo.", level="CONSENSUS")
                plan = debate_res.get("execution_plan", {})
                
                # Validar con Risk Guardian
                approved, reason, lot_size = self.risk_guardian.validate_opportunity(
                    symbol=symbol,
                    signal_type=verdict,
                    entry_price=opp["entry_price"],
                    sl_price=plan.get("sl", opp["sl_price"]),
                    tp_price=plan.get("tp", opp["tp_price"]),
                    account_summary=account,
                    open_positions=positions,
                    current_spread_pips=opp["spread_pips"],
                    tick_info=opp["tick_info"]
                )

                decision_events.append({
                    "symbol": symbol,
                    "verdict": verdict,
                    "consensus_score": consensus_score,
                    "approved": approved,
                    "reason": reason,
                    "lot": lot_size
                })

                if approved:
                    self.log(f"🛡️ [RIESGO APROBADO] Lote calculado: {lot_size} en {symbol}. {reason}", level="RISK")
                    if self.auto_trade:
                        order_res = self.connector.open_order(
                            symbol=symbol,
                            order_type=verdict,
                            volume=lot_size,
                            sl=plan.get("sl", opp["sl_price"]),
                            tp=plan.get("tp", opp["tp_price"]),
                            comment=f"Swarm-{consensus_score}"
                        )
                        if order_res["success"]:
                            self.log(f"⚡ [ORDEN EJECUTADA] {verdict} {lot_size} lotes en {symbol} (Ticket #{order_res['ticket']}).", level="EXECUTION")
                        else:
                            self.log(f"❌ Error al enviar orden: {order_res.get('error')}", level="ERROR")
                    else:
                        self.log(f"ℹ️ Modo Simulación: Veredicto {verdict} listo para {symbol} (Auto-Trade desactivado).", level="ALERT")
                else:
                    self.log(f"⛔ [VETO DE RIESGO] {symbol}: {reason}", level="WARNING")

        # 5. Estructurar snapshot del estado para ChatGPT
        state = {
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": account.get("mode", self.connector.active_mode),
            "auto_trade": self.auto_trade,
            "account": account,
            "open_positions": positions,
            "committee_roster": [
                {"name": "BullHunter", "role": "Analista Alcista & Liquidez", "avatar": "🐂", "status": "ACTIVO"},
                {"name": "BearCritic", "role": "Abogado del Diablo & Trampas", "avatar": "🐻", "status": "ACTIVO"},
                {"name": "RiskSentinel", "role": "Matemático de Capital & Drawdown", "avatar": "🛡️", "status": "ACTIVO"},
                {"name": "ChiefArbiter", "role": "Juez & Director de Mesa", "avatar": "⚖️", "status": "ACTIVO"}
            ],
            "debates": debates_by_symbol,
            "scanned_markets": [
                {
                    "symbol": m.get("symbol"),
                    "status": m.get("status"),
                    "signal": m.get("signal"),
                    "score": m.get("score"),
                    "macro_trend": m.get("macro_trend"),
                    "current_price": m.get("current_price"),
                    "entry_price": m.get("entry_price"),
                    "sl_price": m.get("sl_price"),
                    "tp_price": m.get("tp_price"),
                    "rsi": m.get("rsi"),
                    "atr": m.get("atr"),
                    "spread_pips": m.get("spread_pips"),
                    "reasons": m.get("reasons", []),
                    "debate": m.get("debate")
                }
                for m in scanned_markets
            ],
            "decision_events": decision_events,
            "recent_logs": self.logs[:25]
        }

        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"Error guardando estado JSON: {e}", level="ERROR")

        return state
