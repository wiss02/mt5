"""Acceso serializado y de solo lectura al conector MT5 del panel.

La API de MetaTrader5 mantiene una conexión global por proceso. Compartimos un
único servicio entre sesiones del panel para evitar cambios concurrentes de
terminal dentro del proceso; no se realizan operaciones de trading aquí.
"""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from time import monotonic

import MetaTrader5 as mt5

from src.core.mt5_connector import MT5Connector, TERMINAL_CONFIGS


def account_kind(trade_mode: int) -> str:
    """Describe el tipo informado por el servidor, no por la ruta elegida."""
    return {
        mt5.ACCOUNT_TRADE_MODE_DEMO: "DEMO",
        mt5.ACCOUNT_TRADE_MODE_CONTEST: "CONCURSO",
        mt5.ACCOUNT_TRADE_MODE_REAL: "REAL",
    }.get(trade_mode, "DESCONOCIDO")


def quote_freshness(tick_time: datetime, now: datetime | None = None) -> tuple[str, int | None]:
    """Una cotización antigua no se presenta como precio en vivo."""
    now = now or datetime.now()
    seconds = (now - tick_time).total_seconds()
    if seconds < -5:
        return "Hora no verificada", None
    seconds = max(0, int(seconds))
    return ("Reciente" if seconds <= 60 else "Desactualizada"), seconds


def suggested_symbols(names: list[str], limit: int = 4) -> list[str]:
    """Resuelve nombres comunes sin asumir que el broker no utiliza sufijos."""
    chosen = []
    for base in ("XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "USDJPY"):
        candidates = [name for name in names if name.upper().startswith(base)]
        if candidates:
            candidates.sort(key=lambda name: (name.upper() != base, len(name), name))
            chosen.append(candidates[0])
        if len(chosen) == limit:
            break
    return chosen or names[:limit]


class MT5ReadService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.connector = MT5Connector()
        self.revision = 0
        self.last_message = "Selecciona un terminal y conecta para ver datos de MT5."
        self._symbols: list[str] = []
        self._symbols_checked = 0.0

    def connect(self, mode: str) -> bool:
        with self._lock:
            if mode not in TERMINAL_CONFIGS:
                self.last_message = "Terminal no válido."
                return False
            try:
                success = self.connector.connect(mode)
                if not success:
                    # El conector puede inicializar MT5 y fallar al consultar la cuenta.
                    mt5.shutdown()
                    self.last_message = "No se pudo conectar. Comprueba el terminal y la sesión de MT5."
                else:
                    self.last_message = "Terminal conectado."
            except Exception:
                mt5.shutdown()
                self.connector.is_connected = False
                self.last_message = "No se pudo conectar. Comprueba el terminal y la sesión de MT5."
                success = False
            self._symbols = []
            self._symbols_checked = 0.0
            self.revision += 1
            return success

    def disconnect(self) -> None:
        with self._lock:
            self.connector.disconnect()
            self._symbols = []
            self._symbols_checked = 0.0
            self.revision += 1
            self.last_message = "Terminal desconectado."

    def status(self) -> dict:
        with self._lock:
            result = {
                "connected": False,
                "terminal_mode": self.connector.active_mode,
                "message": self.last_message,
                "revision": self.revision,
            }
            if not self.connector.is_connected:
                return result
            terminal = mt5.terminal_info()
            info = mt5.account_info()
            if not terminal or not terminal.connected or not info:
                result["message"] = "MT5 no está conectado al servidor o no devuelve datos de cuenta."
                return result
            result.update(
                connected=True,
                account_kind=account_kind(info.trade_mode),
                account={
                    "login": info.login,
                    "server": info.server,
                    "currency": info.currency,
                    "leverage": info.leverage,
                    "balance": info.balance,
                    "equity": info.equity,
                    "free_margin": info.margin_free,
                    "margin": info.margin,
                    "margin_level": info.margin_level,
                    "floating_profit": info.profit,
                },
            )
            return result

    def symbols(self) -> list[str]:
        with self._lock:
            if not self.status()["connected"]:
                return []
            if not self._symbols or monotonic() - self._symbols_checked > 60:
                items = mt5.symbols_get()
                if items is not None:
                    self._symbols = sorted({item.name for item in items})
                self._symbols_checked = monotonic()
            return self._symbols.copy()

    def dashboard(self, watch: list[str] | None, focus: str | None, timeframe: str) -> dict:
        """Resuelve los símbolos del terminal activo y toma una captura consistente."""
        with self._lock:
            names = self.symbols()
            available = set(names)
            selected = (
                suggested_symbols(names) if watch is None
                else list(dict.fromkeys(symbol for symbol in watch if symbol in available))
            )
            active = focus if focus in selected else next(iter(selected), None)
            result = self.snapshot(selected, active, timeframe)
            result.update(watch=selected, focus=active, period=timeframe)
            return result

    def snapshot(self, symbols: list[str], chart_symbol: str | None, timeframe: str) -> dict:
        with self._lock:
            result = self.status()
            result.update(quotes=[], positions=None, candles=None, captured_at=datetime.now())
            if not result["connected"]:
                return result
            for symbol in dict.fromkeys(symbols):
                try:
                    tick = self.connector.get_symbol_tick(symbol)
                except (ValueError, OverflowError, OSError, ZeroDivisionError):
                    # El broker puede exponer símbolos sin especificaciones válidas.
                    tick = None
                # Algunos brokers devuelven ticks vacíos con precio y fecha cero.
                # No los mostramos como una cotización operativa.
                if tick and tick["bid"] > 0 and tick["ask"] > 0 and tick["time"].year > 1970:
                    tick["freshness"], tick["age_seconds"] = quote_freshness(tick["time"])
                    result["quotes"].append(tick)
                else:
                    result["quotes"].append({"symbol": symbol, "unavailable": True})
            positions = mt5.positions_get()
            if positions is not None:
                result["positions"] = [
                    {
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "type": "COMPRA" if p.type == mt5.POSITION_TYPE_BUY else "VENTA",
                        "volume": p.volume,
                        "price_open": p.price_open,
                        "current_price": p.price_current,
                        "sl": p.sl,
                        "tp": p.tp,
                        "profit": p.profit,
                        "swap": p.swap,
                    }
                    for p in positions
                ]
            if chart_symbol:
                if chart_symbol not in symbols:
                    try:
                        self.connector.get_symbol_tick(chart_symbol)
                    except (ValueError, OverflowError, OSError, ZeroDivisionError):
                        pass
                result["candles"] = self.connector.get_ohlcv(chart_symbol, timeframe, 120)
            return result
