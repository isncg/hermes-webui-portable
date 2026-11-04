@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%~1"=="" (
  for %%I in ("%~dp0..") do set "ROOT=%%~fI"
) else (
  for %%I in ("%~1") do set "ROOT=%%~fI"
)

call :apply_target "hermes-webui" || exit /b 1
call :apply_target "hermes-agent" || exit /b 1
exit /b 0

:apply_target
set "TARGET_NAME=%~1"
set "TARGET_DIR=%ROOT%\%~1"
set "PATCH_DIR=%ROOT%\patches\%~1"

if not exist "%TARGET_DIR%\.git" (
  echo [patch] %TARGET_NAME% submodule directory is missing: "%TARGET_DIR%"
  exit /b 1
)
if not exist "%PATCH_DIR%" exit /b 0

for /f "usebackq delims=" %%P in (`dir /b /a-d /on "%PATCH_DIR%\*.patch" 2^>nul`) do (
  call :apply_patch "%TARGET_NAME%" "%TARGET_DIR%" "%PATCH_DIR%\%%P" "%%P" || exit /b 1
)
exit /b 0

:apply_patch
git -C "%~2" apply --check --whitespace=nowarn "%~3" >nul 2>&1
if not errorlevel 1 (
  echo [patch] applying %~1/%~4
  git -C "%~2" apply --whitespace=nowarn "%~3" || exit /b 1
  exit /b 0
)

git -C "%~2" apply --reverse --check --whitespace=nowarn "%~3" >nul 2>&1
if not errorlevel 1 (
  echo [patch] already applied: %~1/%~4
  exit /b 0
)

echo [patch] Patch does not apply cleanly in either direction: "%~3"
exit /b 1
