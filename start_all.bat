@echo off
echo Starting Backend...
start cmd /k "cd backend && venv\Scripts\activate && uvicorn app.main:app --reload"

timeout /t 3

echo Starting Frontend...
start cmd /k "cd frontend && npm start"

echo All services starting...