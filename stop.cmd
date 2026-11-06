@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Stop the background Hermes WebUI instance started by start.cmd.
call "%~dp0run-webui.cmd" -Stop %*
exit /b %ERRORLEVEL%
