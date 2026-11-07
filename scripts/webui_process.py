from __future__ import annotations

import ctypes
import json
import os
import socket
import subprocess
import sys
import time
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
        "Usage: run-webui.cmd [-Start | -Foreground | -Status | -Stop] "
        "[-Port number] [-BindHost address] [-RequirePassword]"
    )
    raise SystemExit(exit_code)


def parse_args(arguments: list[str]) -> dict[str, object]:
    options: dict[str, object] = {
        "background": False,
        "foreground": False,
        "stop": False,
        "status": False,
        "require_password": False,
        "port": None,
        "bind_host": None,
    }
    index = 0
    while index < len(arguments):
        option = arguments[index]
        normalized = option.lstrip("-/").lower()
        if normalized in {"h", "help", "?"}:
            usage()
        if normalized in {"start", "background"}:
            options["background"] = True
            index += 1
            continue
        if normalized in {"server", "foreground"}:
            options["foreground"] = True
            index += 1
            continue
        if normalized in {"stop", "status"}:
            options[normalized] = True
            index += 1
            continue
        if normalized in {"requirepassword", "require-password"}:
            options["require_password"] = True
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
    modes = [
        name
        for name in ("background", "foreground", "stop", "status")
        if options[name]
    ]
    if len(modes) > 1:
        print(
            "[portable] Conflicting options: " + ", ".join(modes),
            file=sys.stderr,
        )
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


def process_image_path(process_id: int) -> str | None:
    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(
        process_query_limited_information, False, process_id
    )
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = ctypes.c_ulong(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            return None
        return buffer.value or None
    finally:
        kernel32.CloseHandle(handle)


def terminate_process(process_id: int) -> bool:
    process_terminate = 0x0001
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.TerminateProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(process_terminate, False, process_id)
    if not handle:
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 1))
    finally:
        kernel32.CloseHandle(handle)


def wait_until_stopped(process_id: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_is_running(process_id):
            return True
        time.sleep(0.1)
    return not process_is_running(process_id)


def read_pid_record() -> dict[str, object] | None:
    try:
        raw = PID_FILE.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    if not raw:
        return None
    try:
        if raw.startswith("{"):
            record = json.loads(raw)
            if not isinstance(record, dict):
                return None
            int(record["pid"])
            return record
        return {"pid": int(raw)}
    except (ValueError, TypeError, KeyError):
        return None


def recorded_process_id() -> int | None:
    record = read_pid_record()
    if record is None:
        return None
    process_id = int(record["pid"])
    if not process_is_running(process_id):
        return None
    image = process_image_path(process_id)
    if image is None:
        return process_id
    recorded_image = record.get("image")
    if recorded_image:
        recorded_image = str(recorded_image)
        try:
            same_image = Path(image).resolve() == Path(recorded_image).resolve()
        except OSError:
            same_image = image.lower() == recorded_image.lower()
        return process_id if same_image else None
    image_name = Path(image).name.lower()
    return process_id if image_name in {"python.exe", "pythonw.exe"} else None


def recorded_bind() -> tuple[str, str] | None:
    record = read_pid_record()
    if record is None:
        return None
    host = record.get("host")
    port = record.get("port")
    if host is None or port is None:
        return None
    return str(host), str(port)


def bind_scope(host: str) -> str:
    value = host.strip().lower()
    if value in {"", "*", "0.0.0.0", "::", "[::]"}:
        return "all-interfaces"
    if value in {"127.0.0.1", "localhost", "::1", "[::1]"}:
        return "loopback"
    return value


def same_bind(existing: tuple[str, str], requested: tuple[str, str]) -> bool:
    return (
        bind_scope(existing[0]) == bind_scope(requested[0])
        and existing[1] == requested[1]
    )


def probe_host(host: str) -> str:
    host = host.strip()
    if not host or host == "*":
        return "127.0.0.1"
    if host in {"0.0.0.0", "[::]"}:
        return "127.0.0.1"
    if host == "::":
        return "::1"
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def local_ipv4_addresses() -> list[str]:
    try:
        entries = socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM
        )
    except OSError:
        return []
    addresses = {
        entry[4][0] for entry in entries if not entry[4][0].startswith("127.")
    }
    return sorted(addresses)


def print_access_urls() -> None:
    host = os.environ["HERMES_WEBUI_HOST"]
    port = os.environ["HERMES_WEBUI_PORT"]
    if bind_scope(host) == "all-interfaces":
        print(f"[portable] local: http://127.0.0.1:{port}/")
        addresses = local_ipv4_addresses()
        if addresses:
            for address in addresses:
                print(f"[portable] lan  : http://{address}:{port}/")
        else:
            print(
                "[portable] lan  : use this computer's IPv4 address "
                f"with port {port}"
            )
        return
    print(f"[portable] url: http://{probe_host(host)}:{port}/")


def probe_health(timeout: float = 2.0) -> tuple[bool, str | None]:
    host = probe_host(os.environ["HERMES_WEBUI_HOST"])
    port = int(os.environ["HERMES_WEBUI_PORT"])
    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}/health", timeout=timeout
        ) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        return False, f"http {error.code}"
    except (OSError, ValueError):
        return False, None
    if isinstance(payload, dict):
        return True, str(payload.get("status", "unknown"))
    return True, "unknown"


def port_is_open(timeout: float = 0.5) -> bool:
    host = probe_host(os.environ["HERMES_WEBUI_HOST"]).strip("[]")
    port = int(os.environ["HERMES_WEBUI_PORT"])
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def stop_background() -> None:
    process_id = recorded_process_id()
    if process_id is None:
        PID_FILE.unlink(missing_ok=True)
        healthy, _ = probe_health()
        if healthy:
            print(
                "[portable] the server is running but was not started by "
                "start.cmd, so it was not stopped."
            )
            print("[portable] stop it from its own terminal with Ctrl-C.")
        else:
            print("[portable] no recorded background process is running.")
    else:
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process_id), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0 and process_is_running(process_id):
            if not terminate_process(process_id) or not wait_until_stopped(process_id):
                raise RuntimeError(f"Could not stop PID {process_id}.")
            print("[portable] taskkill was unavailable; terminated directly.")
        elif not wait_until_stopped(process_id):
            raise RuntimeError(f"Could not stop PID {process_id}.")
        print(f"[portable] stopped PID {process_id}")
    PID_FILE.unlink(missing_ok=True)


def tail(path: Path, line_count: int = 20) -> None:
    if not path.exists():
        return
    print(f"--- {path.name} ---")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    encoding = sys.stdout.encoding or "utf-8"
    for line in lines[-line_count:]:
        print(line.encode(encoding, errors="replace").decode(encoding))


def show_status() -> None:
    process_id = recorded_process_id()
    if process_id is None:
        print("[portable] background PID: not running")
    else:
        print(f"[portable] background PID: {process_id}")

    healthy, health = probe_health()
    if healthy:
        print(f"[portable] health: {health}")
        if process_id is None:
            print(
                "[portable] note: the server was not started by start.cmd "
                "(no PID record)."
            )
    elif health:
        print(f"[portable] health: unavailable ({health})")
    else:
        print("[portable] health: unavailable")
    if healthy:
        print_access_urls()

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


def require_lan_password() -> None:
    if os.environ.get("HERMES_WEBUI_PASSWORD", "").strip():
        return
    import getpass

    try:
        password = getpass.getpass("[portable] LAN password: ")
    except (KeyboardInterrupt, EOFError):
        raise RuntimeError("LAN password entry cancelled.") from None
    if password.strip():
        os.environ["HERMES_WEBUI_PASSWORD"] = password
        print("[portable] password set for this run.")
        return
    raise RuntimeError(
        "LAN mode requires a non-empty password."
    )


def start_background() -> None:
    host = os.environ["HERMES_WEBUI_HOST"]
    port = os.environ["HERMES_WEBUI_PORT"]
    process_id = recorded_process_id()
    if process_id is not None:
        existing_bind = recorded_bind()
        if existing_bind is None and bind_scope(host) == "all-interfaces":
            raise RuntimeError(
                "a background instance is already running but its listening "
                "address is unknown. Run stop.cmd, then start-lan.cmd again."
            )
        if existing_bind is not None and not same_bind(
            existing_bind, (host, port)
        ):
            raise RuntimeError(
                "a background instance is already running on "
                f"{existing_bind[0]}:{existing_bind[1]}. Run stop.cmd before "
                f"switching to {host}:{port}."
            )
        print(
            f"[portable] already running: PID {process_id}; start skipped."
        )
        print_access_urls()
        return
    PID_FILE.unlink(missing_ok=True)

    healthy, health = probe_health()
    if healthy:
        if bind_scope(host) == "all-interfaces":
            raise RuntimeError(
                "a server is already running on this port but was not started "
                "by start.cmd. Stop it before using LAN mode."
            )
        print(f"[portable] server is already running (health: {health}); start skipped.")
        print_access_urls()
        return
    if port_is_open():
        raise RuntimeError(
            f"port {host}:{port} "
            "is already in use by another program. Stop it or pass -Port."
        )

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
    image = process_image_path(process.pid) or str(PYTHON)
    PID_FILE.write_text(
        json.dumps(
            {
                "pid": process.pid,
                "image": image,
                "host": host,
                "port": port,
            }
        ),
        encoding="utf-8",
    )
    state = wait_for_startup(process)
    if state == "exited":
        PID_FILE.unlink(missing_ok=True)
        print(
            "[portable] server exited during startup "
            f"(exit code {process.returncode}).",
            file=sys.stderr,
        )
        tail(OUT_LOG)
        tail(ERR_LOG)
        raise SystemExit(1)
    print(f"[portable] started PID {process.pid}")
    if state == "healthy":
        print("[portable] health: up")
    else:
        print("[portable] health: not ready yet (still starting)")
    print_access_urls()
    print("[portable] use stop.cmd to stop it.")


def wait_for_startup(process: subprocess.Popen[bytes], timeout: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return "exited"
        healthy, _ = probe_health(timeout=0.75)
        if healthy:
            return "healthy"
        time.sleep(0.25)
    return "running" if process.poll() is None else "exited"


def run_foreground() -> int:
    print_access_urls()
    print("[portable] Ctrl-C stops the server.")
    try:
        return subprocess.call(
            [str(PYTHON), "server.py"], cwd=WEBUI, env=os.environ.copy()
        )
    except KeyboardInterrupt:
        return 130


def main() -> int:
    options = parse_args(sys.argv[1:])
    VAR.mkdir(parents=True, exist_ok=True)
    import_dotenv()
    configure_environment(options)
    if options["stop"]:
        stop_background()
        return 0
    if options["status"]:
        show_status()
        return 0
    validate_runtime()
    if options["require_password"]:
        require_lan_password()
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
