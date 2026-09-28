@echo off
setlocal
cd /d "%~dp0"
echo Book3D Studio - Windows setup
python --version
if errorlevel 1 (
  echo Python was not found on PATH.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating isolated environment...
  python -m venv .venv
  if errorlevel 1 goto :fail
)

echo Updating pip...
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

echo Installing Book3D Studio dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Setup complete.
echo Run start_windows.bat to launch Book3D Studio.
pause
exit /b 0

:fail
echo.
echo Setup failed. Copy the error shown above and send it to ChatGPT.
pause
exit /b 1
