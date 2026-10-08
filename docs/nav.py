#!/usr/bin/env python3
"""Start, stop, restart, or show status for the local API and Vite dev server.

Usage:
  python docs/nav.py start|stop|restart|status
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".run"
API_PORT = 8000
WEB_PORT = 5173
API_URL = f"http://127.0.0.1:{API_PORT}/api/health"
WEB_URL = f"http://127.0.0.1:{WEB_PORT}/"


def pool_port() -> int | None:
    path = ROOT / "backend" / ".env"
    if not path.exists():
        return None
    raw = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "PROXY_POOL_URL":
            raw = value.strip().strip('"').strip("'")
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    host = ""
    rest = raw.split("://", 1)[1]
    hostport = rest.split("/", 1)[0]
    if hostport.startswith("["):
        host = hostport[1:].split("]", 1)[0]
        port_text = hostport.rsplit(":", 1)[-1] if "]:" in hostport else ""
    elif ":" in hostport:
        host, port_text = hostport.rsplit(":", 1)
    else:
        host, port_text = hostport, ""
    if host.lower() not in {"127.0.0.1", "localhost", "::1"}:
        return None
    if port_text.isdigit():
        return int(port_text)
    return 443 if raw.startswith("https://") else 80


def python_bin() -> Path:
    if os.name == "nt":
        return ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
    return ROOT / "backend" / ".venv" / "bin" / "python"


def vite_bin() -> Path:
    base = ROOT / "frontend" / "node_modules" / ".bin"
    if os.name == "nt":
        return base / "vite.cmd"
    return base / "vite"


def listening_pids(port: int) -> list[int]:
    pids: set[int] = set()
    if os.name == "nt":
        output = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[3].upper() != "LISTENING":
                continue
            local = parts[1]
            if local.rsplit(":", 1)[-1] == str(port):
                try:
                    pids.add(int(parts[-1]))
                except ValueError:
                    continue
        return sorted(pids)
    for command in (["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], ["ss", "-lptn", f"sport = :{port}"]):
        try:
            output = subprocess.run(command, capture_output=True, text=True, check=False).stdout
        except FileNotFoundError:
            continue
        if command[0] == "lsof":
            pids.update(int(line) for line in output.split() if line.isdigit())
        else:
            for line in output.splitlines():
                if f":{port}" not in line:
                    continue
                for piece in line.replace(",", " ").split():
                    if piece.startswith("pid="):
                        pids.add(int(piece.split("=", 1)[1]))
        if pids:
            break
    return sorted(pids)


def alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        output = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return str(pid) in output and "No tasks" not in output
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid(name: str) -> int | None:
    path = RUN / f"{name}.pid"
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def write_pid(name: str, pid: int) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / f"{name}.pid").write_text(str(pid), encoding="utf-8")


def clear_pid(name: str) -> None:
    path = RUN / f"{name}.pid"
    if path.exists():
        path.unlink()


def kill_pid(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
    for _ in range(20):
        if not alive(pid):
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def stop_service(name: str, port: int) -> None:
    pids = set(listening_pids(port))
    recorded = read_pid(name)
    if recorded:
        pids.add(recorded)
    for pid in sorted(pids):
        if alive(pid):
            kill_pid(pid)
    clear_pid(name)
    for _ in range(30):
        if not listening_pids(port):
            return
        time.sleep(0.1)


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_http(url: str, timeout: float = 40) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def spawn(name: str, command: list[str], cwd: Path) -> int:
    RUN.mkdir(parents=True, exist_ok=True)
    log = open(RUN / f"{name}.log", "wb", buffering=0)
    kwargs: dict = {
        "cwd": cwd,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    log.close()
    write_pid(name, process.pid)
    return process.pid


def log_tail(name: str) -> str:
    path = RUN / f"{name}.log"
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-12:])


def start() -> int:
    py = python_bin()
    vite = vite_bin()
    missing = []
    if not py.exists():
        missing.append(str(py))
    if not vite.exists():
        missing.append(str(vite))
    if missing:
        print("missing runtime, install dependencies first:")
        for item in missing:
            print(" ", item)
        return 1
    pool = pool_port()
    pool_ok = True
    if pool is None:
        print("pool skipped, PROXY_POOL_URL is empty or not a local address")
    elif listening_pids(pool):
        print(f"pool already listening on {pool}")
    else:
        spawn("pool", [str(py), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(pool)], ROOT / "proxy-pool")
        pool_ok = wait_http(f"http://127.0.0.1:{pool}/alive")
    if listening_pids(API_PORT) or listening_pids(WEB_PORT):
        print("api and web already running; use restart if you want a fresh process")
    else:
        spawn("api", [str(py), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)], ROOT / "backend")
        spawn(
            "web",
            [str(vite), "--host", "127.0.0.1", "--port", str(WEB_PORT)],
            ROOT / "frontend",
        )
    api_ok = wait_http(API_URL)
    web_ok = wait_http(WEB_URL)
    print(f"api  {API_URL} {'up' if api_ok else 'not ready'}")
    print(f"web  {WEB_URL} {'up' if web_ok else 'not ready'}")
    if pool is not None:
        print(f"pool http://127.0.0.1:{pool}/alive {'up' if pool_ok else 'not ready'}")
    print(f"logs {RUN}")
    if not api_ok:
        print(log_tail("api"))
    if not web_ok:
        print(log_tail("web"))
    if pool is not None and not pool_ok:
        print(log_tail("pool"))
    return 0 if api_ok and web_ok and pool_ok else 1


def stop() -> int:
    stop_service("api", API_PORT)
    stop_service("web", WEB_PORT)
    pool = pool_port()
    if pool:
        stop_service("pool", pool)
    print(f"api  port {API_PORT} {'still listening' if listening_pids(API_PORT) else 'stopped'}")
    print(f"web  port {WEB_PORT} {'still listening' if listening_pids(WEB_PORT) else 'stopped'}")
    if pool:
        print(f"pool port {pool} {'still listening' if listening_pids(pool) else 'stopped'}")
    else:
        print("pool skipped")
    busy = listening_pids(API_PORT) or listening_pids(WEB_PORT) or (pool and listening_pids(pool))
    return 1 if busy else 0


def status() -> int:
    rows = [("api", API_PORT, API_URL), ("web", WEB_PORT, WEB_URL)]
    pool = pool_port()
    if pool:
        rows.append(("pool", pool, f"http://127.0.0.1:{pool}/alive"))
    for name, port, url in rows:
        pids = listening_pids(port)
        state = "up" if pids and port_open(port) else "down"
        shown = ",".join(str(pid) for pid in pids) or "-"
        print(f"{name:4} {state:4} port {port} pid {shown} {url}")
    if not pool:
        print("pool skip PROXY_POOL_URL is empty or not local")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Control the local NEXA API and web server.")
    parser.add_argument("action", choices=("start", "stop", "restart", "status"))
    args = parser.parse_args()
    if args.action == "start":
        return start()
    if args.action == "stop":
        return stop()
    if args.action == "restart":
        stopped = stop()
        if stopped:
            return stopped
        return start()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
