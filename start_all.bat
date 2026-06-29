@echo off
REM TopicPilot-CN PaperAgent - start backend (18181) + 旧前端 (18182) + React 前端 (18183).
REM Session 56 切换策略: 双前端并行, 默认打开 React (18183).
REM 旧前端保留为 legacy, 不删除 (回滚路径).
REM Close the popup windows to stop, or run stop_all.bat to hard-kill.

chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo [X] .venv\Scripts\python.exe not found. Run 'uv sync' first.
  pause
  exit /b 1
)

if not exist apps\web-react\node_modules (
  echo [!] apps\web-react\node_modules missing. Run 'npm install' under apps\web-react first.
  pause
  exit /b 1
)

set PYTHONIOENCODING=utf-8
set "LOG_DIR=.runtime\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

REM step 1: kill any leftover on 18181 / 18182 / 18183
call stop_all.bat >nul
timeout /t 1 /nobreak >nul

REM step 2: start backend (uvicorn on 18181) hidden in background
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$wd = (Resolve-Path '.').Path; $py = Join-Path $wd '.venv\\Scripts\\python.exe'; $out = Join-Path $wd '.runtime\\logs\\backend.out.log'; $err = Join-Path $wd '.runtime\\logs\\backend.err.log'; Start-Process -FilePath $py -ArgumentList '-m','uvicorn','app.main:app','--app-dir','apps\\api','--host','127.0.0.1','--port','18181','--log-level','info' -WorkingDirectory $wd -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err"

REM step 3: start 旧 frontend (legacy web on 18182) hidden in background
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$wd = (Resolve-Path '.').Path; $py = Join-Path $wd '.venv\\Scripts\\python.exe'; $out = Join-Path $wd '.runtime\\logs\\frontend.out.log'; $err = Join-Path $wd '.runtime\\logs\\frontend.err.log'; Start-Process -FilePath $py -ArgumentList 'apps\\web\\dev_server.py' -WorkingDirectory $wd -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err"

REM step 3b: start 新 React frontend (vite dev on 18183) hidden in background
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$wd = (Resolve-Path '.').Path; $out = Join-Path $wd '.runtime\\logs\\web-react.out.log'; $err = Join-Path $wd '.runtime\\logs\\web-react.err.log'; Start-Process -FilePath 'npx.cmd' -ArgumentList 'vite','--host','127.0.0.1','--port','18183' -WorkingDirectory (Join-Path $wd 'apps\web-react') -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err"

REM step 4: wait for backend port
echo [*] waiting for backend 18181...
set /a waited=0
:wait_backend_loop
netstat -an | findstr ":18181 " | findstr "LISTENING" >nul
if not errorlevel 1 goto backend_ready
if !waited! geq 20 (
  echo [X] backend not ready in 20s, check the popup window
  goto legacy_ok
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_backend_loop
:backend_ready

REM step 5: wait for 旧 frontend port
echo [*] waiting for legacy frontend 18182...
set /a waited=0
:wait_legacy_loop
netstat -an | findstr ":18182 " | findstr "LISTENING" >nul
if not errorlevel 1 goto legacy_ready
if !waited! geq 15 (
  echo [!] legacy frontend not ready in 15s, skipping
  goto react_ok
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_legacy_loop
:legacy_ready
:legacy_ok

REM step 6: wait for 新 React frontend port
echo [*] waiting for React frontend 18183...
set /a waited=0
:wait_react_loop
netstat -an | findstr ":18183 " | findstr "LISTENING" >nul
if not errorlevel 1 goto react_ready
if !waited! geq 20 (
  echo [X] React frontend not ready in 20s, check the popup window
  goto react_ok
)
ping -n 2 127.0.0.1 >nul
set /a waited+=1
goto wait_react_loop
:react_ready
:react_ok

echo.
echo ============================================
echo  [OK] backend:        http://127.0.0.1:18181
echo  [OK] legacy web:     http://127.0.0.1:18182  (apps/web, 旧前端, 备用)
echo  [OK] react web:      http://127.0.0.1:18183  (apps/web-react, 默认)
echo  [*] opening React frontend (default) in your browser...
echo  [*] logs: .runtime\logs\backend.err.log / frontend.err.log / web-react.err.log
echo  [*] or run stop_all.bat to hard-kill
echo ============================================

start "" "http://127.0.0.1:18183"

endlocal
exit /b 0
