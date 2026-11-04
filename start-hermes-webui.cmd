@echo off
setlocal
set "ROOT=%~dp0"
set "WEBUI=%ROOT%hermes-webui"
set "AGENT=%ROOT%hermes-agent"
set "RUNTIME_FILE=%ROOT%var\runtime-python.txt"

if not exist "%RUNTIME_FILE%" (
  echo [portable] Runtime configuration missing. Run setup.cmd first.
  exit /b 1
)
set /p PY=<"%RUNTIME_FILE%"

rem Process environment wins over the optional portable .env file.
if exist "%ROOT%.env" for /f "usebackq eol=# tokens=1,* delims==" %%k in ("%ROOT%.env") do if not defined %%k set "%%k=%%l"

if not defined HERMES_HOME set "HERMES_HOME=%USERPROFILE%\.hermes"
if not defined HERMES_WEBUI_STATE_DIR set "HERMES_WEBUI_STATE_DIR=%HERMES_HOME%\webui"
if not defined HERMES_WEBUI_AGENT_DIR set "HERMES_WEBUI_AGENT_DIR=%AGENT%"
if not defined HERMES_WEBUI_DEFAULT_WORKSPACE set "HERMES_WEBUI_DEFAULT_WORKSPACE=%ROOT%workspace"
if not defined HERMES_WEBUI_PYTHON set "HERMES_WEBUI_PYTHON=%PY%"
if not defined HERMES_WEBUI_HOST set "HERMES_WEBUI_HOST=127.0.0.1"
if not defined HERMES_WEBUI_PORT set "HERMES_WEBUI_PORT=8787"
if not defined HERMES_WEBUI_YAML_MINI set "HERMES_WEBUI_YAML_MINI=1"

if not exist "%PY%" (
  echo [portable] Runtime missing: "%PY%"
  echo [portable] Run setup.cmd first.
  exit /b 1
)
if not exist "%WEBUI%\server.py" (
  echo [portable] WebUI submodule is missing. Run setup.cmd first.
  exit /b 1
)
if not exist "%AGENT%\cli.py" (
  echo [portable] Agent submodule is missing. Run setup.cmd first.
  exit /b 1
)

if not exist "%HERMES_WEBUI_STATE_DIR%" mkdir "%HERMES_WEBUI_STATE_DIR%"
if not exist "%HERMES_WEBUI_DEFAULT_WORKSPACE%" mkdir "%HERMES_WEBUI_DEFAULT_WORKSPACE%"

echo [portable] home      : %HERMES_HOME%
echo [portable] state     : %HERMES_WEBUI_STATE_DIR%
echo [portable] agent     : %HERMES_WEBUI_AGENT_DIR%
echo [portable] python    : %PY%
echo [portable] workspace : %HERMES_WEBUI_DEFAULT_WORKSPACE%
echo [portable] url       : http://%HERMES_WEBUI_HOST%:%HERMES_WEBUI_PORT%
echo [portable] Ctrl-C stops the server.
echo.

cd /d "%WEBUI%"
"%PY%" server.py
exit /b %ERRORLEVEL%
