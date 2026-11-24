"""Un handler por intención (RF-03, RF-05 … RF-14, P7).

Cada handler devuelve un `Resultado` con el texto (plantilla), los HECHOS numéricos usados para
armarlo (sirven para verificar que no haya cifras inventadas), un gráfico opcional y, si falta un
dato obligatorio, el slot pendiente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import charts, db
from .reglas import _restar_meses

DESCARGO = ("Esto es información general, no una recomendación personalizada de inversión. "
            "Antes de invertir, revisa tu perfil de riesgo y, si puedes, consulta a un asesor acreditado.")

CONSEJOS = {
    "diversificacion": "Diversificar significa repartir tu dinero entre distintos instrumentos, sectores y plazos "
                       "para que una mala noticia en uno no afecte todo tu patrimonio.",
    "fondos mutuos": "Un fondo mutuo junta el dinero de muchas personas y lo administra una AGF. Hay fondos más "
                     "conservadores (deuda de corto plazo) y más riesgosos (acciones); fíjate en la comisión y en "
                     "el plazo de rescate.",
    "deposito a plazo": "Un depósito a plazo te paga una tasa conocida a cambio de dejar el dinero inmovilizado un "
                        "tiempo. Es de bajo riesgo, pero si lo rescatas antes puedes perder los intereses.",
    "etf": "Un ETF es un fondo que se transa en bolsa como una acción y suele replicar un índice; permite "
           "diversificar con poco dinero y comisiones bajas.",
    "apv": "El Ahorro Previsional Voluntario (APV) complementa tu pensión y tiene beneficios tributarios; conviene "
           "comparar comisiones entre instituciones.",
    "acciones": "Comprar acciones es comprar una parte de una empresa: pueden subir o bajar bastante en el corto "
                "plazo, por eso se recomiendan para horizontes largos y dinero que no necesitarás pronto.",
    "ahorro": "Una regla práctica es separar el ahorro apenas recibes tu ingreso, tener un fondo de emergencia "
              "líquido antes de invertir y revisar tus gastos por categoría cada mes.",
    "criptomonedas": "Las criptomonedas son muy volátiles y no tienen garantía estatal; si decides exponerte, que "
                     "sea con una parte pequeña de tu patrimonio que estés dispuesto a perder.",
    "dividendos": "Los dividendos son la parte de las utilidades que una empresa reparte a sus accionistas; no "
                  "están garantizados y dependen de los resultados de la empresa.",
    "riesgo": "El riesgo y la rentabilidad esperada van de la mano: a mayor potencial de ganancia, mayor "
              "posibilidad de pérdida. Define tu horizonte y tolerancia antes de elegir instrumentos.",
}
CONSEJO_GENERAL = ("Antes de invertir conviene tener claro tu objetivo, tu plazo y cuánto riesgo toleras, contar "
                   "con un fondo de emergencia y diversificar.")

MESES_TXT = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]


@dataclass
class Resultado:
    texto: str
    hechos: dict = field(default_factory=dict)
    grafico: dict | None = None
    pendiente: dict | None = None
    accion: str | None = None  # p. ej. "movimiento_guardado"


def clp(n: float) -> str:
    signo = "-" if n < 0 else ""
    return f"{signo}${abs(int(round(n))):,}".replace(",", ".")


def num(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") if float(x).is_integer() else f"{x:,.2f}".replace(",", "X").replace(
        ".", ",").replace("X", ".")


def fecha_txt(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES_TXT[d.month - 1]} de {d.year}"


def _periodo(entidades: dict, hoy: date, meses_defecto: int) -> tuple[date, date]:
    p = entidades.get("periodo")
    if p:
        return date.fromisoformat(p["desde"]), date.fromisoformat(p["hasta"])
    return _restar_meses(hoy, meses_defecto - 1), hoy


def _periodo_txt(desde: date, hasta: date) -> str:
    return f"entre el {fecha_txt(desde.isoformat())} y el {fecha_txt(hasta.isoformat())}"


# ---------------------------------------------------------------- charla

def saludo(con, e, hoy, sesion) -> Resultado:
    return Resultado("¡Hola! Soy tu asistente de finanzas personales. Puedo registrar tus ingresos, gastos y "
                     "compras de acciones, decirte tu saldo y hacer gráficos. ¿En qué te ayudo?")


def ayuda(con, e, hoy, sesion) -> Resultado:
    ejemplos = ["gasté 25 lucas en el súper", "me pagaron 1.850.000 de sueldo", "compré 10 acciones de SQM-B a 41.000",
                "¿cuánta plata tengo?", "gráfico de ingresos vs gastos de los últimos 6 meses",
                "compara SQM-B con Falabella este año", "¿en qué se me va la plata?"]
    return Resultado("Puedo ayudarte con esto (escríbelo como te salga):\n" + "\n".join(f"• {x}" for x in ejemplos)
                     + "\nTus datos sensibles (RUT, tarjetas, cuentas, claves) se ocultan automáticamente.",
                     {"ejemplos": ejemplos})


def despedida(con, e, hoy, sesion) -> Resultado:
    return Resultado("¡Hasta pronto! Tus datos quedan guardados en tu computador.")


def fuera_de_dominio(con, e, hoy, sesion) -> Resultado:
    return Resultado("Solo puedo ayudarte con tus finanzas personales: ingresos, gastos, saldo, inversiones y "
                     "gráficos. Escribe «ayuda» para ver ejemplos.")


# ---------------------------------------------------------------- registros

def _registrar_movimiento(con, e, hoy, tipo: str) -> Resultado:
    intencion = f"registrar_{tipo}"
    if not e.get("monto"):
        pregunta = "¿Cuánto fue el gasto?" if tipo == "gasto" else "¿De cuánto fue el ingreso?"
        return Resultado(pregunta, pendiente={"intencion": intencion, "entidades": e, "falta": "monto"})
    fecha = e.get("fecha") or hoy.isoformat()
    categoria = e.get("categoria") or "otros"
    db.insertar_movimiento(con, fecha, tipo, e["monto"], categoria, e.get("descripcion", ""), "chat")
    saldo = db.caja(con)
    hechos = {"monto": e["monto"], "fecha": fecha, "categoria": categoria, "saldo": saldo}
    verbo = "gasto" if tipo == "gasto" else "ingreso"
    return Resultado(f"Listo, registré un {verbo} de {clp(e['monto'])} en «{categoria}» el {fecha_txt(fecha)}. "
                     f"Tu saldo disponible ahora es {clp(saldo)}.", hechos, accion="movimiento_guardado")


def registrar_gasto(con, e, hoy, sesion) -> Resultado:
    return _registrar_movimiento(con, e, hoy, "gasto")


def registrar_ingreso(con, e, hoy, sesion) -> Resultado:
    return _registrar_movimiento(con, e, hoy, "ingreso")


def _registrar_operacion(con, e, hoy, tipo: str) -> Resultado:
    intencion = f"registrar_{tipo}"
    if not e.get("ticker"):
        return Resultado("¿De qué acción? (por ejemplo SQM-B, FALABELLA o COPEC)",
                         pendiente={"intencion": intencion, "entidades": e, "falta": "ticker"})
    if not e.get("cantidad"):
        return Resultado(f"¿Cuántas acciones de {e['ticker']}?",
                         pendiente={"intencion": intencion, "entidades": e, "falta": "cantidad"})
    ticker, cantidad = e["ticker"], float(e["cantidad"])
    fecha = e.get("fecha") or hoy.isoformat()
    hechos = {"ticker": ticker, "cantidad": cantidad, "fecha": fecha}
    nota = ""
    precio = e.get("precio")
    if not precio:
        up = db.ultimo_precio(con, ticker, date.fromisoformat(fecha))
        if not up:
            return Resultado(f"No tengo precios de {ticker}. ¿A qué precio por acción fue la operación?",
                             hechos, pendiente={"intencion": intencion, "entidades": e, "falta": "precio"})
        precio = up[1]
        hechos["fecha_precio"] = up[0]
        nota = f" Usé el último precio conocido ({clp(precio)} del {fecha_txt(up[0])})."
    hechos["precio"] = precio
    if tipo == "venta":
        tenencia = db.posiciones(con).get(ticker, {}).get("cantidad", 0)
        hechos["tenencia"] = tenencia
        if cantidad > tenencia + 1e-9:
            return Resultado(f"No puedo registrar la venta: tienes {num(tenencia)} acciones de {ticker} y quieres "
                             f"vender {num(cantidad)}.", hechos)
    total = cantidad * float(precio)
    db.insertar_operacion(con, fecha, tipo, ticker, cantidad, float(precio), "chat")
    saldo = db.caja(con)
    hechos.update(total=total, saldo=saldo, tenencia_nueva=db.posiciones(con).get(ticker, {}).get("cantidad", 0))
    verbo = "compra" if tipo == "compra" else "venta"
    return Resultado(f"Registré la {verbo} de {num(cantidad)} acciones de {ticker} a {clp(precio)} "
                     f"(total {clp(total)}) el {fecha_txt(fecha)}.{nota} Ahora tienes "
                     f"{num(hechos['tenencia_nueva'])} acciones de {ticker} y tu saldo disponible es {clp(saldo)}.",
                     hechos, accion="operacion_guardada")


def registrar_compra(con, e, hoy, sesion) -> Resultado:
    return _registrar_operacion(con, e, hoy, "compra")


def registrar_venta(con, e, hoy, sesion) -> Resultado:
    return _registrar_operacion(con, e, hoy, "venta")


# ---------------------------------------------------------------- consultas

def consultar_saldo(con, e, hoy, sesion) -> Resultado:
    saldo = db.caja(con, hoy)
    valor = db.valor_portafolio(con, hoy)
    hechos = {"saldo": saldo, "valor_acciones": round(valor), "patrimonio": round(saldo + valor),
              "fecha": hoy.isoformat()}
    return Resultado(f"Al {fecha_txt(hoy.isoformat())} tienes {clp(saldo)} disponibles. Sumando tus acciones "
                     f"({clp(valor)}), tu patrimonio es {clp(saldo + valor)}.", hechos)


def consultar_portafolio(con, e, hoy, sesion) -> Resultado:
    pos = db.posiciones(con, hoy)
    if e.get("ticker"):
        pos = {k: v for k, v in pos.items() if k == e["ticker"]}
        if not pos:
            return Resultado(f"No tienes acciones de {e['ticker']}.", {"ticker": e["ticker"]})
    if not pos:
        return Resultado("Todavía no tienes acciones registradas.")
    lineas, hechos, total_valor, total_costo = [], {"posiciones": {}}, 0.0, 0.0
    for ticker, p in sorted(pos.items()):
        up = db.ultimo_precio(con, ticker, hoy)
        precio = up[1] if up else p["costo_promedio"]
        valor, costo = p["cantidad"] * precio, p["cantidad"] * p["costo_promedio"]
        ganancia = valor - costo
        pct = ganancia / costo * 100 if costo else 0
        total_valor += valor
        total_costo += costo
        hechos["posiciones"][ticker] = {"cantidad": p["cantidad"], "costo_promedio": round(p["costo_promedio"], 2),
                                        "precio": precio, "valor": round(valor), "ganancia": round(ganancia),
                                        "pct": round(pct, 1)}
        lineas.append(f"• {ticker}: {num(p['cantidad'])} acciones, costo promedio {clp(p['costo_promedio'])}, "
                      f"último precio {clp(precio)} → valor {clp(valor)} ({'+' if ganancia >= 0 else ''}"
                      f"{num(round(pct, 1))}%, {clp(ganancia)})")
    total_g = total_valor - total_costo
    total_pct = total_g / total_costo * 100 if total_costo else 0
    hechos.update(total_valor=round(total_valor), total_ganancia=round(total_g), total_pct=round(total_pct, 1))
    texto = ("Tu portafolio:\n" + "\n".join(lineas) + f"\nValor total {clp(total_valor)}; resultado no realizado "
             f"{clp(total_g)} ({num(round(total_pct, 1))}%).")
    if any(charts._es_demo(con, t) for t in pos):
        texto += " (Precios simulados de ejemplo.)"
    return Resultado(texto, hechos)


def consultar_movimientos(con, e, hoy, sesion) -> Resultado:
    desde, hasta = _periodo(e, hoy, 1) if e.get("periodo") else (date(hoy.year, hoy.month, 1), hoy)
    tipo, categoria = e.get("tipo"), e.get("categoria")
    if categoria and not tipo:
        tipo = "ingreso" if categoria in ("sueldo", "honorarios", "dividendos", "regalo") else "gasto"
    r = db.totales_periodo(con, desde, hasta, tipo, categoria)
    hechos = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "ingresos": r["ingresos"],
              "gastos": r["gastos"], "n": r["n"], "mayores": r["mayores"]}
    filtro = f" en «{categoria}»" if categoria else ""
    if r["n"] == 0:
        return Resultado(f"No encontré movimientos{filtro} {_periodo_txt(desde, hasta)}.", hechos)
    partes = []
    if tipo != "ingreso":
        partes.append(f"gastaste {clp(r['gastos'])}")
    if tipo != "gasto":
        partes.append(f"recibiste {clp(r['ingresos'])}")
    texto = f"{_periodo_txt(desde, hasta).capitalize()}{filtro} " + " y ".join(partes) + f" ({r['n']} movimientos)."
    if tipo is None:
        neto = r["ingresos"] - r["gastos"]
        hechos["neto"] = neto
        texto += f" Resultado neto: {clp(neto)}."
    if r["mayores"]:
        m = r["mayores"][0]
        texto += f" El mayor fue «{m['descripcion'] or m['categoria']}» por {clp(m['monto'])} el {fecha_txt(m['fecha'])}."
    return Resultado(texto, hechos)


# ---------------------------------------------------------------- gráficos

def grafico_linea_tiempo(con, e, hoy, sesion) -> Resultado:
    metrica = e.get("metrica") or "saldo"
    if e.get("serie"):
        g = charts.desde_serie(e["serie"], f"{metrica.capitalize()} (datos entregados)", metrica.capitalize())
        return Resultado(f"Aquí está el gráfico con los {len(e['serie'])} datos que me diste.",
                         {"serie": e["serie"], "n": len(e["serie"])}, g)
    desde, hasta = _periodo(e, hoy, 12)
    g = charts.linea_tiempo(con, metrica, desde, hasta)
    datos = g["series"][0]["datos"]
    hechos = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "inicial": datos[0], "final": datos[-1]}
    return Resultado(f"Evolución de tu {metrica} {_periodo_txt(desde, hasta)}: partió en {clp(datos[0])} y "
                     f"terminó en {clp(datos[-1])}.", hechos, g)


def grafico_ingresos_egresos(con, e, hoy, sesion) -> Resultado:
    if e.get("serie"):
        g = charts.desde_serie(e["serie"], "Datos entregados", "Monto")
        return Resultado("Aquí está el gráfico con los datos que me diste.", {"serie": e["serie"]}, g)
    desde, hasta = _periodo(e, hoy, 6)
    g = charts.ingresos_egresos(con, desde, hasta)
    ing, egr = sum(g["series"][0]["datos"]), sum(g["series"][1]["datos"])
    hechos = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "ingresos": ing, "egresos": egr,
              "neto": ing - egr}
    return Resultado(f"{_periodo_txt(desde, hasta).capitalize()} tus ingresos sumaron {clp(ing)} y tus egresos "
                     f"{clp(egr)}; el resultado neto es {clp(ing - egr)}.", hechos, g)


def grafico_comparar_acciones(con, e, hoy, sesion) -> Resultado:
    pedidos = e.get("tickers") or ([e["ticker"]] if e.get("ticker") else [])
    disponibles = db.tickers_disponibles(con)
    if not pedidos:
        pedidos = sorted(db.posiciones(con, hoy)) or disponibles[:2]
    validos = [t for t in pedidos if t in disponibles]
    faltan = [t for t in pedidos if t not in disponibles]
    if not validos:
        return Resultado(f"No tengo precios de {', '.join(faltan)}. Acciones disponibles: {', '.join(disponibles)}.",
                         {"disponibles": disponibles})
    desde, hasta = _periodo(e, hoy, 12)
    g = charts.comparar_acciones(con, validos, desde, hasta)
    hechos = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "variaciones": {}}
    partes = []
    for t in validos:
        s = db.serie_precios(con, t, desde, hasta)
        if len(s) >= 2:
            var = (s[-1][1] / s[0][1] - 1) * 100
            hechos["variaciones"][t] = round(var, 1)
            partes.append(f"{t} {'+' if var >= 0 else ''}{num(round(var, 1))}%")
    texto = f"Variación {_periodo_txt(desde, hasta)}: " + ", ".join(partes) + "."
    if faltan:
        texto += f" No tengo precios de {', '.join(faltan)} (disponibles: {', '.join(disponibles)})."
        hechos["disponibles"] = disponibles
    if g["nota"]:
        texto += f" {g['nota']}."
    return Resultado(texto, hechos, g)


def grafico_gastos_categoria(con, e, hoy, sesion) -> Resultado:
    if e.get("serie"):
        g = charts.desde_serie(e["serie"], "Datos entregados", "Monto")
        g["tipo"] = "doughnut"
        return Resultado("Aquí está el gráfico con los datos que me diste.", {"serie": e["serie"]}, g)
    desde, hasta = _periodo(e, hoy, 1) if e.get("periodo") else (date(hoy.year, hoy.month, 1), hoy)
    g = charts.gastos_categoria(con, desde, hasta)
    if not g["etiquetas"]:
        return Resultado(f"No hay gastos {_periodo_txt(desde, hasta)}.", {"desde": desde.isoformat(),
                                                                          "hasta": hasta.isoformat()})
    total = sum(g["series"][0]["datos"])
    mayor, monto_mayor = g["etiquetas"][0], g["series"][0]["datos"][0]
    pct = monto_mayor / total * 100
    hechos = {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "total": total, "mayor": mayor,
              "monto_mayor": monto_mayor, "pct": round(pct, 1)}
    return Resultado(f"{_periodo_txt(desde, hasta).capitalize()} gastaste {clp(total)}. La categoría principal fue "
                     f"«{mayor}» con {clp(monto_mayor)} ({num(round(pct, 1))}%).", hechos, g)


# ---------------------------------------------------------------- consejo (P7)

def consejo_inversion(con, e, hoy, sesion) -> Resultado:
    tema = e.get("tema")
    clave = tema if tema in CONSEJOS else None
    texto = CONSEJOS.get(clave, CONSEJO_GENERAL)
    return Resultado(f"{texto}\n\n{DESCARGO}", {"tema": tema or ""})


HANDLERS = {
    "saludo": saludo, "ayuda": ayuda, "despedida": despedida, "fuera_de_dominio": fuera_de_dominio,
    "registrar_gasto": registrar_gasto, "registrar_ingreso": registrar_ingreso,
    "registrar_compra": registrar_compra, "registrar_venta": registrar_venta,
    "consultar_saldo": consultar_saldo, "consultar_portafolio": consultar_portafolio,
    "consultar_movimientos": consultar_movimientos,
    "grafico_linea_tiempo": grafico_linea_tiempo, "grafico_ingresos_egresos": grafico_ingresos_egresos,
    "grafico_comparar_acciones": grafico_comparar_acciones, "grafico_gastos_categoria": grafico_gastos_categoria,
    "consejo_inversion": consejo_inversion,
}


def ejecutar(con, intencion: str, entidades: dict, hoy: date, sesion: dict | None = None) -> Resultado:
    return HANDLERS.get(intencion, fuera_de_dominio)(con, entidades, hoy, sesion or {})
