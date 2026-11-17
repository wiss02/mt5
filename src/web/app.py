"""Servidor local del panel Nexus."""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import sys
from datetime import datetime
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.mt5_connector import TIMEFRAMES
from src.core.manual_trader import ManualTrader
from src.web.mt5_service import MT5ReadService, quote_freshness

STATIC = Path(__file__).resolve().parent / "static"
STATE_FILE = ROOT / "data" / "live_state.json"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/panel.css": ("panel.css", "text/css; charset=utf-8"),
    "/assets/panel.js": ("panel.js", "text/javascript; charset=utf-8"),
    "/assets/vendor/bootstrap.min.css": ("vendor/bootstrap.min.css", "text/css; charset=utf-8"),
    "/assets/vendor/bootstrap.bundle.min.js": ("vendor/bootstrap.bundle.min.js", "text/javascript; charset=utf-8"),
    "/assets/vendor/bootstrap-icons.min.css": ("vendor/bootstrap-icons.min.css", "text/css; charset=utf-8"),
    "/assets/vendor/fonts/bootstrap-icons.woff2": ("vendor/fonts/bootstrap-icons.woff2", "font/woff2"),
}


@lru_cache(maxsize=2)
def plotly_bundle(compressed: bool) -> bytes:
    bundle = get_plotlyjs().encode("utf-8")
    return gzip.compress(bundle, compresslevel=5) if compressed else bundle


def agent_snapshot(current_account: dict, path: Path = STATE_FILE) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        updated = datetime.strptime(data.get("last_update", ""), "%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError, TypeError):
        return None

    freshness, age = quote_freshness(updated)
    account = data.get("account")
    other_account = (
        isinstance(account, dict)
        and bool(account.get("login") and current_account.get("login"))
        and (account["login"], account.get("server")) != (current_account["login"], current_account.get("server"))
    )
    return {
        "last_update": data["last_update"],
        "freshness": freshness,
        "age_seconds": age,
        "mode": data.get("mode"),
        "auto_trade": data.get("auto_trade"),
        "other_account": other_account,
        "scanned_markets": data.get("scanned_markets"),
    }


def json_values(value):
    if isinstance(value, dict):
        return {key: json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_values(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class PanelServer(ThreadingHTTPServer):
    def __init__(self, port: int, service: MT5ReadService):
        self.service = service
        super().__init__(("127.0.0.1", port), PanelHandler)


class PanelHandler(BaseHTTPRequestHandler):
    server: PanelServer
    timeout = 15

    def log_request(self, code="-", size="-"):
        if str(code).startswith("5"):
            super().log_request(code, size)

    def local_host(self) -> bool:
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def send_body(self, payload, content_type, status=HTTPStatus.OK, cache="no-store", encoding=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if encoding:
            self.send_header("Content-Encoding", encoding)
            self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data, status=HTTPStatus.OK):
        payload = json.dumps(json_values(data), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_body(payload, "application/json; charset=utf-8", status)

    def do_GET(self):
        if not self.local_host():
            self.send_json({"message": "Dirección local requerida."}, HTTPStatus.FORBIDDEN)
            return
        target = urlsplit(self.path)
        path = target.path
        try:
            if path == "/api/snapshot":
                query = parse_qs(target.query, keep_blank_values=True, max_num_fields=12)
                timeframe = query.get("period", ["M15"])[0]
                if timeframe not in TIMEFRAMES:
                    raise ValueError("Periodo no válido.")
                watch = query.get("watch")
                if watch is not None and len(watch) > 4:
                    raise ValueError("Selecciona hasta cuatro instrumentos.")
                focus = query.get("symbol", [None])[0]
                snapshot = self.server.service.dashboard(watch, focus, timeframe)
                candles = snapshot["candles"]
                snapshot["candles"] = candles.to_dict(orient="records") if candles is not None else []
                snapshot.get("account", {}).pop("login", None)
                self.send_json(snapshot)
            elif path == "/api/symbols":
                self.send_json({"symbols": self.server.service.symbols()})
            elif path == "/api/agents":
                status = self.server.service.status()
                self.send_json({"snapshot": agent_snapshot(status.get("account", {}))})
            elif path == "/assets/plotly.js":
                compress = "gzip" in self.headers.get("Accept-Encoding", "")
                self.send_body(plotly_bundle(compress), "text/javascript; charset=utf-8",
                               cache="private, max-age=3600", encoding="gzip" if compress else None)
            elif path in ASSETS:
                name, content_type = ASSETS[path]
                cache = "private, max-age=86400" if name.startswith("vendor/") else "no-store"
                self.send_body((STATIC / name).read_bytes(), content_type, cache=cache)
            else:
                self.send_json({"message": "Página no encontrada."}, HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except ValueError as error:
            self.send_json({"message": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception:
            logging.exception("Error al consultar el panel")
            self.send_json({"message": "No se pudieron consultar los datos del panel."},
                           HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        if not self.local_host() or self.headers.get("Origin") != f"http://{self.headers.get('Host')}":
            self.send_json({"message": "Solicitud de origen no permitido."}, HTTPStatus.FORBIDDEN)
            return

        if self.path == "/api/manual_trade":
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length))
                symbol = payload.get("symbol", "EURUSD")
                action = payload.get("action", "BUY")
                sl_price = payload.get("sl_price")
                sl_pips = payload.get("sl_pips")
                risk_pct = float(payload.get("risk_pct", 2.0))
                tp_ratio = float(payload.get("tp_ratio", 3.0))

                trader = ManualTrader(self.server.service.connector, risk_pct=risk_pct)
                result = trader.execute_order(
                    symbol=symbol,
                    action=action,
                    sl_price=sl_price,
                    sl_pips=sl_pips,
                    tp_ratio=tp_ratio,
                    risk_pct=risk_pct
                )
                if result.get("success"):
                    self.send_json(result, HTTPStatus.OK)
                else:
                    self.send_json(result, HTTPStatus.BAD_REQUEST)
            except Exception as e:
                logging.exception("Error en manual_trade")
                self.send_json({"success": False, "error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if self.path != "/api/terminal":
            self.send_json({"message": "Página no encontrada."}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 200 or self.headers.get_content_type() != "application/json":
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            mode = payload.get("mode") if isinstance(payload, dict) else None
            if mode not in ("DEMO", "REAL", "disconnect"):
                raise ValueError
        except (OSError, ValueError):
            self.send_json({"message": "Selecciona una opción de terminal válida."}, HTTPStatus.BAD_REQUEST)
            return

        service = self.server.service
        try:
            if mode == "disconnect":
                service.disconnect()
                self.send_json({"message": "Terminal desconectado."})
            elif service.connect(mode):
                self.send_json({"message": "Terminal conectado."})
            else:
                self.send_json({"message": service.last_message}, HTTPStatus.SERVICE_UNAVAILABLE)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            logging.exception("Error al cambiar la conexión a MT5")
            self.send_json({"message": "No se pudo cambiar la conexión a MT5."},
                           HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=8502, type=int)
    args = parser.parse_args()
    with PanelServer(args.port, MT5ReadService()) as server:
        print(f"Nexus: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.service.disconnect()


if __name__ == "__main__":
    main()
