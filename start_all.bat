@echo off
REM TopicPilot-CN 一键启动前后端 (开发环境, Windows 11 + git-bash 兼容)
REM 后端: uvicorn 18181, 前端: http.server 18182
REM 双击或在 cmd / git-bash 跑都行. 关闭窗口即停服务.

setlocal

cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo [X] .venv\Scripts\python.exe 不存在. 先 uv sync 或 python -m venv .venv
  pause
  exit /b 1
)

if not exist data mkdir data
if exist data\topicpilot.db del /f /q data\topicpilot.db
echo [*] DB 已重置: data\topicpilot.db

set PYTHONIOENCODING=utf-8

start "TopicPilot-CN Backend (18181)" cmd /k ^
  ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps\api --host 127.0.0.1 --port 18181 --log-level info"

start "TopicPilot-CN Frontend (18182)" cmd /k ^
  "cd apps\web && ..\..\.venv\Scripts\python.exe dev_server.py"

echo.
echo [OK] 后端: http://127.0.0.1:18181  (docs: /docs)
echo [OK] 前端: http://127.0.0.1:18182
echo [*] 关闭两个弹出窗口即停服务. 再次启动前先关掉旧的, 否则端口被占.
echo.
endlocal
