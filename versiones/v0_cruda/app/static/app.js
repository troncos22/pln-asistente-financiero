"use strict";

const $ = (s) => document.querySelector(s);
const sesionId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())).slice(0, 32);
const COLORES = ["#1f6f5c", "#c2702a", "#4a6fb5", "#a8456b", "#7a8b2e", "#5b5f97", "#b5893a", "#2e8b9a", "#8c4f3a", "#5f7f7a"];
const NOMBRES_DATO = { rut: "RUT", tarjeta: "tarjeta", cuenta: "cuenta bancaria", correo: "correo", telefono: "teléfono", clave: "clave" };

const clp = (n) => (n < 0 ? "-" : "") + "$" + Math.abs(Math.round(n)).toLocaleString("es-CL");
const fecha = (iso) => iso ? iso.split("-").reverse().join("-") : "";

function el(tag, clase, texto) {
  const e = document.createElement(tag);
  if (clase) e.className = clase;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function css(nombre) {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
}

async function api(url, opciones) {
  const r = await fetch(url, opciones);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

// ------------------------------------------------------------------ estado
async function cargarEstado() {
  try {
    const e = await api("/api/estado");
    const chip = $("#chip-llm");
    chip.textContent = e.llm_disponible ? `${e.modelo} listo` : `${e.modelo} no disponible`;
    chip.className = "chip " + (e.llm_disponible ? "ok" : "mal");
    $("#chip-modo").textContent = `NLU: ${e.nlu_modo} · hoy ${fecha(e.hoy)}`;
  } catch {
    $("#chip-llm").textContent = "sin conexión";
  }
}

// ------------------------------------------------------------------ gráficos
function configGrafico(spec) {
  const dona = spec.tipo === "doughnut";
  const enCLP = spec.unidad === "CLP";
  const datasets = spec.series.map((s, i) => ({
    label: s.nombre,
    data: s.datos,
    type: s.tipo || undefined,
    order: s.tipo === "line" ? 0 : 1,
    backgroundColor: dona ? COLORES.slice(0, s.datos.length) : COLORES[i % COLORES.length] + (spec.tipo === "bar" && !s.tipo ? "cc" : "22"),
    borderColor: dona ? css("--superficie") : COLORES[i % COLORES.length],
    borderWidth: 2,
    pointRadius: spec.etiquetas.length > 30 ? 0 : 3,
    tension: 0.25,
    spanGaps: true,
    fill: false,
  }));
  const formato = (v) => (enCLP ? clp(v) : Number(v).toLocaleString("es-CL"));
  const ejes = dona ? {} : {
    x: { ticks: { color: css("--texto-suave"), maxTicksLimit: 12 }, grid: { display: false } },
    y: { ticks: { color: css("--texto-suave"), callback: formato }, grid: { color: css("--borde") } },
  };
  return {
    type: spec.tipo,
    data: { labels: spec.etiquetas, datasets },
    options: {
      responsive: true,
      interaction: { mode: dona ? "nearest" : "index", intersect: false },
      plugins: {
        title: { display: true, text: spec.titulo, color: css("--texto"), font: { size: 14, weight: "600" } },
        legend: { labels: { color: css("--texto-suave") } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${formato(c.parsed.y ?? c.parsed)}` } },
      },
      scales: ejes,
    },
  };
}

function dibujarGrafico(contenedor, spec) {
  if (!window.Chart) {
    contenedor.append(el("p", "nota", "No se pudo cargar Chart.js."));
    return;
  }
  const caja = el("div", "grafico");
  const lienzo = el("canvas");
  lienzo.setAttribute("role", "img");
  lienzo.setAttribute("aria-label", spec.titulo);
  caja.append(lienzo);
  if (spec.nota) caja.append(el("p", "nota", spec.nota));
  contenedor.append(caja);
  new Chart(lienzo, configGrafico(spec));
}

// ------------------------------------------------------------------ chat
function agregarMensaje(rol, texto) {
  const m = el("div", `msg ${rol}`);
  m.append(el("div", "burbuja", texto));
  $("#mensajes").append(m);
  $("#mensajes").scrollTop = $("#mensajes").scrollHeight;
  return m;
}

function renderRespuesta(r) {
  const m = agregarMensaje("asistente" + (r.bloqueado ? " bloqueado" : ""), r.respuesta);
  if (r.enmascarados && r.enmascarados.length) {
    const fila = el("div", "etiquetas");
    [...new Set(r.enmascarados)].forEach((t) => fila.append(el("span", "etiqueta", `Ocultado: ${NOMBRES_DATO[t] || t}`)));
    m.insertBefore(fila, m.firstChild);
  }
  if (r.bloqueado) {
    const fila = el("div", "etiquetas");
    fila.append(el("span", "etiqueta", `Posible prompt injection (puntaje ${r.puntaje_inyeccion})`));
    m.insertBefore(fila, m.firstChild);
  }
  if (r.grafico) dibujarGrafico(m, r.grafico);
  const det = el("details", "detalle");
  det.append(el("summary", "", `${r.intencion || "bloqueado"} · ${r.fuente_nlu} · ${r.latencia_ms} ms`));
  const info = {
    intencion: r.intencion, entidades: r.entidades, fuente_nlu: r.fuente_nlu, redaccion: r.redaccion,
    puntaje_inyeccion: r.puntaje_inyeccion, etiquetas_inyeccion: r.etiquetas_inyeccion,
    mensaje_enviado_al_modelo: r.mensaje_enmascarado, salida_llm: r.salida_llm, hechos: r.hechos,
  };
  det.append(el("pre", "", JSON.stringify(info, null, 2)));
  m.append(det);
  $("#mensajes").scrollTop = $("#mensajes").scrollHeight;
}

async function enviar(texto) {
  texto = texto.trim();
  if (!texto) return;
  agregarMensaje("usuario", texto);
  $("#texto").value = "";
  $("#enviar").disabled = true;
  const espera = agregarMensaje("asistente", "Pensando…");
  espera.querySelector(".burbuja").classList.add("escribiendo");
  try {
    const r = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sesion_id: sesionId, mensaje: texto }),
    });
    espera.remove();
    renderRespuesta(r);
    refrescarPanel();
  } catch (e) {
    espera.remove();
    agregarMensaje("asistente bloqueado", "No pude procesar el mensaje: " + e.message);
  } finally {
    $("#enviar").disabled = false;
    $("#texto").focus();
  }
}

// ------------------------------------------------------------------ panel
async function refrescarPanel() {
  try {
    const [r, movs, port, aud] = await Promise.all([
      api("/api/resumen"), api("/api/movimientos?limite=40"), api("/api/portafolio"), api("/api/auditoria?limite=40"),
    ]);
    $("#k-caja").textContent = clp(r.caja);
    $("#k-patrimonio").textContent = clp(r.patrimonio);
    $("#k-ingresos").textContent = clp(r.ingresos_mes);
    $("#k-gastos").textContent = clp(r.gastos_mes);

    const tm = $("#t-movimientos");
    tm.replaceChildren();
    movs.forEach((m) => {
      const tr = el("tr");
      tr.append(el("td", "", fecha(m.fecha)));
      const td = el("td", "", m.descripcion || m.categoria);
      td.append(el("br"), el("small", "", `${m.categoria} · ${m.origen}`));
      tr.append(td);
      tr.append(el("td", "der monto " + (m.tipo === "ingreso" ? "positivo" : "negativo"), (m.tipo === "ingreso" ? "+" : "−") + clp(m.monto)));
      tm.append(tr);
    });

    const tp = $("#t-portafolio");
    tp.replaceChildren();
    port.forEach((p) => {
      const tr = el("tr");
      tr.append(el("td", "", p.ticker));
      tr.append(el("td", "der", Number(p.cantidad).toLocaleString("es-CL")));
      tr.append(el("td", "der monto", clp(p.valor)));
      tr.append(el("td", "der monto " + (p.ganancia >= 0 ? "positivo" : "negativo"), `${clp(p.ganancia)} (${p.pct.toLocaleString("es-CL")}%)`));
      tp.append(tr);
    });

    const la = $("#l-auditoria");
    la.replaceChildren();
    aud.forEach((a) => {
      const li = el("li");
      li.append(el("span", "evento " + a.evento, a.evento), document.createTextNode(` · ${a.ts.replace("T", " ")}`));
      const d = a.detalle || {};
      const resumen = d.intencion !== undefined
        ? `${d.mensaje_enmascarado || ""} → ${d.intencion || "bloqueado"} (${d.fuente_nlu}); ocultados: ${(d.enmascarados || []).join(", ") || "ninguno"}; inyección: ${d.puntaje_inyeccion}`
        : JSON.stringify(d);
      li.append(el("div", "", resumen));
      la.append(li);
    });
  } catch (e) {
    console.error(e);
  }
}

// ------------------------------------------------------------------ eventos
$("#formulario").addEventListener("submit", (ev) => { ev.preventDefault(); enviar($("#texto").value); });
$("#texto").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); enviar($("#texto").value); }
});
$("#sugerencias").addEventListener("click", (ev) => { if (ev.target.tagName === "BUTTON") enviar(ev.target.textContent); });

document.querySelectorAll(".pestanas button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".pestanas button").forEach((x) => x.classList.toggle("activa", x === b));
  document.querySelectorAll(".vista").forEach((v) => v.classList.toggle("activa", v.id === "v-" + b.dataset.tab));
}));

$("#privado").addEventListener("change", (ev) => {
  document.body.classList.toggle("privado", ev.target.checked);
  try { localStorage.setItem("privado", ev.target.checked ? "1" : "0"); } catch {}
});
try {
  if (localStorage.getItem("privado") === "1") { $("#privado").checked = true; document.body.classList.add("privado"); }
} catch {}

document.querySelectorAll("form.importar").forEach((f) => f.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const archivo = f.querySelector("input[type=file]").files[0];
  if (!archivo) return;
  const datos = new FormData();
  datos.append("archivo", archivo);
  try {
    const r = await api(f.dataset.url, { method: "POST", body: datos });
    $("#r-importar").textContent = JSON.stringify(r, null, 2);
    refrescarPanel();
  } catch (e) {
    $("#r-importar").textContent = "Error: " + e.message;
  }
}));

agregarMensaje("asistente", "¡Hola! Soy tu asistente financiero. Cuéntame tus gastos e ingresos, pregúntame por tu saldo o pídeme un gráfico. Escribe «ayuda» para ver ejemplos.");
cargarEstado();
refrescarPanel();
