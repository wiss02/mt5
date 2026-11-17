# 🚀 PLATAFORMA DE TRADING CUANTITATIVO MULTI-AGENTE (MT5 + SWARM CONSENSUS)
> **Documento de Sincronización para Colaboración entre ChatGPT y Antigravity**  
> *Última actualización: Noviembre 2026*

---

## 📌 1. Estado Actual del Proyecto (Status: 100% OPERATIVO EN VIVO)
- **Servidor Web Local:** Nexus se inicia con `.\.venv\Scripts\python.exe -m src.web.app` en `http://127.0.0.1:8502`.
- **Entorno:** Python `3.11.7` (64-bit) en `.venv`.
- **Modo Dual MT5:** Totalmente funcional entre Demo (Exness) y Real (Vantage).
- **Red de Agentes de Consenso:** Activa en `src/agents/consensus_network.py`.
- **Enlace de Datos en Tiempo Real:** `data/live_state.json` y `data/agent_debate.json`.

---

## 🏛️ 2. El Comité de Agentes en Vivo (Consensus Network)

Para lograr consistencia y rentabilidad real protegiendo el capital, las decisiones se toman a través de un **comité de 4 agentes especializados** que debaten y votan en tiempo real:

1. 🐂 **`BullHunter` (Especialista en Estructura Alcista y Liquidez):**
   - Identifica confluencias de compra, tomas de liquidez en mínimos, rebotes en EMA 21/50 y momentum RSI.
2. 🐻 **`BearCritic` (El Abogado del Diablo):**
   - Busca activamente las fallas, resistencias mayores H1, trampas de liquidez y spreads elevados para invalidar malas operaciones.
3. 🛡️ **`RiskSentinel` (Matemático de Capital):**
   - Aplica el control de riesgo: cálculo de lote exacto según 1% de riesgo por trade, ratio R/B mínimo 1:2.0 y Stop Loss por ATR.
4. ⚖️ **`ChiefArbiter` (Juez y Director de Mesa):**
   - Pondera el debate entre BullHunter y BearCritic. Solo aprueba la orden si el **Consenso supera el 75%** y RiskSentinel otorga luz verde.

---

## 🌐 3. Servidor Web del Panel (Creado por ChatGPT)
- **URL Local:** `http://127.0.0.1:8502`
- **Endpoints:**
  - `GET /` -> Interfaz completa de supervisión NEXUS.
  - `GET /api/snapshot` -> Datos de cuenta, métricas y velas.
  - `GET /api/agents` -> Estado del escáner multimercado y debates del comité.
  - `POST /api/terminal` -> Conmutación en caliente entre cuenta DEMO y REAL.
  - `POST /api/manual_trade` -> Envío manual de órdenes al terminal conectado.

---

## 📁 4. Estructura de Archivos
```text
plataforma/
├── .venv/                         # Entorno virtual
├── data/
│   ├── live_state.json            # Estado maestro para la web
│   └── agent_debate.json          # Transcripción del debate del comité
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   └── mt5_connector.py       # Conexión dual MT5 y ejecución de órdenes
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── scout_agent.py         # Escáner cuantitativo MTF
│   │   ├── consensus_network.py   # Red de debate de 4 agentes
│   │   ├── risk_guardian.py       # Gestor de riesgo matemático
│   │   ├── trade_manager.py       # Breakeven y trailing stop
│   │   └── brain_agent.py         # Orquestador del sistema
│   └── web/                       # Panel Web NEXUS (HTTP Server + Static Assets)
│       ├── app.py                 # Servidor HTTP local (puerto 8502 por defecto)
│       └── static/                # HTML, CSS, JS, Bootstrap
├── run_agents.py                  # Ciclo de agentes por consola
├── manual_order.py                # Envío manual de órdenes por consola
├── test_debate.py                 # Prueba del debate en directo
└── PROJECT_STATUS.md              # Sincronización con ChatGPT
```

## 5. Repositorio y datos locales

El README contiene el inicio rápido de Nexus y las pruebas del panel. Las capturas que genera MT5, el debate de los agentes, las credenciales y el entorno virtual quedan en el equipo. Para retomar el trabajo con Codex o Antigravity, consultar este archivo y el historial del repositorio.
