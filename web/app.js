/* ==========================================================================
   Panel de Análisis — Keylogger Educativo
   Lógica del cliente. Consulta la API LOCAL /api/data y dibuja todo.
   Sin librerías externas: JavaScript puro y SVG hecho a mano.
   --------------------------------------------------------------------------
   Bloques:
     - Utilidades (selección, escape, formato es-PE, iconos, fechas, debounce)
     - Tooltip flotante accesible (ratón + teclado)
     - Temas (oscuro / claro / hacker) y efectos, con localStorage
     - Carga de datos y estados (cargando / con datos / vacío / error)
     - Render: KPIs, barras, donut, área temporal, timeline
     - Registro por ventana: vista Detalle (ver más/menos) y vista Tabla ordenable
     - Filtro con resaltado, exportación CSV, modo presentación, banner
   Colores de gráficos: se usan variables CSS var(--cat-N); así, al cambiar de
   tema, todo se recolorea al instante sin volver a renderizar.
   ========================================================================== */

"use strict";

/* --- Selección y constantes -------------------------------------------- */
const $ = (sel) => document.querySelector(sel);
const cat = (i) => `var(--cat-${(i % 8) + 1})`;      // color categórico por índice
const TEMAS = ["dark", "light", "hacker"];
const ICONO_TEMA = { dark: "🌙", light: "☀️", hacker: "🖥️" };
const ETIQUETA_TEMA = { dark: "Tema oscuro", light: "Tema claro", hacker: "Tema hacker" };

/* Estado del cliente */
let DATOS = null;         // último JSON recibido (para re-render al cambiar de vista)
let SEGMENTOS = [];       // caché de segmentos para filtro/tabla
let VISTA = "detalle";    // "detalle" | "tabla"
let ORDEN = { col: "ts", dir: "asc" };   // orden de la tabla
let AUTO_TIMER = null, HORA_TIMER = null, ULTIMA_CARGA = null;
let YA_ANIMADO = false;   // las barras/tarjetas solo animan la primera vez

/* ========================================================================
   UTILIDADES
   ======================================================================== */

/** Escapa texto antes de inyectarlo en el DOM (previene inyección/XSS). */
function esc(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

/** Formatea números con separador de miles es-PE. */
function num(n) { return (Number(n) || 0).toLocaleString("es-PE"); }

/** Retarda una función (debounce) para el buscador. */
function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

/** Icono emoji orientativo según el título de la ventana. */
function iconoVentana(nombre) {
  const n = (nombre || "").toLowerCase();
  if (n.includes("chrome") || n.includes("edge") || n.includes("firefox") || n.includes("navegador")) return "🌐";
  if (n.includes("word") || n.includes(".doc") || n.includes("bloc") || n.includes("notepad")) return "📝";
  if (n.includes("code") || n.includes("python") || n.includes("terminal") || n.includes("cmd") || n.includes("powershell")) return "💻";
  if (n.includes("whatsapp") || n.includes("telegram") || n.includes("discord") || n.includes("slack")) return "💬";
  if (n.includes("excel") || n.includes(".xls")) return "📊";
  if (n.includes("mail") || n.includes("correo") || n.includes("outlook") || n.includes("gmail")) return "✉️";
  if (n.includes("otras")) return "🗂️";
  return "🪟";
}

/** Convierte "YYYY-MM-DD HH:MM:SS" en milisegundos (hora local); NaN si falla. */
function parseTs(str) {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(String(str || "").trim());
  if (!m) return NaN;
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]).getTime();
}

/** Hora legible; incluye fecha si el rango abarca varios días. */
function fmtHora(ms, conFecha) {
  const d = new Date(ms), p = (x) => String(x).padStart(2, "0");
  const hora = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  return conFecha ? `${p(d.getDate())}/${p(d.getMonth() + 1)} ${hora}` : hora;
}

/** Redondea hacia arriba a un máximo "bonito" para las escalas. */
function maxBonito(v) {
  if (v <= 0) return 1;
  const base = Math.pow(10, Math.floor(Math.log10(v))), f = v / base;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * base;
}

/* ========================================================================
   TOOLTIP FLOTANTE (compartido; ratón y teclado)
   El contenido se arma con esc(), así que innerHTML es seguro.
   ======================================================================== */
const TT = $("#tooltip");
let TT_VISIBLE = false;

function ttContenido({ titulo, filas = [], color }) {
  const punto = color ? `<span class="tt-color" style="background:${color}"></span>` : "";
  const cuerpo = filas.map((f) => `<div class="tt-fila">${punto}${esc(f)}</div>`).join("");
  return `<span class="tt-titulo">${esc(titulo)}</span>${cuerpo}`;
}
function mostrarTT(html) { TT.innerHTML = html; TT.classList.add("visible"); TT.setAttribute("aria-hidden", "false"); TT_VISIBLE = true; }
function moverTT(x, y) {
  const pad = 14, w = TT.offsetWidth, h = TT.offsetHeight;
  let tx = x + 14, ty = y + 16;
  if (tx + w + pad > window.innerWidth) tx = x - w - 14;
  if (ty + h + pad > window.innerHeight) ty = y - h - 14;
  TT.style.left = Math.max(pad, tx) + "px";
  TT.style.top = Math.max(pad, ty) + "px";
}
function ocultarTT() { TT.classList.remove("visible"); TT.setAttribute("aria-hidden", "true"); TT_VISIBLE = false; }

document.addEventListener("mouseover", (e) => {
  const t = e.target.closest("[data-tt]");
  if (t) { mostrarTT(t.dataset.tt); moverTT(e.clientX, e.clientY); }
});
document.addEventListener("mousemove", (e) => { if (TT_VISIBLE) moverTT(e.clientX, e.clientY); });
document.addEventListener("mouseout", (e) => { if (e.target.closest("[data-tt]")) ocultarTT(); });
document.addEventListener("focusin", (e) => {
  const t = e.target.closest("[data-tt]");
  if (t) { const r = t.getBoundingClientRect(); mostrarTT(t.dataset.tt); moverTT(r.left + r.width / 2, r.top); }
});
document.addEventListener("focusout", (e) => { if (e.target.closest("[data-tt]")) ocultarTT(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") ocultarTT(); });

/* ========================================================================
   TEMAS Y EFECTOS (persistidos en localStorage con try/catch)
   ======================================================================== */
function lsGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); } catch { /* modo privado */ } }

function aplicarTema(t) {
  document.documentElement.setAttribute("data-theme", t);
  const btn = $("#tema");
  btn.querySelector(".tema-icono").textContent = ICONO_TEMA[t];
  const sig = TEMAS[(TEMAS.indexOf(t) + 1) % TEMAS.length];
  btn.setAttribute("aria-label", `${ETIQUETA_TEMA[t]}. Cambiar a ${ETIQUETA_TEMA[sig].toLowerCase()}`);
  btn.setAttribute("title", `${ETIQUETA_TEMA[t]} → ${ETIQUETA_TEMA[sig]}`);
}
function iniciarTema() {
  let t = lsGet("tema");
  if (!TEMAS.includes(t)) {
    // Primera visita: respeta el sistema (por defecto, oscuro).
    t = (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) ? "light" : "dark";
  }
  aplicarTema(t);
  $("#tema").addEventListener("click", () => {
    const actual = document.documentElement.getAttribute("data-theme");
    const nuevo = TEMAS[(TEMAS.indexOf(actual) + 1) % TEMAS.length];
    aplicarTema(nuevo); lsSet("tema", nuevo);
  });

  // Toggle de efectos (scanlines/glow del tema hacker)
  const fx = lsGet("efectos");
  const efectosOn = fx === null ? true : fx === "on";
  $("#efectos").checked = efectosOn;
  document.documentElement.setAttribute("data-fx", efectosOn ? "on" : "off");
  $("#efectos").addEventListener("change", (e) => {
    const on = e.target.checked;
    document.documentElement.setAttribute("data-fx", on ? "on" : "off");
    lsSet("efectos", on ? "on" : "off");
  });
}

/* ========================================================================
   CARGA DE DATOS Y ESTADOS
   ======================================================================== */
async function cargar() {
  try {
    const r = await fetch("/api/data", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    marcarEstado(true);
    ULTIMA_CARGA = new Date();
    actualizarHora();
    render(data);
  } catch (e) {
    marcarEstado(false);
    mostrarError();
    console.error("No se pudo cargar /api/data:", e);
  }
}

function marcarEstado(ok) {
  const pill = $("#estado"), txt = pill.querySelector(".estado-texto");
  if (ok) { txt.textContent = "En línea"; pill.className = "pill pill-ok"; }
  else { txt.textContent = "Sin conexión"; pill.className = "pill pill-err"; }
}

/** Muestra una de las cuatro vistas: "carga", "panel", "vacio" o "error". */
function mostrarSolo(id) {
  for (const v of ["carga", "panel", "vacio", "error"]) {
    $("#" + v).classList.toggle("oculto", v !== id);
  }
}
function mostrarError() {
  // Si ya hay datos pintados, un fallo puntual no borra el panel (solo el LED).
  if ($("#panel").classList.contains("oculto")) mostrarSolo("error");
}

/** Muestra la hora (hh:mm:ss) de la última actualización correcta. */
function actualizarHora() {
  if (!ULTIMA_CARGA) return;
  const p = (x) => String(x).padStart(2, "0");
  const d = ULTIMA_CARGA;
  $("#actualizado").textContent = `⟳ ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/* ========================================================================
   RENDER PRINCIPAL
   ======================================================================== */
function render(data) {
  DATOS = data;
  $("#generado").textContent = data.generated_at || "—";

  if (!data.has_data) {
    mostrarSolo("vacio");
    if (data.message) $("#vacio-msg").textContent = data.message;
    return;
  }
  mostrarSolo("panel");

  const animar = !YA_ANIMADO;
  renderKPIs(data.stats);
  renderVentanas(data.windows || [], { animar });
  renderComposicion(data.stats);
  renderTiempo(data.segments || []);
  renderBarras("#grafico-especiales", (data.special_keys || []).slice(0, 8).map((k) => ({
    nombre: k.key, etiqueta: k.key, valor: k.count, extra: [],
  })), { animar, vacioMsg: "Sin teclas especiales registradas." });
  renderBarras("#grafico-sesiones", (data.sessions || []).map((s) => ({
    nombre: `Sesión #${s.index}`, etiqueta: `Sesión #${s.index}`, valor: s.events,
    extra: [`${num(s.chars)} caracteres`, `${num(s.specials)} especiales`, `${num(s.windows_count)} ventana(s)`],
  })), { animar, vacioMsg: "Sin sesiones registradas." });
  renderTimeline(data.sessions || []);

  SEGMENTOS = data.segments || [];
  renderRegistro();

  YA_ANIMADO = true;
}

/* --- KPIs --------------------------------------------------------------- */
function renderKPIs(s) {
  s = s || {};
  const cards = [
    { v: num(s.total_events), e: "Pulsaciones", ic: "⌨️", col: "var(--accent)" },
    { v: num(s.total_chars), e: "Caracteres", ic: "🔤", col: "var(--cat-2)" },
    { v: num(s.total_specials), e: "Teclas especiales", ic: "⎋", col: "var(--cat-4)" },
    { v: num(s.windows_count), e: "Ventanas", ic: "🪟", col: "var(--cat-3)" },
    { v: num(s.sessions_count), e: "Sesiones", ic: "⏺️", col: "var(--cat-5)" },
    { v: s.duration || "—", e: "Duración total", ic: "⏱️", col: "var(--cat-6)" },
  ];
  $("#kpis").innerHTML = cards.map((c, i) => `
    <div class="kpi ${YA_ANIMADO ? "" : "aparece"}" style="--acento-kpi:${c.col};animation-delay:${i * 40}ms">
      <span class="icono" aria-hidden="true">${c.ic}</span>
      <div class="valor">${esc(c.v)}</div>
      <div class="etiqueta">${esc(c.e)}</div>
    </div>`).join("");
}

/* --- Actividad por ventana (top 8, resto en «Otras») -------------------- */
function renderVentanas(windows, opts) {
  const orden = [...windows].sort((a, b) => b.events - a.events);
  let filas = orden.map((w) => ({
    nombre: w.window, etiqueta: `${iconoVentana(w.window)} ${w.window}`, valor: w.events,
    extra: [`${num(w.chars)} caracteres`, `${num(w.specials)} especiales`],
  }));
  if (filas.length > 8) {
    const top = filas.slice(0, 7);
    const resto = orden.slice(7);
    const suma = resto.reduce((t, w) => t + w.events, 0);
    top.push({ nombre: "Otras", etiqueta: `🗂️ Otras (${resto.length})`, valor: suma, extra: [`${num(resto.length)} ventanas agrupadas`] });
    filas = top;
  }
  renderBarras("#grafico-ventanas", filas, opts);
}

/* --- Barras horizontales (tooltip + foco por teclado) ------------------- */
function renderBarras(sel, filas, { animar = false, vacioMsg = "Sin datos." } = {}) {
  const cont = $(sel);
  if (!filas.length) { cont.innerHTML = `<p class="vacio-nota">${esc(vacioMsg)}</p>`; return; }
  const max = Math.max(...filas.map((f) => f.valor), 1);
  cont.innerHTML = filas.map((f, i) => {
    const pct = Math.max(3, Math.round((f.valor / max) * 100));
    const color = cat(i);
    const tt = ttContenido({ titulo: f.nombre, color, filas: [`${num(f.valor)} pulsaciones`, ...(f.extra || [])] });
    return `
      <div class="barra-fila" tabindex="0" role="group"
           aria-label="${esc(f.nombre)}: ${num(f.valor)} pulsaciones" data-tt="${esc(tt)}">
        <span class="barra-etq" title="${esc(f.etiqueta)}">${esc(f.etiqueta)}</span>
        <span class="barra-pista"><span class="barra-relleno" style="width:${animar ? 0 : pct}%;background:${color}" data-pct="${pct}"></span></span>
        <span class="barra-val">${num(f.valor)}</span>
      </div>`;
  }).join("");
  if (animar) {
    requestAnimationFrame(() => cont.querySelectorAll(".barra-relleno").forEach((el) => { el.style.width = el.dataset.pct + "%"; }));
  }
}

/* --- Donut de composición (SVG con tooltips) ---------------------------- */
function renderComposicion(s) {
  s = s || {};
  const chars = s.total_chars || 0, esp = s.total_specials || 0, total = chars + esp;
  const cont = $("#grafico-composicion");
  if (total === 0) { cont.innerHTML = `<p class="vacio-nota">Sin datos.</p>`; return; }

  const R = 54, C = 2 * Math.PI * R, fChars = chars / total, pct = (x) => Math.round((x / total) * 100);
  const ttChars = ttContenido({ titulo: "Caracteres", color: "var(--cat-1)", filas: [`${num(chars)} · ${pct(chars)}%`] });
  const ttEsp = ttContenido({ titulo: "Teclas especiales", color: "var(--cat-4)", filas: [`${num(esp)} · ${pct(esp)}%`] });

  cont.innerHTML = `
    <div class="donut-wrap">
      <svg class="donut-svg" width="160" height="160" viewBox="0 0 160 160" role="img"
           aria-label="Composición: ${num(chars)} caracteres (${pct(chars)}%) y ${num(esp)} teclas especiales (${pct(esp)}%)">
        <g transform="rotate(-90 80 80)">
          <circle cx="80" cy="80" r="${R}" fill="none" style="stroke:var(--bg)" stroke-width="18"/>
          <circle class="donut-arco" cx="80" cy="80" r="${R}" fill="none" style="stroke:var(--cat-1)" stroke-width="18"
                  data-tt="${esc(ttChars)}" stroke-dasharray="${(fChars * C).toFixed(2)} ${C.toFixed(2)}"/>
          <circle class="donut-arco" cx="80" cy="80" r="${R}" fill="none" style="stroke:var(--cat-4)" stroke-width="18"
                  data-tt="${esc(ttEsp)}" stroke-dasharray="${((1 - fChars) * C).toFixed(2)} ${C.toFixed(2)}"
                  stroke-dashoffset="${(-fChars * C).toFixed(2)}"/>
        </g>
        <text x="80" y="77" text-anchor="middle" class="donut-centro-num">${num(total)}</text>
        <text x="80" y="93" text-anchor="middle" class="donut-centro-txt">PULSACIONES</text>
      </svg>
      <div class="leyenda">
        <div class="leyenda-item"><span class="leyenda-punto" style="background:var(--cat-1)"></span> Caracteres <span class="leyenda-val">${num(chars)} · ${pct(chars)}%</span></div>
        <div class="leyenda-item"><span class="leyenda-punto" style="background:var(--cat-4)"></span> Especiales <span class="leyenda-val">${num(esp)} · ${pct(esp)}%</span></div>
      </div>
    </div>`;
}

/* --- Actividad en el tiempo (área SVG desde marcas de tiempo) ----------- */
function renderTiempo(segmentos) {
  const cont = $("#grafico-tiempo");
  const puntos = segmentos.map((s) => ({ t: parseTs(s.ts), v: (s.chars || 0) + (s.specials || 0) }))
    .filter((p) => !isNaN(p.t) && p.v > 0);
  if (!puntos.length) { cont.innerHTML = `<p class="vacio-nota">Sin datos temporales.</p>`; return; }

  const minT = Math.min(...puntos.map((p) => p.t)), maxT = Math.max(...puntos.map((p) => p.t));
  const rango = maxT - minT, conFecha = rango > 86400000;
  const N = Math.max(4, Math.min(20, puntos.length)), cubos = new Array(N).fill(0);
  for (const p of puntos) {
    const idx = rango > 0 ? Math.min(N - 1, Math.floor(((p.t - minT) / rango) * N)) : 0;
    cubos[idx] += p.v;
  }

  const W = 800, H = 240, mL = 46, mR = 14, mT = 14, mB = 30;
  const pW = W - mL - mR, pH = H - mT - mB, baseY = mT + pH;
  const maxV = maxBonito(Math.max(...cubos, 1));
  const px = (i) => mL + (N === 1 ? pW / 2 : (i / (N - 1)) * pW);
  const py = (v) => mT + pH - (v / maxV) * pH;

  let ejeY = "";
  for (let k = 0; k <= 4; k++) {
    const val = (maxV * k) / 4, y = py(val);
    ejeY += `<line class="svg-eje-linea" x1="${mL}" y1="${y.toFixed(1)}" x2="${W - mR}" y2="${y.toFixed(1)}"/>`;
    ejeY += `<text class="svg-eje-txt" x="${mL - 8}" y="${(y + 3).toFixed(1)}" text-anchor="end">${num(Math.round(val))}</text>`;
  }
  const tramo = rango / N;
  let ejeX = "";
  [0, Math.floor((N - 1) / 2), N - 1].forEach((i, j, arr) => {
    if (arr.indexOf(i) !== j) return;
    const anchor = i === 0 ? "start" : i === N - 1 ? "end" : "middle";
    ejeX += `<text class="svg-eje-txt" x="${px(i).toFixed(1)}" y="${H - 10}" text-anchor="${anchor}">${esc(fmtHora(minT + i * tramo, conFecha))}</text>`;
  });

  const pts = cubos.map((v, i) => [px(i), py(v)]);
  const linea = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `M${pts[0][0].toFixed(1)} ${baseY} ` + pts.map((p) => `L${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ") + ` L${pts[pts.length - 1][0].toFixed(1)} ${baseY} Z`;
  const circulos = cubos.map((v, i) => {
    const tt = ttContenido({ titulo: fmtHora(minT + i * tramo, conFecha), color: "var(--accent)", filas: [`${num(v)} pulsaciones`] });
    return `<circle class="area-punto" cx="${px(i).toFixed(1)}" cy="${py(v).toFixed(1)}" r="4" tabindex="0"
                    data-tt="${esc(tt)}" aria-label="${esc(fmtHora(minT + i * tramo, conFecha))}: ${num(v)} pulsaciones"></circle>`;
  }).join("");

  cont.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet" style="display:block;max-height:280px"
         role="group" aria-label="Actividad de pulsaciones a lo largo del tiempo (usa Tab para recorrer los puntos)">
      <defs><linearGradient id="gradArea" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" style="stop-color:var(--accent);stop-opacity:.35"/>
        <stop offset="100%" style="stop-color:var(--accent);stop-opacity:0"/>
      </linearGradient></defs>
      ${ejeY}
      <path class="area-relleno" d="${area}"/>
      <path class="area-linea" d="${linea}"/>
      ${circulos}
      ${ejeX}
    </svg>`;
}

/* --- Timeline de sesiones ---------------------------------------------- */
function renderTimeline(sesiones) {
  const cont = $("#timeline");
  if (!sesiones.length) { cont.innerHTML = `<p class="vacio-nota">Sin sesiones.</p>`; return; }
  cont.innerHTML = sesiones.map((s) => {
    const ventanas = (s.windows || []).slice(0, 6).map((w) => `<span class="tl-vtag" title="${esc(w)}">${esc(iconoVentana(w))} ${esc(w)}</span>`).join("");
    const masV = (s.windows_count || 0) > 6 ? `<span class="tl-vtag">+${num(s.windows_count - 6)} más</span>` : "";
    return `
    <div class="tl-item">
      <div class="tl-titulo"><span>Sesión #${esc(s.index)}</span><span class="tl-badge">${num(s.events)} pulsaciones</span></div>
      <div class="tl-meta">
        <span>▶ ${esc(s.start || "—")}</span>
        <span>⏹ ${esc(s.stop || "en curso")}</span>
        ${s.duration ? `<span>⏱ ${esc(s.duration)}</span>` : ""}
        <span>🔤 ${num(s.chars)}</span><span>⎋ ${num(s.specials)}</span>
        <span>🪟 ${num(s.windows_count)} ventana(s)</span>
      </div>
      ${ventanas ? `<div class="tl-ventanas">${ventanas}${masV}</div>` : ""}
    </div>`;
  }).join("");
}

/* ========================================================================
   REGISTRO POR VENTANA: filtro + vista Detalle / Tabla
   ======================================================================== */

/** Devuelve HTML seguro con las coincidencias de `q` envueltas en <mark>. */
function resaltar(texto, q) {
  const s = String(texto ?? "");
  if (!q) return esc(s);
  const low = s.toLowerCase(), ql = q.toLowerCase();
  let out = "", i = 0, idx;
  while ((idx = low.indexOf(ql, i)) !== -1) {
    out += esc(s.slice(i, idx)) + `<mark class="marca">${esc(s.slice(idx, idx + ql.length))}</mark>`;
    i = idx + ql.length;
  }
  return out + esc(s.slice(i));
}

/** Aplica el filtro de búsqueda a los segmentos. */
function filtrar(q) {
  q = (q || "").toLowerCase().trim();
  const lista = !q ? SEGMENTOS : SEGMENTOS.filter((s) =>
    (s.window || "").toLowerCase().includes(q) || (s.text || "").toLowerCase().includes(q));
  return { q, lista };
}

function renderRegistro() {
  const { q, lista } = filtrar($("#filtro").value);
  $("#filtro-conteo").textContent = q ? `${num(lista.length)} de ${num(SEGMENTOS.length)}` : "";
  if (VISTA === "detalle") renderDetalle(lista, q); else renderTabla(lista, q);
}

/* --- Vista Detalle (progressive disclosure: ver más / ver menos) -------- */
function renderDetalle(lista, q) {
  const cont = $("#segmentos");
  if (!lista.length) { cont.innerHTML = `<p class="vacio-nota">${q ? "Ningún registro coincide con el filtro." : "Sin registros."}</p>`; return; }
  cont.innerHTML = lista.map((s) => {
    const largo = (s.text || "").length > 240;
    return `
    <div class="seg ${largo ? "tiene-mas" : ""}">
      <div class="seg-cab">
        <span class="seg-ventana">
          <span class="seg-consola" aria-hidden="true"><span class="punto p1"></span><span class="punto p2"></span><span class="punto p3"></span></span>
          <span class="ic" aria-hidden="true">${iconoVentana(s.window)}</span>
          <span class="nom" title="${esc(s.window)}">${resaltar(s.window, q)}</span>
        </span>
        <span class="seg-meta">
          <span class="chip ses">Sesión ${esc(s.session)}</span>
          <span>🕒 ${esc(s.ts)}</span>
          <span class="chip">${num(s.chars)} car.</span>
          <span class="chip">${num(s.specials)} esp.</span>
        </span>
      </div>
      <pre class="seg-texto ${largo ? "colapsado" : ""}">${resaltar(s.text, q)}</pre>
      <div class="seg-vermas"><button type="button" class="seg-vermas-btn">ver más ▾</button></div>
    </div>`;
  }).join("");
}

/* --- Vista Tabla ordenable --------------------------------------------- */
const COLUMNAS = [
  { key: "session", etq: "Sesión", tipo: "num", val: (s) => s.session },
  { key: "ts", etq: "Hora", tipo: "txt", val: (s) => s.ts, orden: (s) => parseTs(s.ts) },
  { key: "window", etq: "Ventana", tipo: "txt", val: (s) => s.window },
  { key: "chars", etq: "Caracteres", tipo: "num", val: (s) => s.chars },
  { key: "specials", etq: "Especiales", tipo: "num", val: (s) => s.specials },
  { key: "text", etq: "Texto", tipo: "txt", val: (s) => s.text, ordenable: false },
];

function renderTabla(lista, q) {
  const cont = $("#tabla");
  if (!lista.length) { cont.innerHTML = `<p class="vacio-nota">${q ? "Ningún registro coincide con el filtro." : "Sin registros."}</p>`; return; }

  const conf = COLUMNAS.find((c) => c.key === ORDEN.col) || COLUMNAS[1];
  const clave = conf.orden || conf.val;
  const ordenada = [...lista].sort((a, b) => {
    const va = clave(a), vb = clave(b);
    let r = conf.tipo === "num" ? (Number(va) || 0) - (Number(vb) || 0) : String(va ?? "").localeCompare(String(vb ?? ""), "es");
    return ORDEN.dir === "asc" ? r : -r;
  });

  const cabeceras = COLUMNAS.map((c) => {
    if (c.ordenable === false) return `<th class="${c.tipo === "num" ? "num" : ""}">${c.etq}</th>`;
    const activo = ORDEN.col === c.key;
    const aria = activo ? (ORDEN.dir === "asc" ? "ascending" : "descending") : "none";
    const flecha = activo ? (ORDEN.dir === "asc" ? "▲" : "▼") : "↕";
    return `<th class="${c.tipo === "num" ? "num" : ""}" aria-sort="${aria}">
      <button class="th-orden" type="button" data-col="${c.key}">${c.etq}<span class="flecha" aria-hidden="true">${flecha}</span></button></th>`;
  }).join("");

  const filas = ordenada.map((s) => `
    <tr>
      <td class="num">${num(s.session)}</td>
      <td>${esc(s.ts)}</td>
      <td>${resaltar(s.window, q)}</td>
      <td class="num">${num(s.chars)}</td>
      <td class="num">${num(s.specials)}</td>
      <td class="col-texto" title="${esc(s.text)}">${resaltar((s.text || "").slice(0, 120), q)}</td>
    </tr>`).join("");

  cont.innerHTML = `<table class="tabla"><thead><tr>${cabeceras}</tr></thead><tbody>${filas}</tbody></table>`;
}

/* --- Exportar CSV (Blob, 100% local, sin red) -------------------------- */
function exportarCSV() {
  const { lista } = filtrar($("#filtro").value);
  const cab = ["Sesion", "Fecha_Hora", "Ventana", "Caracteres", "Especiales", "Texto_reconstruido"];
  const escCSV = (v) => `"${String(v ?? "").replaceAll('"', '""').replace(/[\r\n]+/g, " ")}"`;
  const filas = lista.map((s) => [s.session, s.ts, s.window, s.chars, s.specials, s.text].map(escCSV).join(";"));
  const contenido = "﻿" + [cab.join(";"), ...filas].join("\r\n");  // BOM para Excel es-PE
  const blob = new Blob([contenido], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const d = new Date(), p = (x) => String(x).padStart(2, "0");
  a.href = url;
  a.download = `registro_keylog_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ========================================================================
   MODO PRESENTACIÓN (Fullscreen API) Y BANNER
   ======================================================================== */
function togglePresentacion() {
  const activo = document.body.classList.toggle("presentacion");
  $("#salir-presentacion").classList.toggle("oculto", !activo);
  try {
    if (activo && document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
    else if (!activo && document.fullscreenElement && document.exitFullscreen) document.exitFullscreen();
  } catch { /* algunos navegadores requieren gesto directo; el modo visual igual se aplica */ }
}
function salirPresentacion() {
  document.body.classList.remove("presentacion");
  $("#salir-presentacion").classList.add("oculto");
  try { if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen(); } catch {}
}

function iniciarBanner() {
  const banner = $("#banner"), btn = $("#banner-toggle");
  btn.addEventListener("click", () => {
    const colapsado = banner.classList.toggle("colapsado");
    btn.textContent = colapsado ? "+" : "−";
    btn.setAttribute("aria-expanded", String(!colapsado));
    btn.setAttribute("aria-label", colapsado ? "Expandir aviso" : "Colapsar aviso");
  });
}

/* ========================================================================
   AUTO-ACTUALIZACIÓN
   ======================================================================== */
function configurarAuto() {
  const chk = $("#auto");
  const aplicar = () => {
    if (AUTO_TIMER) { clearInterval(AUTO_TIMER); AUTO_TIMER = null; }
    if (chk.checked) AUTO_TIMER = setInterval(cargar, 4000);
  };
  chk.addEventListener("change", aplicar);
  aplicar();
}

/* ========================================================================
   ARRANQUE
   ======================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  iniciarTema();
  iniciarBanner();
  $("#refrescar").addEventListener("click", cargar);
  $("#reintentar").addEventListener("click", cargar);
  $("#imprimir").addEventListener("click", () => window.print());
  $("#presentacion").addEventListener("click", togglePresentacion);
  $("#salir-presentacion").addEventListener("click", salirPresentacion);
  $("#csv").addEventListener("click", exportarCSV);

  // Filtro con debounce (150 ms)
  $("#filtro").addEventListener("input", debounce(renderRegistro, 150));

  // Cambio de vista Detalle / Tabla
  const setVista = (v) => {
    VISTA = v;
    $("#vista-detalle").classList.toggle("activo", v === "detalle");
    $("#vista-tabla").classList.toggle("activo", v === "tabla");
    $("#vista-detalle").setAttribute("aria-pressed", String(v === "detalle"));
    $("#vista-tabla").setAttribute("aria-pressed", String(v === "tabla"));
    $("#segmentos").classList.toggle("oculto", v !== "detalle");
    $("#tabla").classList.toggle("oculto", v !== "tabla");
    renderRegistro();
  };
  $("#vista-detalle").addEventListener("click", () => setVista("detalle"));
  $("#vista-tabla").addEventListener("click", () => setVista("tabla"));

  // Progressive disclosure (ver más / ver menos) — delegación
  $("#segmentos").addEventListener("click", (e) => {
    const btn = e.target.closest(".seg-vermas-btn");
    if (!btn) return;
    const pre = btn.closest(".seg").querySelector(".seg-texto");
    const colapsado = pre.classList.toggle("colapsado");
    btn.textContent = colapsado ? "ver más ▾" : "ver menos ▴";
  });

  // Ordenar tabla — delegación
  $("#tabla").addEventListener("click", (e) => {
    const th = e.target.closest(".th-orden");
    if (!th) return;
    const col = th.dataset.col;
    if (ORDEN.col === col) ORDEN.dir = ORDEN.dir === "asc" ? "desc" : "asc";
    else ORDEN = { col, dir: "asc" };
    renderRegistro();
  });

  // Salir del modo presentación si se cierra la pantalla completa (Esc)
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && document.body.classList.contains("presentacion")) salirPresentacion();
  });

  configurarAuto();
  HORA_TIMER = setInterval(actualizarHora, 1000);
  cargar();
});
