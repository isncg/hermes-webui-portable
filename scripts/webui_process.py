from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "hermes-webui"
AGENT = ROOT / "hermes-agent"
PYTHON = Path(
    os.environ.get(
        "HERMES_WEBUI_PYTHON",
        ROOT / ".runtime" / "python-official" / "python.exe",
    )
)
VAR = ROOT / "var"
PID_FILE = VAR / "webui.pid"
OUT_LOG = VAR / "webui.out.log"
ERR_LOG = VAR / "webui.err.log"


def usage(exit_code: int = 0) -> None:
    print(
        "Usage: run-webui.cmd [-Background | -Status | -Stop] "
        "[-Port number] [-BindHost address]"
    )
    raise SystemExit(exit_code)


def parse_args(arguments: list[str]) -> dict[str, object]:
    options: dict[str, object] = {
        "background": False,
        "stop": False,
        "status": False,
        "port": None,
        "bind_host": None,
    }
    index = 0
    while index < len(arguments):
        option = arguments[index]
        normalized = option.lstrip("-/").lower()
        if normalized in {"h", "help", "?"}:
            usage()
        if normalized in {"background", "stop", "status"}:
            options[normalized] = True
            index += 1
            continue
        if normalized in {"port", "bindhost"}:
            if index + 1 >= len(arguments):
                print(f"[portable] Missing value for {option}.", file=sys.stderr)
                usage(2)
            value = arguments[index + 1]
            if normalized == "port":
                try:
                    port = int(value)
                except ValueError:
                    print(f"[portable] Invalid port: {value}", file=sys.stderr)
                    usage(2)
                if not 1 <= port <= 65535:
                    print(f"[portable] Invalid port: {value}", file=sys.stderr)
                    usage(2)
                options["port"] = port
            else:
                options["bind_host"] = value
            index += 2
            continue
        print(f"[portable] Unknown option: {option}", file=sys.stderr)
        usage(2)
    return options


def import_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and not os.environ.get(name):
            os.environ[name] = value.strip()


def configure_environment(options: dict[str, object]) -> None:
    defaults = {
        "HERMES_HOME": str(Path.home() / ".hermes"),
        "HERMES_WEBUI_AGENT_DIR": str(AGENT),
        "HERMES_WEBUI_DEFAULT_WORKSPACE": str(ROOT / "workspace"),
        "HERMES_WEBUI_PYTHON": str(PYTHON),
        "HERMES_WEBUI_HOST": "127.0.0.1",
        "HERMES_WEBUI_PORT": "8787",
        "HERMES_WEBUI_YAML_MINI": "1",
    }
    for name, value in defaults.items():
        if not os.environ.get(name):
            os.environ[name] = value
    if not os.environ.get("HERMES_WEBUI_STATE_DIR"):
        os.environ["HERMES_WEBUI_STATE_DIR"] = str(
            Path(os.environ["HERMES_HOME"]) / "webui"
        )
    if options["port"] is not None:
        os.environ["HERMES_WEBUI_PORT"] = str(options["port"])
    if options["bind_host"]:
        os.environ["HERMES_WEBUI_HOST"] = str(options["bind_host"])


def process_is_running(process_id: int) -> bool:
    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(process_query_limited_information, False, process_id)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def recorded_process_id() -> int | None:
    try:
        process_id = int(PID_FILE.read_text(encoding="ascii").strip())
    except (FileNotFoundError, ValueError):
        return None
    return process_id if process_is_running(process_id) else None


def stop_background() -> None:
    process_id = recorded_process_id()
    if process_id is None:
        print("[portable] no recorded background process is running.")
    else:
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process_id), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0 and process_is_running(process_id):
            raise RuntimeError(f"Could not stop PID {process_id}.")
        print(f"[portable] stopped PID {process_id}")
    PID_FILE.unlink(missing_ok=True)


def tail(path: Path, line_count: int = 20) -> None:
    if not path.exists():
        return
    print(f"--- {path.name} ---")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-line_count:]:
        print(line)


def show_status() -> None:
    process_id = recorded_process_id()
    if process_id is None:
        print("[portable] background PID: not running")
    else:
        print(f"[portable] background PID: {process_id}")

    host = os.environ["HERMES_WEBUI_HOST"]
    port = os.environ["HERMES_WEBUI_PORT"]
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=3) as response:
            payload = json.load(response)
        print(f"[portable] health: {payload.get('status', 'unknown')}")
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"[portable] health: unavailable ({error})")

    tail(OUT_LOG)
    tail(ERR_LOG)


def validate_runtime() -> None:
    if not PYTHON.exists():
        raise RuntimeError(f"Runtime missing: {PYTHON}. Run setup.cmd first.")
    if not (WEBUI / "server.py").exists():
        raise RuntimeError("WebUI submodule missing. Run setup.cmd first.")
    if not (AGENT / "cli.py").exists():
        raise RuntimeError("Agent submodule missing. Run setup.cmd first.")
    Path(os.environ["HERMES_WEBUI_STATE_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["HERMES_WEBUI_DEFAULT_WORKSPACE"]).mkdir(
        parents=True, exist_ok=True
    )


def start_background() -> None:
    process_id = recorded_process_id()
    if process_id is not None:
        raise RuntimeError(f"A recorded background instance is already running: {process_id}")
    PID_FILE.unlink(missing_ok=True)
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with OUT_LOG.open("wb") as stdout, ERR_LOG.open("wb") as stderr:
        process = subprocess.Popen(
            [str(PYTHON), str(WEBUI / "server.py")],
            cwd=WEBUI,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=creation_flags,
            close_fds=True,
        )
    PID_FILE.write_text(str(process.pid), encoding="ascii")
    print(f"[portable] started PID {process.pid}")
    print(
        "[portable] url: "
        f"http://{os.environ['HERMES_WEBUI_HOST']}:{os.environ['HERMES_WEBUI_PORT']}"
    )


def run_foreground() -> int:
    print(
        "[portable] url: "
        f"http://{os.environ['HERMES_WEBUI_HOST']}:{os.environ['HERMES_WEBUI_PORT']}"
    )
    try:
        return subprocess.call(
            [str(PYTHON), "server.py"], cwd=WEBUI, env=os.environ.copy()
        )
    except KeyboardInterrupt:
        return 130


def main() -> int:
    options = parse_args(sys.argv[1:])
    VAR.mkdir(parents=True, exist_ok=True)
    if options["stop"]:
        stop_background()
        return 0

    import_dotenv()
    configure_environment(options)
    if options["status"]:
        show_status()
        return 0

    validate_runtime()
    if options["background"]:
        start_background()
        return 0
    return run_foreground()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"[portable] {error}", file=sys.stderr)
        raise SystemExit(1)
