# Copilot Instructions

## Token-efficient commands

- Prefix shell commands with `rtk` whenever possible. Use the dedicated wrappers for search, file reads, tests, builds, linting, and git commands.
- Prefer focused commands and targeted source reads. Avoid dumping whole files or scanning the repository broadly when a narrower query can answer the question.
- Keep edits minimal and scoped to the requested behavior. Validate with the narrowest relevant test, typecheck, lint, or build command after editing.

## Codebase memory

Use the `codebase-memory` knowledge graph first for structural code questions. Its results are more precise and use less context than broad grep or repository-wide file reads.

1. Call `list_projects` and `index_status` before structural exploration.
2. Find symbols with `search_graph`, then read only the implementation with `get_code_snippet`.
3. Use `trace_path` for callers, callees, and impact analysis. Use `direction="both"` when full context is needed.
4. Use `detect_changes` to identify symbols affected by local changes.
5. Call `check_index_coverage` for every evidence path before relying on graph results. For partial, stale, skipped, or unknown coverage, inspect the reported source with `rtk read` or `rtk grep`.
6. Check `has_more` and paginate with `offset`; never treat one graph page as exhaustive.

### Tool selection

| Question                               | Preferred tool              |
| -------------------------------------- | --------------------------- |
| Find a symbol                          | `search_graph`              |
| Read an implementation                 | `get_code_snippet`          |
| Find callers or callees                | `trace_path`                |
| Assess local-change impact             | `detect_changes`            |
| Query relationships across services    | `query_graph`               |
| Search comments, config, or plain text | `search_code` or `rtk grep` |

Do not make negative, exhaustive, dead-code, or complete-impact claims from a single graph page. Index the repository only when it is not indexed or when a large external update requires fresh results. Use `rtk read` or `rtk grep` as a fallback when graph coverage is insufficient.
