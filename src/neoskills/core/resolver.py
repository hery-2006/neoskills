"""Resolver — dependency resolution engine with cycle detection.

Walks the dependency graph declared in SkillManifest.depends_on,
performs topological sorting, and reports unresolved dependencies.
"""

import re
from dataclasses import dataclass, field
from importlib.metadata import distributions

from neoskills.core.index import SkillIndex
from neoskills.core.linker import Linker
from neoskills.core.manifest import SkillManifest


class CyclicDependencyError(Exception):
    """Raised when a cycle is detected in the skill dependency graph."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"Cyclic dependency: {' -> '.join(cycle)}")


@dataclass
class DepIssue:
    """A single dependency problem found during validation."""

    skill_id: str
    kind: str  # "missing_skill" | "missing_tool" | "missing_package" | "agent_mismatch"
    detail: str


@dataclass
class ResolveResult:
    """Result of resolving a skill's full dependency tree."""

    install_order: list[SkillManifest] = field(default_factory=list)  # topologically sorted
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


def _installed_packages() -> set[str]:
    """Return the set of installed Python package names (lowercased)."""
    return {d.metadata["Name"].lower() for d in distributions() if d.metadata["Name"]}


def _strip_version_spec(pkg_spec: str) -> str:
    """Strip version specifiers from a package spec, e.g. 'foo>=1.0' -> 'foo'."""
    return re.split(r"[><=!~;]", pkg_spec)[0].strip().lower()


class Resolver:
    """Walks the skill dependency graph and produces a topological install order."""

    def __init__(self, index: SkillIndex, linker: Linker):
        self.index = index
        self.linker = linker

    def resolve(self, manifest: SkillManifest, target: str) -> ResolveResult:
        """Walk dependency graph via DFS, topological sort.

        - Resolve depends_on.skills transitively
        - Check depends_on.packages via importlib.metadata.distributions()
        - Raise CyclicDependencyError on cycles
        """
        result = ResolveResult()
        installed_pkgs = _installed_packages()

        # DFS state
        visited: set[str] = set()
        in_stack: set[str] = set()
        order: list[SkillManifest] = []

        def dfs(m: SkillManifest, path: list[str]) -> None:
            sid = m.spec.skill_id
            if sid in in_stack:
                # Find the cycle portion of the path
                cycle_start = path.index(sid)
                raise CyclicDependencyError(path[cycle_start:] + [sid])
            if sid in visited:
                return

            in_stack.add(sid)
            path.append(sid)

            # Check package dependencies
            for pkg_spec in m.depends_on.packages:
                pkg_name = _strip_version_spec(pkg_spec)
                if pkg_name not in installed_pkgs:
                    if pkg_name not in result.unresolved_packages:
                        result.unresolved_packages.append(pkg_name)

            # Check tool dependencies (tools are just recorded, not resolved transitively)
            for tool in m.depends_on.tools:
                if tool not in result.unresolved_tools:
                    result.unresolved_tools.append(tool)

            # Recurse into skill dependencies
            for dep_id in m.depends_on.skills:
                dep_manifest = self.index.get(dep_id)
                if dep_manifest is None:
                    if dep_id not in result.unresolved_skills:
                        result.unresolved_skills.append(dep_id)
                else:
                    dfs(dep_manifest, path[:])

            in_stack.discard(sid)
            visited.add(sid)
            order.append(m)

        dfs(manifest, [])
        result.install_order = order
        return result

    def validate(self, manifest: SkillManifest, target: str) -> list[DepIssue]:
        """Check a single manifest for unmet dependencies."""
        issues: list[DepIssue] = []
        sid = manifest.spec.skill_id

        # Check skill dependencies
        for dep_id in manifest.depends_on.skills:
            if self.index.get(dep_id) is None:
                issues.append(DepIssue(skill_id=sid, kind="missing_skill", detail=dep_id))

        # Check tool dependencies
        for tool in manifest.depends_on.tools:
            issues.append(DepIssue(skill_id=sid, kind="missing_tool", detail=tool))

        # Check package dependencies
        installed_pkgs = _installed_packages()
        for pkg_spec in manifest.depends_on.packages:
            pkg_name = _strip_version_spec(pkg_spec)
            if pkg_name not in installed_pkgs:
                issues.append(DepIssue(skill_id=sid, kind="missing_package", detail=pkg_name))

        # Check agent mismatch
        if manifest.depends_on.agent:
            # Extract agent type from target name for comparison
            if manifest.depends_on.agent != target:
                issues.append(
                    DepIssue(skill_id=sid, kind="agent_mismatch", detail=manifest.depends_on.agent)
                )

        return issues

    def check_all(self, target: str) -> list[DepIssue]:
        """Validate all linked skills.

        Uses linker.list_links() to find linked skills,
        then validate() each.
        """
        issues: list[DepIssue] = []
        links = self.linker.list_links(target)
        for link_info in links:
            skill_id = link_info["skill_id"]
            manifest = self.index.get(skill_id)
            if manifest is None:
                continue
            issues.extend(self.validate(manifest, target))
        return issues
