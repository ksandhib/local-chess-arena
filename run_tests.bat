@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run start.bat once first to create the virtual environment.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements-dev.txt >nul 2>&1
python -m unittest discover -s tests -t . -v
pause
