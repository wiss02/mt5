"""
Prueba del Comité de Debate de Agentes en Tiempo Real.
"""

from rich.console import Console
from rich.panel import Panel
from src.core.mt5_connector import MT5Connector
from src.agents.scout_agent import ScoutAgent
from src.agents.consensus_network import ConsensusNetwork

console = Console()

def main():
    console.print(Panel.fit("[bold cyan]🎙️ COMITÉ DE TRADING EN VIVO: DEBATE MULTI-AGENTE[/bold cyan]", border_style="cyan"))

    connector = MT5Connector(active_mode="DEMO")
    if not connector.connect():
        console.print("[bold red]❌ Error al conectar a MT5 DEMO.[/bold red]")
        return

    account = connector.get_account_summary()
    scout = ScoutAgent(symbols=["XAUUSD", "EURUSD"])
    network = ConsensusNetwork()

    for symbol in ["XAUUSD", "EURUSD"]:
        console.print(f"\n[bold yellow]════════════════════════════════════════════════════════════[/bold yellow]")
        console.print(f"[bold yellow]👉 SESIÓN DE DEBATE PARA: {symbol}[/bold yellow]")
        console.print(f"[bold yellow]════════════════════════════════════════════════════════════[/bold yellow]\n")

        mkt = scout.analyze_symbol(connector, symbol)
        debate = network.conduct_debate(symbol, mkt, account)

        for msg in debate["debate"]:
            color = "green" if msg["role"] == "Analista Alcista" else ("red" if msg["role"] == "Abogado del Diablo" else ("blue" if msg["role"] == "Guardián de Capital" else "magenta"))
            console.print(f"{msg['avatar']} [bold {color}]{msg['agent']} ({msg['role']})[/bold {color}] a las {msg['timestamp']}:")
            console.print(f"   [white]{msg['text']}[/white]\n")

        verdict_color = "green" if debate["verdict"] in ["BUY", "SELL"] else "yellow"
        console.print(Panel(
            f"[bold {verdict_color}]DECISIÓN FINAL: {debate['verdict']} (Consenso: {debate['consensus_score']}%)[/bold {verdict_color}]\n"
            f"Plan de Ejecución: {debate['execution_plan']}",
            title="⚖️ Sentencia del Comité",
            border_style=verdict_color
        ))

    connector.disconnect()

if __name__ == "__main__":
    main()

