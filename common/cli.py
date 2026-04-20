import subprocess
import os
import sys
import json
import re

UNIT = "my-aibox"
DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root

SYSTEMCTL = ["systemctl", "--user"]
JOURNALCTL = ["journalctl", "--user"]


def _systemctl(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(SYSTEMCTL + list(args), capture_output=capture, text=True)


def _unit_is_active() -> bool:
    return _systemctl("is-active", "--quiet", UNIT).returncode == 0


def _unit_is_installed() -> bool:
    # list-unit-files exits 0 and prints the unit line when installed, else empty.
    r = _systemctl("list-unit-files", f"{UNIT}.service", "--no-legend", capture=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def _require_unit_installed() -> None:
    if not _unit_is_installed():
        print(
            f"{UNIT}.service is not installed.\n"
            f"Run `my-aibox install` first to set up the systemd user service."
        )
        sys.exit(1)


def _cmd_install():
    src = os.path.join(DIR, f"{UNIT}.service")
    dst_dir = os.path.expanduser("~/.config/systemd/user")
    dst = os.path.join(dst_dir, f"{UNIT}.service")

    with open(src) as f:
        template = f.read()
    rendered = template.format(project_dir=DIR)

    os.makedirs(dst_dir, exist_ok=True)
    with open(dst, "w") as f:
        f.write(rendered)
    print(f"✓ installed {dst} (project_dir={DIR})")

    _systemctl("daemon-reload")
    rc = _systemctl("enable", "--now", UNIT).returncode
    if rc != 0:
        sys.exit(rc)
    print(f"✓ enabled and started {UNIT}.service")


def _sync_version():
    """Sync version from pyproject.toml to frontend/package.json."""
    pyproject = os.path.join(DIR, "pyproject.toml")
    pkg_json = os.path.join(DIR, "frontend", "package.json")

    with open(pyproject) as f:
        match = re.search(r'^version\s*=\s*"(.+?)"', f.read(), re.MULTILINE)
    if not match:
        return
    version = match.group(1)

    with open(pkg_json) as f:
        pkg = json.load(f)
    if pkg.get("version") != version:
        pkg["version"] = version
        with open(pkg_json, "w") as f:
            json.dump(pkg, f, indent=2)
            f.write("\n")
        print(f"✓ synced version {version} → package.json")


def _listen_urls(host: str, port: int) -> list[str]:
    """URLs the service is reachable at. For 0.0.0.0 both localhost and the
    first non-loopback IPv4 are reported so users know it's not just local."""
    if host in ("0.0.0.0", ""):
        urls = [f"http://localhost:{port}"]
        if lan := _lan_ip():
            urls.append(f"http://{lan}:{port}")
        return urls
    return [f"http://{host}:{port}"]


def _lan_ip() -> str | None:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))  # no packets sent; just picks the outbound iface
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _cmd_run():
    os.execvp(
        os.path.join(DIR, ".venv", "bin", "python"),
        [os.path.join(DIR, ".venv", "bin", "python"), "app.py"],
    )


def _cmd_status():
    if not _unit_is_active():
        print(f"{UNIT}: stopped")
        return
    # Pull a short summary; fall back gracefully if fields are missing.
    show = _systemctl(
        "show", UNIT,
        "-p", "MainPID", "-p", "ActiveEnterTimestamp", "-p", "MemoryCurrent",
        capture=True,
    ).stdout
    props = dict(line.split("=", 1) for line in show.strip().splitlines() if "=" in line)
    from core.config import app_config
    port = app_config.server_config.get("port", 8080)
    lines = [f"{UNIT}: running", f"  port:    {port}"]
    if pid := props.get("MainPID"):
        lines.append(f"  pid:     {pid}")
    if ts := props.get("ActiveEnterTimestamp"):
        lines.append(f"  started: {ts}")
    if mem := props.get("MemoryCurrent"):
        try:
            mb = int(mem) / (1024 * 1024)
            lines.append(f"  memory:  {mb:.1f} MB")
        except ValueError:
            pass
    print("\n".join(lines))


def _cmd_logs(follow: bool):
    args = JOURNALCTL + ["-u", UNIT]
    if follow:
        args.append("-f")
    else:
        args += ["-n", "100", "--no-pager"]
    os.execvp(args[0], args)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "run":
        _cmd_run()

    elif cmd == "install":
        _cmd_install()

    elif cmd in ("start", "stop", "restart"):
        _require_unit_installed()
        rc = _systemctl(cmd, UNIT).returncode
        if rc == 0:
            past = {"start": "started", "stop": "stopped", "restart": "restarted"}[cmd]
            print(f"✓ {UNIT}.service {past}")
            if cmd in ("start", "restart"):
                from core.config import app_config
                server = app_config.server_config
                for url in _listen_urls(server["host"], server["port"]):
                    print(f"  listening on {url}")
        sys.exit(rc)

    elif cmd == "status":
        _require_unit_installed()
        _cmd_status()

    elif cmd == "logs":
        _require_unit_installed()
        follow = "-f" in sys.argv[2:] or "--follow" in sys.argv[2:]
        _cmd_logs(follow)

    elif cmd == "build":
        _sync_version()
        subprocess.run(["npm", "run", "build"], cwd=os.path.join(DIR, "frontend"), check=True)

    elif cmd == "check":
        subprocess.run(["uv", "run", "ruff", "check", "."], cwd=DIR, check=True)
        print("✓ ruff check passed")
        subprocess.run(
            ["uv", "run", "pytest", "-m", "not integration", "tests/unit"],
            cwd=DIR, check=True,
        )
        print("✓ unit tests passed")

    elif cmd == "test":
        # Pass-through: everything after `my-aibox test` goes to pytest.
        extra = sys.argv[2:] or ["tests/unit"]
        subprocess.run(["uv", "run", "pytest", *extra], cwd=DIR, check=True)

    else:
        print("Usage: my-aibox <command>\n")
        print("  run                 Run the app in the foreground")
        print("  install             Install and enable the systemd user service")
        print("  start|stop|restart  Manage the systemd user service")
        print("  status              Show service status")
        print("  logs [-f]           Tail service logs (journalctl)")
        print("  build               Build the frontend (syncs version)")
        print("  check               Lint Python + run unit tests")
        print("  test [pytest args]  Run pytest (default: tests/unit). Use")
        print("                      `my-aibox test -m integration` for real-service tests.")
        sys.exit(0 if cmd is None else 1)
