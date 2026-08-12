@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run start_here.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py
pause
