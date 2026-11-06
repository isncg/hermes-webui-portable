@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "WEBUI=%ROOT%\hermes-webui"
set "AGENT=%ROOT%\hermes-agent"
set "GATEWAY_ONLY=0"
set "SKIP_INSTALL=0"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="-GatewayOnly" goto enable_gateway_only
if /i "%~1"=="/GatewayOnly" goto enable_gateway_only
if /i "%~1"=="-SkipInstall" goto enable_skip_install
if /i "%~1"=="/SkipInstall" goto enable_skip_install
if /i "%~1"=="-h" goto usage
if /i "%~1"=="--help" goto usage
if /i "%~1"=="/?" goto usage
echo [setup] Unknown option: %~1
goto usage_error

:enable_gateway_only
set "GATEWAY_ONLY=1"
shift
goto parse_args

:enable_skip_install
set "SKIP_INSTALL=1"
shift
goto parse_args

:args_done
call "%ROOT%\versions.cmd" || exit /b 1

where git.exe >nul 2>&1 || (
  echo [setup] Git is required but was not found on PATH.
  exit /b 1
)

echo [setup] initializing pinned submodules
git -C "%ROOT%" submodule sync --recursive || goto command_failed
git -C "%ROOT%" submodule update --init --recursive || goto command_failed

call :verify_commit "%WEBUI%" "%HERMES_WEBUI_COMMIT%" "hermes-webui" || exit /b 1
call :verify_commit "%AGENT%" "%HERMES_AGENT_COMMIT%" "hermes-agent" || exit /b 1

call "%ROOT%\scripts\apply-patches.cmd" "%ROOT%" || exit /b 1

for %%D in (data workspace var) do if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D" || goto command_failed
if not exist "%ROOT%\.env" (
  copy /y "%ROOT%\.env.example" "%ROOT%\.env" >nul || goto command_failed
  echo [setup] created .env from .env.example
)

if "%SKIP_INSTALL%"=="1" (
  echo [setup] submodules and patches are ready; dependency installation skipped.
  exit /b 0
)

call :ensure_uv || exit /b 1
call :ensure_runtime || exit /b 1

echo [setup] installing Hermes WebUI dependencies
"%UV_EXE%" pip install --python "%PYTHON_EXE%" --break-system-packages --only-binary=:all: -r "%WEBUI%\requirements.txt" || goto binary_install_failed

if "%GATEWAY_ONLY%"=="1" (
  echo [setup] gateway-only mode selected; Hermes Agent dependencies were not installed.
) else (
  echo [setup] installing Hermes Agent into the shared runtime
  "%UV_EXE%" pip install --python "%PYTHON_EXE%" --break-system-packages --only-binary=:all: -e "%AGENT%" || goto binary_install_failed
)

echo [setup] validating the offline YAML fallback
"%PYTHON_EXE%" "%WEBUI%\tests\test_yaml_mini_fallback.py" "%WEBUI%" || goto command_failed

echo.
echo [setup] ready. Start with: .\start.cmd
exit /b 0

:ensure_uv
set "UV_DIR=%ROOT%\.runtime\uv-%UV_VERSION%"
set "UV_EXE=%UV_DIR%\uv.exe"
set "UV_ARCHIVE=%ROOT%\var\uv-%UV_VERSION%-windows-x64.zip"
set "UV_DOWNLOAD=%UV_ARCHIVE%.download"
set "UV_URL=https://github.com/astral-sh/uv/releases/download/%UV_VERSION%/uv-x86_64-pc-windows-msvc.zip"

if exist "%UV_EXE%" (
  "%UV_EXE%" --version 2>nul | findstr.exe /b /c:"uv %UV_VERSION%" >nul
  if not errorlevel 1 exit /b 0
  echo [setup] replacing unexpected uv executable: "%UV_EXE%"
  del /f /q "%UV_EXE%" >nul 2>&1
)

if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if /i not "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
  echo [setup] Automatic runtime setup currently supports Windows x64 only.
  exit /b 1
)
for %%T in (curl.exe tar.exe certutil.exe findstr.exe) do where %%T >nul 2>&1 || (
  echo [setup] Required Windows tool was not found: %%T
  exit /b 1
)

if not exist "%UV_DIR%" mkdir "%UV_DIR%" || exit /b 1
if exist "%UV_DOWNLOAD%" del /f /q "%UV_DOWNLOAD%" >nul 2>&1
echo [setup] downloading uv %UV_VERSION%
curl.exe -fL --retry 3 --output "%UV_DOWNLOAD%" "%UV_URL%" || exit /b 1

certutil.exe -hashfile "%UV_DOWNLOAD%" SHA256 | findstr.exe /i /c:"%UV_WINDOWS_X64_SHA256%" >nul
if errorlevel 1 (
  echo [setup] uv download checksum verification failed.
  del /f /q "%UV_DOWNLOAD%" >nul 2>&1
  exit /b 1
)

move /y "%UV_DOWNLOAD%" "%UV_ARCHIVE%" >nul || exit /b 1
tar.exe -xf "%UV_ARCHIVE%" -C "%UV_DIR%" || exit /b 1
del /f /q "%UV_ARCHIVE%" >nul 2>&1
if not exist "%UV_EXE%" (
  echo [setup] uv.exe was not found after extracting the downloaded archive.
  exit /b 1
)
"%UV_EXE%" --version
exit /b 0

:ensure_runtime
set "UV_CACHE_DIR=%ROOT%\.cache\uv"
set "UV_PYTHON_PREFERENCE=only-managed"
set "PYTHON_EXE="
set "PY_MANAGER="

call :find_python_manager
if defined PY_MANAGER goto ensure_official_python

set "UV_PYTHON_INSTALL_DIR=%ROOT%\.runtime\python-uv"
set "PYTHON_EXE=%UV_PYTHON_INSTALL_DIR%\%HERMES_PYTHON_DIR%\python.exe"
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:3] == (3, 14, 10) else 1)" >nul 2>&1
  if not errorlevel 1 goto record_runtime
)

echo [setup] Python Install Manager not found; using the uv-managed runtime fallback
"%UV_EXE%" python install --reinstall "%HERMES_PYTHON_VERSION%" || exit /b 1
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
  echo [setup] Windows policy blocked the uv-managed Python runtime.
  echo [setup] Install the official Python Install Manager, then rerun setup.cmd.
  exit /b 1
)
goto record_runtime

:ensure_official_python
set "PYTHON_EXE=%ROOT%\.runtime\python-official\python.exe"

if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:3] == (3, 14, 10) else 1)" >nul 2>&1
  if not errorlevel 1 goto record_runtime
  echo [setup] existing official Python runtime is unusable; reinstalling it
)

echo [setup] installing official Python %HERMES_PYTHON_VERSION% into .runtime
"%PY_MANAGER%" install -y --force --target="%ROOT%\.runtime\python-official" "%HERMES_PYTHON_VERSION%" || exit /b 1
"%PYTHON_EXE%" --version >nul 2>&1 || exit /b 1

:record_runtime
> "%ROOT%\var\runtime-python.txt" echo %PYTHON_EXE%
"%PYTHON_EXE%" --version
exit /b 0

:find_python_manager
pymanager.exe help install >nul 2>&1
if not errorlevel 1 (
  set "PY_MANAGER=pymanager.exe"
  exit /b 0
)
py.exe help install >nul 2>&1
if not errorlevel 1 set "PY_MANAGER=py.exe"
exit /b 0

:verify_commit
set "ACTUAL_COMMIT="
for /f "usebackq delims=" %%I in (`git -C "%~1" rev-parse HEAD 2^>nul`) do set "ACTUAL_COMMIT=%%I"
if not defined ACTUAL_COMMIT (
  echo [setup] Could not read the %~3 commit.
  exit /b 1
)
if /i not "%ACTUAL_COMMIT%"=="%~2" (
  echo [setup] Unexpected %~3 commit: %ACTUAL_COMMIT% ^(expected %~2^)
  exit /b 1
)
exit /b 0

:binary_install_failed
echo [setup] A dependency has no compatible prebuilt Windows wheel.
echo [setup] No compiler will be invoked. Check the pinned dependency versions or use -GatewayOnly.
exit /b 1

:command_failed
echo [setup] Command failed with exit code %ERRORLEVEL%.
exit /b %ERRORLEVEL%

:usage
echo Usage: setup.cmd [-GatewayOnly] [-SkipInstall]
exit /b 0

:usage_error
echo Usage: setup.cmd [-GatewayOnly] [-SkipInstall]
exit /b 2
