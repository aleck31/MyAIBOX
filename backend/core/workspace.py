"""Per-user per-module workspace storage.

Layout::

    storage/workspace/<username>/<module>/
      report.md
      chart.png
      ...

One directory per (user, module). Files persist across sessions — a
clear-history on the chat does not touch the workspace.

This module owns all path resolution. Any caller should:

- Use `path_for(user, module)` to get the directory (call `ensure` if
  writing).
- Use `safe_join(dir, name)` to turn a caller-supplied filename into an
  absolute path; it rejects anything that escapes the workspace root
  (``..``, absolute paths, symlink tricks).

File content IO itself is done by callers / the Strands `file_write`
tool; this module only enforces where things land.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List


# Runtime workspace root. Relative to the process cwd (systemd sets
# WorkingDirectory to the project root).
ROOT = os.path.join("storage", "workspace")

# Filenames we tolerate. Unicode letters/digits are allowed so agents
# can write names like "夏天感冒常见症状.md"; what we reject are path
# separators, traversal, hidden files, and anything unprintable.
_MODULE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")

# Module-internal names (username, agent_id) are ASCII — they come from
# Cognito or code constants, so we keep the tighter regex for those.
_SAFE_MODULE = _MODULE_NAME


def _is_safe_filename(name: str) -> bool:
    """Reject path separators, traversal, hidden/empty names, control chars.

    Accepts arbitrary Unicode letters/digits/symbols otherwise, so names
    like ``夏天感冒常见症状.md`` or ``report (v2).md`` work.
    """
    if not name or len(name) > 255:
        return False
    if name in (".", ".."):
        return False
    if name.startswith("."):
        return False  # no hidden files
    if any(c in name for c in ("/", "\\", "\x00")):
        return False
    # Any control character (tab, newline, etc.) is a red flag.
    if not all(c.isprintable() for c in name):
        return False
    return True


@dataclass(frozen=True)
class WorkspaceFile:
    name: str
    size: int
    mtime: float  # unix seconds


class WorkspaceError(ValueError):
    """Raised when a caller-supplied path would escape the workspace."""


def path_for(username: str, module: str) -> str:
    """Return the absolute workspace directory for (user, module).

    Both components are validated to catch programmer errors early;
    anything user-supplied should already be authenticated by the
    caller (username comes from Cognito, module is an app constant).
    """
    if not _SAFE_MODULE.match(username):
        raise WorkspaceError(f"invalid username: {username!r}")
    if not _SAFE_MODULE.match(module):
        raise WorkspaceError(f"invalid module: {module!r}")
    return os.path.abspath(os.path.join(ROOT, username, module))


def ensure(username: str, module: str) -> str:
    """Create the workspace directory if missing; return its absolute path."""
    p = path_for(username, module)
    os.makedirs(p, exist_ok=True)
    return p


def safe_join(workspace_dir: str, filename: str) -> str:
    """Resolve ``workspace_dir/filename`` with boundary check.

    Accepts only plain filenames (no subdirectories, no traversal). We
    intentionally do not support nested folders in MVP — flat layout
    matches what the UI shows and keeps security trivial.
    """
    if not _is_safe_filename(filename):
        raise WorkspaceError(f"invalid filename: {filename!r}")
    root = os.path.realpath(workspace_dir)
    target = os.path.realpath(os.path.join(root, filename))
    # Ensure target stays inside root even after symlink resolution.
    if target != root and not target.startswith(root + os.sep):
        raise WorkspaceError("path escapes workspace")
    return target


def list_files(username: str, module: str) -> List[WorkspaceFile]:
    p = path_for(username, module)
    if not os.path.isdir(p):
        return []
    out: List[WorkspaceFile] = []
    for name in sorted(os.listdir(p)):
        fp = os.path.join(p, name)
        if not os.path.isfile(fp):
            continue  # skip directories / sockets / etc.
        try:
            st = os.stat(fp)
        except OSError:
            continue
        out.append(WorkspaceFile(name=name, size=st.st_size, mtime=st.st_mtime))
    return out


def delete_file(username: str, module: str, filename: str) -> bool:
    """Delete a file. Returns False if the file didn't exist."""
    p = path_for(username, module)
    target = safe_join(p, filename)
    if not os.path.isfile(target):
        return False
    os.remove(target)
    return True
