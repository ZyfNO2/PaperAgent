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

:: Kill any process on ports 18181 and 18183
echo [1/4] Checking ports 18181 and 18183...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":18181.*LISTENING" 2^>nul') do (
    echo   Killing PID %%a on port 18181...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":18183.*LISTENING" 2^>nul') do (
    echo   Killing PID %%a on port 18183...
    taskkill /F /PID %%a >nul 2>&1
)

:: Start API server
echo [2/4] Starting API server (uvicorn)...
cd /d "G:\PaperAgent\apps\api"
start "PaperAgent API" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 18181"

:: Wait for API server to be ready
echo   Waiting for API server...
set "ready=0"
for /l %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:18181/health >nul 2>&1
    if not errorlevel 1 (
        set "ready=1"
        echo   API server is ready!
        goto :start_react
    )
    echo   Still waiting... (%%i/15)
)
echo [WARNING] API server may not be ready. Continuing anyway.

:start_react
:: Start React dev server
echo [3/4] Starting React dev server (Vite)...
cd /d "G:\PaperAgent\apps\web-react"
start "PaperAgent React" cmd /k "npm run dev"

:: Wait for Vite dev server to be ready
echo   Waiting for Vite dev server...
set "vite_ready=0"
for /l %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:18183 >nul 2>&1
    if not errorlevel 1 (
        set "vite_ready=1"
        echo   Vite dev server is ready!
        goto :open
    )
    echo   Still waiting... (%%i/15)
)
echo [WARNING] Vite may not be ready. Trying to open browser anyway.

:open
echo [4/4] Opening browser...
timeout /t 1 /nobreak >nul
start http://127.0.0.1:18183/

echo.
echo ============================================
echo   PaperAgent is running!
echo.
echo   Frontend:  http://127.0.0.1:18183/
echo   API:       http://127.0.0.1:18181/api/v1/research/
echo   Health:    http://127.0.0.1:18181/health
echo.
echo   To stop: close "PaperAgent API" and "PaperAgent React" windows
echo   or run:  taskkill /F /IM python.exe ^& taskkill /F /IM node.exe
echo ============================================
echo.
echo This window can be closed.
pause
