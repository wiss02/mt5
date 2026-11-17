# Nexus

Panel web de supervisión para MetaTrader 5 con vista de cuenta, seguimiento de mercados, gráficos de velas y consulta de las capturas de los agentes. La interfaz usa Bootstrap y se adapta a pantallas de escritorio y celular.

## Ejecutar el panel

Desde PowerShell en Windows, con Python 3.11 de 64 bits y MetaTrader 5 instalado y configurado:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.web.app
```

Abre [Nexus en localhost](http://127.0.0.1:8502) y selecciona el terminal desde **Conectar MT5**. Las rutas de los terminales están en [el conector de MT5](src/core/mt5_connector.py). Si usas Gemini en el motor de agentes, copia `.env.example` a `.env` y añade tu clave de forma local.

El proyecto también incluye un módulo de órdenes manuales y un motor de agentes que puede gestionar posiciones de acuerdo con su configuración. Las pruebas del panel pueden ejecutarse sin conectar una cuenta ni iniciar el motor:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Puedes continuar revisando y editando el código desde GitHub en el celular. Para ver cotizaciones en el panel local se necesita el equipo Windows que ejecuta MT5 y el servidor.

La [guía de coordinación](PROJECT_STATUS.md) recoge la arquitectura y el avance para Codex y Antigravity.
