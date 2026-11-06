@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Keep the window open when the script was launched by double-click.
rem Set HERMES_START_NO_PAUSE=1 to skip the wait in automation.
set "PAUSE_AT_END=0"
echo(%cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "%~nx0" >nul
if not errorlevel 1 set "PAUSE_AT_END=1"
if defined HERMES_START_NO_PAUSE set "PAUSE_AT_END=0"

rem Start Hermes WebUI in the background. If an instance is already running,
rem this script reports it and exits without starting a second one.
call "%~dp0run-webui.cmd" -Start %*
set "START_RESULT=%ERRORLEVEL%"
if not "%START_RESULT%"=="0" (
  if "%PAUSE_AT_END%"=="1" (
    echo.
    echo [portable] Startup failed. Press any key to close this window.
    pause >nul
  )
  exit /b %START_RESULT%
)

set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" (
  start "" "%CHROME%" --app=http://localhost:8787/
) else (
  echo [portable] Google Chrome not found: "%CHROME%"
  echo [portable] Open http://localhost:8787/ in your browser.
)

if "%PAUSE_AT_END%"=="1" (
  echo.
  echo [portable] Server is running in the background. Press any key to close this window.
  pause >nul
)
exit /b 0
