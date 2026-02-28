import subprocess
import os
import sys
import json
import re

SESSION = "my-aibox"
DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root


def _running() -> bool:
    return subprocess.run(["tmux", "has-session", "-t", SESSION], capture_output=True).returncode == 0


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


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "start":
        if _running():
            print(f"Already running (tmux session: {SESSION})")
            sys.exit(1)
        subprocess.run(["tmux", "new-session", "-d", "-s", SESSION, "-c", DIR, "uv run python app.py"], check=True)
        print(f"Started (tmux session: {SESSION})")

    elif cmd == "stop":
        if not _running():
            print("Not running")
            sys.exit(1)
        subprocess.run(["tmux", "kill-session", "-t", SESSION], check=True)
        print("Stopped")

    elif cmd == "restart":
        if _running():
            subprocess.run(["tmux", "kill-session", "-t", SESSION])
            import time
            time.sleep(1)
        subprocess.run(["tmux", "new-session", "-d", "-s", SESSION, "-c", DIR, "uv run python app.py"], check=True)
        print(f"Started (tmux session: {SESSION})")

    elif cmd == "status":
        if not _running():
            print(f"{SESSION}: stopped")
        else:
            pid = subprocess.run(
                ["tmux", "list-panes", "-t", SESSION, "-F", "#{pane_pid}"],
                capture_output=True, text=True
            ).stdout.strip()
            etime = subprocess.run(
                ["ps", "-o", "etime=", "-p", pid], capture_output=True, text=True
            ).stdout.strip() if pid else ""
            from core.config import app_config
            port = app_config.server_config.get("port", 8080)
            lines = [f"{SESSION}: running", f"  port:   {port}"]
            if pid:
                lines.append(f"  pid:    {pid}")
            if etime:
                lines.append(f"  uptime: {etime}")
            print("\n".join(lines))

    elif cmd == "build":
        _sync_version()
        subprocess.run(["npm", "run", "build"], cwd=os.path.join(DIR, "frontend"), check=True)

    elif cmd == "check":
        subprocess.run(["uv", "run", "ruff", "check", "."], cwd=DIR, check=True)
        print("✓ ruff check passed")

    elif cmd == "attach":
        os.execvp("tmux", ["tmux", "attach", "-t", SESSION])

    else:
        print("Usage: my-aibox [start|stop|restart|status|attach|build|check]")
        sys.exit(0 if cmd is None else 1)
