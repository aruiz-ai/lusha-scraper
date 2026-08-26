@echo off
setlocal
cd /d "%~dp0"

REM Construye LushaScraper.exe (un doble clic en dist\LushaScraper.exe).
REM Los navegadores de Playwright NO se empaquetan: se descargan en la
REM primera ejecucion al lado del exe (carpeta ms-playwright).

if not exist build-venv (
    python -m venv build-venv
    if errorlevel 1 goto :error
)

call build-venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

pyinstaller --noconfirm --clean ^
    --onefile --noconsole ^
    --name LushaScraper ^
    --collect-all playwright ^
    --collect-submodules googleapiclient ^
    --collect-data googleapiclient ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    app.py
if errorlevel 1 goto :error

echo.
echo Listo: dist\LushaScraper.exe
pause
exit /b 0

:error
echo.
echo Error durante la compilacion. Revisa el mensaje anterior.
pause
exit /b 1