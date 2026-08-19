# SPECS — Lusha Contact Scraper

Proyecto aparte que replica la arquitectura de `scrapping/` (LinkedIn) pero para
**Lusha** (`dashboard.lusha.com`), sin reveals de créditos: solo se exportan los
datos visibles de cada contacto en la lista de resultados (nombre, cargo, URL de
LinkedIn). Filtros: **Departamento**, **Seniority** y **País** (uno o varios
valores cada uno; el país es texto libre, sin validar).

## Endpoints (`app.py`)

- `GET /` — página web.
- `GET /api/auth/status` — `{logged_in, login_running, last_result}`.
  `logged_in` = existe `data/storage_state.json`.
- `POST /api/login` — inicia un thread que abre Chromium (visible) en
  `dashboard.lusha.com`; si aparece `auth.lusha.com/login`, espera hasta
  `LOGIN_TIMEOUT_SECONDS` (5 min) a que el usuario entre y guarda la sesión.
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
  - `filters.departments`, `filters.seniorities` y `filters.countries` aceptan
    lista o texto separado por comas/saltos de línea (se normaliza a lista en
    `app.py`).
  - Si `all_pages` es true → `max_pages = 0` (modo "todas las páginas").
  - Si no, `max_pages` se recorta a `[1, MAX_PAGES_LIMIT]` (50).
  - Crea el job y arranca `_run_job` en un thread daemon.
- `GET /api/jobs/<id>` — estado del job (polling del frontend).
- `GET /api/jobs/<id>/download` — descarga el `.xlsx` cuando el job está `done`.

### `_run_job`

- `progress(page_no, found, results)` actualiza el job y acumula resultados
  deduplicados (mismo criterio que el proyecto LinkedIn: por `url` o `name|role`).
- Errores:
  - `LoginRequiredError` → estado `needs_login`.
  - `CaptchaError` → estado `error`.
  - `ScraperError` / otras → estado `error`.
- Al terminar, si hay filas, `export_to_excel` genera el Excel y el job pasa a
  `done` con `filepath`/`filename`.

## `config.py`

- Rutas: `DATA_DIR`, `EXPORTS_DIR`, `STORAGE_STATE_PATH`.
- URLs: `LUSHA_DASHBOARD_URL`, `LUSHA_PROSPECTING_URL`
  (`/prospecting/contacts`).
- Límites: `DEFAULT_MAX_PAGES=10`, `MAX_PAGES_LIMIT=50`,
  `ALL_PAGES_SAFETY_LIMIT=200`, `LOGIN_TIMEOUT_SECONDS=5*60`.
- **Delays conservadores**: `PAGE_DELAY_MIN=3.5`, `PAGE_DELAY_MAX=6.0`,
  `SCROLL_DELAY_MIN=1.5`, `SCROLL_DELAY_MAX=3.0`, `SCROLL_STEP=300`,
  `SCROLL_STEP_DELAY=150`, `RESULT_WAIT_SECONDS=4`, `LOGIN_POLL_SECONDS=2`.
- Crea `data/` y `data/exports/` al importarse.

## `jobs.py`

Gestor del proyecto LinkedIn, con soporte de filtros:
`create(company, max_pages, all_pages=False, departments=None, seniorities=None)`.
El job guarda `departments` y `seniorities` (listas). Jobs en memoria (volátiles).

## `excel_writer.py`

- Cabeceras: `Nombre | Cargo | URL de LinkedIn`.
- Nombre de archivo: `contactos_<empresa>_<YYYY-mm-dd_HH-MM-SS>.xlsx` en
  `data/exports/`. Cabecera azul, anchos y `freeze_panes="A2"`.

## `scraper/lusha.py` + `scraper/selectors.py`

Clase `LushaScraper` (espejo de `LinkedInScraper`, sin reveals de créditos):

| Método | Qué hace |
| --- | --- |
| `scrape(company, progress, max_pages, departments=None, seniorities=None, countries=None)` | `asyncio.run(_scrape)`. |
| `_scrape` | Página 1: carga `/prospecting/contacts`, `_search(company)`, `_apply_departments(departments)`, `_apply_seniorities(seniorities)`, `_apply_countries(countries)`; páginas 2+: `_goto_next_page`. Espera resultados, extrae filas, dedup, notifica y **para** si no hay `_has_next`. Al terminar guarda `storage_state` refrescado. Retorna lista de `{name, role, url}`. |
| `_search` | Rellena el buscador `[data-test-id="prospecting-free-text-search"]` (fallback `input.peer`) y pulsa Enter. |
| `_apply_departments` | Expande el grupo `contactDepartment-filter`; por cada departamento escribe en `contactDepartment-filter-input` y hace clic en la opción con texto exacto. Valida contra `KNOWN_DEPARTMENTS` (los no existentes se omiten). **Cada selección dispara la búsqueda automáticamente** (cambia el `requestId` de la URL); al final colapsa el grupo. |
| `_apply_seniorities` | Expande el grupo `contactSeniority-filter`; recorre los checkboxes `checkbox-contactSeniority-N` y hace clic en la fila cuya etiqueta normalizada (lowercase, ignorando el conteo de población y el title-case, p.ej. "C-Suite 2.6K") coincide. Valida contra `KNOWN_SENIORITIES`. **Cada selección dispara la búsqueda automáticamente**; al final colapsa el grupo. |
| `_apply_countries` | Expande el grupo `contactLocation-filter`; por cada país escribe en `contactLocation-filter-input`, espera el filtrado del dropdown y hace clic en la opción `contactLocation-option-N` cuyo texto exacto coincide (sin validación: texto libre). Cada país seleccionado dispara la búsqueda automáticamente; al final colapsa con Escape (el botón "Apply" del pie solo aplica la sección ZIP/rango). |
| `_expand_filter` / `_collapse_filter` | Helpers compartidos: expanden/colapsan un grupo acordeón de filtro. |
| `_wait_for_results` | Espera hasta ~25s a que aparezcan filas `[data-test-id^="contacts-table-contact-name-"]`, con sleeps cada `RESULT_WAIT_SECONDS`. |
| `_extract_results` | Por fila: nombre (primera línea del texto), cargo (`job-title-N`), URL de LinkedIn (`a[href*="linkedin.com/in/"]`). Salta filas sin nombre ni URL. |
| `_has_next` / `_goto_next_page` | Detecta `pagination-next-page` deshabilitado (`disabled`/`aria-disabled`) y hace clic. |
| `_check_interruptions` | Redirección a `auth.lusha.com`/login → `LoginRequiredError`; captcha/challenge → `CaptchaError`. Se comprueba en el `goto` inicial, al inicio de `_search`, `_apply_departments`, `_apply_seniorities`, `_goto_next_page` y **tras** cualquier excepción de esas acciones (un redirect tardío también se detecta). |
| `_login` | Carga el dashboard; si está en `auth.lusha.com`, espera login manual del usuario (polling cada `LOGIN_POLL_SECONDS`). Guarda `storage_state`. |
| `_open` | Chromium visible, mismo anti-detección que LinkedIn: UA Chrome/151, `--disable-blink-features=AutomationControlled`, `--disable-infobars`, `ignore_default_args=["--enable-automation"]`, locale `es-ES`, timezone `America/Mexico_City`, init script `navigator.webdriver=undefined`. |
| `_human_delay(lo, hi)` | `random.uniform(lo, hi)`; se usa `PAGE_DELAY_MIN/MAX` entre páginas. |

### Selectores verificados en vivo (2026)

- `SEARCH_INPUT` / fallback `input.peer`: buscador de contactos.
- `RESULT_ROW`: `[data-test-id^="contacts-table-contact-name-"]` — 25 por página.
- `JOB_TITLE`: `[data-test-id^="job-title-"]`.
- `LINKEDIN_LINK`: `a[href*="linkedin.com/in/"]` dentro de la fila.
- `NEXT_PAGE` / `PREV_PAGE`: `[data-test-id="pagination-next-page"]` etc.
- `DEPARTMENT_FILTER` / `DEPARTMENT_INPUT`:
  `[data-test-id="contactDepartment-filter"]` (grupo acordeón) y
  `[data-test-id="contactDepartment-filter-input"]` (input "Enter departments").
  Al expandirse muestra todos los departamentos como chips; escribir filtra y el
  clic selecciona (multi-select, incluye toggle "Include/Exclude").
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
  `datalist` de niveles, `max_pages` (1–50) con opción "Recorrer todas las
  páginas". Botón **Buscar contactos**.
- `app.js` envía `filters.departments` y `filters.seniorities` como listas (se
  separan por `,` o saltos de línea).
- Banner de sesión (login manual vía `POST /api/login`), tarjeta de progreso con
  barra indeterminada en modo "todas las páginas", tabla de vista previa
  (`PREVIEW_LIMIT=60`), botón **Descargar Excel**.
- Polling de autenticación y del job cada 1.5s.

## Flujo de una búsqueda

1. Usuario abre la app; si no hay sesión, inicia sesión en la ventana automatizada
   (guardada en `data/storage_state.json`).
2. Rellena empresa (opcional: departamentos y/o seniority) y páginas →
   `POST /api/search` → `{job_id}`.
3. `_run_job` ejecuta `scraper.scrape()`: página 1 busca la empresa y luego aplica
   los departamentos (`_apply_departments`) y seniorities (`_apply_seniorities`);
   siguientes páginas usan `pagination-next-page`. Cada página llama a `progress`,
   acumulando resultados deduplicados.
4. Al terminar, `export_to_excel` genera `contactos_<empresa>_*.xlsx` y el job
   queda `done`.
5. El botón **Descargar Excel** apunta a `GET /api/jobs/<id>/download`.

## Notas

- `data/storage_state.json` no se versiona (`.gitignore`). El scraper refresca la
  sesión guardada al terminar cada búsqueda (cookies rotadas por Lusha).
- Si Lusha redirige a `auth.lusha.com` en mitad de una operación, se lanza
  `LoginRequiredError` (el job pasa a `needs_login` con banner de sesión), no un
  error genérico de Playwright.
- Jobs volátiles en memoria.
- Retiro de búsquedas de Lusha a alto volumen: los delays conservadores y
  `ALL_PAGES_SAFETY_LIMIT` ayudan a evitarlo.
- Legal: scraping del dashboard puede violar los ToS de Lusha; uso personal y
  bajo volumen.