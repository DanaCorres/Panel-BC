"""
Recolecta titulares recientes de medios de Baja California.
- Fuentes con RSS: se leen directo (más estable).
- Fuentes sin RSS: scraping simple del home (más frágil, puede romperse
  si el medio cambia su HTML; revisar SOURCES si un scraper deja de traer notas).
- Facebook / Instagram no se incluyen: requieren login, no son accesibles vía script.

Salida: raw_items.json con una lista de {source, title, url, published}
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
]

# NOTA: amotijuana.com, canal66.tv y tjcomunica.com son la versión en sitio web
# de páginas de Facebook de la lista original (yoamotijuanaoficial, Canal66tv,
# tjcomunica1/comunicatj), pero bloquean cualquier request automatizado con
# error 403 -- tanto la portada como el feed RSS -- por protección tipo
# Cloudflare contra bots. Como los runners de GitHub Actions corren desde IPs
# de datacenter, se toparían con el mismo bloqueo. No se incluyen aquí porque
# fallarían siempre; si algún día habilitan un feed público, se pueden agregar
# a RSS_SOURCES.

MAX_PER_SOURCE = 15


def fetch_rss(source):
    items = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:MAX_PER_SOURCE]:
            items.append({
                "source": source["name"],
                "title": entry.get("title", "").strip(),
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
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if len(text) < 25 or len(text) > 200:
                continue
            if href in seen:
                continue
            if not href.startswith("http"):
                if href.startswith("/"):
                    base = re.match(r"https?://[^/]+", source["url"]).group(0)
                    href = base + href
                else:
                    continue
            seen.add(href)
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


def main():
    all_items = []
    for s in RSS_SOURCES:
        all_items.extend(fetch_rss(s))
    for s in HTML_SOURCES:
        all_items.extend(fetch_html(s))

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items,
    }
    with open("raw_items.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Recolectadas {len(all_items)} notas de {len(RSS_SOURCES) + len(HTML_SOURCES)} fuentes.")


if __name__ == "__main__":
    main()
