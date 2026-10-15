"""Descarga los RSS de sources.json, agrupa y resume las noticias con Claude,
y escribe site/data/noticias.json (más una copia en site/data/archivo/).

Uso:
    python scripts/actualizar.py              # descarga feeds reales
    python scripts/actualizar.py --demo FILE  # usa titulares de un JSON local (pruebas)

Sin ANTHROPIC_API_KEY publica los titulares sin agrupar ni resumir.
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "site" / "data"
HORAS_VENTANA = 30
MAX_POR_FUENTE = 25
SECCIONES = ["Perú", "Política", "Economía", "Mundo", "Sociedad", "Tecnología y ciencia", "Deportes", "Cultura"]
LIMA = timezone(timedelta(hours=-5))
GOOGLE_NEWS = "https://news.google.com/rss/search?q=site:{dominio}+when:1d&hl=es-419&gl=PE&ceid=PE:es-419"


def limpiar(texto, limite=300):
    texto = unescape(re.sub(r"<[^>]+>", " ", texto or ""))
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:limite]


def leer_feed(fuente, ambito):
    import feedparser

    if "google_news" in fuente:
        url = GOOGLE_NEWS.format(dominio=fuente["google_news"])
    else:
        url = fuente["rss"]
    feed = feedparser.parse(url, agent="GM-Noticias/1.0 (+https://github.com)")
    corte = datetime.now(timezone.utc) - timedelta(hours=HORAS_VENTANA)
    items = []
    for entrada in feed.entries[:MAX_POR_FUENTE]:
        fecha = entrada.get("published_parsed") or entrada.get("updated_parsed")
        fecha = datetime(*fecha[:6], tzinfo=timezone.utc) if fecha else None
        if fecha and fecha < corte:
            continue
        titulo = limpiar(entrada.get("title"), 200)
        if "google_news" in fuente:  # Google News agrega " - Medio" al titular
            titulo = titulo.rsplit(" - ", 1)[0]
        if not titulo or not entrada.get("link"):
            continue
        items.append({
            "titulo": titulo,
            "extracto": limpiar(entrada.get("summary")),
            "url": entrada.get("link"),
            "fuente": fuente["nombre"],
            "ambito": ambito,
            "fecha": fecha.isoformat() if fecha else None,
        })
    print(f"  {fuente['nombre']}: {len(items)} titulares", file=sys.stderr)
    return items


def descargar_todo():
    fuentes = json.loads((RAIZ / "sources.json").read_text(encoding="utf-8"))
    tareas = [(f, ambito) for ambito in ("peru", "mundo") for f in fuentes[ambito]]
    with ThreadPoolExecutor(max_workers=8) as pool:
        resultados = pool.map(lambda t: _seguro(leer_feed, *t), tareas)
    return [item for lote in resultados for item in lote]


def _seguro(fn, fuente, ambito):
    try:
        return fn(fuente, ambito)
    except Exception as e:  # un feed caído no debe tumbar la actualización
        print(f"  {fuente['nombre']}: error {e}", file=sys.stderr)
        return []


ESQUEMA = {
    "type": "object",
    "properties": {
        "destacada": {"type": "integer", "description": "Índice en 'noticias' de la noticia más importante del día"},
        "noticias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "resumen": {"type": "string"},
                    "seccion": {"type": "string", "enum": SECCIONES},
                    "importancia": {"type": "integer", "description": "1 (menor) a 5 (mayor)"},
                    "fuentes": {"type": "array", "items": {"type": "integer"}, "description": "Índices de los titulares originales que cubren este hecho"},
                },
                "required": ["titulo", "resumen", "seccion", "importancia", "fuentes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["destacada", "noticias"],
    "additionalProperties": False,
}

INSTRUCCIONES = """Eres el editor de GM Noticias, un portal peruano que resume cada día las noticias más importantes de Perú y del mundo.

Recibes una lista numerada de titulares de varios medios. Tu trabajo:
1. Agrupa los titulares que cuentan el mismo hecho en una sola noticia.
2. Elige entre 25 y 40 noticias que de verdad importan a un lector peruano informado. Descarta farándula, horóscopos, publirreportajes, ofertas y notas de servicio sin relevancia.
3. Para cada noticia escribe un titular propio y claro, y un resumen neutral de 2 a 3 frases con tus propias palabras. No copies frases de los medios ni inventes datos que no estén en los titulares o extractos.
4. Asigna una sección y una importancia de 1 a 5, y lista los índices de los titulares originales que la cubren.
Escribe en español neutro."""


def resumir_con_claude(items):
    import anthropic

    lista = "\n".join(
        f"[{i}] ({it['fuente']}, {it['ambito']}) {it['titulo']} — {it['extracto']}" for i, it in enumerate(items)
    )
    cliente = anthropic.Anthropic()
    respuesta = cliente.beta.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        system=INSTRUCCIONES,
        messages=[{"role": "user", "content": f"Titulares de las últimas {HORAS_VENTANA} horas:\n\n{lista}"}],
    )
    if respuesta.stop_reason != "end_turn":
        raise RuntimeError(f"Claude terminó con stop_reason={respuesta.stop_reason}")
    texto = next(b.text for b in respuesta.content if b.type == "text")
    datos = json.loads(texto)

    noticias = []
    for n in datos["noticias"]:
        enlaces, vistos = [], set()
        for i in n["fuentes"]:
            if 0 <= i < len(items) and items[i]["url"] not in vistos:
                vistos.add(items[i]["url"])
                enlaces.append({"medio": items[i]["fuente"], "url": items[i]["url"]})
        if enlaces:
            noticias.append({k: n[k] for k in ("titulo", "resumen", "seccion", "importancia")} | {"enlaces": enlaces})
    destacada = datos["destacada"] if 0 <= datos["destacada"] < len(noticias) else 0
    if noticias:
        noticias.insert(0, noticias.pop(destacada))
    return noticias


def sin_resumen(items):
    """Respaldo sin API key: titulares tal cual, sin duplicados exactos."""
    vistos, noticias = set(), []
    for it in items:
        clave = it["titulo"].lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        noticias.append({
            "titulo": it["titulo"],
            "resumen": it["extracto"],
            "seccion": "Perú" if it["ambito"] == "peru" else "Mundo",
            "importancia": 3,
            "enlaces": [{"medio": it["fuente"], "url": it["url"]}],
        })
    return noticias[:60]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", help="JSON con titulares de ejemplo en lugar de descargar feeds")
    args = parser.parse_args()

    if args.demo:
        items = json.loads(Path(args.demo).read_text(encoding="utf-8"))
    else:
        print("Descargando feeds…", file=sys.stderr)
        items = descargar_todo()
    print(f"{len(items)} titulares en total", file=sys.stderr)
    if not items:
        sys.exit("No se obtuvo ningún titular; se conserva la edición anterior.")

    if os.environ.get("ANTHROPIC_API_KEY"):
        noticias = resumir_con_claude(items)
        modo = "claude"
    else:
        print("Sin ANTHROPIC_API_KEY: se publican titulares sin resumir.", file=sys.stderr)
        noticias = sin_resumen(items)
        modo = "titulares"

    ahora = datetime.now(LIMA)
    edicion = {
        "actualizado": ahora.isoformat(timespec="minutes"),
        "modo": modo,
        "total_titulares": len(items),
        "medios": sorted({it["fuente"] for it in items}),
        "noticias": noticias,
    }
    DATOS.mkdir(parents=True, exist_ok=True)
    (DATOS / "archivo").mkdir(exist_ok=True)
    salida = json.dumps(edicion, ensure_ascii=False, indent=1)
    (DATOS / "noticias.json").write_text(salida, encoding="utf-8")
    (DATOS / "archivo" / f"{ahora:%Y-%m-%d}.json").write_text(salida, encoding="utf-8")
    fechas = sorted((p.stem for p in (DATOS / "archivo").glob("*.json")), reverse=True)
    (DATOS / "archivo.json").write_text(json.dumps(fechas), encoding="utf-8")
    print(f"Publicadas {len(noticias)} noticias ({modo}).", file=sys.stderr)


if __name__ == "__main__":
    main()
