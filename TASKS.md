# TASKS -- Neoskills v0.4 Status

**Updated:** 2026-03-30
**Version:** 0.4.1 (released to PyPI)

---

## Completed

- [x] Ontology layer implementation (models, graph, loader, writer, engine, taxonomy, lifecycle, versioning, composition, export, scaffold)
- [x] 17 CLI ontology subcommands
- [x] 47 ontology tests + existing test suite (172 total, all passing)
- [x] Lint clean (ruff check src/ -- 0 errors)
- [x] Git rebase conflict resolved (create_cmd.py -- ontology scaffold wins over metadata.yaml)
- [x] Test fixes (test_create_metadata updated for ontology.yaml, OntologyLoader skip_defaults for test isolation)
- [x] PyPI release v0.4.1
- [x] README.md rewrite with full documentation
- [x] CLAUDE.md project guide
- [x] Integration smoke test (load, stats, validate, discover, create, enrich)

---

## Future: Post-v0.4 Enhancements

1. **Graph persistence cache** -- serialize the in-memory graph to `.neoskills/cache/graph.json` to avoid full filesystem walk on every `ontology load`. Invalidate on mtime changes.

2. **Domain-aware validation** -- `ontology validate` currently reports `belongs_to -> domain` edges as broken because domains are stored separately from skill nodes. Fix the validator to check domain nodes too.

3. **`neoskills ontology enrich-all`** -- batch enrichment across all skills. The CLI command exists but needs real-world testing with 110+ skills.

4. **Composition runtime** -- `compose` creates a `CompositionSpec` but there's no executor that actually chains skills at runtime. This would integrate with the KSTAR loop or agent runtime.

5. **MCP plugin testing** -- 7 tools added to `src/neoskills/runtime/claude/plugin.py`. Need testing inside an actual Claude Code plugin session.

6. **Ontology-aware search** -- current `neoskills search` is substring-only. Could enhance with graph-backed faceted search using the ontology indexes.

7. **Additional export formats** -- `to_cytoscape` for web visualization, beyond current Mermaid/DOT/JSON/ASCII.

---

## Design Decisions Log

| Decision | Rationale |
|----------|-----------|
| `ontology.yaml` as sidecar (not embedded in SKILL.md) | Keeps SKILL.md human-readable; ontology can evolve independently; excluded from intrinsic checksums |
| Progressive enrichment L0-L3 | Backward compatible -- bare SKILL.md still works (L0); ontology is additive |
| In-memory graph, no external DB | File-system-as-database philosophy; graph materializes from YAML at runtime |
| Inverted indexes in SkillGraph | O(1) faceted lookup by domain/type/state/tag/namespace/enrichment |
| Two-level domain taxonomy | Flat enough to be useful, deep enough for organization; defined in `taxonomy.py` |
| `metadata.yaml` superseded by `ontology.yaml` | Ontology covers everything metadata.yaml had (type, depends_on) plus lifecycle, versioning, composition |
| `OntologyLoader(skip_defaults=True)` | Test isolation -- `from_paths()` doesn't load real ~/.neoskills/ |
| Homebrew tap/install/link model preserved | Ontology layer sits above Cellar/Brew; doesn't change the deployment model |
