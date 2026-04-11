@echo off
setlocal
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "PY=%BACKEND%\venv\Scripts\python.exe"

if not exist "%PY%" (
  echo No backend venv found. Running backend\setup_venv.bat ...
  call "%BACKEND%\setup_venv.bat"
  if errorlevel 1 exit /b 1
)

if not exist "%PY%" (
  echo ERROR: venv python missing: %PY%
  exit /b 1
)

echo Starting Backend ^(venv only — not global Python^)...
start "Archipelago Backend" /D "%BACKEND%" cmd /k run_dev.bat

timeout /t 3 /nobreak >nul

echo Starting Frontend...
start "Archipelago Frontend" /D "%ROOT%frontend" cmd /k npm start

echo All services starting...
endlocal
