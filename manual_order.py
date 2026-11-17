"""
Script Interactivo para Colocar Órdenes Manuales Inteligentes al 2% de Riesgo.
Calcula el lotaje matemático estricto según la cuenta y coloca SL/TP para dejar correr.
"""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.core.mt5_connector import MT5Connector
from src.core.manual_trader import ManualTrader

console = Console()

def run_manual_trade():
    console.print(Panel.fit("[bold green]⚡ EJECUTOR MANUAL DE TRADING AL 2% DE RIESGO[/bold green]\nProtección automática de ganancias al alcanzar el 1 a 2.", border_style="green"))

    # Conectar a la terminal activa
    mode = "DEMO"
    if len(sys.argv) > 1 and sys.argv[1].upper() in ["DEMO", "REAL"]:
        mode = sys.argv[1].upper()

    connector = MT5Connector(active_mode=mode)
    if not connector.connect():
        console.print("[bold red]❌ No se pudo conectar a MT5.[/bold red]")
        return

    account = connector.get_account_summary()
    balance = account.get("balance", 0.0)
    currency = account.get("currency", "")

    console.print(f"Cuenta Activa: [cyan]{account.get('login')}[/cyan] ({mode}) | Balance: [bold green]{balance:.2f} {currency}[/bold green]")

    trader = ManualTrader(connector, risk_pct=2.0)

    # Parámetros por argumento o por defecto
    symbol = sys.argv[2] if len(sys.argv) > 2 else "EURUSD"
    action = sys.argv[3].upper() if len(sys.argv) > 3 else "BUY"
    sl_pips = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0

    console.print(f"\n[yellow]⏳ Calculando lotaje exacto para {action} en {symbol} con SL de {sl_pips} pips (Riesgo: 2.0%)...[/yellow]")

    res = trader.execute_order(
        symbol=symbol,
        action=action,
        sl_pips=sl_pips,
        tp_ratio=3.0,  # 1:3 para dejar correr
        risk_pct=2.0
    )

    if not res.get("success"):
        console.print(f"[bold red]❌ Operación no realizada:[/bold red] {res.get('error')}")
        if "calculation_details" in res:
            console.print(res["calculation_details"])
    else:
        console.print("\n[bold green]✅ ¡ORDEN EJECUTADA EXITOSAMENTE EN MT5![/bold green]")
        table = Table(title="Detalles de la Operación", style="green")
        table.add_column("Propiedad", style="cyan")
        table.add_column("Valor", style="white")
        for k, v in res.items():
            if k != "success":
                table.add_row(k.replace("_", " ").title(), str(v))
        console.print(table)

    connector.disconnect()

if __name__ == "__main__":
    run_manual_trade()
