@echo off
REM TopicPilot-CN OneTopic MVP - stop backend (18181) and frontend (18182).
REM Uses taskkill /F to hard-kill any process bound to those ports.

chcp 65001 >nul
setlocal
cd /d %~dp0

set KILLED=0

call :kill_port 18181 "backend"
call :kill_port 18182 "frontend"

echo.
if %KILLED%==0 (
  echo [OK] no process to kill, ports are free
) else (
  echo [OK] killed %KILLED% process(es)
)
echo [*] Run start_all.bat to bring services back.

endlocal
exit /b 0

:kill_port
set "PORT=%~1"
set "NAME=%~2"
echo [*] Killing process on %PORT% (%NAME%)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  if not "%%P"=="" if not "%%P"=="0" (
    echo    kill PID %%P
    taskkill /F /PID %%P >nul 2>&1
    if not errorlevel 1 set /a KILLED+=1
  )
)
exit /b 0
