@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
pip install composio
echo.
echo Done. Restart your backend server.
