@echo off
REM Smoke test for TopicPilot-CN Phase 01 API.
REM Usage: scripts\smoke.bat [BASE_URL]

set BASE=%~1
if "%BASE%"=="" set BASE=http://127.0.0.1:18181

set REPO=%~dp0..
set PH=%REPO%\tmp\smoke_placeholder.json
set FU=%REPO%\tmp\smoke_complete.json

echo === 1) GET %BASE%/health ===
curl -s -w "  [HTTP %%{http_code}]" %BASE%/health
echo.

echo.
echo === 2) POST %BASE%/api/v1/projects (placeholder, expects D) ===
for /f "delims=" %%R in ('curl -s -X POST %BASE%/api/v1/projects -H "Content-Type: application/json" --data-binary "@%PH%"') do (
  set RESP=%%R
)
echo %RESP%
for /f "tokens=2 delims=:," %%A in ('echo %RESP% ^| findstr /R "id"') do set PID=%%A
echo  - placeholder id = %PID%
echo.

echo === 3) GET %BASE%/api/v1/projects/%PID%
curl -s -w "  [HTTP %%{http_code}]" %BASE%/api/v1/projects/%PID%
echo.

echo.
echo === 4) POST validate (placeholder - expect BLOCKED) ===
curl -s -w "  [HTTP %%{http_code}]" -X POST %BASE%/api/v1/projects/%PID%/intake/validate
echo.

echo.
echo === 5) POST %BASE%/api/v1/projects (complete, expects A) ===
for /f "delims=" %%R in ('curl -s -X POST %BASE%/api/v1/projects -H "Content-Type: application/json" --data-binary "@%FU%"') do (
  set RESP=%%R
)
echo %RESP%
for /f "tokens=2 delims=:," %%A in ('echo %RESP% ^| findstr /R "id"') do set FID=%%A
echo  - complete id = %FID%
echo.

echo === 6) GET %BASE%/api/v1/projects/%FID%
curl -s -w "  [HTTP %%{http_code}]" %BASE%/api/v1/projects/%FID%
echo.

echo.
echo === 7) POST validate (complete - expect OK) ===
curl -s -w "  [HTTP %%{http_code}]" -X POST %BASE%/api/v1/projects/%FID%/intake/validate
echo.

echo.
echo === 8) Negative: duplicate case_id (expect 409) ===
curl -s -w "  [HTTP %%{http_code}]" -X POST %BASE%/api/v1/projects -H "Content-Type: application/json" --data-binary "@%FU%"
echo.

echo === 9) Negative: missing project (expect 404) ===
curl -s -w "  [HTTP %%{http_code}]" %BASE%/api/v1/projects/99999
echo.
