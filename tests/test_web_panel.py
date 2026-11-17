"""Comprobaciones del panel sin enviar órdenes ni conectar un terminal real."""

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import MetaTrader5 as mt5

from src.web.mt5_service import MT5ReadService, account_kind, quote_freshness, suggested_symbols


class MT5ServiceTests(unittest.TestCase):
    def test_account_type_comes_from_mt5(self):
        self.assertEqual(account_kind(mt5.ACCOUNT_TRADE_MODE_DEMO), "DEMO")
        self.assertEqual(account_kind(mt5.ACCOUNT_TRADE_MODE_REAL), "REAL")
        self.assertEqual(account_kind(-999), "DESCONOCIDO")

    def test_quote_freshness_including_future_timestamp(self):
        now = datetime(2026, 11, 16, 12, 0)
        self.assertEqual(quote_freshness(now - timedelta(seconds=15), now), ("Reciente", 15))
        self.assertEqual(quote_freshness(now - timedelta(minutes=2), now), ("Desactualizada", 120))
        self.assertEqual(quote_freshness(now + timedelta(minutes=1), now), ("Hora no verificada", None))

    def test_suggests_exact_broker_symbols_including_suffixes(self):
        names = ["XAUUSD.sc", "EURUSD.a", "EURUSD", "BTCUSDm"]
        self.assertEqual(suggested_symbols(names), ["XAUUSD.sc", "EURUSD", "BTCUSDm"])

    def test_snapshot_distinguishes_missing_ticks_and_failed_positions(self):
        service = MT5ReadService()
        service.connector.is_connected = True
        info = SimpleNamespace(trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL, login=1, server="test",
                               currency="USC", leverage=500, balance=100, equity=95,
                               margin_free=90, margin=5, margin_level=1900, profit=-5)
        invalid_tick = {"symbol": "BTCUSD", "bid": 0, "ask": 0, "time": datetime(1970, 1, 1)}
        with patch("src.web.mt5_service.mt5.terminal_info", return_value=SimpleNamespace(connected=True)), \
             patch("src.web.mt5_service.mt5.account_info", return_value=info), \
             patch("src.web.mt5_service.mt5.positions_get", return_value=None), \
             patch.object(service.connector, "get_symbol_tick", return_value=invalid_tick):
            result = service.snapshot(["BTCUSD"], None, "M15")
        self.assertEqual(result["account_kind"], "REAL")
        self.assertEqual(result["terminal_mode"], "DEMO")
        self.assertEqual(result["account"]["currency"], "USC")
        self.assertEqual(result["quotes"], [{"symbol": "BTCUSD", "unavailable": True}])
        self.assertIsNone(result["positions"])

    def test_disconnected_terminal_does_not_return_cached_account_data(self):
        service = MT5ReadService()
        service.connector.is_connected = True
        with patch("src.web.mt5_service.mt5.terminal_info", return_value=SimpleNamespace(connected=False)), \
             patch("src.web.mt5_service.mt5.account_info", return_value=None):
            result = service.snapshot([], None, "M15")
        self.assertFalse(result["connected"])
        self.assertNotIn("account", result)
        self.assertIsNone(result["positions"])


    def test_dashboard_resolves_watch_against_active_broker_catalog(self):
        service = MT5ReadService()
        with patch.object(service, "symbols", return_value=["EURUSD", "XAUUSD.sc"]), \
             patch.object(service, "snapshot", return_value={}) as capture:
            result = service.dashboard(["XAUUSD.sc", "XAUUSD.sc", "XAUUSD"], "XAUUSD", "H1")
        self.assertEqual(result["watch"], ["XAUUSD.sc"])
        self.assertEqual(result["focus"], "XAUUSD.sc")
        capture.assert_called_once_with(["XAUUSD.sc"], "XAUUSD.sc", "H1")


if __name__ == "__main__":
    unittest.main()
