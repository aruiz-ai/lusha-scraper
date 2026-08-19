import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
STORAGE_STATE_PATH = os.path.join(DATA_DIR, "storage_state.json")

LUSHA_DASHBOARD_URL = "https://dashboard.lusha.com"
LUSHA_PROSPECTING_URL = "https://dashboard.lusha.com/prospecting/contacts"

DEFAULT_MAX_PAGES = 10
MAX_PAGES_LIMIT = 50
ALL_PAGES_SAFETY_LIMIT = 200
LOGIN_TIMEOUT_SECONDS = 5 * 60

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

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)