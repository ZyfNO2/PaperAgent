@echo off
REM TopicPilot-CN 一键跑全量测试 (pytest)
REM 不需要服务在跑, pytest 自己管理 fixture.

setlocal
cd /d %~dp0
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -m pytest -v
endlocal
