"use strict";

const byId = (id) => document.getElementById(id);
const text = (id, content) => { byId(id).textContent = content; };
const dash = "—";
const sections = {
  resumen: ["Vista general", "Cuenta, cotizaciones y posiciones en MetaTrader 5."],
  mercados: ["Mercados", "Selecciona un instrumento de tu lista para ver sus velas."],
  riesgo: ["Riesgo y lotaje", "Métricas de cuenta y reglas del gestor en revisión."],
  posiciones: ["Posiciones", "Consulta precios, niveles de protección y resultado abierto."],
  agentes: ["Agentes", "Consulta la última captura exportada por el motor de análisis."],
  configuracion: ["Configuración", "Revisa la conexión activa y las opciones del panel."],
};

let page = "resumen";
let snapshot = null;
let period = "M15";
let watch = null;
let focus = null;
let request = null;
let changingTerminal = false;
let catalog = [];
let watchDraft = new Set();
let plotlyLoading = null;
let chartVersion = 0;

const dateFormat = new Intl.DateTimeFormat("es-BO", {
  weekday: "long", day: "numeric", month: "long", timeZone: "America/La_Paz",
});
const currencyNumber = new Intl.NumberFormat("es-BO", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const chartDate = new Intl.DateTimeFormat("es-BO", {day: "numeric", month: "short", timeZone: "UTC"});
const chartTime = new Intl.DateTimeFormat("es-BO", {hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "UTC"});

function money(value, currency = "") {
  return Number.isFinite(value) ? [currencyNumber.format(value), currency].filter(Boolean).join(" ") : dash;
}

function price(value, digits) {
  return Number.isFinite(value) ? value.toFixed(Number.isInteger(digits) ? Math.min(12, Math.max(0, digits)) : 5) : dash;
}

function age(seconds) {
  if (!Number.isFinite(seconds)) return "Hora no verificada";
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h`;
  return `${Math.floor(seconds / 86400)} d`;
}

async function api(path, options) {
  const response = await fetch(path, {cache: "no-store", ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "No se pudo completar la consulta.");
  return data;
}

function notice(message, tone = "warning") {
  const element = byId("panel-notice");
  element.textContent = message;
  element.className = `alert alert-${tone} py-2 px-3`;
  element.hidden = !message;
}

function renderRoute(withFocus = false) {
  const key = window.location.hash.slice(1);
  page = Object.hasOwn(sections, key) ? key : "resumen";
  text("page-title", sections[page][0]);
  text("page-description", sections[page][1]);
  document.querySelectorAll("[data-pages]").forEach((section) => {
    section.hidden = !section.dataset.pages.split(" ").includes(page);
  });
  document.querySelectorAll(".side-nav a").forEach((link) => {
    const active = link.hash === `#${page}`;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  if (withFocus && key !== "workspace") {
    byId("workspace").focus({preventScroll: true});
    window.scrollTo(0, 0);
  }
  renderChart();
  refresh(true);
}

function drawAccount(data) {
  const account = data?.account || {};
  const connected = data?.connected === true;
  const positionCount = data?.positions?.length;
  text("balance", money(account.balance, account.currency));
  text("equity", money(account.equity, account.currency));
  text("floating-profit", money(account.floating_profit, account.currency));
  byId("floating-profit").classList.toggle("gain", account.floating_profit > 0);
  byId("floating-profit").classList.toggle("loss", account.floating_profit < 0);
  text("free-margin", money(account.free_margin, account.currency));
  text("position-count", Number.isInteger(positionCount) ? `${positionCount} posiciones abiertas` : "Posiciones abiertas");
  text("sidebar-server", account.server || "Terminal local");
  text("settings-server", account.server || dash);
  text("settings-account", data?.account_kind || dash);
  text("settings-leverage", account.leverage ? `1:${account.leverage}` : dash);
  text("connection-label", connected ? data.account_kind : data ? "Sin conexión" : "Sin datos");
  byId("connection-state").dataset.state = connected ? "online" : "offline";
  text("terminal-button-label", connected ? "Terminal" : "Conectar MT5");
  byId("edit-watch").disabled = !connected;
  byId("disconnect").disabled = !connected || changingTerminal;
  document.querySelectorAll("[data-period]").forEach((button) => { button.disabled = !connected; });
}

function smallEmpty(icon, label) {
  const empty = document.createElement("div");
  empty.className = "small-empty";
  const mark = document.createElement("i");
  mark.className = `bi ${icon}`;
  mark.setAttribute("aria-hidden", "true");
  const caption = document.createElement("p");
  caption.textContent = label;
  empty.append(mark, caption);
  return empty;
}

function symbolName(symbol) {
  const names = {
    XAUUSD: "Oro · USD", XAGUSD: "Plata · USD", EURUSD: "Euro · USD",
    GBPUSD: "Libra · USD", USDJPY: "Dólar · Yen", BTCUSD: "Bitcoin · USD",
  };
  return names[symbol.slice(0, 6).toUpperCase()] || "Instrumento MT5";
}

function makeQuoteRow(symbol) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "watch-row";
  row.dataset.symbol = symbol;
  row.innerHTML = '<span><strong></strong><small></small></span><span class="watch-price"><strong></strong><small><span class="tick-dot" aria-hidden="true"></span><span></span></small></span>';
  row.querySelector("strong").textContent = symbol;
  row.querySelector("small").textContent = symbolName(symbol);
  row.addEventListener("click", () => {
    focus = symbol;
    refresh(true);
  });
  return row;
}

function drawWatch(data) {
  const quotes = data?.quotes ?? [];
  const list = byId("watch-list");
  if (!quotes.length) {
    list.replaceChildren(smallEmpty("bi-binoculars", data?.connected
      ? "Agrega los instrumentos que quieras seguir."
      : "Conecta MT5 para agregar instrumentos."));
  } else {
    const current = [...list.querySelectorAll(".watch-row")];
    if (current.map((row) => row.dataset.symbol).join("\n") !== quotes.map((quote) => quote.symbol).join("\n")) {
      list.replaceChildren(...quotes.map((quote) => makeQuoteRow(quote.symbol)));
    }
    [...list.children].forEach((row, i) => {
      const tick = quotes[i];
      row.setAttribute("aria-pressed", String(tick.symbol === focus));
      row.querySelector(".watch-price strong").textContent = price(tick.bid, tick.digits);
      const fresh = tick.freshness === "Reciente";
      row.querySelector(".tick-dot").className = `tick-dot ${tick.unavailable ? "" : fresh ? "fresh" : "stale"}`;
      row.querySelector(".watch-price small > :last-child").textContent = tick.unavailable
        ? "Sin cotización" : fresh ? `Hace ${age(tick.age_seconds)}` : tick.freshness;
    });
  }
  const tick = quotes.find((entry) => entry.symbol === focus);
  const spread = tick?.point > 0 ? `${((tick.ask - tick.bid) / tick.point).toFixed(1)} pts` : dash;
  text("watch-detail", tick && !tick.unavailable
    ? `Ask ${price(tick.ask, tick.digits)} · Spread ${spread}`
    : "Cuando elijas un símbolo verás el ask y el spread.");
}

function tableRows(id, rows) {
  const body = byId(id);
  body.replaceChildren(...rows.map((values) => {
    const row = document.createElement("tr");
    values.forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      if (index === 0) cell.scope = "row";
      cell.textContent = value ?? dash;
      row.append(cell);
    });
    return row;
  }));
}

function drawPositions(data) {
  const positions = data?.positions;
  const hasRows = Boolean(positions?.length);
  byId("positions-empty").hidden = hasRows;
  byId("positions-empty").querySelector("p").textContent = data?.connected
    ? positions ? "No hay posiciones abiertas en esta cuenta." : "MT5 no devolvió las posiciones."
    : "Conecta MT5 para consultar tus posiciones.";
  byId("positions-total").hidden = !Array.isArray(positions);
  text("positions-total", positions?.length ?? "");
  byId("positions-table").hidden = !hasRows;
  byId("positions-warning").hidden = !positions?.some((position) => !position.sl);
  if (hasRows) {
    tableRows("position-rows", positions.map((position) => [
      position.symbol, position.type, position.volume, position.price_open, position.current_price,
      position.sl || "Sin SL", position.tp || "Sin TP", money(position.profit, data.account.currency),
    ]));
  }
}

function loadPlotly() {
  if (!plotlyLoading) {
    plotlyLoading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/assets/plotly.js";
      script.onload = () => resolve(window.Plotly);
      script.onerror = () => {
        script.remove();
        plotlyLoading = null;
        reject(new Error("No se pudo cargar el gráfico."));
      };
      document.head.append(script);
    });
  }
  return plotlyLoading;
}

async function renderChart() {
  const version = ++chartVersion;
  if (!["resumen", "mercados"].includes(page)) return;
  const chart = byId("candle-chart");
  const data = snapshot;
  const hasCandles = Boolean(data?.candles?.length);
  text("instrument-title", data?.focus || "Gráfico de velas");
  text("instrument-caption", data?.focus ? `${symbolName(data.focus)} · ${data.period}` : "MetaTrader 5 · UTC");
  chart.hidden = !hasCandles;
  byId("chart-empty").hidden = hasCandles;
  byId("reset-chart").hidden = !hasCandles;
  byId("chart-connect").hidden = Boolean(data?.connected);
  if (!hasCandles) {
    text("chart-empty-title", !data?.connected ? "Conecta MetaTrader 5" : data.focus ? "Velas no disponibles" : "Selecciona un mercado");
    text("chart-empty-caption", !data?.connected ? "Selecciona tu terminal para ver el gráfico y las cotizaciones."
      : data.focus ? "El terminal todavía no devolvió velas para este periodo." : "Agrega instrumentos a tu lista de seguimiento.");
    return;
  }
  try {
    const plotly = await loadPlotly();
    if (version !== chartVersion) return;
    const theme = getComputedStyle(document.documentElement);
    const color = (token) => theme.getPropertyValue(token).trim();
    const candle = data.candles;
    // Una posición por vela; las pausas del bróker no consumen espacio del gráfico.
    const times = candle.map((bar) => bar.time);
    const tickCount = Math.min(times.length, Math.max(2, Math.min(7, Math.floor(chart.clientWidth / 100))));
    const ticks = Array.from({length: tickCount}, (_, i) => times[Math.floor((i + 0.5) * times.length / tickCount)]);
    const labels = ticks.map((time) => {
      const utc = new Date(time.endsWith("Z") || time.includes("+") ? time : `${time}Z`);
      return data.period === "D1" ? chartDate.format(utc) : `${chartTime.format(utc)}<br>${chartDate.format(utc)}`;
    });
    chart.setAttribute("aria-label", `Gráfico de velas de ${data.focus}, periodo ${data.period}`);
    await plotly.react(chart, [{
      type: "candlestick", name: data.focus,
      x: times, open: candle.map((bar) => bar.open),
      high: candle.map((bar) => bar.high), low: candle.map((bar) => bar.low), close: candle.map((bar) => bar.close),
      increasing: {line: {color: "#1b9a76", width: 1}, fillcolor: "#1b9a76"},
      decreasing: {line: {color: "#d55b69", width: 1}, fillcolor: "#d55b69"},
    }], {
      uirevision: `${data.revision}-${data.focus}-${data.period}`,
      autosize: true, dragmode: "pan", hovermode: "closest",
      paper_bgcolor: color("--surface"), plot_bgcolor: color("--surface"),
      font: {family: "Segoe UI, sans-serif", size: 11, color: color("--muted")},
      margin: {l: 8, r: 8, t: 20, b: 33},
      xaxis: {
        type: "category", gridcolor: color("--grid"), rangeslider: {visible: false},
        tickmode: "array", tickvals: ticks, ticktext: labels,
      },
      yaxis: {gridcolor: color("--grid"), side: "right", automargin: true, tickformat: "~g", zeroline: false},
    }, {
      responsive: true, displaylogo: false, displayModeBar: true,
      modeBarButtons: [["zoomIn2d", "zoomOut2d"]],
    });
  } catch {
    if (version !== chartVersion) return;
    chart.hidden = true;
    byId("reset-chart").hidden = true;
    byId("chart-empty").hidden = false;
    text("chart-empty-title", "No se pudo cargar el gráfico");
    text("chart-empty-caption", "Pulsa Actualizar para volver a intentarlo.");
  }
}

function drawAgents(data, message = "") {
  text("agent-time", data ? `${data.last_update} · ${data.freshness === "Desactualizada" ? "Captura antigua" : data.freshness}`
    : message || "Sin captura disponible");
  const mode = data?.mode;
  byId("agent-mode").hidden = !mode;
  text("agent-mode", mode || "");
  const alerts = [];
  if (data) {
    const auto = data.auto_trade === true ? "activo" : data.auto_trade === false ? "desactivado" : "sin confirmar";
    alerts.push(`Auto-trade en la captura: ${auto}. Ese valor no indica si el gestor externo puede ajustar el SL.`);
    if (data.other_account) alerts.push("La captura corresponde a otra cuenta.");
  }
  byId("agent-warning").hidden = !alerts.length;
  text("agent-warning", alerts.join(" "));
  const rows = Array.isArray(data?.scanned_markets) ? data.scanned_markets.filter((market) => market && typeof market === "object") : [];
  byId("agent-table").hidden = !rows.length;
  byId("agent-empty").hidden = Boolean(rows.length);
  tableRows("agent-rows", rows.map((market) => [
    market.symbol, market.signal, market.score, market.macro_trend, market.rsi,
  ]));
}

function applySnapshot(data) {
  snapshot = data;
  focus = data?.focus ?? null;
  text("page-date", dateFormat.format());
  drawAccount(data);
  drawWatch(data);
  drawPositions(data);
  renderChart();
  const updated = data?.captured_at;
  text("last-update", updated ? `Última consulta ${updated.slice(11, 19)} · 5 s` : "Consulta automática · 5 s");
  if (data?.connected && data.account_kind !== data.terminal_mode) {
    notice(`El terminal elegido es ${data.terminal_mode}, pero MT5 informa una cuenta ${data.account_kind}.`);
  } else if (data && !data.connected && data.message.startsWith("MT5 no")) {
    notice(data.message);
  } else {
    notice("");
  }
}

async function refresh(force = false) {
  if (changingTerminal || (request && !force)) return;
  request?.abort();
  const active = new AbortController();
  request = active;
  const query = new URLSearchParams({period});
  if (watch !== null) {
    (watch.length ? watch : [""]).forEach((symbol) => query.append("watch", symbol));
  }
  if (focus) query.set("symbol", focus);
  try {
    const next = await api(`/api/snapshot?${query}`, {signal: active.signal});
    if (active.signal.aborted) return;
    if (snapshot && next.terminal_mode !== snapshot.terminal_mode && watch !== null) {
      watch = null;
      focus = null;
      return refresh(true);
    }
    applySnapshot(next);
    if (page === "agentes") {
      try {
        const agents = await api("/api/agents", {signal: active.signal});
        if (!active.signal.aborted) drawAgents(agents.snapshot);
      } catch (error) {
        if (!active.signal.aborted) drawAgents(null, error.message);
      }
    }
  } catch (error) {
    if (active.signal.aborted) return;
    applySnapshot(null);
    if (page === "agentes") drawAgents(null, "No se pudo consultar el panel.");
    notice("No se pudo consultar el panel local. Pulsa Actualizar para reintentar.");
  } finally {
    if (request === active) request = null;
  }
}

async function updateTerminal(mode) {
  if (changingTerminal) return;
  changingTerminal = true;
  request?.abort();
  const message = byId("terminal-message");
  message.hidden = false;
  message.classList.remove("text-danger");
  message.textContent = mode === "disconnect" ? "Desconectando…" : `Conectando a ${mode}…`;
  byId("connect").disabled = true;
  byId("disconnect").disabled = true;
  try {
    await api("/api/terminal", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mode}),
    });
    bootstrap.Modal.getInstance(byId("terminal-modal")).hide();
  } catch (error) {
    message.classList.add("text-danger");
    message.textContent = error.message;
  } finally {
    changingTerminal = false;
    byId("connect").disabled = false;
    watch = null;
    focus = null;
    refresh(true);
  }
}

function drawCatalog() {
  const query = byId("symbol-search").value.trim().toLowerCase();
  const visible = catalog.filter((symbol) => symbol.toLowerCase().includes(query));
  const limit = watchDraft.size >= 4;
  text("watch-count", `${watchDraft.size} / 4 seleccionados${visible.length > 60 ? " · Escribe para filtrar más símbolos" : ""}`);
  const options = visible.slice(0, 60).map((symbol) => {
    const row = document.createElement("label");
    row.className = "symbol-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "form-check-input";
    input.checked = watchDraft.has(symbol);
    input.disabled = limit && !input.checked;
    input.addEventListener("change", () => {
      if (input.checked) watchDraft.add(symbol);
      else watchDraft.delete(symbol);
      drawCatalog();
      byId("symbol-options").querySelectorAll("input")[visible.indexOf(symbol)]?.focus();
    });
    row.append(input, document.createTextNode(symbol));
    return row;
  });
  byId("symbol-options").replaceChildren(...(options.length ? options : [smallEmpty("bi-search", "No se encontraron símbolos.")]));
}

function setTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.dataset.bsTheme = dark ? "dark" : "light";
  const button = byId("theme-toggle");
  button.setAttribute("aria-label", dark ? "Activar tema claro" : "Activar tema oscuro");
  button.firstElementChild.className = dark ? "bi bi-sun" : "bi bi-moon-stars";
  renderChart();
}

document.querySelector(".side-nav").addEventListener("click", (event) => {
  if (event.target.closest("a")) bootstrap.Offcanvas.getInstance(byId("sidebar"))?.hide();
});
document.querySelector(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  byId("workspace").focus();
});
window.addEventListener("hashchange", () => renderRoute(true));
byId("refresh").addEventListener("click", () => refresh(true));
byId("terminal-modal").addEventListener("show.bs.modal", () => {
  byId("terminal-mode").value = snapshot?.terminal_mode ?? "DEMO";
  byId("terminal-message").hidden = true;
});
byId("terminal-form").addEventListener("submit", (event) => {
  event.preventDefault();
  updateTerminal(byId("terminal-mode").value);
});
byId("disconnect").addEventListener("click", () => updateTerminal("disconnect"));
byId("theme-toggle").addEventListener("click", () => {
  const theme = document.documentElement.dataset.bsTheme === "dark" ? "light" : "dark";
  localStorage.setItem("nexus-theme", theme);
  setTheme(theme);
});
document.querySelector(".period-choices").addEventListener("click", (event) => {
  const button = event.target.closest("[data-period]");
  if (!button || !snapshot?.connected) return;
  period = button.dataset.period;
  document.querySelectorAll("[data-period]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  refresh(true);
});
byId("reset-chart").addEventListener("click", () => {
  window.Plotly?.relayout(byId("candle-chart"), {"xaxis.autorange": true, "yaxis.autorange": true});
});
byId("watch-modal").addEventListener("show.bs.modal", async () => {
  watchDraft = new Set(snapshot?.watch ?? []);
  catalog = [];
  byId("symbol-search").value = "";
  byId("save-watch").disabled = true;
  text("watch-count", "Cargando símbolos…");
  byId("symbol-options").replaceChildren();
  try {
    const data = await api("/api/symbols");
    catalog = data.symbols;
    drawCatalog();
    byId("save-watch").disabled = !catalog.length;
  } catch {
    text("watch-count", "No se pudieron cargar los símbolos de MT5.");
  }
});
byId("symbol-search").addEventListener("input", drawCatalog);
byId("save-watch").addEventListener("click", () => {
  watch = [...watchDraft];
  bootstrap.Modal.getInstance(byId("watch-modal")).hide();
  refresh(true);
});

setTheme(localStorage.getItem("nexus-theme"));
renderRoute();
setInterval(() => { if (!document.hidden) refresh(); }, 5000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
new ResizeObserver(([entry]) => {
  const chart = entry.target;
  if (entry.contentRect.width > 0 && chart.data) window.Plotly.Plots.resize(chart).catch(() => {});
}).observe(byId("candle-chart"));
