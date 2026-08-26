import os
import sys


def _base_dir():
    # En el ejecutable (PyInstaller) __file__ apunta al dir temporal de
    # extraccion (_MEIPASS), que se borra al cerrar. Los datos y navegadores
    # deben vivir al lado del .exe para persistir entre ejecuciones.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
STORAGE_STATE_PATH = os.path.join(DATA_DIR, "storage_state.json")

# En el exe los navegadores de Playwright viven al lado del ejecutable
# (se descargan en la primera ejecución); en desarrollo se usa la instalación
# normal de `playwright install chromium`.
if getattr(sys, "frozen", False):
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE_DIR, "ms-playwright")
    )
BROWSERS_DIR = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or os.path.join(
    BASE_DIR, "ms-playwright"
)

LUSHA_DASHBOARD_URL = "https://dashboard.lusha.com"
LUSHA_PROSPECTING_URL = "https://dashboard.lusha.com/prospecting/contacts"

DEFAULT_MAX_PAGES = 10
MAX_PAGES_LIMIT = 50
ALL_PAGES_SAFETY_LIMIT = 200
LOGIN_TIMEOUT_SECONDS = 15 * 60

# Subida a Google Drive (cuenta de servicio). Credenciales en formato JSON
# descargadas desde Google Cloud Console; si `DRIVE_FOLDER_ID` está vacío se
# sube a la raíz de la carpeta compartida con la cuenta de servicio.
DRIVE_CREDENTIALS_PATH = os.path.join(DATA_DIR, "service-account.json")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1465JOKCpFGc0DG73ws3lRo131MxEcVzM")
DRIVE_PUBLIC_LINKS = True

# Delays conservadores (Lusha es sensible al volumen).
PAGE_DELAY_MIN = 15.0
PAGE_DELAY_MAX = 25.0
SCROLL_DELAY_MIN = 1.5
SCROLL_DELAY_MAX = 3.0
SCROLL_STEP = 300
SCROLL_STEP_DELAY = 150
RESULT_WAIT_SECONDS = 4
LOGIN_POLL_SECONDS = 2

try:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)
except OSError:
    # En el exe se valida la escritura antes de arrancar (bootstrap) y se
    # informa al usuario; aquí el fallo no debe tumbar el arranque.
    pass