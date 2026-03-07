# Skill Organization & Dependencies — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make skills first-class entities with typed classification, multi-scope discovery, and dependency resolution.

**Architecture:** Introduce SkillManifest (composes SkillSpec + metadata.yaml), SkillIndex (multi-scope discovery), and Resolver (dependency DAG). All additive — existing SkillSpec, Linker, Cellar unchanged.

**Tech Stack:** Python 3.13, PyYAML, Click, pytest. No new dependencies.

**Design doc:** `docs/plans/2026-03-07-skill-organization-design.md`

---

### Task 1: Domain Models — SkillType, Scope, DependencySet

**Files:**
- Create: `src/neoskills/core/manifest.py`
- Test: `tests/unit/test_manifest.py`

**Step 1: Write the failing tests**

```python
# tests/unit/test_manifest.py
"""Tests for SkillManifest, DependencySet, SkillType, Scope."""

from pathlib import Path

from neoskills.core.manifest import (
    DependencySet,
    Scope,
    SkillManifest,
    SkillType,
)


class TestSkillType:
    def test_enum_values(self):
        assert SkillType.REGULAR.value == "regular"
        assert SkillType.META.value == "meta"
        assert SkillType.AGENT_SKILL.value == "agent-skill"

    def test_from_string(self):
        assert SkillType("regular") == SkillType.REGULAR
        assert SkillType("agent-skill") == SkillType.AGENT_SKILL


class TestScope:
    def test_enum_values(self):
        assert Scope.USER.value == "user"
        assert Scope.PROJECT.value == "project"
        assert Scope.PLUGIN.value == "plugin"


class TestDependencySet:
    def test_empty_defaults(self):
        deps = DependencySet()
        assert deps.skills == []
        assert deps.tools == []
        assert deps.agent is None
        assert deps.packages == []

    def test_with_values(self):
        deps = DependencySet(
            skills=["rubric-builder"],
            tools=["Bash", "Read"],
            agent="tutoring-agent",
            packages=["pandas>=2.0"],
        )
        assert deps.skills == ["rubric-builder"]
        assert deps.agent == "tutoring-agent"
        assert len(deps.packages) == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'neoskills.core.manifest'`

**Step 3: Write minimal implementation**

```python
# src/neoskills/core/manifest.py
"""SkillManifest — first-class skill entity composing SkillSpec + metadata.yaml."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from neoskills.core.models import SkillSpec


class SkillType(Enum):
    """What kind of work a skill does."""

    REGULAR = "regular"
    META = "meta"
    AGENT_SKILL = "agent-skill"


class Scope(Enum):
    """Where a skill lives — auto-derived from filesystem location."""

    USER = "user"
    PROJECT = "project"
    PLUGIN = "plugin"


@dataclass
class DependencySet:
    """All dependencies a skill declares."""

    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    agent: str | None = None
    packages: list[str] = field(default_factory=list)


@dataclass
class SkillManifest:
    """First-class skill entity: SkillSpec (SKILL.md) + metadata.yaml extension."""

    spec: SkillSpec
    type: SkillType = SkillType.REGULAR
    scope: Scope = Scope.USER
    depends_on: DependencySet = field(default_factory=DependencySet)
    resolved: bool = False
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_manifest.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add src/neoskills/core/manifest.py tests/unit/test_manifest.py
git commit -m "feat: add SkillType, Scope, DependencySet, SkillManifest models"
```

---

### Task 2: SkillManifest.from_skill_dir — Load and Merge

**Files:**
- Modify: `src/neoskills/core/manifest.py`
- Test: `tests/unit/test_manifest.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_manifest.py`:

```python
class TestSkillManifest:
    def test_from_skill_dir_no_metadata(self, tmp_path: Path):
        """Skill with only SKILL.md — defaults to regular, no deps."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A test\n---\n\n# My Skill\n"
        )
        manifest = SkillManifest.from_skill_dir(skill_dir, tap_name="mySkills")
        assert manifest.spec.skill_id == "my-skill"
        assert manifest.spec.description == "A test"
        assert manifest.type == SkillType.REGULAR
        assert manifest.depends_on.skills == []
        assert manifest.depends_on.agent is None

    def test_from_skill_dir_with_metadata(self, tmp_path: Path):
        """Skill with both SKILL.md and metadata.yaml."""
        skill_dir = tmp_path / "eval-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: eval-skill\ndescription: Evaluate work\n---\n\n# Eval\n"
        )
        (skill_dir / "metadata.yaml").write_text(
            "type: agent-skill\n"
            "depends_on:\n"
            "  skills:\n"
            "    - rubric-builder\n"
            "  tools:\n"
            "    - Bash\n"
            "    - Read\n"
            "  agent: tutoring-agent\n"
            "  packages:\n"
            '    - "pandas>=2.0"\n'
        )
        manifest = SkillManifest.from_skill_dir(skill_dir, tap_name="mySkills")
        assert manifest.spec.name == "eval-skill"
        assert manifest.type == SkillType.AGENT_SKILL
        assert manifest.depends_on.skills == ["rubric-builder"]
        assert manifest.depends_on.tools == ["Bash", "Read"]
        assert manifest.depends_on.agent == "tutoring-agent"
        assert manifest.depends_on.packages == ["pandas>=2.0"]

    def test_from_skill_dir_partial_metadata(self, tmp_path: Path):
        """metadata.yaml with only type, no depends_on."""
        skill_dir = tmp_path / "meta-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: meta-skill\ndescription: Manages skills\n---\n\n# Meta\n"
        )
        (skill_dir / "metadata.yaml").write_text("type: meta\n")
        manifest = SkillManifest.from_skill_dir(skill_dir)
        assert manifest.type == SkillType.META
        assert manifest.depends_on.skills == []

    def test_from_skill_dir_invalid_metadata_ignored(self, tmp_path: Path):
        """Malformed metadata.yaml falls back to defaults."""
        skill_dir = tmp_path / "bad-meta"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad-meta\ndescription: test\n---\n\n# Bad\n"
        )
        (skill_dir / "metadata.yaml").write_text("not: valid: yaml: {{{\n")
        manifest = SkillManifest.from_skill_dir(skill_dir)
        assert manifest.type == SkillType.REGULAR
        assert manifest.depends_on.skills == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_manifest.py::TestSkillManifest -v`
Expected: FAIL with `AttributeError: type object 'SkillManifest' has no attribute 'from_skill_dir'`

**Step 3: Write the implementation**

Add to `SkillManifest` in `src/neoskills/core/manifest.py`:

```python
    @classmethod
    def from_skill_dir(cls, skill_dir: Path, tap_name: str = "") -> "SkillManifest":
        """Load SkillSpec from SKILL.md, extend with metadata.yaml if present."""
        import yaml

        spec = SkillSpec.from_skill_dir(skill_dir, tap_name)
        scope = cls._derive_scope(skill_dir)

        # Load metadata.yaml extension
        meta_file = skill_dir / "metadata.yaml"
        skill_type = SkillType.REGULAR
        deps = DependencySet()

        if meta_file.exists():
            try:
                meta = yaml.safe_load(meta_file.read_text()) or {}
            except yaml.YAMLError:
                meta = {}

            if "type" in meta:
                try:
                    skill_type = SkillType(meta["type"])
                except ValueError:
                    pass

            dep_data = meta.get("depends_on", {})
            if isinstance(dep_data, dict):
                deps = DependencySet(
                    skills=dep_data.get("skills", []),
                    tools=dep_data.get("tools", []),
                    agent=dep_data.get("agent"),
                    packages=dep_data.get("packages", []),
                )

        return cls(spec=spec, type=skill_type, scope=scope, depends_on=deps)

    @staticmethod
    def _derive_scope(skill_dir: Path) -> "Scope":
        """Auto-derive scope from filesystem location."""
        parts = skill_dir.parts
        if "plugins" in parts:
            return Scope.PLUGIN
        elif ".neoskills" in parts and "taps" in parts:
            return Scope.USER
        else:
            return Scope.PROJECT
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_manifest.py -v`
Expected: PASS (all 9 tests)

**Step 5: Commit**

```bash
git add src/neoskills/core/manifest.py tests/unit/test_manifest.py
git commit -m "feat: SkillManifest.from_skill_dir loads SKILL.md + metadata.yaml"
```

---

### Task 3: Scope Derivation Tests

**Files:**
- Test: `tests/unit/test_manifest.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_manifest.py`:

```python
class TestScopeDerivation:
    def test_user_scope(self, tmp_path: Path):
        path = tmp_path / ".neoskills" / "taps" / "mySkills" / "skills" / "my-skill"
        assert SkillManifest._derive_scope(path) == Scope.USER

    def test_project_scope(self, tmp_path: Path):
        path = tmp_path / "myproject" / "skills" / "my-skill"
        assert SkillManifest._derive_scope(path) == Scope.PROJECT

    def test_project_scope_claude_dir(self, tmp_path: Path):
        path = tmp_path / "myproject" / ".claude" / "skills" / "my-skill"
        assert SkillManifest._derive_scope(path) == Scope.PROJECT

    def test_plugin_scope(self, tmp_path: Path):
        path = tmp_path / ".neoskills" / "taps" / "mySkills" / "plugins" / "my-plugin" / "skills" / "a-skill"
        assert SkillManifest._derive_scope(path) == Scope.PLUGIN

    def test_plugin_scope_takes_priority(self, tmp_path: Path):
        """When both 'plugins' and 'taps' are in the path, plugin wins."""
        path = tmp_path / ".neoskills" / "taps" / "x" / "plugins" / "y" / "skills" / "z"
        assert SkillManifest._derive_scope(path) == Scope.PLUGIN
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_manifest.py::TestScopeDerivation -v`
Expected: PASS (all 5 — the implementation from Task 2 already handles these)

**Step 3: Commit**

```bash
git add tests/unit/test_manifest.py
git commit -m "test: add scope derivation tests for user, project, plugin"
```

---

### Task 4: Clean Up models.py — Remove Unused v0.2 Models

**Files:**
- Modify: `src/neoskills/core/models.py:28-92` (remove `Skill`, `SkillMetadata`, `Provenance`, `Target`, `Bundle`)

**Step 1: Verify nothing imports the old models**

Run: `uv run python -c "from neoskills.core.models import Skill, SkillMetadata, Provenance, Bundle, Target; print('found')"` — these should exist.

Then search for imports:

```bash
grep -r "from neoskills.core.models import" src/ --include="*.py" | grep -v SkillSpec | grep -v SkillFormat | grep -v TransportType
```

Expected: No results (nothing imports Skill, SkillMetadata, Provenance, Bundle, Target).

**Step 2: Run existing tests to confirm baseline**

Run: `uv run pytest tests/ -v`
Expected: All 79+ tests pass.

**Step 3: Remove unused models**

Edit `src/neoskills/core/models.py` — remove:
- `SkillMetadata` dataclass (lines 29-40)
- `Skill` dataclass (lines 43-53)
- `Provenance` dataclass (lines 56-66)
- `Target` dataclass (lines 69-79)
- `Bundle` dataclass (lines 82-92)

Also remove the unused `datetime` import. Keep: `SkillFormat`, `TransportType`, `SkillSpec`.

The file should become:

```python
"""Domain models for neoskills."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SkillFormat(Enum):
    """Skill file format conventions by agent."""

    CLAUDE_CODE = "claude-code"
    OPENCODE = "opencode"
    OPENCLAW = "openclaw"
    CANONICAL = "canonical"


class TransportType(Enum):
    """How skills are transferred to/from a target."""

    LOCAL_FS = "local-fs"
    SSH = "ssh"
    RSYNC = "rsync"
    ZIP = "zip"


# --- v0.3 Brew-style models ---


@dataclass
class SkillSpec:
    """Unified skill metadata derived entirely from SKILL.md frontmatter.

    Replaces the combination of Skill + SkillMetadata + Provenance.
    """

    skill_id: str
    name: str
    description: str = ""
    version: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    source: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = ""
    tap: str = ""
    path: Path | None = None

    @classmethod
    def from_skill_dir(cls, skill_dir: Path, tap_name: str = "") -> "SkillSpec":
        """Parse a SkillSpec from a skill directory containing SKILL.md."""
        from neoskills.core.frontmatter import parse_frontmatter

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"No SKILL.md in {skill_dir}")

        fm, _ = parse_frontmatter(skill_md.read_text())
        return cls(
            skill_id=skill_dir.name,
            name=fm.get("name", skill_dir.name),
            description=fm.get("description", ""),
            version=fm.get("version", ""),
            author=fm.get("author", ""),
            tags=fm.get("tags", []),
            targets=fm.get("targets", []),
            source=fm.get("source", tap_name),
            tools=fm.get("tools", []),
            model=fm.get("model", ""),
            tap=tap_name,
            path=skill_dir,
        )
```

**Step 4: Run all tests to verify nothing breaks**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add src/neoskills/core/models.py
git commit -m "refactor: remove unused v0.2 models (Skill, SkillMetadata, Provenance, Bundle, Target)"
```

---

### Task 5: SkillIndex — Multi-Scope Discovery

**Files:**
- Create: `src/neoskills/core/index.py`
- Test: `tests/unit/test_index.py`

**Step 1: Write the failing tests**

```python
# tests/unit/test_index.py
"""Tests for SkillIndex — multi-scope skill discovery."""

from pathlib import Path

import pytest

from neoskills.core.cellar import Cellar
from neoskills.core.index import SkillIndex
from neoskills.core.manifest import Scope, SkillManifest, SkillType
from neoskills.core.tap import TapManager


@pytest.fixture
def populated_cellar(tmp_path: Path) -> Cellar:
    """Cellar with a tap containing two skills, one with metadata.yaml."""
    cellar = Cellar(root=tmp_path / ".neoskills")
    cellar.initialize()

    # Create tap with skills
    tap_skills = cellar.tap_skills_dir("mySkills")
    tap_skills.mkdir(parents=True)

    # Regular skill (no metadata.yaml)
    s1 = tap_skills / "git-commit"
    s1.mkdir()
    (s1 / "SKILL.md").write_text(
        "---\nname: git-commit\ndescription: Commit helper\n---\n\n# Git Commit\n"
    )

    # Agent skill (with metadata.yaml)
    s2 = tap_skills / "evaluate-artifact"
    s2.mkdir()
    (s2 / "SKILL.md").write_text(
        "---\nname: evaluate-artifact\ndescription: Evaluate student work\n---\n\n# Eval\n"
    )
    (s2 / "metadata.yaml").write_text(
        "type: agent-skill\ndepends_on:\n  skills:\n    - rubric-builder\n  agent: tutoring-agent\n"
    )

    return cellar


class TestSkillIndex:
    def test_scan_user_skills(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        manifests = index.scan(scopes=[Scope.USER])
        assert len(manifests) == 2
        ids = {m.spec.skill_id for m in manifests}
        assert "git-commit" in ids
        assert "evaluate-artifact" in ids

    def test_scan_returns_correct_types(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        manifests = index.scan()
        by_id = {m.spec.skill_id: m for m in manifests}
        assert by_id["git-commit"].type == SkillType.REGULAR
        assert by_id["evaluate-artifact"].type == SkillType.AGENT_SKILL

    def test_scan_returns_correct_scope(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        manifests = index.scan()
        for m in manifests:
            assert m.scope == Scope.USER

    def test_get_existing_skill(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        manifest = index.get("evaluate-artifact")
        assert manifest is not None
        assert manifest.depends_on.agent == "tutoring-agent"

    def test_get_missing_skill(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        assert index.get("nonexistent") is None

    def test_search(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        results = index.search("evaluate")
        assert len(results) == 1
        assert results[0].spec.skill_id == "evaluate-artifact"

    def test_search_no_match(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        assert index.search("zzz-no-match") == []

    def test_scan_project_skills(self, populated_cellar: Cellar, tmp_path: Path):
        """Skills in a project directory are discovered with PROJECT scope."""
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)

        project_skills = tmp_path / "myproject" / "skills"
        project_skills.mkdir(parents=True)
        s = project_skills / "local-helper"
        s.mkdir()
        (s / "SKILL.md").write_text(
            "---\nname: local-helper\ndescription: Project skill\n---\n\n# Local\n"
        )

        manifests = index.scan_project(project_skills)
        assert len(manifests) == 1
        assert manifests[0].scope == Scope.PROJECT
        assert manifests[0].spec.skill_id == "local-helper"

    def test_scan_plugin_skills(self, populated_cellar: Cellar):
        """Skills inside plugins are discovered with PLUGIN scope."""
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)

        plugin_skills = populated_cellar.tap_dir("mySkills") / "plugins" / "my-plugin" / "skills"
        plugin_skills.mkdir(parents=True)
        s = plugin_skills / "plugin-skill"
        s.mkdir()
        (s / "SKILL.md").write_text(
            "---\nname: plugin-skill\ndescription: From plugin\n---\n\n# Plugin\n"
        )

        manifests = index.scan(scopes=[Scope.PLUGIN])
        assert len(manifests) == 1
        assert manifests[0].scope == Scope.PLUGIN

    def test_scan_filter_by_scope(self, populated_cellar: Cellar):
        mgr = TapManager(populated_cellar)
        index = SkillIndex(populated_cellar, mgr)
        # No project skills exist, so filtering to PROJECT returns empty
        manifests = index.scan(scopes=[Scope.PROJECT])
        assert manifests == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_index.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'neoskills.core.index'`

**Step 3: Write the implementation**

```python
# src/neoskills/core/index.py
"""SkillIndex — unified skill discovery across user, project, and plugin scopes."""

from pathlib import Path

from neoskills.core.cellar import Cellar
from neoskills.core.manifest import Scope, SkillManifest
from neoskills.core.tap import TapManager


class SkillIndex:
    """Discovers and indexes SkillManifests across all scopes."""

    def __init__(self, cellar: Cellar, tap_manager: TapManager):
        self.cellar = cellar
        self.tap_manager = tap_manager

    def scan(self, scopes: list[Scope] | None = None) -> list[SkillManifest]:
        """Scan all (or filtered) scopes, return unified manifest list."""
        scopes = scopes or [Scope.USER, Scope.PROJECT, Scope.PLUGIN]
        manifests: list[SkillManifest] = []

        if Scope.USER in scopes:
            manifests.extend(self._scan_user_skills())
        if Scope.PLUGIN in scopes:
            manifests.extend(self._scan_plugin_skills())
        # PROJECT requires explicit directory — use scan_project() directly

        return manifests

    def scan_project(self, project_skills_dir: Path) -> list[SkillManifest]:
        """Scan a project-level skills directory."""
        return self._scan_directory(project_skills_dir)

    def get(self, skill_id: str) -> SkillManifest | None:
        """Find a single skill by ID across all user and plugin scopes."""
        for manifest in self.scan():
            if manifest.spec.skill_id == skill_id:
                return manifest
        return None

    def search(self, query: str, scopes: list[Scope] | None = None) -> list[SkillManifest]:
        """Search by name/description/tags, optionally filtered by scope."""
        query_lower = query.lower()
        results = []
        for manifest in self.scan(scopes):
            text = (
                f"{manifest.spec.skill_id} {manifest.spec.name} "
                f"{manifest.spec.description} {' '.join(manifest.spec.tags)}"
            ).lower()
            if query_lower in text:
                results.append(manifest)
        return results

    def _scan_user_skills(self) -> list[SkillManifest]:
        """All skills across all taps."""
        manifests: list[SkillManifest] = []
        for tap_name in self.tap_manager.list_taps():
            skills_dir = self.cellar.tap_skills_dir(tap_name)
            for m in self._scan_directory(skills_dir, tap_name):
                manifests.append(m)
        return manifests

    def _scan_plugin_skills(self) -> list[SkillManifest]:
        """Skills inside taps/{name}/plugins/{plugin}/skills/."""
        manifests: list[SkillManifest] = []
        for tap_name in self.tap_manager.list_taps():
            plugins_dir = self.cellar.tap_plugins_dir(tap_name)
            if not plugins_dir.exists():
                continue
            for plugin_dir in sorted(plugins_dir.iterdir()):
                if not plugin_dir.is_dir():
                    continue
                plugin_skills = plugin_dir / "skills"
                if plugin_skills.exists():
                    manifests.extend(self._scan_directory(plugin_skills, tap_name))
        return manifests

    @staticmethod
    def _scan_directory(skills_dir: Path, tap_name: str = "") -> list[SkillManifest]:
        """Scan a directory of skill subdirectories, returning manifests."""
        manifests: list[SkillManifest] = []
        if not skills_dir.exists():
            return manifests
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            try:
                manifests.append(SkillManifest.from_skill_dir(skill_dir, tap_name))
            except Exception:
                continue  # skip malformed skills
        return manifests
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_index.py -v`
Expected: PASS (all 10 tests)

**Step 5: Run all tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/neoskills/core/index.py tests/unit/test_index.py
git commit -m "feat: add SkillIndex for multi-scope skill discovery"
```

---

### Task 6: Resolver — Dependency Resolution Engine

**Files:**
- Create: `src/neoskills/core/resolver.py`
- Test: `tests/unit/test_resolver.py`

**Step 1: Write the failing tests**

```python
# tests/unit/test_resolver.py
"""Tests for Resolver — dependency resolution engine."""

from pathlib import Path

import pytest

from neoskills.core.cellar import Cellar
from neoskills.core.index import SkillIndex
from neoskills.core.linker import Linker
from neoskills.core.manifest import DependencySet, SkillManifest, SkillType
from neoskills.core.resolver import CyclicDependencyError, DepIssue, Resolver
from neoskills.core.tap import TapManager


def _make_skill(cellar: Cellar, skill_id: str, deps: dict | None = None, skill_type: str = "regular"):
    """Helper: create a skill directory with SKILL.md and optional metadata.yaml."""
    skill_dir = cellar.tap_skills_dir("mySkills") / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: Test skill {skill_id}\n---\n\n# {skill_id}\n"
    )
    if deps or skill_type != "regular":
        import yaml
        meta = {"type": skill_type}
        if deps:
            meta["depends_on"] = deps
        (skill_dir / "metadata.yaml").write_text(yaml.dump(meta))
    return skill_dir


@pytest.fixture
def resolver_env(tmp_path: Path):
    """Set up cellar, tap, linker, index, resolver."""
    cellar = Cellar(root=tmp_path / ".neoskills")
    cellar.initialize()
    cellar.tap_skills_dir("mySkills").mkdir(parents=True)

    # Override target path to tmp
    target_dir = tmp_path / "claude_skills"
    target_dir.mkdir()
    config = cellar.load_config()
    config["targets"] = {"claude-code": {"skill_path": str(target_dir)}}
    cellar.save_config(config)

    mgr = TapManager(cellar)
    linker = Linker(cellar)
    index = SkillIndex(cellar, mgr)
    resolver = Resolver(index, linker)
    return cellar, mgr, linker, index, resolver


class TestResolverResolve:
    def test_no_deps(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "simple")
        manifest = index.get("simple")
        result = resolver.resolve(manifest, "claude-code")
        assert result.ok
        assert len(result.install_order) == 1
        assert result.install_order[0].spec.skill_id == "simple"

    def test_single_dep(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "dep-a")
        _make_skill(cellar, "dep-b", deps={"skills": ["dep-a"]})
        manifest = index.get("dep-b")
        result = resolver.resolve(manifest, "claude-code")
        assert result.ok
        assert len(result.install_order) == 2
        # dep-a must come before dep-b
        ids = [m.spec.skill_id for m in result.install_order]
        assert ids.index("dep-a") < ids.index("dep-b")

    def test_transitive_deps(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "base")
        _make_skill(cellar, "middle", deps={"skills": ["base"]})
        _make_skill(cellar, "top", deps={"skills": ["middle"]})
        manifest = index.get("top")
        result = resolver.resolve(manifest, "claude-code")
        assert result.ok
        ids = [m.spec.skill_id for m in result.install_order]
        assert ids.index("base") < ids.index("middle") < ids.index("top")

    def test_unresolved_skill(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "orphan", deps={"skills": ["missing-skill"]})
        manifest = index.get("orphan")
        result = resolver.resolve(manifest, "claude-code")
        assert not result.ok
        assert "missing-skill" in result.unresolved_skills

    def test_cyclic_dependency(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "cycle-a", deps={"skills": ["cycle-b"]})
        _make_skill(cellar, "cycle-b", deps={"skills": ["cycle-a"]})
        manifest = index.get("cycle-a")
        with pytest.raises(CyclicDependencyError):
            resolver.resolve(manifest, "claude-code")

    def test_package_dep_unresolved(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "needs-pkg", deps={"packages": ["nonexistent_pkg_xyz"]})
        manifest = index.get("needs-pkg")
        result = resolver.resolve(manifest, "claude-code")
        assert "nonexistent_pkg_xyz" in result.unresolved_packages


class TestResolverValidate:
    def test_validate_healthy(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "healthy")
        manifest = index.get("healthy")
        issues = resolver.validate(manifest, "claude-code")
        assert issues == []

    def test_validate_missing_dep(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        _make_skill(cellar, "broken", deps={"skills": ["ghost"]})
        manifest = index.get("broken")
        issues = resolver.validate(manifest, "claude-code")
        assert any(i.kind == "missing_skill" for i in issues)


class TestResolverCheckAll:
    def test_check_all_no_linked(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        issues = resolver.check_all("claude-code")
        assert issues == []

    def test_check_all_with_linked_broken_dep(self, resolver_env):
        cellar, mgr, linker, index, resolver = resolver_env
        skill_dir = _make_skill(cellar, "linked-broken", deps={"skills": ["missing"]})
        linker.link("linked-broken", skill_dir, "claude-code")
        issues = resolver.check_all("claude-code")
        assert len(issues) > 0
        assert any(i.skill_id == "linked-broken" for i in issues)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'neoskills.core.resolver'`

**Step 3: Write the implementation**

```python
# src/neoskills/core/resolver.py
"""Resolver — dependency resolution engine for skill manifests."""

from dataclasses import dataclass, field
from importlib.metadata import distributions
from pathlib import Path

from neoskills.core.index import SkillIndex
from neoskills.core.linker import Linker
from neoskills.core.manifest import SkillManifest


class CyclicDependencyError(Exception):
    """Raised when skill dependencies form a cycle."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"Cyclic dependency: {' -> '.join(cycle)}")


@dataclass
class DepIssue:
    """A single dependency issue."""

    skill_id: str
    kind: str  # "missing_skill" | "missing_tool" | "missing_package" | "agent_mismatch"
    detail: str


@dataclass
class ResolveResult:
    """Result of dependency resolution."""

    install_order: list[SkillManifest] = field(default_factory=list)
    unresolved_skills: list[str] = field(default_factory=list)
    unresolved_tools: list[str] = field(default_factory=list)
    unresolved_packages: list[str] = field(default_factory=list)
    agent_mismatch: str | None = None

    @property
    def ok(self) -> bool:
        return not (
            self.unresolved_skills
            or self.unresolved_tools
            or self.unresolved_packages
            or self.agent_mismatch
        )


class Resolver:
    """Dependency resolver for skill manifests."""

    def __init__(self, index: SkillIndex, linker: Linker):
        self.index = index
        self.linker = linker

    def resolve(self, manifest: SkillManifest, target: str) -> ResolveResult:
        """Walk dependency graph, return ordered install plan."""
        result = ResolveResult()

        # Topological sort via DFS
        visited: set[str] = set()
        in_stack: set[str] = set()
        order: list[SkillManifest] = []

        def visit(m: SkillManifest, path: list[str]):
            sid = m.spec.skill_id
            if sid in in_stack:
                raise CyclicDependencyError(path + [sid])
            if sid in visited:
                return
            in_stack.add(sid)
            for dep_id in m.depends_on.skills:
                dep_manifest = self.index.get(dep_id)
                if dep_manifest is None:
                    if dep_id not in result.unresolved_skills:
                        result.unresolved_skills.append(dep_id)
                else:
                    visit(dep_manifest, path + [sid])
            in_stack.remove(sid)
            visited.add(sid)
            order.append(m)

        visit(manifest, [])
        result.install_order = order

        # Check package dependencies (best-effort)
        installed_packages = {d.metadata["Name"].lower() for d in distributions()}
        for pkg_spec in manifest.depends_on.packages:
            # Strip version specifier for name check
            pkg_name = pkg_spec.split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip().lower()
            if pkg_name not in installed_packages:
                result.unresolved_packages.append(pkg_spec)

        return result

    def validate(self, manifest: SkillManifest, target: str) -> list[DepIssue]:
        """Check a single manifest for unmet dependencies."""
        issues: list[DepIssue] = []
        sid = manifest.spec.skill_id

        for dep_id in manifest.depends_on.skills:
            if self.index.get(dep_id) is None:
                issues.append(DepIssue(sid, "missing_skill", f"Depends on '{dep_id}' which is not found"))

        installed_packages = {d.metadata["Name"].lower() for d in distributions()}
        for pkg_spec in manifest.depends_on.packages:
            pkg_name = pkg_spec.split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip().lower()
            if pkg_name not in installed_packages:
                issues.append(DepIssue(sid, "missing_package", f"Package '{pkg_spec}' not installed"))

        return issues

    def check_all(self, target: str) -> list[DepIssue]:
        """Validate all linked skills — full health report."""
        issues: list[DepIssue] = []
        links = self.linker.list_links(target)

        for link_info in links:
            if not link_info["linked"] or link_info["broken"]:
                continue
            manifest = self.index.get(link_info["skill_id"])
            if manifest is not None:
                issues.extend(self.validate(manifest, target))

        return issues
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_resolver.py -v`
Expected: PASS (all 10 tests)

**Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/neoskills/core/resolver.py tests/unit/test_resolver.py
git commit -m "feat: add Resolver for dependency resolution with cycle detection"
```

---

### Task 7: Runtime Dependency Checker

**Files:**
- Create: `src/neoskills/runtime/deps.py`
- Test: `tests/unit/test_runtime_deps.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_runtime_deps.py
"""Tests for runtime dependency checking."""

from pathlib import Path

from neoskills.runtime.deps import check_deps


class TestCheckDeps:
    def test_no_metadata(self, tmp_path: Path):
        """Skill with no metadata.yaml has no issues."""
        skill_dir = tmp_path / "simple"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: simple\n---\n\n# Simple\n")
        issues = check_deps(skill_dir)
        assert issues == []

    def test_missing_package(self, tmp_path: Path):
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

    def test_installed_package_ok(self, tmp_path: Path):
        """Skill depending on an installed package (pyyaml) has no package issues."""
        skill_dir = tmp_path / "has-yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: has-yaml\n---\n\n# YAML\n")
        (skill_dir / "metadata.yaml").write_text(
            "depends_on:\n  packages:\n    - pyyaml\n"
        )
        issues = check_deps(skill_dir)
        pkg_issues = [i for i in issues if i.kind == "missing_package"]
        assert pkg_issues == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_runtime_deps.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'neoskills.runtime.deps'`

**Step 3: Write the implementation**

```python
# src/neoskills/runtime/deps.py
"""Runtime dependency verification — best-effort, opt-in."""

from importlib.metadata import distributions
from pathlib import Path

import yaml

from neoskills.core.resolver import DepIssue


def check_deps(skill_dir: Path) -> list[DepIssue]:
    """Read metadata.yaml and verify deps are available.

    Intended to be called by skills or agent runtime at load time.
    Only checks packages (skill-to-skill requires SkillIndex context).
    """
    meta_file = skill_dir / "metadata.yaml"
    if not meta_file.exists():
        return []

    try:
        meta = yaml.safe_load(meta_file.read_text()) or {}
    except yaml.YAMLError:
        return []

    dep_data = meta.get("depends_on", {})
    if not isinstance(dep_data, dict):
        return []

    issues: list[DepIssue] = []
    skill_id = skill_dir.name

    # Check packages
    installed = {d.metadata["Name"].lower() for d in distributions()}
    for pkg_spec in dep_data.get("packages", []):
        pkg_name = pkg_spec.split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip().lower()
        if pkg_name not in installed:
            issues.append(DepIssue(skill_id, "missing_package", f"Package '{pkg_spec}' not installed"))

    return issues
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_runtime_deps.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/neoskills/runtime/deps.py tests/unit/test_runtime_deps.py
git commit -m "feat: add runtime dependency checker (best-effort, opt-in)"
```

---

### Task 8: Update `create` Command — Scaffold metadata.yaml

**Files:**
- Modify: `src/neoskills/cli/create_cmd.py`
- Test: `tests/unit/test_cli.py` (add test)

**Step 1: Write the failing test**

Add to existing `tests/unit/test_cli.py` (or create inline):

```python
# In tests/unit/test_create_metadata.py
"""Test that create command scaffolds metadata.yaml."""

from pathlib import Path
from click.testing import CliRunner

from neoskills.cli.create_cmd import create
from neoskills.core.cellar import Cellar


def test_create_scaffolds_metadata_yaml(tmp_path: Path):
    cellar = Cellar(root=tmp_path / ".neoskills")
    cellar.initialize()
    # Create the default tap skills dir
    cellar.tap_skills_dir("mySkills").mkdir(parents=True)

    runner = CliRunner()
    result = runner.invoke(create, ["my-new-skill", "--root", str(cellar.root)])
    assert result.exit_code == 0

    skill_dir = cellar.tap_skills_dir("mySkills") / "my-new-skill"
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "metadata.yaml").exists()

    import yaml
    meta = yaml.safe_load((skill_dir / "metadata.yaml").read_text())
    assert meta["type"] == "regular"
    assert "depends_on" in meta
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_create_metadata.py -v`
Expected: FAIL — `metadata.yaml` doesn't exist yet.

**Step 3: Modify create_cmd.py**

Add after line 38 (`(skill_dir / "SKILL.md").write_text(...)`) in `src/neoskills/cli/create_cmd.py`:

```python
    # Scaffold metadata.yaml
    import yaml

    metadata = {
        "type": "regular",
        "depends_on": {
            "skills": [],
            "tools": [],
            "agent": None,
            "packages": [],
        },
    }
    (skill_dir / "metadata.yaml").write_text(yaml.dump(metadata, default_flow_style=False))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_create_metadata.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/neoskills/cli/create_cmd.py tests/unit/test_create_metadata.py
git commit -m "feat: create command scaffolds metadata.yaml alongside SKILL.md"
```

---

### Task 9: Update `doctor` Command — Report Dependency Issues

**Files:**
- Modify: `src/neoskills/cli/doctor_cmd.py`

**Step 1: Run existing doctor tests as baseline**

Run: `uv run pytest tests/ -k doctor -v`
Expected: All pass.

**Step 2: Modify doctor_cmd.py**

Add after the symlink health check section (after line 65) in `src/neoskills/cli/doctor_cmd.py`:

```python
    # 5. Check dependency health
    from neoskills.core.index import SkillIndex
    from neoskills.core.resolver import Resolver

    index = SkillIndex(cellar, mgr)
    resolver = Resolver(index, linker)
    dep_issues = resolver.check_all(target)
    if dep_issues:
        click.echo(f"  Dependency issues ({len(dep_issues)}):")
        for issue in dep_issues[:10]:
            click.echo(f"    - [{issue.kind}] {issue.skill_id}: {issue.detail}")
        if len(dep_issues) > 10:
            click.echo(f"    ... and {len(dep_issues) - 10} more")
        issues += len(dep_issues)
```

**Step 3: Run all tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All tests pass (doctor command still works — new section just adds info when deps exist).

**Step 4: Commit**

```bash
git add src/neoskills/cli/doctor_cmd.py
git commit -m "feat: doctor reports dependency issues via Resolver.check_all()"
```

---

### Task 10: Update `list` Command — Add --scope Filter

**Files:**
- Modify: `src/neoskills/cli/list_cmd.py`

**Step 1: Run existing list tests as baseline**

Run: `uv run pytest tests/ -k "list" -v`
Expected: All pass.

**Step 2: Modify list_cmd.py**

Add `--scope` option to the `list_skills` command. Modify lines 11-16:

```python
@click.command("list")
@click.option("--linked", is_flag=True, help="Show only linked skills.")
@click.option("--available", is_flag=True, help="Show all skills in default tap.")
@click.option("--target", default=None, help="Target agent.")
@click.option("--tap", "tap_name", default=None, help="Tap to list from.")
@click.option("--scope", "scope_filter", default=None,
              type=click.Choice(["user", "project", "plugin"], case_sensitive=False),
              help="Filter by scope.")
@click.option("--root", default=None, type=click.Path(), help="Workspace root.")
def list_skills(
    linked: bool, available: bool, target: str | None, tap_name: str | None,
    scope_filter: str | None, root: str | None,
) -> None:
```

Add scope-filtered listing after the existing branches (before the default block). Add a new branch at the top of the function body after creating cellar/mgr/linker:

```python
    if scope_filter:
        from neoskills.core.index import SkillIndex
        from neoskills.core.manifest import Scope

        index = SkillIndex(cellar, mgr)
        scope = Scope(scope_filter)
        manifests = index.scan(scopes=[scope])
        click.echo(f"Skills ({scope_filter} scope, {len(manifests)} found):")
        for m in manifests:
            type_tag = f" [{m.type.value}]" if m.type.value != "regular" else ""
            click.echo(f"  {m.spec.skill_id:40s}{type_tag}")
        return
```

Also update `info` command to show type and deps (at end of `info` function):

```python
    # Show manifest info if metadata.yaml exists
    from neoskills.core.manifest import SkillManifest
    manifest = SkillManifest.from_skill_dir(skill_path)
    if manifest.type.value != "regular":
        click.echo(f"Type:        {manifest.type.value}")
    if manifest.depends_on.skills:
        click.echo(f"Depends on:  {', '.join(manifest.depends_on.skills)}")
    if manifest.depends_on.agent:
        click.echo(f"Agent:       {manifest.depends_on.agent}")
    if manifest.depends_on.packages:
        click.echo(f"Packages:    {', '.join(manifest.depends_on.packages)}")
```

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/neoskills/cli/list_cmd.py
git commit -m "feat: list --scope filter and info shows type/deps from manifest"
```

---

### Task 11: Update `install` Command — Auto-Resolve Dependencies

**Files:**
- Modify: `src/neoskills/cli/brew_install_cmd.py`

**Step 1: Run existing tests as baseline**

Run: `uv run pytest tests/ -v`
Expected: All pass.

**Step 2: Modify brew_install_cmd.py**

After the skill is found/copied and before linking (around line 62), add dependency resolution:

```python
    # Resolve dependencies before linking
    from neoskills.core.index import SkillIndex
    from neoskills.core.manifest import SkillManifest
    from neoskills.core.resolver import CyclicDependencyError, Resolver

    index = SkillIndex(cellar, mgr)
    resolver = Resolver(index, linker)

    try:
        manifest = SkillManifest.from_skill_dir(skill_path)
    except Exception:
        manifest = None

    if manifest and manifest.depends_on.skills:
        try:
            result = resolver.resolve(manifest, target or "claude-code")
            if result.unresolved_skills:
                click.echo(f"Warning: unresolved deps: {', '.join(result.unresolved_skills)}")
            # Auto-link dependency skills (skip the skill itself, it's linked below)
            for dep_manifest in result.install_order[:-1]:
                dep_path = dep_manifest.spec.path
                if dep_path:
                    dep_action = linker.link(dep_manifest.spec.skill_id, dep_path, target)
                    if dep_action.action == "linked":
                        click.echo(f"  Auto-linked dependency: {dep_manifest.spec.skill_id}")
        except CyclicDependencyError as e:
            click.echo(f"Error: {e}")
            raise SystemExit(1)
```

Similarly, in `uninstall`, add a reverse-dependency check before line 85:

```python
    # Check if other skills depend on this one
    from neoskills.core.index import SkillIndex
    from neoskills.core.manifest import SkillManifest
    from neoskills.core.tap import TapManager

    mgr = TapManager(cellar)
    index = SkillIndex(cellar, mgr)
    dependents = []
    for m in index.scan():
        if skill_id in m.depends_on.skills:
            dependents.append(m.spec.skill_id)
    if dependents:
        click.echo(f"Warning: these skills depend on {skill_id}: {', '.join(dependents)}")
```

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/neoskills/cli/brew_install_cmd.py
git commit -m "feat: install auto-resolves deps, uninstall warns about dependents"
```

---

### Task 12: Update `link` Command — Dependency-Aware Linking

**Files:**
- Modify: `src/neoskills/cli/link_cmd.py`

**Step 1: Modify link_cmd.py**

In the single-skill `link` path (after finding skill_path, before calling `linker.link`), add:

```python
    # Check dependencies
    from neoskills.core.index import SkillIndex
    from neoskills.core.manifest import SkillManifest
    from neoskills.core.resolver import CyclicDependencyError, Resolver

    index = SkillIndex(cellar, mgr)
    resolver = Resolver(index, linker)

    try:
        manifest = SkillManifest.from_skill_dir(skill_path)
    except Exception:
        manifest = None

    if manifest and manifest.depends_on.skills:
        try:
            result = resolver.resolve(manifest, target or "claude-code")
            if result.unresolved_skills:
                click.echo(f"Warning: unresolved deps: {', '.join(result.unresolved_skills)}")
            for dep_manifest in result.install_order[:-1]:
                dep_path = dep_manifest.spec.path
                if dep_path:
                    dep_action = linker.link(dep_manifest.spec.skill_id, dep_path, target)
                    if dep_action.action == "linked":
                        click.echo(f"  Auto-linked dependency: {dep_manifest.spec.skill_id}")
        except CyclicDependencyError as e:
            click.echo(f"Error: {e}")
            raise SystemExit(1)
```

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add src/neoskills/cli/link_cmd.py
git commit -m "feat: link command auto-resolves skill dependencies"
```

---

### Task 13: Version Bump and Spec Update

**Files:**
- Modify: `src/neoskills/__init__.py`
- Modify: `src/neoskills/core/cellar.py:10` (default config version)

**Step 1: Bump version**

`src/neoskills/__init__.py`:
```python
__version__ = "0.4.0"
```

`src/neoskills/core/cellar.py` line 11:
```python
    "version": "0.4.0",
```

**Step 2: Update version test**

In `tests/unit/test_core.py` line 103, change `"0.3.1"` to `"0.4.0"`.

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/neoskills/__init__.py src/neoskills/core/cellar.py tests/unit/test_core.py
git commit -m "Bump version to 0.4.0 — skill organization and dependencies"
```

---

### Task 14: Final Integration Test

**Files:**
- Run all tests, then manual smoke test

**Step 1: Full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass (79 existing + ~28 new = ~107 total).

**Step 2: Lint check**

Run: `uv run ruff check src/ tests/`
Expected: Clean (or only pre-existing warnings).

**Step 3: Commit any fixes**

If lint issues found, fix and commit.

**Step 4: Final summary commit (if needed)**

```bash
git log --oneline -15  # review the task commits
```
