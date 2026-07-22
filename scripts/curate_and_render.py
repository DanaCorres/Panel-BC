"""
Toma raw_items.json (salida de fetch_news.py), le pide a Claude que elija
las notas más relevantes por categoría y las resuma en sus propias palabras
(nunca copiar texto textual, por derechos de autor), y regenera index.html
a partir de templates/index_template.html.
 
Requiere la variable de entorno ANTHROPIC_API_KEY (se configura como
"secret" en GitHub, ver README).
"""
 
import json
import os
import re
from datetime import datetime, timezone
 
import anthropic
 
MODEL = "claude-haiku-4-5-20251001"  # rápido y barato, suficiente para curar titulares
 
# Cuántos titulares como máximo se le mandan a Claude para curar. Limitarlo
# evita que la respuesta (que también es texto) se vuelva tan larga que se
# corte antes de terminar el JSON.
MAX_ITEMS_TO_CURATE = 40
MAX_NOTES_PER_CATEGORY = 4
 
CATEGORIES = ["seguridad", "politica", "economia", "sociedad"]
CATEGORY_LABELS = {
    "seguridad": "Seguridad",
    "politica": "Política y gobierno",
    "economia": "Economía",
    "sociedad": "Sociedad, cultura y deportes",
}
CATEGORY_COLORS = {
    "seguridad": "var(--seguridad)",
    "politica": "var(--politica)",
    "economia": "var(--economia)",
    "sociedad": "var(--sociedad)",
}
 
SYSTEM_PROMPT = f"""Eres un editor de noticias para un panel enfocado en Baja California, México.
Se te da una lista de titulares recientes tomados de medios locales (con su fuente y URL).
Tu trabajo:
1. Quédate solo con las notas relevantes para Baja California (Tijuana, Mexicali, Ensenada,
   Tecate, Rosarito, San Quintín). Descarta notas genéricas de espectáculos/deportes internacionales
   que no tengan relación con el estado.
2. Clasifica cada nota elegida en una de estas categorías: seguridad, politica, economia, sociedad.
3. Elige como máximo {MAX_NOTES_PER_CATEGORY} notas por categoría, priorizando lo más importante
   e impactante del día.
4. Para cada nota, escribe un título MUY corto (máx 12 palabras) y un resumen MUY breve
   (máx 20 palabras), ambos EN TUS PROPIAS PALABRAS -- nunca copies el titular original tal cual
   ni frases textuales de la fuente. Sé conciso: es más importante que el JSON quede completo
   que dar detalle.
5. IMPORTANTE sobre el formato: responde ÚNICAMENTE con JSON válido, sin texto adicional, sin
   bloques de markdown (nada de ```). Si un título o resumen necesita usar comillas dobles,
   escápalas como \\" para no romper el JSON. No uses saltos de línea dentro de los valores de
   texto. Estructura exacta:
 
{{"seguridad": [{{"title": "...", "summary": "...", "source": "...", "url": "..."}}],
 "politica": [...], "economia": [...], "sociedad": [...]}}
 
Si una categoría no tiene notas relevantes, devuélvela como lista vacía.
"""
 
 
def build_user_prompt(items):
    lines = []
    for it in items[:MAX_ITEMS_TO_CURATE]:
        if not it.get("title"):
            continue
        lines.append(f"- [{it['source']}] {it['title']} ({it['url']})")
    return "Titulares disponibles:\n" + "\n".join(lines)
 
 
def extract_json(text):
    """Intenta parsear el JSON tal cual; si falla (ej. se cortó a la mitad),
    intenta recortar hasta el último objeto completo por categoría en vez
    de tronar todo el pipeline."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
 
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[aviso] JSON no válido en el primer intento ({e}); "
              f"intentando reparar recortando al último objeto completo.")
 
    # Reparación simple: corta el texto justo después de la última "}"
    # que cierra una nota completa, y cierra manualmente las listas/objeto.
    last_brace = text.rfind("}")
    if last_brace == -1:
        raise ValueError("No se pudo reparar el JSON: no hay ningún '}' en la respuesta.")
 
    truncated = text[:last_brace + 1]
    # Cuenta llaves/corchetes abiertos sin cerrar y los cierra en orden inverso.
    open_stack = []
    in_string = False
    escape = False
    for ch in truncated:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            open_stack.append(ch)
        elif ch in "}]":
            if open_stack:
                open_stack.pop()
 
    closers = {"{": "}", "[": "]"}
    repaired = truncated + "".join(closers[c] for c in reversed(open_stack))
    return json.loads(repaired)
 
 
def curate(items):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Falta la variable de entorno ANTHROPIC_API_KEY")
 
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(items)}],
    )
    print(f"[info] stop_reason de la API: {resp.stop_reason}")
    text = resp.content[0].text
    return extract_json(text)
 
 
def render_cards(curated):
    html_blocks = []
    for cat in CATEGORIES:
        notes = curated.get(cat, [])
        html_blocks.append(f'<section>\n<div class="section-title"><span class="dot" '
                            f'style="background:{CATEGORY_COLORS[cat]}"></span>'
                            f'<h2>{CATEGORY_LABELS[cat]}</h2></div>')
        if not notes:
            html_blocks.append('<p style="font-size:13px;color:var(--muted)">'
                                'Sin notas relevantes en esta actualización.</p>')
        for note in notes:
            html_blocks.append(f'''
<div class="card {cat}">
  <h3><a href="{note.get("url", "#")}" style="color:inherit;text-decoration:none">{note.get("title", "")}</a></h3>
  <p>{note.get("summary", "")}</p>
  <p class="src">{note.get("source", "")}</p>
</div>''')
        html_blocks.append("</section>")
    return "\n".join(html_blocks)
 
 
def render_stats(curated):
    parts = []
    for cat in CATEGORIES:
        n = len(curated.get(cat, []))
        parts.append(f'<div class="stat"><p>{CATEGORY_LABELS[cat]}</p><p>{n} notas</p></div>')
    return "\n".join(parts)
 
 
def main():
    with open("raw_items.json", encoding="utf-8") as f:
        raw = json.load(f)
 
    curated = curate(raw["items"])
 
    with open("templates/index_template.html", encoding="utf-8") as f:
        template = f.read()
 
    now = datetime.now(timezone.utc)
    fecha_str = now.strftime("%d de %B de %Y, %H:%M UTC")
 
    html = template.replace("{{FECHA}}", fecha_str)
    html = html.replace("{{STATS}}", render_stats(curated))
    html = html.replace("{{CARDS}}", render_cards(curated))
 
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
 
    print("index.html regenerado correctamente.")
 
 
if __name__ == "__main__":
    main()
