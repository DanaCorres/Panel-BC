# Panel de noticias — Baja California

Dashboard que muestra las noticias más relevantes de Baja California, organizadas
por Seguridad, Política, Economía y Sociedad/deportes. Se actualiza solo cada
3 horas: un GitHub Action recolecta titulares, se los manda a Claude para que
elija los más relevantes y los resuma, y regenera index.html.

## 1. Súbelo a GitHub

git init
git add .
git commit -m "Panel de noticias de Baja California"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/panel-bc.git
git push -u origin main

## 2. Activa GitHub Pages

En el repositorio: Settings -> Pages -> "Build and deployment" -> Deploy from
a branch -> rama main, carpeta / (root). En un par de minutos tu panel
estará en https://TU_USUARIO.github.io/panel-bc/

## 3. Configura la API key de Claude (necesaria para la curación automática)

1. Crea una cuenta y una API key en console.anthropic.com.
   Necesitas tener saldo/crédito cargado; con el modelo Haiku cada corrida cuesta
   fracciones de centavo, así que corriendo cada 3 horas el gasto mensual es mínimo.
2. En tu repo de GitHub: Settings -> Secrets and variables -> Actions -> New repository secret.
3. Nombre: ANTHROPIC_API_KEY. Valor: tu API key. Guarda.

## 4. Verifica que el Action tenga permiso de escritura

Settings -> Actions -> General -> Workflow permissions -> elige
"Read and write permissions" y guarda. Sin esto, el Action no podrá hacer
commit del index.html actualizado.

## 5. Pruébalo manualmente

Ve a la pestaña Actions del repo, elige el workflow "Actualizar panel de
noticias" y dale Run workflow. Revisa los logs: si algo falla (típicamente
un scraper que dejó de funcionar, o la API key mal puesta), ahí aparecerá el error.

A partir de ahí corre solo cada 3 horas (cron "0 */3 * * *", en UTC — ajusta
el horario en .github/workflows/update.yml si quieres que coincida con horas
específicas en horario de Baja California, UTC-7/UTC-8).

## Cómo está armado

- scripts/fetch_news.py — junta titulares. RSS para las fuentes que lo tienen
  (ZETA Tijuana, El Vigía, AFN Tijuana); scraping simple de la portada para las
  que no (El Mexicano, El Imparcial). Guarda todo en raw_items.json.
- scripts/curate_and_render.py — manda esos titulares a Claude (modelo Haiku),
  pide que elija máximo 5 notas por categoría y las resuma con sus propias
  palabras, y regenera index.html a partir de templates/index_template.html.
- .github/workflows/update.yml — corre ambos scripts cada 3 horas y sube los
  cambios automáticamente.

## Limitaciones a tener en cuenta

- Facebook e Instagram no están incluidos. Esas páginas de tu lista original
  (yoamotijuanaoficial, jousinpalafoxnoticias, comunicatj, JoseIbarraBC,
  tjcomunica1, VictorLagunasTJ, chismecitopolitico, LaCaliente921Ensenada,
  Canal66tv) requieren inicio de sesión y no se pueden leer por script.
- Tres de esas páginas sí tienen sitio web equivalente, pero tampoco se
  pudieron integrar: yoamotijuanaoficial -> amotijuana.com, Canal66tv ->
  canal66.tv, y tjcomunica1/comunicatj -> tjcomunica.com. Los tres bloquean
  cualquier request automatizado (portada y RSS) con error 403, protección
  tipo Cloudflare contra bots. Como GitHub Actions corre desde IPs de
  datacenter, se toparía con el mismo bloqueo. La única forma real de leerlos
  sería con un navegador automatizado con técnicas anti-detección (Playwright
  + plugins stealth), que no es garantía de funcionar y aumenta bastante la
  complejidad y fragilidad del pipeline.
- jousinpalafoxnoticias, JoseIbarraBC, chismecitopolitico y VictorLagunasTJ no
  tienen sitio web propio: son cuentas/páginas personales de líderes de
  opinión, solo existen en redes sociales.
- El scraping (no-RSS) es frágil. Si El Mexicano o El Imparcial rediseñan su
  sitio, el scraper de fetch_news.py puede dejar de traer notas de esa fuente
  hasta que se ajuste el código. Revisa los logs del Action de vez en cuando.
- Otras fuentes de tu lista (psn.si, Uniradio Baja, TV Azteca BC, N+, Imagen
  TV, Radiopatrulla, tjcomunica.com, siempreenlanoticia.com, politico.mx, entre
  otras) no están integradas en este pipeline; se pueden agregar a
  HTML_SOURCES o RSS_SOURCES en fetch_news.py si alguna tiene RSS o una
  estructura de HTML fácil de leer.
- El resumen lo genera un modelo de lenguaje: puede cometer errores o perder
  matices. Trátalo como un primer vistazo, no como fuente única.
