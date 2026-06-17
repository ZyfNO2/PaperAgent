@echo off
REM TopicPilot-CN OneTopic MVP - run full pytest suite.
REM Kills leftover, starts backend + frontend, runs pytest, leaves services up.
REM Run stop_all.bat to shut down.

chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo [X] .venv\Scripts\python.exe not found. Run 'uv sync' first.
  exit /b 1
)

set PYTHONIOENCODING=utf-8

REM step 1: kill leftover
call stop_all.bat >nul
timeout /t 1 /nobreak >nul

REM step 2: start backend
start "TopicPilot-CN Backend (18181)" cmd /k ^
  "set PYTHONIOENCODING=utf-8 && .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps\api --host 127.0.0.1 --port 18181 --log-level warning"

REM step 3: start frontend
start "TopicPilot-CN Frontend (18182)" cmd /k ^
  "set PYTHONIOENCODING=utf-8 && .venv\Scripts\python.exe apps\web\dev_server.py"

REM step 4: wait for backend
echo [*] waiting for backend 18181...
set /a waited=0
:wait_backend_loop
netstat -an | findstr ":18181 " | findstr "LISTENING" >nul
if not errorlevel 1 goto backend_ready
if !waited! geq 20 (
  echo [X] backend not ready in 20s, check the popup window
  exit /b 1
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_backend_loop
:backend_ready

REM step 5: wait for frontend
echo [*] waiting for frontend 18182...
set /a waited=0
:wait_frontend_loop
netstat -an | findstr ":18182 " | findstr "LISTENING" >nul
if not errorlevel 1 goto frontend_ready
if !waited! geq 15 (
  echo [X] frontend not ready in 15s, check the popup window
  exit /b 1
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_frontend_loop
:frontend_ready

echo.
echo ============================================
echo  backend:  http://127.0.0.1:18181
echo  frontend: http://127.0.0.1:18182
echo ============================================
echo.

REM step 6: run pytest
echo [*] running pytest...
.venv\Scripts\python.exe -m pytest -v
set EXITCODE=%errorlevel%

echo.
if %EXITCODE%==0 (
  echo [OK] pytest all green
) else (
  echo [X] pytest failed, exit code %EXITCODE%
)
echo.
echo [*] services still running, run stop_all.bat to shut them down

endlocal & exit /b %EXITCODE%
