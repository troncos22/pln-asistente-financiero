"""NLU por reglas y normalizadores de entidades (RF-01, RF-02, RF-14).

Sirve como (a) modo `reglas` sin LLM, (b) normalizador de lo que extrae el LLM en el modo
`hibrido` y (c) línea base simple para comparar contra el LLM.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from .db import fin_de_mes

INTENCIONES = [
    "saludo", "ayuda", "despedida",
    "registrar_ingreso", "registrar_gasto", "registrar_compra", "registrar_venta",
    "consultar_saldo", "consultar_portafolio", "consultar_movimientos",
    "grafico_linea_tiempo", "grafico_ingresos_egresos", "grafico_comparar_acciones", "grafico_gastos_categoria",
    "consejo_inversion", "fuera_de_dominio",
]

CATEGORIAS_GASTO = ["vivienda", "alimentacion", "transporte", "servicios", "salud", "educacion",
                    "entretencion", "ropa", "deudas", "otros"]
CATEGORIAS_INGRESO = ["sueldo", "honorarios", "dividendos", "arriendo", "regalo", "otros"]
METRICAS = ["saldo", "patrimonio", "ingresos", "gastos"]

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
         "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "sept": 9,
         "oct": 10, "nov": 11, "dic": 12}
_MES_LARGO = r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"

NUMEROS_PALABRA = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
                   "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "quince": 15,
                   "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
                   "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200,
                   "trescientos": 300, "quinientos": 500, "medio": 0.5, "media": 0.5}

TICKERS_ALIAS = {
    "SQM-B": [r"sqm[\s-]?b", r"sqm", r"soquimich"],
    "FALABELLA": [r"falabella"],
    "COPEC": [r"empresas copec", r"copec"],
    "BSANTANDER": [r"bsantander", r"banco santander", r"santander"],
    "CHILE": [r"banco de chile", r"banco chile", r"bchile"],
    "CENCOSUD": [r"cencosud"],
    "ENELCHILE": [r"enel ?chile", r"enel"],
    "LTM": [r"latam", r"ltm"],
}
_NO_TICKER = {"CLP", "USD", "UF", "RUT", "RUN", "IPC", "AFP", "APV", "SII", "OK", "PIN", "CVV", "CVC", "DAN", "API",
              "UAI", "IA", "PDF", "CSV", "URL", "ETF", "IVA", "YA", "NO", "SI", "MI", "LA", "EL", "DE", "VS", "Y",
              "PLN", "LLM", "TV", "BIP", "DPF"}

CATEGORIA_CLAVES = {
    "alimentacion": [r"super\w*", r"lider", r"jumbo", r"unimarc", r"tottus", r"santa isabel", r"almuerz\w*",
                     r"comida", r"feria", r"\bpan\b", r"verduleria", r"restaurant\w*", r"delivery", r"rappi",
                     r"pedidos ya", r"uber eats", r"once", r"cafe", r"completo\w*", r"sushi", r"pizza", r"mercaderia"],
    "transporte": [r"uber", r"cabify", r"didi", r"taxi", r"micro", r"metro", r"\bbip\b", r"bencina", r"combustible",
                   r"estacionamiento", r"peaje", r"\btag\b", r"colectivo", r"pasaje", r"\bbus\b", r"locomocion"],
    "vivienda": [r"arriendo", r"dividendo hipotecario", r"hipoteca\w*", r"gastos comunes", r"departamento",
                 r"\bdepto\b"],
    "servicios": [r"\bluz\b", r"\bagua\b", r"\bgas\b", r"internet", r"plan (del )?celular", r"telefono",
                  r"aguas andinas", r"metrogas", r"movistar", r"entel", r"\bwom\b", r"\bvtr\b", r"cuenta de la luz",
                  r"cuenta del agua", r"\benel\b"],
    "salud": [r"farmacia", r"remedio\w*", r"medic\w*", r"doctor\w*", r"consulta medica", r"dentista", r"isapre",
              r"fonasa", r"examen\w*", r"clinica", r"psicolog\w*"],
    "educacion": [r"universidad", r"colegio", r"matricula", r"arancel", r"\bcurso\w*", r"libro\w*", r"cuaderno\w*",
                  r"diplomado", r"\bu\b"],
    "entretencion": [r"\bcine\b", r"concierto", r"netflix", r"spotify", r"streaming", r"salida", r"carrete",
                     r"\bbar\b", r"videojuego\w*", r"juego\w*", r"viaje\w*", r"vacaciones", r"entrada\w*", r"disney"],
    "ropa": [r"\bropa\b", r"zapatilla\w*", r"polera\w*", r"pantalon\w*", r"zapato\w*", r"chaqueta\w*", r"vestido\w*",
             r"poleron\w*"],
    "deudas": [r"credito", r"cuota\w*", r"prestamo\w*", r"deuda\w*", r"avance", r"tarjeta de credito"],
}
CATEGORIA_INGRESO_CLAVES = {
    "sueldo": [r"sueldo", r"salario", r"remuneracion", r"liquidacion", r"aguinaldo", r"\bbono\b"],
    "honorarios": [r"honorario\w*", r"\bboleta\b", r"freelance", r"pega extra", r"pololito", r"proyecto",
                   r"cliente"],
    "dividendos": [r"dividendo\w*(?! hipotecario)"],
    "arriendo": [r"arriendo", r"arrendatario"],
    "regalo": [r"regal\w*", r"cumpleanos", r"me dieron plata"],
}


# ---------------------------------------------------------------- normalización

def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


# ---------------------------------------------------------------- montos

_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_MULT = r"millones|millon|mill|mm|palos?|lucas?|mil|k|m\b"
RE_MONTO = re.compile(
    rf"(?P<signo>\$|clp)?\s*(?P<num>{_NUM})\s*(?P<mult>{_MULT})?(?P<pesos>\s*(pesos|clp|\$))?", re.IGNORECASE
)
RE_MONTO_PALABRA = re.compile(
    rf"\b(?P<palabra>{'|'.join(sorted(NUMEROS_PALABRA, key=len, reverse=True))})\s+(?P<mult>{_MULT})\b"
)


def _a_numero(token: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        return float(token.replace(".", "").replace(",", "."))
    return float(token.replace(",", "."))


def _multiplicador(mult: str | None) -> float:
    if not mult:
        return 1
    mult = mult.lower()
    if mult.startswith("mill") or mult in ("mm", "m") or mult.startswith("palo"):
        return 1_000_000
    if mult.startswith("luca") or mult in ("mil", "k"):
        return 1_000
    return 1


def extraer_montos(texto: str) -> list[dict]:
    """Devuelve los candidatos a monto con su posición y si tienen marca explícita de dinero."""
    t = normalizar(texto)
    candidatos = []
    for m in RE_MONTO.finditer(t):
        num = m.group("num")
        ini, fin = m.start("num"), m.end()
        siguiente = t[fin:fin + 14]
        anterior = t[max(0, ini - 3):ini]
        # descartar fechas, cantidades de acciones, porcentajes y números pegados a letras
        if re.match(r"\s*(de )?" + _MES_LARGO, siguiente) and not m.group("mult"):
            continue
        if re.match(r"[/-]\d", t[m.end("num"):m.end("num") + 2]) or re.search(r"\d[/-]$", anterior):
            continue
        if re.match(r"\s*(acciones|accion|papeles|titulos|unidades|%|por ?ciento|meses|mes|dias|anos|semanas)",
                    siguiente) and not m.group("mult"):
            continue
        if t[max(0, ini - 1):ini].isalpha() or t[m.end("num"):m.end("num") + 1].isalpha() and not m.group("mult"):
            continue
        valor = _a_numero(num) * _multiplicador(m.group("mult"))
        if not m.group("mult") and not m.group("signo") and re.fullmatch(r"(19|20)\d{2}", num):
            continue  # años
        explicito = bool(m.group("signo") or m.group("mult") or m.group("pesos"))
        candidatos.append({"valor": int(round(valor)), "inicio": ini, "explicito": explicito, "texto": m.group(0)})
    for m in RE_MONTO_PALABRA.finditer(t):
        valor = NUMEROS_PALABRA[m.group("palabra")] * _multiplicador(m.group("mult"))
        candidatos.append({"valor": int(round(valor)), "inicio": m.start(), "explicito": True, "texto": m.group(0)})
    if re.search(r"\b(un|1) palo\b", t) is None and re.search(r"\bmedio palo\b", t):
        candidatos.append({"valor": 500_000, "inicio": t.find("medio palo"), "explicito": True, "texto": "medio palo"})
    return sorted(candidatos, key=lambda c: c["inicio"])


def parse_monto(texto: str) -> int | None:
    candidatos = [c for c in extraer_montos(texto) if c["valor"] > 0]
    if not candidatos:
        return None
    explicitos = [c for c in candidatos if c["explicito"]]
    return (explicitos or candidatos)[0]["valor"]


# ---------------------------------------------------------------- fechas y períodos

def _restar_meses(d: date, n: int) -> date:
    a, m = d.year, d.month - n
    while m <= 0:
        a, m = a - 1, m + 12
    return date(a, m, 1)


def _anio_para_mes(mes: int, hoy: date, dia: int = 1) -> int:
    return hoy.year if (mes, dia) <= (hoy.month, hoy.day) else hoy.year - 1


def parse_fecha(texto: str, hoy: date) -> str | None:
    t = normalizar(texto)
    if re.search(r"\b(anteayer|antes de ayer|antier)\b", t):
        return (hoy - timedelta(days=2)).isoformat()
    if re.search(r"\bayer\b", t):
        return (hoy - timedelta(days=1)).isoformat()
    if re.search(r"\bhoy\b", t):
        return hoy.isoformat()
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        d, mes = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3)) if m.group(3) else _anio_para_mes(mes, hoy, d)
        anio = anio + 2000 if anio < 100 else anio
        try:
            return date(anio, mes, d).isoformat()
        except ValueError:
            return None
    m = re.search(rf"\b(\d{{1,2}}) de {_MES_LARGO}(?: (?:de |del )?(\d{{4}}))?", t)
    if m:
        d, mes = int(m.group(1)), MESES[m.group(2)]
        anio = int(m.group(3)) if m.group(3) else _anio_para_mes(mes, hoy, d)
        try:
            return date(anio, mes, d).isoformat()
        except ValueError:
            return None
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    m = re.search(r"\b(el|este|el pasado) (" + "|".join(dias) + r")\b", t)
    if m:
        objetivo = dias.index(m.group(2))
        delta = (hoy.weekday() - objetivo) % 7 or 7
        return (hoy - timedelta(days=delta)).isoformat()
    m = re.search(r"\bel (\d{1,2})\b(?! de)", t)
    if m and 1 <= int(m.group(1)) <= 31 and not re.search(r"\bel \d{1,2} ?(%|acciones|por)", t):
        d = int(m.group(1))
        if d <= hoy.day:
            return date(hoy.year, hoy.month, d).isoformat()
    return None


def _periodo(desde: date, hasta: date) -> dict:
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat()}


def parse_periodo(texto: str, hoy: date) -> dict | None:
    t = normalizar(texto)
    m = re.search(r"\bultim[oa]s? (\d+|un|una|dos|tres|cuatro|cinco|seis|doce) (mes|meses|dias|semanas|anos)\b", t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else int(NUMEROS_PALABRA[m.group(1)])
        unidad = m.group(2)
        if unidad.startswith("mes"):
            return _periodo(_restar_meses(hoy, n - 1), hoy)
        if unidad.startswith("dia"):
            return _periodo(hoy - timedelta(days=n - 1), hoy)
        if unidad.startswith("semana"):
            return _periodo(hoy - timedelta(days=7 * n - 1), hoy)
        return _periodo(_restar_meses(hoy, 12 * n - 1), hoy)
    if re.search(r"\b(ultimo ano|ultimos doce meses|el ultimo ano|en un ano|ano completo|12 meses)\b", t):
        return _periodo(_restar_meses(hoy, 11), hoy)
    if re.search(r"\bultimo (trimestre)\b", t):
        return _periodo(_restar_meses(hoy, 2), hoy)
    if re.search(r"\bultimo semestre\b", t):
        return _periodo(_restar_meses(hoy, 5), hoy)
    if re.search(r"\b(este mes|el mes actual|mes en curso|en lo que va del mes)\b", t):
        return _periodo(date(hoy.year, hoy.month, 1), hoy)
    if re.search(r"\b(el mes pasado|mes anterior|del mes pasado|ultimo mes)\b", t):
        inicio = _restar_meses(hoy, 1)
        return _periodo(inicio, fin_de_mes(inicio.year, inicio.month))
    if re.search(r"\b(esta semana)\b", t):
        return _periodo(hoy - timedelta(days=hoy.weekday()), hoy)
    if re.search(r"\b(la semana pasada|semana anterior)\b", t):
        lunes = hoy - timedelta(days=hoy.weekday() + 7)
        return _periodo(lunes, lunes + timedelta(days=6))
    if re.search(r"\b(este ano|en lo que va del ano|ano actual|del ano)\b", t):
        return _periodo(date(hoy.year, 1, 1), hoy)
    if re.search(r"\b(el ano pasado|ano anterior)\b", t):
        return _periodo(date(hoy.year - 1, 1, 1), date(hoy.year - 1, 12, 31))
    if re.search(r"\bhoy\b", t):
        return _periodo(hoy, hoy)
    m = re.search(rf"\b(?:entre|de|desde) {_MES_LARGO}(?: (?:de |del )?(\d{{4}}))? (?:y|a|hasta) {_MES_LARGO}"
                  rf"(?: (?:de |del )?(\d{{4}}))?", t)
    if m:
        m1, m2 = MESES[m.group(1)], MESES[m.group(3)]
        a2 = int(m.group(4)) if m.group(4) else _anio_para_mes(m2, hoy)
        a1 = int(m.group(2)) if m.group(2) else (a2 if m1 <= m2 else a2 - 1)
        return _periodo(date(a1, m1, 1), min(fin_de_mes(a2, m2), hoy))
    m = re.search(rf"\bdesde {_MES_LARGO}(?: (?:de |del )?(\d{{4}}))?", t)
    if m:
        mes = MESES[m.group(1)]
        anio = int(m.group(2)) if m.group(2) else _anio_para_mes(mes, hoy)
        return _periodo(date(anio, mes, 1), hoy)
    m = re.search(rf"\b{_MES_LARGO}(?: (?:de |del )?(\d{{4}}))?", t)
    if m and not re.search(rf"\d{{1,2}} de {m.group(1)}", t):
        mes = MESES[m.group(1)]
        anio = int(m.group(2)) if m.group(2) else _anio_para_mes(mes, hoy)
        return _periodo(date(anio, mes, 1), min(fin_de_mes(anio, mes), hoy))
    m = re.search(r"\b(?:en|el|del|durante) (?:ano )?(20\d{2})\b", t)
    if m:
        anio = int(m.group(1))
        return _periodo(date(anio, 1, 1), min(date(anio, 12, 31), hoy))
    return None


# ---------------------------------------------------------------- acciones

def detectar_tickers(texto: str) -> list[str]:
    t = normalizar(texto)
    encontrados: list[tuple[int, str]] = []
    ocupado: list[tuple[int, int]] = []
    for ticker, alias in TICKERS_ALIAS.items():
        for a in alias:
            m = re.search(rf"\b{a}\b", t)
            if m and not any(i <= m.start() < f for i, f in ocupado):
                encontrados.append((m.start(), ticker))
                ocupado.append((m.start(), m.end()))
                break
    if re.search(r"\bCHILE\b", texto) and "CHILE" not in [x[1] for x in encontrados]:
        encontrados.append((texto.find("CHILE"), "CHILE"))
    for m in re.finditer(r"\b([A-Z]{2,9}(?:-[A-Z])?)\b", texto):
        sigla = m.group(1)
        if sigla not in _NO_TICKER and sigla not in [x[1] for x in encontrados] and sigla not in ("CHILE",) \
                and not any(sigla.lower() in a for alias in TICKERS_ALIAS.values() for a in alias):
            encontrados.append((m.start(), sigla))
    return [tk for _, tk in sorted(encontrados)]


def parse_cantidad(texto: str) -> float | None:
    t = normalizar(texto)
    m = re.search(r"(\d+(?:[.,]\d+)?|" + "|".join(NUMEROS_PALABRA) + r")\s+(acciones|accion|papeles|titulos|unidades)",
                  t)
    if m:
        v = m.group(1)
        return float(v.replace(",", ".")) if v[0].isdigit() else float(NUMEROS_PALABRA[v])
    return None


def parse_precio(texto: str, cantidad: float | None) -> float | None:
    """Precio por acción. 'a 41.000' = unitario; 'por 650 mil' o 'total' = total / cantidad."""
    t = normalizar(texto)
    unitario = re.search(r"\b(a|en|@|precio(?: de)?|valor(?: de)?)\s*\$?\s*(" + _NUM + r")\s*(" + _MULT + r")?", t)
    total = re.search(r"\b(por|total(?: de)?|pague|invirtiendo|gastando)\s*\$?\s*(" + _NUM + r")\s*(" + _MULT + r")?",
                      t)
    if unitario and not re.match(r"\s*(acciones|accion)", t[unitario.end():unitario.end() + 10]):
        return _a_numero(unitario.group(2)) * _multiplicador(unitario.group(3))
    if total and cantidad:
        bruto = _a_numero(total.group(2)) * _multiplicador(total.group(3))
        if re.search(r"(por accion|c/u|cada una|por unidad|por papel)", t):
            return bruto
        return round(bruto / cantidad, 2)
    return None


# ---------------------------------------------------------------- categorías, métricas y series

def detectar_categoria(texto: str, tipo: str) -> str | None:
    t = normalizar(texto)
    claves = CATEGORIA_CLAVES if tipo == "gasto" else CATEGORIA_INGRESO_CLAVES
    for nombre in (CATEGORIAS_GASTO if tipo == "gasto" else CATEGORIAS_INGRESO):
        if re.search(rf"\b{nombre}\b", t) and nombre != "otros":
            return nombre
    if tipo == "gasto" and re.search(r"\buber eats\b", t):
        return "alimentacion"
    for nombre, patrones in claves.items():
        if any(re.search(rf"\b{p}" if not p.startswith(r"\b") else p, t) for p in patrones):
            return nombre
    return None


def detectar_metrica(texto: str) -> str | None:
    t = normalizar(texto)
    for metrica, patron in (("patrimonio", r"patrimonio|riqueza|patrimonial|valor total"),
                            ("gastos", r"gast|egreso|salida"),
                            ("ingresos", r"ingres|ganancia|gane|sueldo|entrada"),
                            ("saldo", r"saldo|caja|plata|dinero|cuenta")):
        if re.search(rf"\b({patron})", t):
            return metrica
    return None


def extraer_serie(texto: str) -> list[list] | None:
    """Pares 'etiqueta valor' entregados en el mensaje (RF-14). Requiere ≥ 2 pares."""
    t = normalizar(texto)
    patron = re.compile(rf"\b({_MES_LARGO}|[a-z]{{3,12}}|20\d{{2}}|(?:q|t)[1-4])\s*[:=]?\s*\$?\s*({_NUM})\s*({_MULT})?")
    excluir = {"gaste", "gane", "pague", "compre", "vendi", "con", "por", "los", "las", "del", "que", "mis", "mes",
               "meses", "unos", "ingresos", "gastos", "saldo", "ultimos", "ultimas", "acciones", "de", "y", "fue",
               "fueron", "tuve", "tengo", "grafica", "grafico", "datos", "estos", "serie", "valores", "dame"}
    pares = []
    for m in patron.finditer(t):
        etiqueta = m.group(1)
        if etiqueta in excluir:
            continue
        valor = _a_numero(m.group(3)) * _multiplicador(m.group(4))
        pares.append([etiqueta.capitalize(), int(round(valor))])
    return pares if len(pares) >= 2 else None


def detectar_tipo(texto: str) -> str | None:
    t = normalizar(texto)
    g = bool(re.search(r"\b(gast\w*|egreso\w*|salida\w*|pague|desembols\w*)", t))
    i = bool(re.search(r"\b(ingres\w*|gane|ganado|entrad\w*|recibi\w*|me pagaron|cobre)", t))
    if g and not i:
        return "gasto"
    if i and not g:
        return "ingreso"
    return None


def extraer_tema(texto: str) -> str | None:
    t = normalizar(texto)
    for tema, patron in (("diversificacion", r"diversific"), ("fondos mutuos", r"fondos? mutuos?"),
                         ("deposito a plazo", r"deposito a plazo|\bdap\b|\bdpf\b"), ("etf", r"\betf"),
                         ("apv", r"\bapv\b|ahorro previsional"), ("acciones", r"\baccion(es)?\b"),
                         ("ahorro", r"ahorr"), ("criptomonedas", r"cripto|bitcoin"), ("dividendos", r"dividend"),
                         ("riesgo", r"riesg")):
        if re.search(patron, t):
            return tema
    return None


# ---------------------------------------------------------------- intención

_R = lambda p: re.compile(p)  # noqa: E731
P_GRAFICO = _R(r"\b(grafic\w*|grafiq\w*|chart|plot|visualiz\w*|dibuja\w*|curva|linea de tiempo|evolucion|"
               r"como (ha|han) (ido|evolucionado|variado|cambiado)|tendencia|historico)\b")
P_COMPARAR = _R(r"\b(compar\w*|versus|vs\.?|contra|frente a)\b")
P_ING_EGR = _R(r"\b(ingresos?\b.{0,25}\b(gastos?|egresos?)|(gastos?|egresos?)\b.{0,25}\bingresos?|"
               r"entradas y salidas|lo que (gano|entra) .{0,20}(gasto|sale))")
P_CATEGORIA = _R(r"\b(por categoria|categorias|en que (gasto|se me va|se va)|distribucion|torta|pie|donde se (me )?va)")
P_COMPRA = _R(r"\b(compre|he comprado|acabo de comprar|adquiri|registra(r)? (una |la )?compra|anota(r)? (una |la )?compra|"
              r"invert[ií] en)\b")
P_VENTA = _R(r"\b(vendi|he vendido|acabo de vender|liquide|registra(r)? (una |la )?venta|anota(r)? (una |la )?venta)\b")
P_ACCIONES = _R(r"\b(acciones?|papeles|titulos)\b")
P_CONSEJO = _R(r"\b(recomiend\w*|conviene|deberia (invertir|comprar|vender)|en que invierto|vale la pena|es buena idea|"
               r"que opinas|diversific\w*|fondos? mutuos?|deposito a plazo|que es (un|una|el|la) |como invertir|"
               r"consejo\w*|como (puedo )?ahorrar|me aconsejas|sugieres|apv|etf|bitcoin|cripto\w*|mejor inversion)")
P_GASTO = _R(r"\b(gaste|pague|me cobraron|desembolse|se me fueron|anota(r)? (un |el )?gasto|registra(r)? (un |el )?gasto|"
             r"gasto de|compre|me compre|salio|me salio|costo|cancele|pagamos|gastamos)\b")
P_INGRESO = _R(r"\b(me pagaron|recibi|gane|me depositaron|me transfirieron|ingreso de|me llego|cobre|"
               r"anota(r)? (un |el )?ingreso|registra(r)? (un |el )?ingreso|me entro|me entraron|me abonaron|"
               r"me dieron|me regalaron|vendi (mi|el|la|un|una) (?!accion))\b")
P_SALDO = _R(r"\b(saldo|cuanto (dinero|plata) (tengo|me queda|hay)|cuanta plata|cuanto tengo|disponible|"
             r"cuanto me queda|caja|cuanto hay en mi cuenta|plata tengo)\b")
P_PORTAFOLIO = _R(r"\b(portafolio|portfolio|cartera|mis acciones|mis inversiones|posicion\w*|cuantas acciones|"
                  r"como van mis|rentabilidad|ganancia\w* de mis|cuanto valen mis|cuanto vale mi)\b")
P_MOVIMIENTOS = _R(r"\b(cuanto (gaste|he gastado|gastamos|llevo gastado|gane|he ganado|ingrese|me entro|recibi)|"
                   r"en que (gaste|me gaste|se me fue)|mis gastos|mis ingresos|movimientos|resumen|cartola|"
                   r"total de (gastos|ingresos)|cuanto se me fue)\b")
P_SALUDO = _R(r"^(hola|holi|buenas|buen dia|buenos dias|buenas tardes|buenas noches|wena|hey|que tal|alo)\b")
P_AYUDA = _R(r"\b(ayuda|ayudame|que puedes hacer|que sabes hacer|como funciona|como te uso|opciones|comandos|"
             r"para que sirves|que haces)\b")
P_DESPEDIDA = _R(r"\b(chao|adios|hasta luego|nos vemos|eso es todo|bye|hasta pronto|muchas gracias|gracias)\b")


def detectar_intencion(texto: str) -> str:
    t = normalizar(texto)
    tickers = detectar_tickers(texto)
    acciones = bool(P_ACCIONES.search(t)) or bool(tickers)
    if P_GRAFICO.search(t) or (P_COMPARAR.search(t) and (tickers or P_ING_EGR.search(t))) or \
            (P_CATEGORIA.search(t) and not re.search(r"\bcuanto\b", t)):
        if (P_COMPARAR.search(t) or len(tickers) >= 1) and tickers:
            return "grafico_comparar_acciones"
        if P_ING_EGR.search(t):
            return "grafico_ingresos_egresos"
        if P_CATEGORIA.search(t):
            return "grafico_gastos_categoria"
        return "grafico_linea_tiempo"
    if P_CONSEJO.search(t) and not P_COMPRA.search(t) and not P_VENTA.search(t):
        return "consejo_inversion"
    if P_VENTA.search(t) and acciones:
        return "registrar_venta"
    if P_COMPRA.search(t) and acciones:
        return "registrar_compra"
    if P_PORTAFOLIO.search(t):
        return "consultar_portafolio"
    if P_MOVIMIENTOS.search(t) or (re.search(r"^(cuanto|que)\b", t) and P_CATEGORIA.search(t)):
        return "consultar_movimientos"
    if P_SALDO.search(t):
        return "consultar_saldo"
    if P_INGRESO.search(t):
        return "registrar_ingreso"
    if P_GASTO.search(t):
        return "registrar_gasto"
    if P_SALUDO.search(t):
        return "saludo"
    if P_AYUDA.search(t):
        return "ayuda"
    if P_DESPEDIDA.search(t):
        return "despedida"
    if P_CATEGORIA.search(t) and re.search(r"\bgast", t):
        return "consultar_movimientos"
    return "fuera_de_dominio"


# ---------------------------------------------------------------- entidades por intención

def extraer_entidades(texto: str, intencion: str, hoy: date) -> dict:
    e: dict = {}
    if intencion in ("registrar_gasto", "registrar_ingreso"):
        tipo = "gasto" if intencion == "registrar_gasto" else "ingreso"
        if (monto := parse_monto(texto)) is not None:
            e["monto"] = monto
        if cat := detectar_categoria(texto, tipo):
            e["categoria"] = cat
        if fecha := parse_fecha(texto, hoy):
            e["fecha"] = fecha
    elif intencion in ("registrar_compra", "registrar_venta"):
        if tickers := detectar_tickers(texto):
            e["ticker"] = tickers[0]
        cantidad = parse_cantidad(texto)
        if cantidad is not None:
            e["cantidad"] = cantidad
        if (precio := parse_precio(texto, cantidad)) is not None:
            e["precio"] = precio
        if fecha := parse_fecha(texto, hoy):
            e["fecha"] = fecha
    elif intencion == "consultar_portafolio":
        if tickers := detectar_tickers(texto):
            e["ticker"] = tickers[0]
    elif intencion == "consultar_movimientos":
        if tipo := detectar_tipo(texto):
            e["tipo"] = tipo
        if cat := detectar_categoria(texto, "gasto") or detectar_categoria(texto, "ingreso"):
            if cat != "otros":
                e["categoria"] = cat
        if periodo := parse_periodo(texto, hoy):
            e["periodo"] = periodo
    elif intencion.startswith("grafico_"):
        if periodo := parse_periodo(texto, hoy):
            e["periodo"] = periodo
        if intencion == "grafico_comparar_acciones" and (tickers := detectar_tickers(texto)):
            e["tickers"] = tickers
        if intencion == "grafico_linea_tiempo" and (metrica := detectar_metrica(texto)):
            e["metrica"] = metrica
        if serie := extraer_serie(texto):
            e["serie"] = serie
            e.pop("periodo", None)  # los meses de la serie son etiquetas, no un período
    elif intencion == "consejo_inversion":
        if tema := extraer_tema(texto):
            e["tema"] = tema
    return e


def interpretar(texto: str, hoy: date) -> dict:
    intencion = detectar_intencion(texto)
    return {"intencion": intencion, "entidades": extraer_entidades(texto, intencion, hoy)}
