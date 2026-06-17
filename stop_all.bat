@echo off
REM TopicPilot-CN 一键停止前后端 (占用 18181 / 18182 端口的进程)
REM 双击或 cmd 跑, 强杀会丢未保存的 uvicorn 日志 (无副作用)

setlocal
echo [*] 关闭占用 18181 (uvicorn) 的进程...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":18181" ^| findstr "LISTENING"') do (
  echo    kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo [*] 关闭占用 18182 (dev_server) 的进程...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":18182" ^| findstr "LISTENING"') do (
  echo    kill PID %%P
  taskkill /F /PID %%P >nul 2>&1
)

echo [OK] 端口已释放.
endlocal
