@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Run setup_venv.bat first.
  pause
  exit /b 1
)
"%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --reload
