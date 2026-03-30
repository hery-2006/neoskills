# neoskills

[![PyPI version](https://img.shields.io/pypi/v/neoskills.svg)](https://pypi.org/project/neoskills/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/neolaf2/neoskills/actions/workflows/ci.yml/badge.svg)](https://github.com/neolaf2/neoskills/actions/workflows/ci.yml)

**Homebrew-style skill manager for AI coding agents.**

neoskills manages portable skill definitions across agent ecosystems (Claude Code, OpenCode, OpenClaw). Browse skills in one place, sync to GitHub, deploy selectively via symlinks, and discover relationships through a built-in ontology graph.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Ontology Layer](#ontology-layer)
- [Agent Targets](#agent-targets)
- [Operating Modes](#operating-modes)
- [CLI Reference](#cli-reference)
- [Development](#development)

---

## Installation

### From PyPI (recommended)

```bash
pip install neoskills
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv tool install neoskills
```

### From source

```bash
git clone https://github.com/neolaf2/neoskills
cd neoskills
uv sync --dev
uv run neoskills --help
```

### Requirements

- **Python 3.13+** (required)
- **Git** (for tap operations)
- **uv** (recommended for development)

---

## Quick Start

```bash
# 1. Initialize the workspace
neoskills init

# 2. Add a tap (a git-hosted skill repository)
neoskills tap https://github.com/your-org/my-skills

# 3. Browse and search
neoskills list                          # all skills in your taps
neoskills list --linked                 # what's deployed to your agent
neoskills search "document processing"  # cross-tap search

# 4. Deploy a skill to your agent
neoskills install kstar-loop            # copies to tap + symlinks to agent

# 5. Create your own skill
neoskills create my-new-skill -d "What it does" --type task

# 6. Check system health
neoskills doctor
```

### What just happened?

`neoskills init` created `~/.neoskills/` with a default tap. `install` found the skill in a tap and created a symlink into your agent's skill directory (e.g., `~/.claude/skills/`). Your agent can now use the skill. `create` scaffolded a new skill with `SKILL.md` + `ontology.yaml`.

---

## How It Works

### Architecture

```
~/.neoskills/                         # Workspace root
├── config.yaml                       # Targets, taps, defaults
├── taps/                             # Git-cloned skill repositories
│   ├── mySkills/                     # Default tap
│   │   └── skills/
│   │       └── <skill-id>/
│   │           ├── SKILL.md          # Skill definition (frontmatter + body)
│   │           ├── ontology.yaml     # Graph metadata (optional, recommended)
│   │           ├── scripts/          # Executable code (optional)
│   │           ├── references/       # Supporting docs (optional)
│   │           └── assets/           # Media/templates (optional)
│   └── <other-taps>/                 # Additional skill sources
└── cache/                            # Backups and temp storage
```

### Deployment model

Skills are deployed to agents via **per-skill symlinks** (zero-copy, instantly reversible):

```
~/.claude/skills/kstar-loop  -->  ~/.neoskills/taps/mySkills/skills/kstar-loop
```

This means:
- **One source of truth** in your tap (version controlled with git)
- **Multiple agents** can link the same skill simultaneously
- **No copying** -- changes to the tap are immediately reflected
- **Reversible** -- `neoskills unlink` removes the symlink, nothing else

### Skill anatomy

Every skill is a directory with at minimum a `SKILL.md`:

```yaml
# SKILL.md frontmatter
---
name: my-skill
description: "What this skill does"
author: "Your Name"
tags: [productivity, automation]
targets: [claude-code]
---

# My Skill

Instructions, prompts, and documentation that the agent will read.
```

Optionally, an `ontology.yaml` sidecar adds graph metadata (type, domain, lifecycle, edges, versioning). See [Ontology Layer](#ontology-layer).

---

## Ontology Layer

The ontology adds a **property graph** over your skills -- nodes and typed edges stored as `ontology.yaml` sidecar files. No external database. The graph materializes from the filesystem at runtime.

### Progressive enrichment

Skills don't need full metadata on day one:

| Level | What's present | How to get there |
|-------|---------------|-----------------|
| **L0 -- Bare** | SKILL.md only | Default for all existing skills |
| **L1 -- Tagged** | + ontology.yaml with type, domain, tags | `neoskills ontology enrich <id>` |
| **L2 -- Connected** | + edges (requires, extends, composes, conflicts) | Author declares relationships |
| **L3 -- Governed** | + lifecycle state, version, capability manifest | Maintained over time |

### Discovery

```bash
# Faceted search
neoskills ontology discover --domain agent-architecture --state operational
neoskills ontology discover --type meta --text "compiler"

# Load and inspect the full graph
neoskills ontology load     # prints summary: skills, edges, domains
neoskills ontology stats    # JSON statistics
```

### Dependencies

```bash
neoskills ontology deps kstar-loop --transitive    # what it requires
neoskills ontology rdeps kstar-planner --tree       # what depends on it
neoskills ontology add-edge skill-a skill-b -t requires
```

Edge types: `requires`, `extends`, `composes_with`, `conflicts_with`, `supersedes`, `derived_from`.

### Lifecycle

Skills move through a state machine:

```
candidate --> validated --> operational --> refined --> deprecated --> archived
```

```bash
neoskills ontology lifecycle                                          # all skills by state
neoskills ontology transition my-skill validated --reason "tested"    # change state
```

### Composition

```bash
# Compose skills into a pipeline
neoskills ontology compose source-text-to-markdown research-md-to-latex \
  --mode pipeline --name md-to-paper

# Plan a decomposition
neoskills ontology split monolithic-skill sub-a sub-b sub-c
```

### Versioning

```bash
neoskills ontology version kstar-loop --bump minor   # 0.1.0 -> 0.2.0
```

### Visualization & export

```bash
neoskills ontology graph kstar-loop --depth 2 --format mermaid
neoskills ontology export --format json --output graph.json
neoskills ontology export --format dot                              # Graphviz
```

### Validation

```bash
neoskills ontology validate   # broken edges, cycles, conflicts
```

### Auto-enrichment

```bash
neoskills ontology enrich my-skill              # single skill, L0 -> L1
neoskills ontology enrich --all --level L1 --dry-run   # preview batch
neoskills ontology enrich --all --level L1             # apply batch
```

### Domain taxonomy

Skills are classified into a two-level hierarchy: agent-architecture, education, document-processing, business, knowledge-work, meta, and more. Domains are auto-inferred from skill names when possible.

See [docs/ontology-design.md](docs/ontology-design.md) for the full design document.

---

## Agent Targets

Built-in targets:

| Target | Agent | Skill path |
|--------|-------|-----------|
| `claude-code` | Claude Code | `~/.claude/skills` |
| `opencode` | OpenCode | `~/.config/opencode/skills` |

Add custom targets:

```bash
neoskills config set targets.my-agent.skill_path /path/to/skills
```

---

## Operating Modes

1. **CLI** (default) -- `neoskills` runs as a standalone command-line tool
2. **Agent-invoked tool** -- Claude Code or OpenCode calls neoskills programmatically
3. **Embedded MCP plugin** -- neoskills runs inside Claude Code as an MCP server, exposing 12+ tools including ontology operations

### Authentication (for Claude-powered features)

neoskills resolves authentication automatically:
1. **.env API key** -- loads from `./`, `.neoskills/`, or `~/.neoskills/.env`
2. **SDK subscription reuse** -- works inside Claude Code/Desktop without a key
3. **Disabled** -- non-LLM features work without any key (tap, link, list, ontology, etc.)

---

## CLI Reference

### Workspace

| Command | Description |
|---------|-------------|
| `neoskills init` | Create `~/.neoskills/` workspace |
| `neoskills config set\|get\|show` | Manage configuration |
| `neoskills doctor` | Health check (symlinks, config, taps) |
| `neoskills migrate` | Migrate from v0.2 structure to v0.3+ |

### Taps

| Command | Description |
|---------|-------------|
| `neoskills tap <url>` | Add a tap (git clone) |
| `neoskills untap <name>` | Remove a tap |
| `neoskills update [name]` | Pull latest from tap(s) |
| `neoskills upgrade` | Update all taps + refresh links |
| `neoskills push` | Commit and push tap to GitHub |

### Skills

| Command | Description |
|---------|-------------|
| `neoskills list [--linked\|--available]` | List skills |
| `neoskills search <query>` | Cross-tap search |
| `neoskills info <skill_id>` | Detailed skill info |
| `neoskills create <skill_id>` | Scaffold new skill (SKILL.md + ontology.yaml) |
| `neoskills install <skill_id>` | One-step deploy (copy + link) |
| `neoskills uninstall <skill_id>` | Remove (unlink + optionally delete) |
| `neoskills link <skill_id>` | Create symlink (tap -> target) |
| `neoskills unlink <skill_id>` | Remove symlink |

### Ontology

| Command | Description |
|---------|-------------|
| `neoskills ontology load` | Build graph, print summary |
| `neoskills ontology stats` | Graph statistics (JSON) |
| `neoskills ontology validate` | Check integrity |
| `neoskills ontology discover` | Faceted search (--domain, --type, --state, --tag, --text) |
| `neoskills ontology deps <id>` | Dependency tree |
| `neoskills ontology rdeps <id>` | Reverse dependencies |
| `neoskills ontology graph <id>` | Neighborhood graph (Mermaid/DOT/JSON) |
| `neoskills ontology lifecycle` | Skills by lifecycle state |
| `neoskills ontology transition <id> <state>` | Change state |
| `neoskills ontology add-edge <src> <tgt> -t <type>` | Add relationship |
| `neoskills ontology remove-edge <src> <tgt> -t <type>` | Remove relationship |
| `neoskills ontology version <id> --bump <level>` | Version bump (major/minor/patch) |
| `neoskills ontology compose <ids...>` | Create composite skill |
| `neoskills ontology split <id> <names...>` | Decomposition plan |
| `neoskills ontology enrich [<id>\|--all]` | Auto-enrich metadata |
| `neoskills ontology export --format <fmt>` | Export graph (json/mermaid/dot) |
| `neoskills ontology conflicts` | Report conflict edges |

### Advanced

| Command | Description |
|---------|-------------|
| `neoskills enhance audit\|normalize\|add-docs\|add-tests` | Claude-powered skill enhancement |
| `neoskills agent list\|run` | Autonomous agent operations |
| `neoskills plugin create\|validate` | Plugin scaffolding and validation |
| `neoskills schedule daily` | Memory-enabled schedule planning |

---

## Development

### Setup

```bash
git clone https://github.com/neolaf2/neoskills
cd neoskills
uv sync --dev
```

### Commands

```bash
uv run pytest -v              # run all tests (172 tests)
uv run ruff check src/        # lint
uv run neoskills --help        # run from source
```

### Project structure

```
src/neoskills/
├── cli/              # Click CLI commands
│   ├── main.py       # Entry point and command registry
│   ├── create_cmd.py # Skill scaffolding
│   ├── ontology_cmd.py # 17 ontology subcommands
│   └── ...           # tap, link, list, doctor, etc.
├── core/             # Cellar, config, checksum, frontmatter, linker
├── ontology/         # Property graph layer (v0.4)
│   ├── models.py     # Enums + dataclasses (SkillNode, OntologyEdge, etc.)
│   ├── graph.py      # SkillGraph -- in-memory property graph
│   ├── loader.py     # Filesystem -> graph
│   ├── writer.py     # Graph -> filesystem (ontology.yaml)
│   ├── engine.py     # High-level API (OntologyEngine)
│   ├── taxonomy.py   # Domain taxonomy + inference
│   ├── lifecycle.py  # State machine transitions
│   ├── versioning.py # Semver operations
│   ├── composition.py # Compose/decompose skills
│   ├── export.py     # Mermaid, DOT, JSON, ASCII tree
│   └── scaffold.py   # Template-based skill creation
├── runtime/          # Agent runtime integrations
│   └── claude/
│       └── plugin.py # MCP plugin (12+ tools)
└── __init__.py
tests/
├── unit/             # 172 tests across 12 test modules
└── integration/      # End-to-end workflow tests
docs/
└── ontology-design.md  # Full ontology design document
```

### Release process

```bash
# 1. Bump version in pyproject.toml and src/neoskills/__init__.py
# 2. Build and upload
uv build
uv run twine upload dist/*

# 3. Verify
pip install --upgrade neoskills && neoskills --version
```

---

## License

MIT -- see [LICENSE](LICENSE)

## Author

Richard Tong
