@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Book3D Studio is not installed yet.
  echo Run install_windows.bat first.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8787
.venv\Scripts\python.exe run.py
pause
