@echo off
REM TopicPilot-CN OneTopic MVP - start backend (18181) + frontend (18182).
REM Kills anything on those ports first, then brings both up.
REM Close the two popup windows to stop, or run stop_all.bat to hard-kill.

chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo [X] .venv\Scripts\python.exe not found. Run 'uv sync' first.
  pause
  exit /b 1
)

set PYTHONIOENCODING=utf-8

REM step 1: kill any leftover on 18181 / 18182
call stop_all.bat >nul
timeout /t 1 /nobreak >nul

REM step 2: start backend (uvicorn on 18181) in a popup window
start "TopicPilot-CN Backend (18181)" cmd /k ^
  "set PYTHONIOENCODING=utf-8 && .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps\api --host 127.0.0.1 --port 18181 --log-level info"

REM step 3: start frontend (static file server on 18182) in a popup window
start "TopicPilot-CN Frontend (18182)" cmd /k ^
  "set PYTHONIOENCODING=utf-8 && .venv\Scripts\python.exe apps\web\dev_server.py"

REM step 4: wait for backend port
echo [*] waiting for backend 18181...
set /a waited=0
:wait_backend_loop
netstat -an | findstr ":18181 " | findstr "LISTENING" >nul
if not errorlevel 1 goto backend_ready
if !waited! geq 20 (
  echo [X] backend not ready in 20s, check the popup window
  goto frontend_ok
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_backend_loop
:backend_ready

REM step 5: wait for frontend port
echo [*] waiting for frontend 18182...
set /a waited=0
:wait_frontend_loop
netstat -an | findstr ":18182 " | findstr "LISTENING" >nul
if not errorlevel 1 goto frontend_ready
if !waited! geq 15 (
  echo [X] frontend not ready in 15s, check the popup window
  goto frontend_ok
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_frontend_loop
:frontend_ready
:frontend_ok

echo.
echo ============================================
echo  [OK] backend:  http://127.0.0.1:18181
echo  [OK] frontend: http://127.0.0.1:18182
echo  [*] browser is not opened automatically
echo  [*] open the frontend URL yourself when needed
echo  [*] close the two popup windows to stop
echo  [*] or run stop_all.bat to hard-kill
echo ============================================

endlocal
exit /b 0
