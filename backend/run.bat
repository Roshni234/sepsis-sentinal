@echo off
REM Sepsis Sentinel Backend startup script for Windows

echo Activating Python virtual environment...
if exist venv (
    call venv\Scripts\activate.bat
) else (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting Sepsis Sentinel API...
echo Server will be available at http://localhost:8000
echo Interactive docs at http://localhost:8000/docs
echo.

uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
