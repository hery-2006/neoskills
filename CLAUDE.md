# CLAUDE.md -- neoskills

## What This Is

**neoskills** is a Homebrew-style skill manager for AI coding agents (Claude Code, OpenCode, OpenClaw). It manages skills as portable directories with SKILL.md definitions, deployed via symlinks to agent skill directories.

**Current version:** 0.4.1

## Build & Test

```bash
# Install dependencies (requires Python >= 3.13)
uv sync --dev

# Run all tests (172 tests)
uv run pytest -v

# Lint (must pass clean)
uv run ruff check src/

# Run a single test file
uv run pytest tests/unit/test_ontology.py -v

# CLI entry point
uv run neoskills --help
```

**Do NOT use pip install directly** -- use `uv` for everything. The project uses `hatchling` as build backend.

## Project Structure

```
src/neoskills/
├── __init__.py       # Version string
├── cli/              # Click CLI commands
│   ├── main.py       # Entry point, command registration (lazy imports)
│   ├── create_cmd.py # Skill scaffolding (uses ontology scaffold)
│   ├── ontology_cmd.py # 17 ontology subcommands
│   └── ...           # tap, link, list, doctor, config, etc.
├── core/             # Cellar, config, checksum, frontmatter, linker
├── ontology/         # Property graph layer (v0.4)
│   ├── models.py     # Enums + dataclasses (SkillNode, OntologyEdge, etc.)
│   ├── graph.py      # SkillGraph -- in-memory property graph
│   ├── loader.py     # Filesystem -> graph (walks taps + plugins)
│   ├── writer.py     # Graph -> filesystem (ontology.yaml)
│   ├── engine.py     # High-level API (OntologyEngine)
│   ├── taxonomy.py   # Domain taxonomy + inference
│   ├── lifecycle.py  # State machine transitions
│   ├── versioning.py # Semver ops
│   ├── composition.py # Compose/decompose skills
│   ├── export.py     # Mermaid, DOT, JSON, ASCII
│   ├── scaffold.py   # Template-based skill creation
│   └── templates/    # YAML templates for scaffolding
├── runtime/          # Agent runtime integrations
│   └── claude/
│       └── plugin.py # MCP plugin with ontology tools
└── ...
tests/
├── unit/             # 172 tests across 12 test modules
│   ├── test_ontology.py  # 47 tests for ontology layer
│   └── ...
├── integration/      # E2E workflow tests
docs/
└── ontology-design.md    # Full design document
```

## Key Architecture

- **Cellar** (`core/cellar.py`): manages `~/.neoskills/` directory, taps, config
- **Tap**: git-cloned skill repositories under `~/.neoskills/taps/`
- **Link**: symlinks from agent skill dirs to tap skill dirs
- **Ontology**: property graph over skills -- nodes + typed edges, materialized from `ontology.yaml` sidecar files at runtime

### Ontology Layer (v0.4)

The ontology uses **progressive enrichment**:
- **L0** -- bare SKILL.md (no ontology.yaml) -- still works, inferred defaults
- **L1** -- tagged: has ontology.yaml with domain, type, tags
- **L2** -- connected: has edges (requires, extends, composes, conflicts)
- **L3** -- governed: has lifecycle state, version, capability manifest

Storage: `ontology.yaml` sits alongside `SKILL.md` in each skill directory. No external database. The in-memory `SkillGraph` rebuilds from filesystem on `ontology load`.

### Key Design Decisions

- `ontology.yaml` as sidecar (not inside SKILL.md) -- keeps SKILL.md clean, excluded from checksums
- `metadata.yaml` is superseded by `ontology.yaml` -- ontology covers all its fields plus more
- Inverted indexes in SkillGraph for O(1) faceted lookup
- Two-level domain taxonomy defined in `taxonomy.py`
- Lifecycle state machine with explicit `valid_transitions` on the enum
- `OntologyLoader(skip_defaults=True)` for test isolation (don't load real ~/.neoskills/)

### Known Issues

- `ontology validate` reports "broken edges" for `belongs_to -> domain` edges because domains are stored separately from skill nodes. The validator needs domain-awareness (post-v0.4 enhancement).

## Version Management

Version is stored in **two places** that must stay in sync:
1. `pyproject.toml` -- `version = "0.4.1"`
2. `src/neoskills/__init__.py` -- `__version__ = "0.4.1"`

Both must be bumped together before a PyPI release.

## Release Process

```bash
# 1. Bump version in both files
# 2. Run tests + lint
uv run pytest -v && uv run ruff check src/
# 3. Build and upload
rm -rf dist/ && uv build
uv run twine upload dist/*
# 4. Commit and push
git add -A && git commit -m "chore: bump to vX.Y.Z" && git push
```

## Conventions

- Use `uv` (not pip) for all dependency management
- `trash` over `rm` for safety
- Each skill is a directory with at minimum a `SKILL.md`
- `ontology.yaml` is optional but recommended (progressive enrichment)
- Tests go in `tests/unit/` with `test_` prefix
- CLI commands are Click groups registered in `cli/main.py` via lazy import
- Variable naming: avoid single-letter `l` (use `lnk` for link items) per ruff E741
