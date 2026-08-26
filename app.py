import os
import threading

from flask import Flask, jsonify, render_template, request, send_file

import config
from excel_writer import export_to_excel
from google_drive import DriveError, upload_xlsx
from jobs import JobManager
from scraper.lusha import LoginRequiredError, LushaScraper, ScraperError

app = Flask(__name__)
jobs = JobManager()
scraper = LushaScraper()
_server = None


@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response

_lock = threading.Lock()
LOGIN_STATE = {"running": False, "last_result": None}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/auth/status")
def auth_status():
    return jsonify(
        {
            "logged_in": os.path.exists(config.STORAGE_STATE_PATH),
            "login_running": LOGIN_STATE["running"],
            "last_result": LOGIN_STATE["last_result"],
        }
    )


@app.post("/api/login")
def api_login():
    with _lock:
        if LOGIN_STATE["running"]:
            return jsonify({"ok": True, "running": True})
        LOGIN_STATE["running"] = True
        LOGIN_STATE["last_result"] = None
    threading.Thread(target=_run_login, daemon=True).start()
    return jsonify({"ok": True, "running": True})


def _run_login():
    try:
        result = scraper.login()
        LOGIN_STATE["last_result"] = {"ok": True, "result": result}
    except Exception as error:
        LOGIN_STATE["last_result"] = {"ok": False, "error": str(error)}
    finally:
        LOGIN_STATE["running"] = False


def _normalize_list(value):
    if isinstance(value, str):
        return [
            part.strip()
            for part in value.replace("\n", ",").split(",")
            if part.strip()
        ]
    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]
    return []


@app.post("/api/search")
def api_search():
    data = request.get_json(silent=True) or {}
    company = (data.get("company") or "").strip()
    if not company:
        return jsonify({"error": "El nombre de la empresa es obligatorio."}), 400

    all_pages = bool(data.get("all_pages"))
    if all_pages:
        max_pages = 0
    else:
        try:
            max_pages = int(data.get("max_pages") or config.DEFAULT_MAX_PAGES)
        except (TypeError, ValueError):
            max_pages = config.DEFAULT_MAX_PAGES
        max_pages = max(1, min(max_pages, config.MAX_PAGES_LIMIT))

    filters = data.get("filters") or {}
    departments = _normalize_list(filters.get("departments"))
    seniorities = _normalize_list(filters.get("seniorities"))
    countries = _normalize_list(filters.get("countries"))

    if not os.path.exists(config.STORAGE_STATE_PATH):
        return jsonify({"error": "Necesitas iniciar sesión en Lusha primero."}), 401

    job = jobs.create(
        company,
        max_pages,
        all_pages=all_pages,
        departments=departments,
        seniorities=seniorities,
        countries=countries,
    )
    threading.Thread(
        target=_run_job,
        kwargs={
            "company": company,
            "max_pages": max_pages,
            "all_pages": all_pages,
            "departments": departments,
            "seniorities": seniorities,
            "countries": countries,
            "job_id": job["id"],
        },
        daemon=True,
    ).start()
    return jsonify({"job_id": job["id"]})


def _run_job(company, max_pages, all_pages, departments, seniorities, countries, job_id):
    jobs.update(job_id, status="running", message="Iniciando búsqueda en Lusha...")

    def progress(page_no, found, results):
        message = (
            f"Página {page_no} procesada"
            if all_pages
            else f"Página {page_no} de {max_pages} procesada"
        )
        jobs.update(
            job_id,
            current_page=page_no,
            message=message,
        )
        jobs.append_results(job_id, results)

    try:
        rows = scraper.scrape(
            company=company,
            progress=progress,
            max_pages=max_pages,
            departments=departments,
            seniorities=seniorities,
            countries=countries,
        )
        jobs.append_results(job_id, rows)
        if not rows:
            jobs.update(job_id, status="done", message="No se encontraron contactos.")
            return
        filepath, filename = export_to_excel(rows, company=company)
        message = f"Scraping completado. {len(rows)} contactos encontrados."
        drive_url = None

        if os.path.exists(config.DRIVE_CREDENTIALS_PATH):
            try:
                _, drive_url = upload_xlsx(filepath, filename)
                if drive_url:
                    message += " Subido a Google Drive."
            except DriveError as error:
                message += f" Aviso: {error}"

        jobs.update(
            job_id,
            status="done",
            message=message,
            filepath=filepath,
            filename=filename,
            drive_url=drive_url,
        )
    except LoginRequiredError:
        jobs.update(
            job_id,
            status="needs_login",
            error="La sesión de Lusha caducó. Inicia sesión de nuevo.",
        )
    except ScraperError as error:
        jobs.update(job_id, status="error", error=str(error))
    except Exception as error:
        jobs.update(
            job_id, status="error", error=f"Error inesperado: {error}"
        )


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job no encontrado."}), 404
    return jsonify(job)


@app.get("/api/jobs/<job_id>/download")
def job_download(job_id):
    job = jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job no encontrado."}), 404
    if job.get("status") != "done" or not job.get("filepath"):
        return jsonify({"error": "No hay archivo disponible para descargar."}), 400
    return send_file(
        job["filepath"], as_attachment=True, download_name=job["filename"]
    )


@app.post("/api/shutdown")
def api_shutdown():
    server = _server
    if server is None:
        return jsonify({"error": "No se puede detener el servidor desde aquí."}), 400
    threading.Timer(1.0, server.shutdown).start()
    return render_template("shutdown.html")


if __name__ == "__main__":
    from werkzeug.serving import make_server

    port = int(os.environ.get("PORT", 5000))
    _server = make_server("127.0.0.1", port, app, threaded=True)
    print(f"Servidor arrancado en http://127.0.0.1:{port}")
    _server.serve_forever()