"""Utilidades de arranque para el ejecutable empaquetado.

Cubre la primera ejecución (descarga de Chromium), la escritura de la carpeta
de datos, la instancia única y la apertura del navegador cuando el servidor
está listo. En desarrollo (python app.py) estas comprobaciones se omiten.
"""

import os
import re
import socket
import sys
import threading
import time

import config


def _debug(message):
    if os.environ.get("LUSHA_DEBUG"):
        try:
            with open(os.path.join(config.DATA_DIR, "boot.log"), "a") as stream:
                stream.write(
                    f"{time.strftime('%H:%M:%S')} {message}\n"
                )
        except Exception:
            pass


def single_instance(name="LushaScraper"):
    """Evita tener dos servidores a la vez (mutex global de Windows)."""
    if not getattr(sys, "frozen", False) or os.name != "nt":
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, name)
    last_error = kernel32.GetLastError()
    _debug("single_instance: mutex_error=" + str(last_error))
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        _show_error(
            "Lusha Contact Scraper ya está en ejecución.\n"
            "Cierra la otra instancia antes de abrir una nueva."
        )
        return False
    return True


def _chromium_installed():
    try:
        names = os.listdir(config.BROWSERS_DIR)
    except OSError:
        return False
    return any(re.fullmatch(r"chromium-\d+", name) for name in names)


def _probe_writable(paths):
    for path in paths:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as error:
            return f"{path} ({error})"
    for path in paths:
        probe = os.path.join(path, ".write_test")
        try:
            with open(probe, "w") as stream:
                stream.write("ok")
            os.remove(probe)
        except OSError as error:
            return f"{path} ({error})"
    return None


def _show_error(message):
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Lusha Contact Scraper", message)
    root.destroy()


def ensure_runnable():
    """Comprueba las condiciones mínimas y muestra los avisos necesarios.

    En desarrollo devuelve True siempre.
    """
    _debug("ensure_runnable: frozen=" + str(getattr(sys, "frozen", False)))
    if not getattr(sys, "frozen", False):
        _debug("ensure_runnable: modo desarrollo, ok")
        return True

    error = _probe_writable([config.DATA_DIR, config.EXPORTS_DIR])
    _debug("ensure_runnable: writable_err=" + repr(error))
    if error:
        _show_error(
            "No se pudo escribir en:\n"
            + error
            + "\n\nMueve el ejecutable a una carpeta con permisos de escritura "
            "(por ejemplo Escritorio, Documentos o una unidad D:) y vuelve a "
            "ejecutarlo."
        )
        return False

    _debug("ensure_runnable: chromium_installed=" + str(_chromium_installed()))
    if _chromium_installed():
        return True

    _debug("ensure_runnable: mostrando instalador de Chromium")
    if _show_browser_install():
        _debug("ensure_runnable: Chromium instalado correctamente")
        return True

    _debug("ensure_runnable: fallo al instalar Chromium")
    _show_error(
        "No se pudo instalar el navegador Chromium de Playwright.\n\n"
        "Revisa la conexión a internet (la descarga es de unos 160 MB) e "
        "inténtalo de nuevo."
    )
    return False


def _show_browser_install():
    """Ventana de progreso mientras se descarga Chromium (solo en el exe)."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Lusha Contact Scraper")
    root.resizable(False, False)
    tk.Label(root, text="Primera ejecución: instalando Chromium...").pack(
        padx=24, pady=(20, 8)
    )
    bar = ttk.Progressbar(root, mode="indeterminate", length=300)
    bar.pack(padx=24, pady=(0, 8))
    tk.Label(
        root,
        text="Se descargan unos 160 MB; puede tardar unos minutos.",
        fg="#555555",
    ).pack(padx=24, pady=(0, 20))
    bar.start(12)

    result = {"ok": False}

    def _finish(ok):
        _debug("browser_install finish: ok=" + str(ok))
        result["ok"] = ok
        root.destroy()

    def _run():
        try:
            from playwright.__main__ import main
        except ImportError as error:
            _debug("browser_install import fail: " + repr(error))
            root.after(0, lambda: _finish(False))
            return
        try:
            _debug("browser_install: llamando playwright main(...)")
            argv = list(sys.argv) if sys.argv else ["LushaScraper"]
            sys.argv = argv + ["install", "chromium"]
            main()
            _debug("browser_install: playwright main retorno sin excepción")
        except SystemExit as error:
            _debug("browser_install SystemExit: " + repr(error))
        except Exception as error:
            _debug("browser_install exception: " + repr(error))
            root.after(0, lambda: _finish(False))
            return
        root.after(0, lambda: _finish(_chromium_installed()))

    threading.Thread(target=_run, daemon=True).start()
    root.mainloop()
    return result["ok"]


def find_free_port(preferred=5000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", preferred))
        return preferred
    except OSError:
        sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def open_browser_when_ready(url):
    """Abre el navegador por defecto cuando el servidor responde."""

    def wait_and_open():
        host, port = url.split("//")[1].split("/")[0].rsplit(":", 1)
        for _ in range(120):
            try:
                with socket.create_connection((host, int(port)), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.5)
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=wait_and_open, daemon=True).start()