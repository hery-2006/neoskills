"""SkillManifest: enriched skill descriptor with type, scope, and dependencies.

Combines SkillSpec (from SKILL.md) with optional metadata.yaml to produce
a complete manifest used for dependency resolution and skill indexing.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

from neoskills.core.models import SkillSpec


class SkillType(Enum):
    """Classification of a skill."""

    REGULAR = "regular"
    META = "meta"
    AGENT_SKILL = "agent-skill"


class Scope(Enum):
    """Where a skill lives in the filesystem hierarchy."""

    USER = "user"
    PROJECT = "project"
    PLUGIN = "plugin"


@dataclass
class DependencySet:
    """Dependencies declared by a skill."""

    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    agent: str | None = None
    packages: list[str] = field(default_factory=list)


@dataclass
class SkillManifest:
    """Enriched skill descriptor combining SkillSpec with metadata.yaml."""

    spec: SkillSpec
    type: SkillType = SkillType.REGULAR
    scope: Scope = Scope.PROJECT
    depends_on: DependencySet = field(default_factory=DependencySet)
    resolved: bool = False

    @classmethod
    def from_skill_dir(cls, skill_dir: Path, tap_name: str = "") -> "SkillManifest":
        """Load a SkillManifest from a skill directory.

        Reads SkillSpec from SKILL.md (required), then merges optional
        metadata.yaml for type and dependency information.
        """
        spec = SkillSpec.from_skill_dir(skill_dir, tap_name=tap_name)

        # Defaults
        skill_type = SkillType.REGULAR
        depends_on = DependencySet()

        # Try loading metadata.yaml
        metadata_path = skill_dir / "metadata.yaml"
        if metadata_path.exists():
            try:
                raw = yaml.safe_load(metadata_path.read_text())
                if isinstance(raw, dict):
                    # Parse type
                    raw_type = raw.get("type")
                    if raw_type:
                        try:
                            skill_type = SkillType(raw_type)
                        except ValueError:
                            pass  # Unknown type string; keep default

                    # Parse depends_on
                    raw_deps = raw.get("depends_on")
                    if isinstance(raw_deps, dict):
                        depends_on = DependencySet(
                            skills=raw_deps.get("skills", []),
                            tools=raw_deps.get("tools", []),
                            agent=raw_deps.get("agent"),
                            packages=raw_deps.get("packages", []),
                        )
            except yaml.YAMLError:
                pass  # Malformed YAML; keep defaults

        scope = _derive_scope(skill_dir)

        return cls(
            spec=spec,
            type=skill_type,
            scope=scope,
            depends_on=depends_on,
            resolved=False,
        )


def _derive_scope(skill_dir: Path) -> Scope:
    """Derive the scope of a skill from its filesystem path.

    Rules (checked in order):
    - If "plugins" appears in the path parts -> PLUGIN
    - If ".neoskills" and "taps" appear in the path parts -> USER
    - Otherwise -> PROJECT
    """
    parts = skill_dir.parts
    if "plugins" in parts:
        return Scope.PLUGIN
    if ".neoskills" in parts and "taps" in parts:
        return Scope.USER
    return Scope.PROJECT
