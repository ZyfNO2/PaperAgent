@echo off
chcp 65001 >nul 2>&1
title PaperAgent - Frontend Server

echo ============================================
echo   PaperAgent Frontend Quick Start
echo ============================================
echo.

:: Check .env exists
if not exist ".env" (
    echo [ERROR] .env file not found in G:\PaperAgent
    echo Please copy .env.example to .env and fill in API keys.
    pause
    exit /b 1
)

:: Kill any process on port 18181
echo [1/3] Checking port 18181...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":18181.*LISTENING" 2^>nul') do (
    echo   Killing PID %%a on port 18181...
    taskkill /F /PID %%a >nul 2>&1
)

:: Start API server
echo [2/3] Starting API server (uvicorn)...
cd /d "G:\PaperAgent\apps\api"
start "PaperAgent API" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 18181"

:: Wait for server to be ready
echo   Waiting for server...
set "ready=0"
for /l %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:18181/health >nul 2>&1
    if not errorlevel 1 (
        set "ready=1"
        echo   Server is ready!
        goto :open
    )
    echo   Still waiting... (%%i/15)
)
echo [WARNING] Server may not be ready. Trying to open browser anyway.

:open
echo [3/3] Opening browser...
timeout /t 1 /nobreak >nul
start http://127.0.0.1:18181/web/

echo.
echo ============================================
echo   PaperAgent is running!
echo.
echo   Frontend:  http://127.0.0.1:18181/web/
echo   API:       http://127.0.0.1:18181/api/v1/research/
echo   Health:    http://127.0.0.1:18181/health
echo.
echo   To stop: close the "PaperAgent API" window
echo   or run:  taskkill /F /IM python.exe
echo ============================================
echo.
echo This window can be closed.
pause
