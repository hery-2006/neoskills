"""Tests for SkillManifest domain models and loading."""

from pathlib import Path

import pytest
import yaml

from neoskills.core.manifest import (
    DependencySet,
    Scope,
    SkillManifest,
    SkillType,
    _derive_scope,
)


class TestSkillType:
    def test_enum_values(self):
        assert SkillType.REGULAR.value == "regular"
        assert SkillType.META.value == "meta"
        assert SkillType.AGENT_SKILL.value == "agent-skill"

    def test_from_string(self):
        assert SkillType("regular") is SkillType.REGULAR
        assert SkillType("meta") is SkillType.META
        assert SkillType("agent-skill") is SkillType.AGENT_SKILL
        with pytest.raises(ValueError):
            SkillType("nonexistent")


class TestScope:
    def test_enum_values(self):
        assert Scope.USER.value == "user"
        assert Scope.PROJECT.value == "project"
        assert Scope.PLUGIN.value == "plugin"


class TestDependencySet:
    def test_empty_defaults(self):
        ds = DependencySet()
        assert ds.skills == []
        assert ds.tools == []
        assert ds.agent is None
        assert ds.packages == []

    def test_with_values(self):
        ds = DependencySet(
            skills=["rubric-builder"],
            tools=["Bash", "Read"],
            agent="tutoring-agent",
            packages=["pandas>=2.0"],
        )
        assert ds.skills == ["rubric-builder"]
        assert ds.tools == ["Bash", "Read"]
        assert ds.agent == "tutoring-agent"
        assert ds.packages == ["pandas>=2.0"]


class TestSkillManifest:
    @pytest.fixture()
    def skill_dir_no_metadata(self, tmp_path: Path) -> Path:
        """Skill directory with only SKILL.md, no metadata.yaml."""
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A test skill\ntags:\n  - testing\n---\n\n# My Skill\n"
        )
        return d

    @pytest.fixture()
    def skill_dir_with_metadata(self, tmp_path: Path) -> Path:
        """Skill directory with SKILL.md and full metadata.yaml."""
        d = tmp_path / "agent-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: agent-skill\ndescription: An agent skill\n---\n\n# Agent Skill\n"
        )
        metadata = {
            "type": "agent-skill",
            "depends_on": {
                "skills": ["rubric-builder"],
                "tools": ["Bash", "Read"],
                "agent": "tutoring-agent",
                "packages": ["pandas>=2.0"],
            },
        }
        (d / "metadata.yaml").write_text(yaml.dump(metadata))
        return d

    @pytest.fixture()
    def skill_dir_partial_metadata(self, tmp_path: Path) -> Path:
        """Skill directory with metadata.yaml containing only type."""
        d = tmp_path / "meta-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: meta-skill\ndescription: A meta skill\n---\n\n# Meta Skill\n"
        )
        metadata = {"type": "meta"}
        (d / "metadata.yaml").write_text(yaml.dump(metadata))
        return d

    @pytest.fixture()
    def skill_dir_invalid_metadata(self, tmp_path: Path) -> Path:
        """Skill directory with malformed metadata.yaml."""
        d = tmp_path / "broken-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: broken-skill\ndescription: Broken\n---\n\n# Broken\n"
        )
        (d / "metadata.yaml").write_text("{{{{not valid yaml at all::::")
        return d

    def test_from_skill_dir_no_metadata(self, skill_dir_no_metadata: Path):
        manifest = SkillManifest.from_skill_dir(skill_dir_no_metadata)
        assert manifest.spec.name == "my-skill"
        assert manifest.spec.description == "A test skill"
        assert manifest.type is SkillType.REGULAR
        assert manifest.scope is Scope.PROJECT
        assert manifest.depends_on.skills == []
        assert manifest.depends_on.tools == []
        assert manifest.depends_on.agent is None
        assert manifest.depends_on.packages == []
        assert manifest.resolved is False

    def test_from_skill_dir_with_metadata(self, skill_dir_with_metadata: Path):
        manifest = SkillManifest.from_skill_dir(skill_dir_with_metadata)
        assert manifest.spec.name == "agent-skill"
        assert manifest.type is SkillType.AGENT_SKILL
        assert manifest.depends_on.skills == ["rubric-builder"]
        assert manifest.depends_on.tools == ["Bash", "Read"]
        assert manifest.depends_on.agent == "tutoring-agent"
        assert manifest.depends_on.packages == ["pandas>=2.0"]
        assert manifest.resolved is False

    def test_from_skill_dir_partial_metadata(self, skill_dir_partial_metadata: Path):
        manifest = SkillManifest.from_skill_dir(skill_dir_partial_metadata)
        assert manifest.spec.name == "meta-skill"
        assert manifest.type is SkillType.META
        assert manifest.depends_on.skills == []
        assert manifest.depends_on.tools == []
        assert manifest.depends_on.agent is None
        assert manifest.depends_on.packages == []

    def test_from_skill_dir_invalid_metadata_ignored(self, skill_dir_invalid_metadata: Path):
        manifest = SkillManifest.from_skill_dir(skill_dir_invalid_metadata)
        assert manifest.spec.name == "broken-skill"
        assert manifest.type is SkillType.REGULAR
        assert manifest.depends_on.skills == []


class TestScopeDerivation:
    def test_user_scope(self):
        p = Path("/home/user/.neoskills/taps/mySkills/skills/my-skill")
        assert _derive_scope(p) is Scope.USER

    def test_project_scope(self):
        p = Path("/home/user/myproject/skills/my-skill")
        assert _derive_scope(p) is Scope.PROJECT

    def test_project_scope_claude_dir(self):
        p = Path("/home/user/myproject/.claude/skills/my-skill")
        assert _derive_scope(p) is Scope.PROJECT

    def test_plugin_scope(self):
        p = Path("/home/user/.neoskills/plugins/some-plugin/skills/my-skill")
        assert _derive_scope(p) is Scope.PLUGIN

    def test_plugin_scope_takes_priority(self):
        p = Path("/home/user/.neoskills/taps/plugins/skills/my-skill")
        assert _derive_scope(p) is Scope.PLUGIN
