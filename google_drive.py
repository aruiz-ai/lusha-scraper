"""Subida de los excels generados a Google Drive mediante cuenta de servicio.

Requiere:
- `config.DRIVE_CREDENTIALS_PATH`: clave JSON de la cuenta de servicio
  (Google Cloud Console -> APIs y servicios -> Credenciales -> Cuentas de servicio).
- La carpeta destino (`config.DRIVE_FOLDER_ID`) compartida con el correo de la
  cuenta de servicio (rol Editor).
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

SCOPES = ["https://www.googleapis.com/auth/drive"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DriveError(Exception):
    pass


def _credentials():
    path = config.DRIVE_CREDENTIALS_PATH
    if not os.path.exists(path):
        raise DriveError(
            f"No se encontraron las credenciales de Google Drive en {path}. "
            "Descarga la clave JSON de la cuenta de servicio y guárdala ahí."
        )
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    creds.refresh(Request())
    return creds


def _service():
    try:
        return build("drive", "v3", credentials=_credentials(), cache_discovery=False)
    except DriveError:
        raise
    except Exception as error:
        raise DriveError(f"No se pudo autenticar con Google Drive: {error}") from error


def upload_xlsx(filepath, filename):
    """Sube el Excel a la carpeta de Drive configurada.

    Devuelve una tupla `(file_id, web_view_link)`. Si `DRIVE_PUBLIC_LINKS`
    está activo, comparte el archivo como "cualquier persona con el enlace".
    """
    service = _service()

    body = {"name": filename, "mimeType": XLSX_MIME}
    if config.DRIVE_FOLDER_ID:
        body["parents"] = [config.DRIVE_FOLDER_ID]

    try:
        media = MediaFileUpload(filepath, mimetype=XLSX_MIME)
        uploaded = service.files().create(
            body=body, media_body=media, fields="id"
        ).execute()
        file_id = uploaded["id"]
    except Exception as error:
        raise DriveError(f"No se pudo subir el archivo a Google Drive: {error}") from error

    if config.DRIVE_PUBLIC_LINKS:
        try:
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception as error:
            raise DriveError(
                f"El archivo se subió pero no se pudo hacer el enlace público: {error}"
            ) from error

    try:
        meta = service.files().get(
            fileId=file_id, fields="id,webViewLink"
        ).execute()
    except Exception:
        meta = {"id": file_id, "webViewLink": None}

    return file_id, meta.get("webViewLink")