@echo off
setlocal
title Local Chess Arena
cd /d "%~dp0"

echo ============================================
echo   LOCAL CHESS ARENA
echo ============================================

rem 1. Check Python (try the "py" launcher first, then "python")
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3.9 or newer was not found.
    echo Install it from https://www.python.org/downloads/ and tick "Add Python to PATH".
    pause
    exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.9 or newer is required.
    pause
    exit /b 1
)

rem 2. Create .venv if missing
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

rem 3. Activate .venv
call ".venv\Scripts\activate.bat"

rem 4. Install requirements (only needs the internet the first time)
if not exist ".venv\.installed" (
    echo Installing requirements...
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Installing requirements failed. Check your internet connection for this first run.
        pause
        exit /b 1
    )
    echo ok> ".venv\.installed"
)

rem 5. Initialize the SQLite database
python -c "from backend.database import init_db; init_db(); print('Database ready: data\\chess.db')"
if errorlevel 1 (
    echo [ERROR] Database initialisation failed.
    pause
    exit /b 1
)

rem 6 + 7. Open the browser shortly after the server starts, then run FastAPI
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
echo.
echo Starting server at http://127.0.0.1:8000  (close this window or press Ctrl+C to stop)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
