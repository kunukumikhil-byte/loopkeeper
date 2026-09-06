@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher was not found.
    echo Install Python 3.11 from python.org and make sure Python is added to PATH.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Creating Python 3.11 virtual environment...
    py -3.11 -m venv venv
    if errorlevel 1 (
        echo Could not create the Python 3.11 environment.
        pause
        exit /b 1
    )
)

call "venv\Scripts\activate.bat"

echo Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Starting LoopKeeper...
echo Open http://127.0.0.1:8000
REM No --reload here: this prevents WatchFiles from restarting when pip/venv files change.
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
