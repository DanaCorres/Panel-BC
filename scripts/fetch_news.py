"""
Recolecta titulares recientes de medios de Baja California.
- Fuentes con RSS: se leen directo (más estable).
- Fuentes sin RSS: scraping simple del home (más frágil, puede romperse
  si el medio cambia su HTML; revisar SOURCES si un scraper deja de traer notas).
- Facebook / Instagram no se incluyen: requieren login, no son accesibles vía script.

Salida: raw_items.json con una lista de {source, title, url, published}

IMPORTANTE sobre el orden de la salida: curate_and_render.py se queda con los
primeros 40 titulares del archivo. Si aquí se escribieran uno tras otro, fuente
por fuente, las tres de RSS (15 cada una = 45) llenarían el cupo y los cinco
medios de scraping nunca llegarían al modelo. Por eso la lista se entrega
intercalada: primero el titular más reciente de cada fuente, luego el segundo
de cada una, y así. Con ocho fuentes, los primeros 40 son cinco de cada una.
"""

import json
import re
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (panel-bc-bot; +https://github.com/)"}

# Fuentes con RSS conocido o probable. Si una URL de feed deja de funcionar,
# el bloque de abajo simplemente la salta (no truena todo el pipeline).
RSS_SOURCES = [
    {"name": "ZETA Tijuana", "url": "https://zetatijuana.com/feed/"},
    {"name": "El Vigía (Ensenada)", "url": "https://www.elvigia.net/rss/"},
    {"name": "AFN Tijuana", "url": "https://afntijuana.info/rss.php"},
]

# Fuentes sin RSS confiable: se scrapea el home y se toman los enlaces
# que parecen notas (heurística simple por longitud de texto y href).
HTML_SOURCES = [
    {"name": "El Mexicano", "url": "https://el-mexicano.com.mx/"},
    {"name": "El Imparcial (Tijuana)", "url": "https://www.elimparcial.com/tijuana"},
    # Estas tres se habían descartado antes por un falso positivo: una prueba
    # anterior devolvió 403 con "host_not_allowed", pero ese bloqueo era de la
    # sandbox de pruebas (que solo tiene permiso de red a un puñado de
    # dominios), no de los sitios en sí. Al probarlas con una herramienta con
    # acceso real a internet, las tres cargan sin problema.
    {"name": "Yo Amo Tijuana", "url": "https://amotijuana.com/"},
    {"name": "Canal 66", "url": "https://canal66.tv/"},
    {"name": "TJ Comunica", "url": "https://tjcomunica.com/"},
]

MAX_PER_SOURCE = 15

# Enlaces del home que no son notas. Al scrapear un menú se cuelan secciones,
# avisos legales y llamados a suscribirse; antes daba igual porque estas
# fuentes nunca llegaban al modelo, ahora sí llegan.
BASURA = re.compile(
    r"aviso de privacidad|t[eé]rminos y condiciones|pol[ií]tica de (privacidad|cookies)|"
    r"suscr[ií]b|reg[ií]strate|inicia sesi[oó]n|contacto|qui[eé]nes somos|directorio|"
    r"publicidad|newsletter|todos los derechos|men[uú] principal|ver m[aá]s|"
    r"lee tambi[eé]n|leer m[aá]s",
    re.IGNORECASE)


def parece_nota(texto: str) -> bool:
    """Filtro mínimo: descarta enlaces de navegación y avisos legales."""
    if not 25 <= len(texto) <= 200:
        return False
    if BASURA.search(texto):
        return False
    # Un titular casi siempre trae varias palabras y un verbo; las secciones
    # del menú suelen ser dos o tres palabras en mayúsculas.
    if len(texto.split()) < 5:
        return False
    if texto.isupper():
        return False
    return True


def fetch_rss(source):
    items = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:MAX_PER_SOURCE]:
            titulo = entry.get("title", "").strip()
            if not titulo:
                continue
            items.append({
                "source": source["name"],
                "title": titulo,
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
    except Exception as e:
        print(f"[aviso] RSS falló para {source['name']}: {e}")
    return items


def fetch_html(source):
    items = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        vistos_titulos = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if not parece_nota(text):
                continue
            if href in seen or text.lower() in vistos_titulos:
                continue
            if not href.startswith("http"):
                if href.startswith("/"):
                    base = re.match(r"https?://[^/]+", source["url"]).group(0)
                    href = base + href
                else:
                    continue
            seen.add(href)
            vistos_titulos.add(text.lower())
            items.append({
                "source": source["name"],
                "title": text,
                "url": href,
                "published": "",
            })
            if len(items) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"[aviso] scraping falló para {source['name']}: {e}")
    return items


def intercalar(por_fuente):
    """Une las listas por turnos: una nota de cada fuente, luego la siguiente.

    Así, al recortar la lista más adelante, el recorte se reparte entre todos
    los medios en vez de quedarse con los primeros dos o tres.
    """
    mezclado = []
    vueltas = max((len(v) for v in por_fuente.values()), default=0)
    for i in range(vueltas):
        for nombre in por_fuente:
            if i < len(por_fuente[nombre]):
                mezclado.append(por_fuente[nombre][i])
    return mezclado


def main():
    por_fuente = {}
    for s in RSS_SOURCES:
        por_fuente[s["name"]] = fetch_rss(s)
    for s in HTML_SOURCES:
        por_fuente[s["name"]] = fetch_html(s)

    all_items = intercalar(por_fuente)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items,
    }
    with open("raw_items.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    for nombre, notas in por_fuente.items():
        marca = "✓" if notas else "✗"
        print(f"  {marca} {nombre}: {len(notas)} notas")

    vivas = sum(1 for v in por_fuente.values() if v)
    print(f"Recolectadas {len(all_items)} notas de {vivas} fuentes vivas "
          f"(de {len(por_fuente)}).")
    print(f"Las primeras 40 —las que verá el modelo— cubren "
          f"{len({n['source'] for n in all_items[:40]})} fuentes distintas.")


if __name__ == "__main__":
    main()
