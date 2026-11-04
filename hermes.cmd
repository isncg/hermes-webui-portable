@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Portable Hermes Agent CLI entry point.
rem Mirrors the installed ``hermes`` command without adding anything to PATH.

for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "AGENT=%ROOT%\hermes-agent"
set "RUNTIME_FILE=%ROOT%\var\runtime-python.txt"

if not exist "%RUNTIME_FILE%" (
  echo [portable] Runtime configuration missing. Run setup.cmd first.
  exit /b 1
)
set /p PY=<"%RUNTIME_FILE%"

if exist "%ROOT%.env" for /f "usebackq eol=# tokens=1,* delims==" %%k in ("%ROOT%.env") do if not defined %%k set "%%k=%%l"

if not defined HERMES_HOME set "HERMES_HOME=%USERPROFILE%\.hermes"

if not exist "%PY%" (
  echo [portable] Runtime missing: "%PY%"
  echo [portable] Run setup.cmd first.
  exit /b 1
)
if not exist "%AGENT%\hermes_cli\main.py" (
  echo [portable] Agent submodule is missing. Run setup.cmd first.
  exit /b 1
)

rem Prefer the pinned source tree while keeping the caller's working directory.
set "PYTHONPATH=%AGENT%;%PYTHONPATH%"
"%PY%" -m hermes_cli.main %*
exit /b %ERRORLEVEL%

