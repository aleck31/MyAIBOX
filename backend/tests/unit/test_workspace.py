"""Workspace path resolution — security-critical, so assertions are
explicit about what crosses the boundary and what doesn't.
"""
from __future__ import annotations

import os

import pytest

from backend.core import workspace


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """Redirect workspace ROOT into a pytest tmpdir."""
    monkeypatch.setattr(workspace, "ROOT", str(tmp_path))
    return tmp_path


def test_path_for_rejects_traversal_in_username(tmp_root):
    with pytest.raises(workspace.WorkspaceError):
        workspace.path_for("../evil", "assistant")


def test_path_for_rejects_traversal_in_module(tmp_root):
    with pytest.raises(workspace.WorkspaceError):
        workspace.path_for("alice", "../assistant")


def test_safe_join_accepts_unicode_filename(tmp_root):
    """Agents write in many languages — Unicode names must round-trip."""
    p = workspace.ensure("alice", "assistant")
    assert workspace.safe_join(p, "夏天感冒常见症状.md").startswith(p)
    assert workspace.safe_join(p, "report (v2).md").startswith(p)


def test_safe_join_rejects_hidden_file(tmp_root):
    p = workspace.ensure("alice", "assistant")
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_join(p, ".env")


def test_safe_join_rejects_control_chars(tmp_root):
    p = workspace.ensure("alice", "assistant")
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_join(p, "a\x00b.md")
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_join(p, "a\nb.md")


def test_safe_join_rejects_traversal(tmp_root):
    p = workspace.ensure("alice", "assistant")
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_join(p, "../../etc/passwd")


def test_safe_join_rejects_absolute_path(tmp_root):
    p = workspace.ensure("alice", "assistant")
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_join(p, "/etc/passwd")


def test_safe_join_blocks_symlink_escape(tmp_root, tmp_path):
    """A symlink inside the workspace must not leak outside."""
    p = workspace.ensure("alice", "assistant")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    os.symlink(str(outside), os.path.join(p, "leak"))
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_join(p, "leak")


def test_list_files_returns_sorted_with_metadata(tmp_root):
    p = workspace.ensure("alice", "assistant")
    (open(os.path.join(p, "b.md"), "w")).write("hello")
    (open(os.path.join(p, "a.md"), "w")).write("hi")
    files = workspace.list_files("alice", "assistant")
    assert [f.name for f in files] == ["a.md", "b.md"]
    assert files[0].size == 2
    assert files[1].size == 5
    assert files[0].mtime > 0


def test_delete_file_rejects_traversal(tmp_root):
    workspace.ensure("alice", "assistant")
    with pytest.raises(workspace.WorkspaceError):
        workspace.delete_file("alice", "assistant", "../../etc/passwd")


def test_users_are_isolated(tmp_root):
    workspace.ensure("alice", "assistant")
    p_bob = workspace.ensure("bob", "assistant")
    open(os.path.join(p_bob, "bob.md"), "w").write("bob")
    assert workspace.list_files("alice", "assistant") == []
    assert len(workspace.list_files("bob", "assistant")) == 1
