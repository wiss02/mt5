"""
Script ejecutor de los Agentes de Trading en Tiempo Real.
Corre un ciclo de escaneo completo en DEMO (o REAL),
evalúa los mercados con los Scouts, valida con Risk Guardian y muestra los resultados.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.agents.brain_agent import BrainAgent

console = Console()

def main():
    console.print(Panel.fit("[bold green]🤖 Iniciando Cerebro Multi-Agente Cuantitativo[/bold green]\nModo: DEMO | Mercados: EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD", border_style="green"))
    
    brain = BrainAgent(default_mode="DEMO", symbols=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"], auto_trade=False)
    
    if not brain.initialize():
        console.print("[bold red]❌ Error al inicializar el cerebro.[/bold red]")
        return

    console.print("\n[yellow]🔍 Ejecutando ciclo de escaneo multimercado en tiempo real...[/yellow]\n")
    state = brain.run_cycle()

    # Tabla de Mercados Escaneados
    table_markets = Table(title="📊 Escáner Multimercado en Tiempo Real (Agente Scout)", style="cyan")
    table_markets.add_column("Símbolo", style="bold white")
    table_markets.add_column("Tendencia H1", style="magenta")
    table_markets.add_column("Precio", style="yellow")
    table_markets.add_column("Spread", style="dim white")
    table_markets.add_column("RSI", style="cyan")
    table_markets.add_column("Score Confluencia", style="bold")
    table_markets.add_column("Señal Agente", style="bold")

    for m in state["scanned_markets"]:
        sig = m.get("signal", "HOLD")
        sig_style = "[bold green]BUY[/bold green]" if sig == "BUY" else ("[bold red]SELL[/bold red]" if sig == "SELL" else "[dim]HOLD[/dim]")
        score = m.get("score", 0)
        score_color = "green" if score >= 75 else ("yellow" if score >= 50 else "dim")

        table_markets.add_row(
            m.get("symbol", "-"),
            m.get("macro_trend", "-"),
            str(m.get("current_price", "-")),
            f"{m.get('spread_pips', '-')} pips",
            str(m.get("rsi", "-")),
            f"[{score_color}]{score}/100[/{score_color}]",
            sig_style
        )
    console.print(table_markets)

    # Detalle de razones
    console.print("\n[bold]🧠 Análisis Detallado del Cerebro por Activo:[/bold]")
    for m in state["scanned_markets"]:
        reasons = m.get("reasons", [])
        console.print(f" • [cyan]{m['symbol']}[/cyan] ({m['signal']} - Score {m['score']}/100): " + ", ".join(reasons))

    console.print(f"\n[bold green]✅ Ciclo completado. Estado sincronizado en data/live_state.json para el panel web de ChatGPT.[/bold green]")

if __name__ == "__main__":
    main()

