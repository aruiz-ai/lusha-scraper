# Lusha Contact Scraper

Herramienta web que busca contactos de una empresa en Lusha (`dashboard.lusha.com`)
y exporta **nombre, cargo y URL de LinkedIn** a Excel.

**Importante:** solo extrae lo que se ve en la lista de resultados de contactos,
**sin gastar créditos** (los créditos de Lusha son solo para revelar email/teléfono).

## Requisitos

- Python 3.10+
- Cuenta de Lusha (plan **Free** es suficiente: las búsquedas y los datos visibles
  de la lista no consumen créditos).
- `pip install -r requirements.txt` y `python -m playwright install chromium`.

## Uso

1. `python app.py` y abre `http://127.0.0.1:5000`.
2. La primera vez, pulsa **Iniciar sesión en Lusha**: se abre una ventana del
   navegador automatizado; entra con tu cuenta (correo + contraseña o SSO). La
   sesión queda guardada en `data/storage_state.json`.
3. Escribe el nombre de la empresa, opcionalmente los departamentos, niveles
   de seniority y/o países a filtrar (uno o varios, separados por coma) y el
   máximo de páginas (25 resultados por página), o marca **Recorrer todas las
   páginas disponibles**.
4. Pulsa **Buscar contactos** y al terminar usa **Descargar Excel (.xlsx)**.

Los archivos generados quedan en `data/exports/` y, si Google Drive está
configurado, se suben automáticamente a la carpeta indicada (enlace **Abrir en
Google Drive** junto al botón de descarga).

## Google Drive (opcional)

Para que los excels se guarden también en la nube:

1. En [Google Cloud Console](https://console.cloud.google.com) crea un proyecto
   y activa la **Google Drive API**.
2. En *APIs y servicios → Credenciales → Crear credenciales → Cuenta de
   servicio*: crea una cuenta de servicio, genera una **clave JSON** y guárdala
   en `data/service-account.json` (este archivo es secreto, no lo compartas).
3. En Google Drive de la cuenta de destino, crea (o usa) una carpeta y
   **compártela con el correo de la cuenta de servicio** (rol Editor). Copia el
   **ID de la carpeta** (el trozo `.../folders/<ID>` de su URL) y ponlo en
   `DRIVE_FOLDER_ID` de `config.py` (o en la variable de entorno
   `DRIVE_FOLDER_ID`).

Los enlaces se generan públicos ("cualquier persona con el enlace");
desactívalo con `DRIVE_PUBLIC_LINKS = False` en `config.py` si lo prefieres.

## Estructura

```
├── app.py               # Flask: rutas y coordinación de jobs
├── config.py            # Rutas, límites y delays (conservadores)
├── jobs.py              # Gestor de jobs en memoria (thread-safe)
├── excel_writer.py      # Generación del Excel (Nombre | Cargo | Correo | Teléfono | URL de LinkedIn)
├── google_drive.py      # Subida de los excels a Google Drive (cuenta de servicio)
├── scraper/
│   ├── lusha.py         # Lógica Playwright (login, búsqueda, filtros, extracción, paginación)
│   └── selectors.py     # Selectores del dashboard (data-test-id)
├── templates/index.html # Página web
├── static/app.js        # Lógica del frontend
└── data/
    ├── storage_state.json   # Sesión guardada de Lusha (no versionar)
    └── exports/             # Excels generados
```

## Notas

- Los selectores se resuelven por `data-test-id` (atributos estables), verificados
  en vivo: buscador `prospecting-free-text-search`, filas
  `contacts-table-contact-name-N`, cargo `job-title-N`, enlace de LinkedIn en la fila
  y paginación `pagination-next-page`.
- Delays conservadores (`3.5–6s` entre páginas) porque Lusha aplica límites de
  actividad de búsqueda con volumen alto.
- Si caduca la sesión, el proceso lo detecta (redirección a `auth.lusha.com`) y
  pide re-iniciar sesión.
- **Aviso legal:** el scraping automatizado del dashboard de Lusha puede violar sus
  términos de servicio. Uso personal y a bajo volumen.