"""Tests for runtime dependency checker."""

from neoskills.runtime.deps import check_deps


class TestCheckDeps:
    def test_no_metadata(self, tmp_path):
        """Skill with no metadata.yaml has no issues."""
        skill_dir = tmp_path / "simple"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: simple\n---\n\n# Simple\n")
        issues = check_deps(skill_dir)
        assert issues == []

    def test_missing_package(self, tmp_path):
        """Skill depending on nonexistent package reports issue."""
        skill_dir = tmp_path / "needs-pkg"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: needs-pkg\n---\n\n# Pkg\n")
        (skill_dir / "metadata.yaml").write_text(
            "depends_on:\n  packages:\n    - nonexistent_pkg_xyz_999\n"
        )
        issues = check_deps(skill_dir)
        assert len(issues) == 1
        assert issues[0].kind == "missing_package"

    def test_installed_package_ok(self, tmp_path):
        """Skill depending on installed package (pyyaml) has no package issues."""
        skill_dir = tmp_path / "has-yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: has-yaml\n---\n\n# YAML\n")
        (skill_dir / "metadata.yaml").write_text(
            "depends_on:\n  packages:\n    - pyyaml\n"
        )
        issues = check_deps(skill_dir)
        pkg_issues = [i for i in issues if i.kind == "missing_package"]
        assert pkg_issues == []

    def test_malformed_yaml(self, tmp_path):
        """Malformed metadata.yaml returns empty list."""
        skill_dir = tmp_path / "bad-yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: bad-yaml\n---\n\n# Bad\n")
        (skill_dir / "metadata.yaml").write_text("{{{{not valid yaml at all::::")
        issues = check_deps(skill_dir)
        assert issues == []

    def test_version_specifier_stripped(self, tmp_path):
        """Version specifiers are stripped before checking."""
        skill_dir = tmp_path / "versioned"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: versioned\n---\n\n# V\n")
        (skill_dir / "metadata.yaml").write_text(
            "depends_on:\n  packages:\n    - pyyaml>=6.0\n"
        )
        issues = check_deps(skill_dir)
        pkg_issues = [i for i in issues if i.kind == "missing_package"]
        assert pkg_issues == []
