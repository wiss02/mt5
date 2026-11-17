"""
Prueba de conexión Dual: DEMO (Metatrader-2) y REAL (MetaTrader 5).
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.core.mt5_connector import MT5Connector

console = Console()

def test_account(connector, mode: str):
    console.print(Panel(f"[bold cyan]Probando conexión en modo: [bold yellow]{mode}[/bold yellow][/bold cyan]"))
    success = connector.connect(mode=mode)
    if not success:
        console.print(f"[bold red]❌ No se pudo conectar a la terminal {mode}.[/bold red]")
        console.print(f"[yellow]Nota: Si la terminal {mode} no está abierta, por favor ábrela con doble clic para que responda.[/yellow]\n")
        return False

    summary = connector.get_account_summary()
    table = Table(title=f"📊 Datos de la Cuenta ({mode})", style="green" if mode == "DEMO" else "red")
    table.add_column("Campo", style="cyan")
    table.add_column("Valor", style="white")
    for k, v in summary.items():
        table.add_row(k.replace("_", " ").title(), str(v))
    console.print(table)
    
    # Probar tick de EURUSD
    tick = connector.get_symbol_tick("EURUSD")
    if tick:
        console.print(f"[bold green]Tick EURUSD ({mode}):[/bold green] Bid={tick['bid']} | Ask={tick['ask']} | Spread={tick['spread_pips']} pips")
    
    console.print(f"[green]✅ Conexión con {mode} verificada con éxito.[/green]\n")
    return True

def main():
    connector = MT5Connector()
    
    # 1. Probar terminal DEMO
    console.print("[bold yellow]1. Probando terminal DEMO (C:\\Program Files\\Metatrader-2\\terminal64.exe)...[/bold yellow]")
    test_account(connector, "DEMO")
    
    # 2. Probar terminal REAL
    console.print("[bold yellow]2. Probando terminal REAL (C:\\Program Files\\MetaTrader 5\\terminal64.exe)...[/bold yellow]")
    test_account(connector, "REAL")
    
    connector.disconnect()

if __name__ == "__main__":
    main()

