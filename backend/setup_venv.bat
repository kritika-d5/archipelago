@echo off
setlocal
cd /d "%~dp0"

echo [Archipelago] Backend venv setup (isolated from global Python)
echo.

if not exist "venv\Scripts\python.exe" (
  echo Creating venv in %~dp0venv ...
  python -m venv venv
  if errorlevel 1 (
    echo ERROR: python -m venv failed. Install Python 3.11+ and try again.
    exit /b 1
  )
) else (
  echo venv already exists.
)

set "PY=%~dp0venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
  echo ERROR: pip install failed.
  exit /b 1
)

echo.
echo Done. Run the backend with:
echo   venv\Scripts\python.exe -m uvicorn app.main:app --reload
echo Or use start_all.bat from the repo root.
endlocal
