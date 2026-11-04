@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ChatGPT (OpenAI Codex) OAuth login for the portable bundle.
rem Browser login is the default. Use --device-code for headless/remote setups.
rem This script only stores credentials; it does not change provider or model settings.

set "ROOT=%~dp0"
set "AUTH_MODE=--browser"

if /i "%~1"=="--device-code" set "AUTH_MODE="

echo [portable] Starting ChatGPT OAuth login...
echo [portable] A browser window will open for OpenAI authorization.
echo [portable] Keep this window open until the browser confirms completion.
echo [portable] If the browser cannot reach localhost:1455, press Ctrl+C and rerun:
echo     .\chatgpt-login.cmd --device-code
echo.

call "%ROOT%hermes.cmd" auth add openai-codex --type oauth %AUTH_MODE% --timeout 180
if errorlevel 1 goto failed

echo.
echo [portable] ChatGPT OAuth login complete.
echo [portable] Credentials were saved; current provider/model settings were not changed.
echo [portable] To choose a GPT model, run:
echo     .\choose-model.cmd
echo     (or .\hermes.cmd model)
echo.
echo [portable] To check login state, run:
echo     .\hermes.cmd auth status openai-codex
echo.
pause
exit /b 0

:failed
echo.
echo [portable] ChatGPT OAuth login failed.
echo [portable] Check your network access to auth.openai.com and chatgpt.com.
echo [portable] If the browser callback cannot complete, retry with:
echo     .\chatgpt-login.cmd --device-code
echo.
pause
exit /b 1
