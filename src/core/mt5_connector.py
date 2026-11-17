"""
Módulo de Conexión y Gestión Dual con MetaTrader 5 (MT5).
Soporta alternar entre cuenta DEMO (Metatrader-2) y cuenta REAL (MetaTrader 5),
lectura de datos en vivo y ejecución completa de órdenes (BUY, SELL, SL, TP, Breakeven).
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5

TERMINAL_CONFIGS = {
    "DEMO": {
        "name": "Cuenta Demo",
        "path": r"C:\Program Files\Metatrader-2\terminal64.exe",
        "color": "green"
    },
    "REAL": {
        "name": "Cuenta Real",
        "path": r"C:\Program Files\MetaTrader 5\terminal64.exe",
        "color": "red"
    }
}

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

MAGIC_NUMBER = 998877  # Identificador único de nuestras órdenes algorítmicas

class MT5Connector:
    def __init__(self, active_mode: str = "DEMO"):
        self.active_mode = active_mode.upper()
        self.is_connected = False
        self.terminal_path = TERMINAL_CONFIGS.get(self.active_mode, {}).get("path")

    def connect(self, mode: Optional[str] = None, timeout: int = 15000) -> bool:
        """Inicia la conexión con la terminal seleccionada (DEMO o REAL)."""
        if mode:
            self.active_mode = mode.upper()
            self.terminal_path = TERMINAL_CONFIGS.get(self.active_mode, {}).get("path")

        if self.is_connected:
            self.disconnect()

        init_kwargs = {"timeout": timeout}
        if self.terminal_path and os.path.exists(self.terminal_path):
            init_kwargs["path"] = self.terminal_path
        else:
            print(f"[ERROR MT5] No se encontró el ejecutable en: {self.terminal_path}", flush=True)
            return False

        print(f"[MT5] Conectando a terminal {self.active_mode} ({self.terminal_path})...", flush=True)
        if not mt5.initialize(**init_kwargs):
            error_code, error_desc = mt5.last_error()
            print(f"[ERROR MT5] Fallo al inicializar {self.active_mode}: ({error_code}) {error_desc}", flush=True)
            self.is_connected = False
            return False

        account_info = mt5.account_info()
        if account_info is None:
            error_code, error_desc = mt5.last_error()
            print(f"[ERROR MT5] No se pudo obtener info de cuenta: ({error_code}) {error_desc}", flush=True)
            self.is_connected = False
            return False

        self.is_connected = True
        print(f"[MT5 CONECTADO] Modo: {self.active_mode} | Cuenta: {account_info.login} | Servidor: {account_info.server} | Balance: {account_info.balance:.2f} {account_info.currency}", flush=True)
        return True

    def switch_account(self, new_mode: str) -> bool:
        """Cambia entre modo DEMO y modo REAL de forma limpia."""
        new_mode = new_mode.upper()
        if new_mode not in TERMINAL_CONFIGS:
            print(f"[MT5] Modo no válido: {new_mode}. Usa 'DEMO' o 'REAL'.")
            return False
        return self.connect(mode=new_mode)

    def get_account_summary(self) -> Dict[str, Any]:
        """Devuelve un resumen completo del estado de la cuenta actual."""
        if not self.is_connected:
            return {}
        info = mt5.account_info()
        if not info:
            return {}
        return {
            "mode": self.active_mode,
            "login": info.login,
            "server": info.server,
            "name": info.name,
            "currency": info.currency,
            "leverage": info.leverage,
            "balance": round(info.balance, 2),
            "equity": round(info.equity, 2),
            "margin": round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "margin_level": round(info.margin_level, 2) if info.margin_level else 0.0,
            "floating_profit": round(info.profit, 2),
            "trade_allowed": info.trade_allowed,
        }

    def get_symbol_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Obtiene el último tick (bid, ask, spread) de un activo."""
        if not self.is_connected:
            return None
        
        if not mt5.symbol_select(symbol, True):
            return None

        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            return None

        divisor = 10 if info.digits in [3, 5] else 1
        spread_pips = (tick.ask - tick.bid) / (info.point * divisor)
        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread_points": round(tick.ask - tick.bid, 5),
            "spread_pips": round(spread_pips, 2),
            "time": datetime.fromtimestamp(tick.time),
            "digits": info.digits,
            "point": info.point,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_tick_value": info.trade_tick_value
        }

    def get_ohlcv(self, symbol: str, timeframe: str = "M15", count: int = 150) -> Optional[pd.DataFrame]:
        """Obtiene velas históricas y las retorna en un DataFrame de pandas."""
        if not self.is_connected:
            return None

        tf = TIMEFRAMES.get(timeframe.upper(), mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        return df[['time', 'open', 'high', 'low', 'close', 'volume']]

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Devuelve una lista con las posiciones actualmente abiertas."""
        if not self.is_connected:
            return []
        
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []

        result = []
        for p in positions:
            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "current_price": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": round(p.profit, 2),
                "swap": round(p.swap, 2),
                "magic": p.magic,
                "comment": p.comment,
                "open_time": datetime.fromtimestamp(p.time).strftime("%Y-%m-%d %H:%M:%S")
            })
        return result

    def open_order(self, symbol: str, order_type: str, volume: float, sl: float, tp: float, comment: str = "AI-Trader") -> Dict[str, Any]:
        """
        Ejecuta una orden a mercado (BUY o SELL) con SL y TP.
        """
        if not self.is_connected:
            return {"success": False, "error": "MT5 no conectado"}

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return {"success": False, "error": f"Símbolo {symbol} no encontrado"}

        if not symbol_info.visible:
            mt5.symbol_select(symbol, True)

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {"success": False, "error": f"No se pudo obtener tick de {symbol}"}

        is_buy = order_type.upper() == "BUY"
        action_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if is_buy else tick.bid

        # Ajuste de volumen a los límites del broker
        vol_step = symbol_info.volume_step
        volume = round(round(volume / vol_step) * vol_step, 2)
        volume = max(symbol_info.volume_min, min(symbol_info.volume_max, volume))

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": action_type,
            "price": price,
            "sl": round(sl, symbol_info.digits),
            "tp": round(tp, symbol_info.digits),
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC if symbol_info.filling_mode & mt5.ORDER_FILLING_IOC else mt5.ORDER_FILLING_FOK,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code = result.retcode if result else mt5.last_error()
            error_comment = result.comment if result else "Sin respuesta"
            return {"success": False, "error": f"Error orden ({error_code}): {error_comment}"}

        return {
            "success": True,
            "ticket": result.order,
            "volume": result.volume,
            "price": result.price,
            "sl": sl,
            "tp": tp,
            "comment": comment
        }

    def modify_position(self, ticket: int, sl: float, tp: float) -> bool:
        """Modifica el Stop Loss o Take Profit de una posición activa (ej. Breakeven)."""
        if not self.is_connected:
            return False

        position = None
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            position = positions[0]

        if not position:
            return False

        symbol_info = mt5.symbol_info(position.symbol)
        if not symbol_info:
            return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
            "sl": round(sl, symbol_info.digits),
            "tp": round(tp, symbol_info.digits),
        }

        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, ticket: int) -> bool:
        """Cierra una posición abierta por su ticket."""
        if not self.is_connected:
            return False

        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return False

        pos = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return False

        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": "Cierre manual/auto",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_all_positions(self) -> int:
        """Cierra de emergencia todas las posiciones abiertas. Retorna cuántas cerró."""
        positions = self.get_open_positions()
        closed_count = 0
        for p in positions:
            if self.close_position(p["ticket"]):
                closed_count += 1
        return closed_count

    def disconnect(self):
        """Cierra la conexión con MT5."""
        if self.is_connected:
            mt5.shutdown()
            self.is_connected = False
            print(f"[MT5] Conexión cerrada para {self.active_mode}.", flush=True)
