# GM Noticias

Portal con las noticias más importantes de Perú y el mundo, actualizado cada mañana.

## Cómo funciona

1. Todos los días a las 6:00 a. m. (hora de Lima), GitHub Actions ejecuta `scripts/actualizar.py`.
2. El script descarga los titulares de las últimas 30 horas de los medios en `sources.json`.
3. Claude agrupa las notas que cuentan el mismo hecho, elige las 25 a 40 más relevantes, escribe un resumen propio de cada una y las clasifica por sección.
4. La edición se guarda en `site/data/noticias.json` (y una copia por fecha en `site/data/archivo/`) y se publica en GitHub Pages.

Cada noticia enlaza a los artículos originales; el portal no copia textos completos.

## Personalizar

- **Medios**: edita `sources.json`. Si un medio no tiene RSS, usa Google News filtrado por su dominio (ver `respaldo_google_news`).
- **Hora**: cambia el `cron` en `.github/workflows/actualizar.yml` (está en UTC).
- **Modelo**: variable de entorno `CLAUDE_MODEL` (por defecto `claude-sonnet-5-5`; `claude-opus-5-5` da mejores resúmenes a mayor costo, `claude-haiku-5-5` es el más barato).

## Probar en local

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # opcional
python scripts/actualizar.py
python -m http.server -d site 8000   # abre http://localhost:8000
```
