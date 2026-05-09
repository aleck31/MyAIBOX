"""Agent skill registry.

Scans a skills directory (default ``~/.agents/skills/``), loads each
``SKILL.md`` via ``strands.vended_plugins.skills.Skill.from_file``, and
exposes a lookup by skill name.

Only skills whose ``name`` passes Strands' strict format
(1-64 lowercase alphanumeric + hyphens, and matching the parent directory
name) are registered — anything else is skipped with a log line, to keep
the agent context clean.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from strands.vended_plugins.skills import Skill

from backend.common.logger import logger


_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


@dataclass(frozen=True)
class SkillEntry:
    """Metadata surface for a loaded skill; the Strands `Skill` stays wrapped inside."""
    name: str
    description: str
    source_path: str


class SkillRegistry:
    def __init__(self, base_dir: str):
        self.base_dir = os.path.expanduser(base_dir)
        self._skills: Dict[str, Skill] = {}
        self._entries: Dict[str, SkillEntry] = {}

    def reload(self) -> None:
        """Rescan ``base_dir`` and rebuild the in-memory registry."""
        self._skills.clear()
        self._entries.clear()
        if not os.path.isdir(self.base_dir):
            logger.info(f"[Skills] directory not found: {self.base_dir}")
            return

        for entry in sorted(os.listdir(self.base_dir)):
            skill_dir = os.path.join(self.base_dir, entry)
            if not os.path.isdir(skill_dir):
                continue
            if not os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
                continue
            try:
                skill = Skill.from_file(skill_dir)
            except Exception as e:
                logger.warning(f"[Skills] failed to load {entry}: {e}")
                continue
            if not _NAME_RE.match(skill.name):
                logger.warning(
                    f"[Skills] skipping {entry}: name {skill.name!r} is not "
                    f"lowercase alphanumeric + hyphens"
                )
                continue
            if skill.name != entry:
                logger.warning(
                    f"[Skills] skipping {entry}: name {skill.name!r} does not "
                    f"match directory"
                )
                continue
            self._skills[skill.name] = skill
            self._entries[skill.name] = SkillEntry(
                name=skill.name,
                description=skill.description,
                source_path=skill_dir,
            )
        logger.info(f"[Skills] loaded {len(self._skills)} skills from {self.base_dir}")

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def get_many(self, names: List[str]) -> List[Skill]:
        """Return the Strands skill objects for the given names, skipping unknown."""
        return [s for s in (self._skills.get(n) for n in names) if s is not None]

    def list_entries(self) -> List[SkillEntry]:
        return sorted(self._entries.values(), key=lambda e: e.name)


# Module-level singleton. The base dir is conventional for multi-project
# reuse; override by constructing a fresh SkillRegistry in tests.
skill_registry = SkillRegistry(os.path.expanduser("~/.agents/skills"))
skill_registry.reload()
