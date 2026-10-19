@echo off
rem Starts the backend (8010) and frontend (5173) together.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python venv missing. Run: npm run setup
  exit /b 1
)
if not exist "node_modules" (
  echo Node modules missing. Run: npm run setup
  exit /b 1
)
npm run dev
