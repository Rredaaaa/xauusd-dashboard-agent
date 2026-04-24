@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

if not exist ".\reports" mkdir ".\reports"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(\\.exe)?$' -and $_.CommandLine -like '*xauusd_agent.py*' -and $_.CommandLine -like '*--serve-dashboard*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

timeout /t 2 /nobreak >nul

start "XAUUSD Live Dashboard" /MIN cmd /c ""%PYTHON_CMD%" -B ".\xauusd_agent.py" --serve-dashboard --quiet --host 127.0.0.1 --port 8787 --live-refresh-seconds 10 --full-refresh-seconds 60 --save ".\reports\xauusd_report.md" --data-json ".\reports\xauusd_data.json" --dashboard ".\reports\xauusd_dashboard.html""
timeout /t 4 /nobreak >nul

start "" "http://127.0.0.1:8787/"
exit /b 0
