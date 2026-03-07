"""CLI commands: link, unlink — manage symlinks without touching tap contents."""

import click

from neoskills.core.cellar import Cellar
from neoskills.core.linker import Linker
from neoskills.core.tap import TapManager


@click.command()
@click.argument("skill_id", required=False)
@click.option("--all", "link_all", is_flag=True, help="Link all skills from default tap.")
@click.option("--target", default=None, help="Target agent.")
@click.option("--root", default=None, type=click.Path(), help="Workspace root.")
def link(skill_id: str | None, link_all: bool, target: str | None, root: str | None) -> None:
    """Create symlink(s) from tap skills to target."""
    from pathlib import Path

    cellar = Cellar(Path(root) if root else None)
    linker = Linker(cellar)
    mgr = TapManager(cellar)

    if link_all:
        actions = linker.link_all(cellar.default_tap_skills_dir, target)
        linked = sum(1 for a in actions if a.action == "linked")
        skipped = sum(1 for a in actions if a.action == "skipped")
        click.echo(f"Linked {linked} skills ({skipped} already linked)")
        return

    if not skill_id:
        click.echo("Provide a skill ID or use --all.")
        raise SystemExit(1)

    skill_path = mgr.get_skill_path(skill_id)
    if skill_path is None:
        click.echo(f"Skill '{skill_id}' not found in any tap.")
        raise SystemExit(1)

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

    action = linker.link(skill_id, skill_path, target)
    click.echo(f"{skill_id}: {action.action}")


@click.command()
@click.argument("skill_id", required=False)
@click.option("--all", "unlink_all_flag", is_flag=True, help="Unlink all managed skills.")
@click.option("--target", default=None, help="Target agent.")
@click.option("--root", default=None, type=click.Path(), help="Workspace root.")
def unlink(
    skill_id: str | None, unlink_all_flag: bool, target: str | None, root: str | None
) -> None:
    """Remove symlink(s) from target."""
    from pathlib import Path

    cellar = Cellar(Path(root) if root else None)
    linker = Linker(cellar)

    if unlink_all_flag:
        actions = linker.unlink_all(target)
        unlinked = sum(1 for a in actions if a.action == "unlinked")
        click.echo(f"Unlinked {unlinked} skills")
        return

    if not skill_id:
        click.echo("Provide a skill ID or use --all.")
        raise SystemExit(1)

    action = linker.unlink(skill_id, target)
    click.echo(f"{skill_id}: {action.action}")
