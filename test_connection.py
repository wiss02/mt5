"""
Script de prueba de conexión con MetaTrader 5 (MT5).
Verifica:
1. Inicialización y enlace con la terminal instalada.
2. Estado de la cuenta (login, balance, equidad, moneda, apalancamiento).
3. Prueba de lectura de ticks en tiempo real (EURUSD, XAUUSD, BTCUSD).
4. Prueba de lectura de velas (M15).
"""

import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.core.mt5_connector import MT5Connector

console = Console()

def run_test():
    console.print(Panel.fit("[bold cyan]Probando Conexión con MetaTrader 5[/bold cyan]", border_style="cyan"))
    
    connector = MT5Connector()
    
    console.print("\n[yellow]⏳ Conectando con MetaTrader 5...[/yellow]")
    connected = connector.connect()
    
    if not connected:
        console.print("[bold red]❌ No se pudo conectar a MT5.[/bold red]")
        console.print("[yellow]Sugerencias:[/yellow]")
        console.print(" 1. Asegúrate de que la aplicación MetaTrader 5 esté abierta e iniciada con tu cuenta (demo o real).")
        console.print(" 2. En MT5, ve a 'Herramientas' -> 'Opciones' -> pestaña 'Asesores Expertos' y verifica que 'Permitir trading algorítmico' esté habilitado si deseas operar.")
        sys.exit(1)
        
    console.print("[bold green]✅ ¡Conexión exitosa con MetaTrader 5![/bold green]\n")
    
    # 1. Resumen de la cuenta
    account = connector.get_account_summary()
    table_acc = Table(title="📊 Datos de la Cuenta Conectada", style="blue")
    table_acc.add_column("Propiedad", style="cyan", no_wrap=True)
    table_acc.add_column("Valor", style="white")
    
    for key, val in account.items():
        table_acc.add_row(key.replace("_", " ").title(), str(val))
    console.print(table_acc)
    
    # 2. Prueba de mercado (Ticks en vivo)
    test_symbols = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"]
    table_ticks = Table(title="\n📈 Prueba de Precios en Tiempo Real (Market Watch)", style="green")
    table_ticks.add_column("Símbolo", style="cyan")
    table_ticks.add_column("Bid", style="green")
    table_ticks.add_column("Ask", style="red")
    table_ticks.add_column("Spread (Pips)", style="yellow")
    table_ticks.add_column("Hora", style="white")
    
    found_any = False
    for sym in test_symbols:
        tick = connector.get_symbol_tick(sym)
        if tick:
            found_any = True
            table_ticks.add_row(
                tick["symbol"],
                f"{tick['bid']:.5f}",
                f"{tick['ask']:.5f}",
                f"{tick['spread_pips']}",
                tick["time"].strftime("%H:%M:%S")
            )
        else:
            table_ticks.add_row(sym, "No disponible", "-", "-", "-")
            
    console.print(table_ticks)
    
    # 3. Prueba de velas históricas
    symbol_to_check = "EURUSD"
    df = connector.get_ohlcv(symbol_to_check, timeframe="M15", count=5)
    if df is not None:
        console.print(f"\n[bold green]✅ Velas M15 obtenidas correctamente para {symbol_to_check}:[/bold green]")
        console.print(df.to_string(index=False))
    else:
        console.print(f"\n[yellow]⚠️ No se pudieron descargar velas de prueba para {symbol_to_check} (comprueba el símbolo exacto en tu broker).[/yellow]")

    connector.disconnect()
    console.print("\n[bold cyan]🏁 Prueba de conexión finalizada con éxito.[/bold cyan]")

if __name__ == "__main__":
    run_test()

