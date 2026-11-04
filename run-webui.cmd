@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ROOT=%~dp0"
set "RUNTIME_FILE=%ROOT%var\runtime-python.txt"
if not exist "%RUNTIME_FILE%" (
  echo [portable] Runtime configuration missing. Run setup.cmd first.
  exit /b 1
)
set /p PYTHON=<"%RUNTIME_FILE%"
set "HERMES_WEBUI_PYTHON=%PYTHON%"

if not exist "%PYTHON%" (
  echo [portable] Runtime missing: "%PYTHON%"
  echo [portable] Run setup.cmd first.
  exit /b 1
)

"%PYTHON%" "%ROOT%scripts\webui_process.py" %*
exit /b %ERRORLEVEL%
