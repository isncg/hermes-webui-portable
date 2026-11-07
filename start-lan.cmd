@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Keep the window open on failure when launched by double-click.
rem Set HERMES_START_NO_PAUSE=1 to skip the wait in automation.
set "PAUSE_AT_END=0"
echo(%cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "%~nx0" >nul
if not errorlevel 1 set "PAUSE_AT_END=1"
if defined HERMES_START_NO_PAUSE set "PAUSE_AT_END=0"

rem Run the WebUI in the current terminal and bind all interfaces.
rem The launcher prompts for a password when HERMES_WEBUI_PASSWORD is unset.
call "%~dp0run-webui.cmd" -Foreground -BindHost 0.0.0.0 -Port 7878 -RequirePassword %*
set "START_RESULT=%ERRORLEVEL%"
if "%START_RESULT%"=="130" exit /b 0
if not "%START_RESULT%"=="0" (
  if "%PAUSE_AT_END%"=="1" (
    echo.
    echo [portable] LAN startup failed. Press any key to close this window.
    pause >nul
  )
  exit /b %START_RESULT%
)
exit /b 0
