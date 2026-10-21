@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
.venv\Scripts\python.exe -c "import flask, requests" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
if not defined MOCK_MODE set "MOCK_MODE=1"
.venv\Scripts\python.exe app.py
goto :eof
:error
echo Setup failed. Ensure Python 3.10+ and internet access for the initial dependency install.
exit /b 1
