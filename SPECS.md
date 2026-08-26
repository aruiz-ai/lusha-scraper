# SPECS — Lusha Contact Scraper

Proyecto aparte que replica la arquitectura de `scrapping/` (LinkedIn) pero para
**Lusha** (`dashboard.lusha.com`), sin reveals de créditos: solo se exportan los
datos visibles de cada contacto en la lista de resultados (nombre, cargo, URL de
LinkedIn). Filtros: **Departamento**, **Seniority** y **País** (uno o varios
valores cada uno; el país es texto libre, sin validar). Al terminar, el Excel se
sube automáticamente a **Google Drive** si hay credenciales configuradas.

## Endpoints (`app.py`)

- `GET /` — página web. Todas las respuestas llevan `Cache-Control: no-store`.
- `GET /api/auth/status` — `{logged_in, login_running, last_result}`.
  `logged_in` = existe `data/storage_state.json`.
- `POST /api/login` — inicia un thread que abre Chromium (visible) en
  `dashboard.lusha.com`; si aparece `auth.lusha.com/login`, espera hasta
  `LOGIN_TIMEOUT_SECONDS` (15 min) a que el usuario entre y guarda la sesión.
- `POST /api/search` — body:
  ```json
  {
    "company": "Google",
    "filters": {
      "departments": ["Engineering & Technical", "Sales"],
      "seniorities": ["C-suite", "Director"],
      "countries": ["Spain"]
    },
    "max_pages": 10       // o bien "all_pages": true
  }
  ```
  - Devuelve 400 si falta `company`; 401 si no hay sesión guardada.
  - `filters.departments`, `filters.seniorities` y `filters.countries` aceptan
    lista o texto separado por comas/saltos de línea (se normaliza a lista en
    `app.py`).
  - Si `all_pages` es true → `max_pages = 0` (modo "todas las páginas").
  - Si no, `max_pages` se recorta a `[1, MAX_PAGES_LIMIT]` (50).
  - Crea el job y arranca `_run_job` en un thread daemon.
- `GET /api/jobs/<id>` — estado del job (polling del frontend).
- `GET /api/jobs/<id>/download` — descarga el `.xlsx` cuando el job está `done`.
- `POST /api/shutdown` — detiene el servidor (botón "Salir" del frontend);
  renderiza `templates/shutdown.html` y apaga el servidor Werkzeug con un
  timer de 1s.

Arranque (`python app.py` / exe): `bootstrap.single_instance()` (mutex global de
Windows), `bootstrap.ensure_runnable()`, puerto libre desde 5000
(`find_free_port`), apertura del navegador del usuario cuando el servidor
responde y servidor con `werkzeug.serving.make_server` (threaded).

### `_run_job`

- `progress(page_no, found, results)` actualiza el job y delega la acumulación
  en `jobs.append_results` (dedup por `url` o `name|role` dentro del manager).
- Errores:
  - `LoginRequiredError` → estado `needs_login`.
  - `ScraperError` → estado `error`.
  - Otras excepciones → estado `error` ("Error inesperado: ...").
- Sin filas → estado `done` con mensaje "No se encontraron contactos." (sin archivo).
- Con filas: `export_to_excel` genera el Excel; si existe
  `config.DRIVE_CREDENTIALS_PATH` se sube a Google Drive (`upload_xlsx`) y el
  mensaje añade "Subido a Google Drive" (o un aviso si falló, sin tumbar el
  job). El job pasa a `done` con `filepath`/`filename`/`drive_url`.

## `config.py`

- Rutas: `BASE_DIR` (junto al `.exe` cuando está empaquetado con PyInstaller,
  vía `sys.frozen`), `DATA_DIR`, `EXPORTS_DIR`, `STORAGE_STATE_PATH`,
  `BROWSERS_DIR`. En el exe fija `PLAYWRIGHT_BROWSERS_PATH=<base>/ms-playwright`
  (Chromium se descarga en la primera ejecución junto al ejecutable).
- URLs: `LUSHA_DASHBOARD_URL`, `LUSHA_PROSPECTING_URL`
  (`/prospecting/contacts`).
- Límites: `DEFAULT_MAX_PAGES=10`, `MAX_PAGES_LIMIT=50`,
  `ALL_PAGES_SAFETY_LIMIT=200`, `LOGIN_TIMEOUT_SECONDS=15*60`.
- Google Drive: `DRIVE_CREDENTIALS_PATH=data/service-account.json`,
  `DRIVE_FOLDER_ID` (carpeta compartida con la cuenta de servicio, sobreescible
  con la variable de entorno `DRIVE_FOLDER_ID`) y `DRIVE_PUBLIC_LINKS=True`
  (comparte el archivo como "cualquiera con el enlace").
- **Delays conservadores**: `PAGE_DELAY_MIN=15`, `PAGE_DELAY_MAX=25`,
  `SCROLL_DELAY_MIN=1.5`, `SCROLL_DELAY_MAX=3.0`, `SCROLL_STEP=300`,
  `SCROLL_STEP_DELAY=150`, `RESULT_WAIT_SECONDS=4`, `LOGIN_POLL_SECONDS=2`.
- Crea `data/` y `data/exports/` al importarse (con try/except para no tumbar
  el arranque si falla la escritura).

## `jobs.py`

`JobManager` en memoria (volátil, con lock):

- `create(company, max_pages, all_pages=False, departments=None,
  seniorities=None, countries=None)` — job con `departments`, `seniorities`,
  `countries` (listas), `status="pending"`, `results=[]`, `found=0`,
  `filename/filepath/drive_url=None`.
- `append_results(job_id, new_results)` — acumula resultados **deduplicados**
  (clave: `url` o `name|role`) y actualiza `found`.
- `get/update`.

## `excel_writer.py`

- Cabeceras: `Nombre | Cargo | Correo | Teléfono | URL de LinkedIn` (Correo y
  Teléfono quedan vacías como placeholder; los datos visibles de la lista no
  incluyen email/teléfono sin gastar créditos).
- Nombre de archivo: `<empresa>.xlsx` (sanitizado con `sanitize_filename`, sin
  timestamp) en `data/exports/`.
- Cabecera azul (`0B66C2`), hipervínculos clicables en la columna de LinkedIn,
  anchos fijos y `freeze_panes="A2"`.

## `google_drive.py`

Subida del Excel mediante cuenta de servicio (`google-api-python-client`):

- `upload_xlsx(filepath, filename)` → `(file_id, web_view_link)`. Sube a
  `DRIVE_FOLDER_ID` (o a la raíz de la cuenta si está vacío); con
  `DRIVE_PUBLIC_LINKS` crea permiso `anyone/reader`.
- `DriveError` envuelve fallos de autenticación, subida o compartición.

## `bootstrap.py`

Utilidades de arranque del empaquetado (en desarrollo casi todo es no-op):

- `single_instance()` — mutex global de Windows; muestra error tkinter si ya
  hay otra instancia.
- `ensure_runnable()` — comprueba escritura en `data/` y `data/exports/`;
  instala Chromium (ventana de progreso tkinter, ~160 MB) si no existe en
  `BROWSERS_DIR`. Log opcional en `data/boot.log` con `LUSHA_DEBUG=1`.
- `find_free_port(preferred=5000)`, `open_browser_when_ready(url)`,
  `_show_error()` (tkinter).

## `scraper/lusha.py` + `scraper/selectors.py`

Clase `LushaScraper` (espejo de `LinkedInScraper`, sin reveals de créditos):

| Método | Qué hace |
| --- | --- |
| `scrape(company, progress, max_pages, departments=None, seniorities=None, countries=None)` | `asyncio.run(_scrape)`. |
| `login(timeout_seconds=None)` | `asyncio.run(_login)`. |
| `_scrape` | Página 1: carga `/prospecting/contacts`, `_search(company)`, `_apply_departments`, `_apply_seniorities`, `_apply_countries`; páginas 2+: `_goto_next_page`. Espera resultados, extrae filas, calcula `_new_items` (dedup local), notifica y **para** si no hay filas nuevas o sin `_has_next`. Al terminar refresca `storage_state` (best effort). Retorna lista de `{name, role, url}`. |
| `_search` | Rellena el buscador `[data-test-id="prospecting-free-text-search"]` (fallback `input.peer`) y pulsa Enter. |
| `_apply_departments` | Valida la entrada contra `KNOWN_DEPARTMENTS` (`_selected_values`: los no existentes se omiten con aviso; si ninguno vale lanza `ScraperError`). Expande `contactDepartment-filter`, escribe cada departamento en `contactDepartment-filter-input` (con espera de estabilización de 1.2s antes de clicar) y clica la opción exacta. **Selección autoverificada** (hasta 3 rondas): lee los chips seleccionados vía `data-for="tooltip-<Dept>"`, reintenta los faltantes y retira los chips extra (departamentos añadidos por carreras de clic erróneas) pulsando su `#svg-container`. Al final colapsa con Escape. |
| `_apply_seniorities` | Expande `contactSeniority-filter`; recorre los checkboxes `checkbox-contactSeniority-N`, compara la etiqueta de `[class*="TextContainer"]` normalizada (lowercase, ignorando conteo de población y title-case, p.ej. "C-Suite 2.6K") contra lo pedido y clica coincidencias. Valida contra `KNOWN_SENIORITIES`. Cada selección dispara la búsqueda automáticamente (espera 2.5s); colapsa con Escape. |
| `_apply_countries` | Expande `contactLocation-filter`; por cada país escribe en `contactLocation-filter-input`, espera el filtrado del dropdown (1.2s) y hace clic en la opción `contactLocation-option-N` cuyo texto coincide exactamente (case-insensitive, sin validación previa: texto libre). Cada país dispara la búsqueda (espera 4s); colapsa con Escape (el botón "Apply" del pie solo aplica la sección ZIP/rango). |
| `_expand_filter` | Abre un grupo acordeón salvo que ya esté abierto: sondea visibilidad de input/checkboxes internos; clicar el centro de un panel abierto caía sobre chips/input y Lusha añadía filtros no pedidos. |
| `_collapse_filter` | `Escape` + espera 1.5s (evita clics accidentales sobre chips). |
| `_wait_for_results` | Hasta ~25s a que haya filas `[data-test-id^="contacts-table-contact-name-"]`, durmiendo `RESULT_WAIT_SECONDS`; tras ver filas espera 2s de estabilización. |
| `_extract_results` | Por fila: nombre (primera línea del texto), cargo (`job-title-N`), URL de LinkedIn (`a[href*="linkedin.com/in/"]`, sin querystring). Salta filas sin nombre ni URL. |
| `_new_items` | Filtra resultados de página contra los acumulados (misma clave de dedup que `JobManager`). |
| `_has_next` / `_goto_next_page` | Detecta `pagination-next-page` deshabilitado (`disabled`/`aria-disabled`) y hace clic. |
| `_check_interruptions` | Comprueba `page.url` contra `CAPTCHA_URL_MARKS` (`captcha`, `challenge`) → `CaptchaError` y `AUTH_URL_MARKS` (`auth.lusha.com`, `/login`, `/signin`) → `LoginRequiredError`. Se comprueba en el `goto` inicial, al inicio de `_search`/`_apply_*`/`_goto_next_page` y **tras** cualquier excepción de esas acciones. |
| `_login` | Carga el dashboard; si no redirige a auth va a prospecting. Valida sesión con `_has_valid_session` (no estar en auth + presencia del panel `filter-panel-wrapper`). Si no hay sesión, espera login manual (polling cada `LOGIN_POLL_SECONDS`) y guarda `storage_state`. Devuelve `"login_completado"`. |
| `_open` | Chromium visible (`--start-maximized`), mismo anti-detección que LinkedIn: UA Chrome/151, `--disable-blink-features=AutomationControlled`, `--disable-infobars`, `ignore_default_args=["--enable-automation"]`, viewport 1366x900, locale `es-ES`, timezone `America/Mexico_City`, init script `navigator.webdriver=undefined`, carga `storage_state` si existe. |
| `_human_delay(lo, hi)` | `random.uniform(lo, hi)`; entre páginas se usan `PAGE_DELAY_MIN/MAX` (15–25s). |

### Selectores verificados en vivo (2026)

- `SEARCH_INPUT` / fallback `input.peer`: buscador de contactos.
- `RESULT_ROW`: `[data-test-id^="contacts-table-contact-name-"]` — 25 por página.
- `JOB_TITLE`: `[data-test-id^="job-title-"]`.
- `LINKEDIN_LINK`: `a[href*="linkedin.com/in/"]` dentro de la fila.
- `NEXT_PAGE` / `PREV_PAGE`: `[data-test-id="pagination-next-page"]` etc.
- `FILTER_PANEL`: `[data-test-id="filter-panel-wrapper"]` — señal de sesión
  válida en `/prospecting/contacts`.
- `DEPARTMENT_FILTER` / `DEPARTMENT_INPUT` / `DEPARTMENT_CHIP`:
  `[data-test-id="contactDepartment-filter"]` (grupo acordeón),
  `contactDepartment-filter-input` (input "Enter departments") y
  `contactDepartment-chip-N` (chips seleccionados, nombre en
  `data-for="tooltip-<Dept>"`, borrado vía `#svg-container`). Escribir filtra y
  el clic selecciona (multi-select, incluye toggle "Include/Exclude").
- `SENIORITY_FILTER` / `SENIORITY_CHECKBOX`:
  `[data-test-id="contactSeniority-filter"]` (grupo acordeón) y
  `[data-test-id^="checkbox-contactSeniority-"]` (lista de checkboxes 0–8).
  No tiene input de búsqueda; el clic sobre el texto exacto selecciona
  (multi-select, botón "Clear", dispara la búsqueda automáticamente).
- `LOCATION_FILTER` / `LOCATION_INPUT` / `LOCATION_OPTION`:
  `[data-test-id="contactLocation-filter"]` (grupo acordeón), input de búsqueda
  `contactLocation-filter-input` y opciones `contactLocation-option-N`. Al
  teclear un país y hacer clic en la opción exacta, la búsqueda se dispara
  automáticamente (cambia el `requestId`). El pie tiene ZIP + rango + botón
  `Apply`, que NO aplica la ubicación (solo el ZIP).
- `KNOWN_DEPARTMENTS` (validación/sugerencias): Engineering & Technical, Business
  Development, Consulting, Customer Service, Finance, General Management,
  Health Care & Medical, Human Resources, Information Technology, Legal,
  Marketing, Operations, Product, Research & Analytics, Sales (15).
- `KNOWN_SENIORITIES` (validación/sugerencias, verificados en vivo 2026):
  Founder, Partner, C-suite, Vice president, Director, Manager, Senior, Entry,
  Intern (9).
- Los datos visibles de la lista **no gastan créditos** (Free = OK).

## Frontend (`templates/index.html` + `static/app.js`)

- Formulario: empresa, **Departamentos (opcional, uno o varios)** con `datalist`
  de sugerencias y separación por coma, **Seniority (niveles, opcional)** con
  `datalist` de niveles, **País/países (opcional)** en texto libre,
  `max_pages` (1–50) con checkbox "Recorrer todas las páginas disponibles"
  (deshabilita el input numérico). Botón **Buscar contactos**.
- `app.js` envía `filters.departments`, `filters.seniorities` y
  `filters.countries` como listas (se separan por `,` o saltos de línea);
  verifica sesión antes de enviar.
- Banner de sesión (login manual vía `POST /api/login`, polling propio cada
  1.5s), tarjeta de progreso con barra determinada o indeterminada en modo
  "todas las páginas", tabla de vista previa (`PREVIEW_LIMIT=60`),
  botones **Descargar Excel** y **Abrir en Google Drive** (si `drive_url`), y
  botón **Salir** (`POST /api/shutdown`).
- Polling del job cada 1.5s (`POLL_INTERVAL`).

## Flujo de una búsqueda

1. Usuario abre la app; si no hay sesión, inicia sesión en la ventana automatizada
   (guardada en `data/storage_state.json`).
2. Rellena empresa (opcional: departamentos, seniority y países) y páginas →
   `POST /api/search` → `{job_id}`.
3. `_run_job` ejecuta `scraper.scrape()`: página 1 busca la empresa y luego aplica
   departamentos, seniorities y países (cada filtro dispara búsqueda propia);
   siguientes páginas usan `pagination-next-page`. Cada página llama a `progress`,
   acumulando resultados deduplicados en el job.
4. Al terminar, `export_to_excel` genera `<empresa>.xlsx`; si hay credenciales de
   Drive se sube y se comparte con enlace público. El job queda `done` con
   `filepath`, `filename` y `drive_url`.
5. El botón **Descargar Excel** apunta a `GET /api/jobs/<id>/download` y
   **Abrir en Google Drive** a `drive_url`.

## Notas

- `data/storage_state.json` y `data/service-account.json` no se versionan
  (`.gitignore`). El scraper refresca la sesión guardada al terminar cada
  búsqueda (cookies rotadas por Lusha).
- Si Lusha redirige a `auth.lusha.com` en mitad de una operación, se lanza
  `LoginRequiredError` (el job pasa a `needs_login` con banner de sesión), no un
  error genérico de Playwright.
- Jobs volátiles en memoria.
- Retiro de búsquedas de Lusha a alto volumen: los delays muy conservadores
  (15–25s entre páginas) y `ALL_PAGES_SAFETY_LIMIT` ayudan a evitarlo. El
  scraper además corta solo si una página no aporta contactos nuevos.
- Empaquetado: `build.bat` + `LushaScraper.spec` (PyInstaller). En el exe los
  datos viven junto al binario y Chromium se descarga en `ms-playwright/` en la
  primera ejecución (guiada por `bootstrap.py`).
- Legal: scraping del dashboard puede violar los ToS de Lusha; uso personal y
  bajo volumen.
