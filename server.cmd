@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Run Hermes WebUI in the current terminal. Press Ctrl-C to stop it.
call "%~dp0run-webui.cmd" -Foreground %*
exit /b %ERRORLEVEL%
