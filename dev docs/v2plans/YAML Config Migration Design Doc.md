# YAML Config Migration — Design Doc

## Problem

The project's configuration lived in two hand-edited JSON files:
`config/config.json` / `config/sampleconfig.json` (paths, API settings,
provider selection) and `config/llm_configs.json` (LLM analysis task
definitions and prompt templates). JSON has no comment support, which makes
these files harder to document and hand-edit than they need to be. A move to
YAML was investigated specifically because the config retrieval code has
several genuinely dynamic mechanisms (path-placeholder interpolation,
provider/capability double-key lookups, task-driven dispatch, a custom
prompt templating mini-language), and it needed to be confirmed that none of
that would break under a format change before doing the work.

Three things came out of that investigation and were done together, since
all three touch the same loading code:

1. A confusing naming collision between `llm_config` and `llm_configs`.
2. A latent fragility in how config placeholders get resolved.
3. The JSON → YAML migration itself.

## 1. Renamed `llm_config` → `llm_provider_config`

`config.json` had a top-level object `llm_config` (singular — provider
selection, models, API keys). Separately, `llm_configs.json` (a whole
different file — analysis tasks + prompt templates) gets merged into the
runtime config as `config['llm_configs']` (plural). One letter apart, with
completely different content — a genuine source of confusion when reading
the code side by side.

Fix: renamed the singular object to `llm_provider_config`. This was the
minimal fix — it removes the near-typo collision without needing to also
rename the file/merged-key on the other side, which already reasonably
describes "the file with LLM-related configs" and would have touched more
call sites (`prompts.py`, `session_llm_analyzer.py`, `run_sdc.py`) for
little added clarity.

Touched: `config/sampleconfig.yaml`, `src/sdc/utils/config_loader.py`,
`src/sdc/llm/chat_api.py`.

## 2. Scoped the placeholder resolver away from `llm_configs`

There are two independent templating syntaxes in this codebase:

- **`{{double_brace}}`** — used only in path-like values under
  `project_paths` (and a few sections that reference it, like
  `logging.log_file_path`). Resolved by
  `config_loader._resolve_placeholders_recursive` (now `resolve_placeholders`)
  via plain `str.replace()`.
- **`{single_brace:directive(...)}`** — the prompt templating
  mini-language in `llm_configs.yaml`, implemented in `src/sdc/llm/prompts.py`
  (`_format_prompt_string`, `_process_placeholder`, `_split_outside_parens`).
  Supports dotted-path lookups into a `Session` object or kwargs, and list
  directives like `:each(...)`/`:join(...)`.

Before this change, `_find_and_load_config()` merged `llm_configs.json` into
`config['llm_configs']` *before* running the double-brace resolver over the
whole `config` tree — so the resolver's recursive walk reached into prompt
text too. Nothing about the two syntaxes prevented a collision; it simply
never happened because no prompt string had happened to contain literal text
like `{{cache_folder}}`. That's "correct by luck," not by design.

Fix: reordered `_find_and_load_config()` so path-placeholder resolution runs
*before* `llm_configs` is merged into `config`. The resolver now physically
cannot see prompt text — the non-collision is structural, not a matter of
prompt authors never typing a colliding substring. This was verified by
temporarily injecting a literal `{{cache_folder}}` into a prompt string,
reloading, and confirming it passed through unresolved.

This was a deliberately small, scoped fix — not a rewrite of either
templating system. The prompt engine's own hand-rolled parsing (brace
balancing, the `:each()/:join()` mini-language) was flagged as "brittle" in
discussion, but a rewrite of it was explicitly out of scope for this pass;
it's a separable concern from the collision-safety fix above.

Touched: `src/sdc/utils/config_loader.py` only.

## 3. JSON → YAML migration

### Why this was judged safe

Every dynamic retrieval mechanism in the codebase — the `{{...}}`
path-templating, the `active_provider`/`capability` double-key lookups in
`chat_api.py`/`embedding_api.py`, the task-driven `output_target.type`
dispatch in `session_llm_analyzer.py`, the dotted-path prompt lookups in
`prompts.py` — operates on the config *after* parsing. `yaml.safe_load()`
produces the same plain `dict`/`list`/`str`/`bool`/`int` shapes as
`json.load()`, so none of that consumer code needed to change. The two real
risks were format-specific, not retrieval-specific:

- **String fidelity**: the prompt templates in `llm_configs.yaml` contain
  literal `\n` escapes, single braces, and colons that are load-bearing for
  the template engine. YAML has multiple string styles (plain, quoted, block
  `|`/`>`) with different whitespace/escaping rules; the wrong one could
  silently corrupt a prompt.
- **Type coercion**: YAML auto-converts things like `yes`/`no`/`on`/`off` to
  booleans and can behave unexpectedly on unquoted strings that look like
  other types. There's no schema/validation layer in front of config values
  (see below), so a wrong coercion would fail silently rather than being
  caught at load time.

### How those risks were handled

- Every prompt string in `llm_configs.yaml` is a **double-quoted YAML
  scalar**, transcribed verbatim from the original JSON string content.
  JSON string escaping (`\n`, `\"`, `\\`) is valid inside YAML double-quoted
  scalars, so this guarantees byte-for-byte fidelity rather than relying on
  a re-typed or reformatted version. This was verified two ways: (1) a
  structural equality check (`yaml.safe_load(...) == json.load(...)`) across
  both migrated files, and (2) directly exercising
  `prompts._format_prompt_string()` against a YAML-loaded template and
  confirming correct rendering (placeholder substitution, `:each()/:join()`
  list formatting, and literal newlines all behaved identically).
- Values that YAML could otherwise auto-coerce in a meaning-changing way
  (`active_provider`, `output_target.type`, `screenconnect_ingestor.mode`,
  etc.) are explicitly double-quoted in both YAML files.

### What changed

- `config/sampleconfig.json` → `config/sampleconfig.yaml`,
  `config/llm_configs.json` → `config/llm_configs.yaml`.
- `requirements.txt`: added `PyYAML`.
- `src/sdc/utils/config_loader.py`: `json.load` → `yaml.safe_load`
  (via a new `load_yaml_config()` helper), `.json` → `.yaml` path lookups.
- `setup.py`: previously re-implemented the JSON-load + `{{...}}`-resolution
  logic independently, twice (`create_directories`, `install_test_data`) —
  a duplication that would only have grown if patched in place for YAML.
  Instead, `setup.py` now imports and reuses `load_yaml_config()` and a new
  `resolve_project_paths()` helper from `config_loader.py`, so there is a
  single implementation of "load config, resolve path placeholders" used by
  both the app and the setup script.
- `.gitignore`: `.json` config patterns → `.yaml` equivalents (including a
  new explicit `!/config/llm_configs.yaml` negation, since that file needs
  to be trackable the same way `sampleconfig.yaml` is).
- `README.md`: setup instructions updated to reference the `.yaml` filenames.

### Explicitly deferred

- **Pydantic schema validation for config.** Discussed and judged a good
  idea — pydantic supports more than type checking: `Literal[...]` can pin a
  field to an exact enumerated set (e.g. `active_provider:
  Literal["google_gemini", "local_llm"]`, or `output_target.type:
  Literal["comprehensive_json", "structured_llm_results",
  "generated_summaries"]` — the latter would catch a typo against
  `session_llm_analyzer.py`'s dispatch `if/elif` chain at load time instead
  of silently falling through at runtime), plus `Field(ge=..., le=...)`
  ranges and cross-field validators. Deferred as a separate follow-up task,
  not bundled into this migration.
- **Rewriting the prompt templating engine.** Acknowledged as brittle
  (hand-rolled brace-balance parsing, no real error recovery beyond logging
  and truncating), but that's an isolated concern from the collision-safety
  scoping fix in section 2 above, and was explicitly out of scope for this
  pass.
- **Converting an existing real `config.json`.** No conversion helper was
  written; regenerating `config.yaml` from the new sample template and
  re-entering values by hand was judged acceptable.

## Verification performed

- `tests/test_config_loader.py` passes unchanged (exercises
  `get_config_value`, which is format-agnostic).
- `setup.py` run end-to-end against a scratch copy of the project: creates
  `config.yaml` from `sampleconfig.yaml`, resolves all `project_paths`
  placeholders (including multi-hop chains like `project_root` →
  `data_folder` → `cache_folder` → `embeddings`), and creates the expected
  directory tree.
- `load_config()` run end-to-end: confirms the `llm_provider_config` rename
  took effect (`llm_config` no longer present), `llm_configs.analysis_tasks`
  keys are intact, and all path placeholders resolved correctly.
- `prompts._format_prompt_string()` exercised directly against a
  YAML-loaded prompt template with a fake session object — output matched
  expected rendering exactly, confirming the template engine works
  unmodified against YAML-sourced strings.
- Injected a literal `{{cache_folder}}` into a prompt string in
  `llm_configs.yaml`, reloaded config, and confirmed it was **not**
  resolved/mangled — proof the scoping fix in section 2 works.

## Addendum: `run_sdc.py` fixes found while testing against real data

Test data was added to the branch after the migration above and used to
actually exercise `ingest --source all`, surfacing two pre-existing
`run_sdc.py` bugs unrelated to the YAML work itself, fixed on the same
branch for convenience:

- **Ingestor signature mismatch.** `run_sdc.py` calls every ingestor
  uniformly with `start_date`/`end_date`/`filters` kwargs, but only
  `ingest_screenconnect` declared `**kwargs` to accept them — the other
  three ingestors raised `TypeError` on any `ingest` call. Fixed by adding
  `**kwargs` to `ingest_notes`, `ingest_sillytavern_chats`, and
  `ingest_syncro_tickets` (they accept and ignore the args; only
  ScreenConnect's API mode uses them).
- **Flags with undefined scope.** `--start-date`/`--end-date`/`--filter`/
  `--show-filters` only ever had real behavior for ScreenConnect, but were
  silently accepted (and silently ignored) for every other `--source`.
  `run_sdc.py` now rejects that combination with a clear `parser.error()`
  instead of no-op'ing.

## Addendum 2: further fixes and additions on the same branch

- **Restored Syncro ticket → Session transformation.** `ingest_syncro_tickets`
  loaded ticket data but never built or saved `Session` objects from it — the
  function stopped right where that logic should begin, so Syncro was the
  only ingestor producing zero output. Grafted the missing logic back in from
  an older backup of the file, adapted to use the current `SyncroGateway`
  (the backup predated that abstraction) and the current `syncro_test_ticket_file`
  config key. Also fixed a real bug found in the ported logic: it skipped
  saving the state watermark entirely if any single ticket in a batch failed
  to parse, which would cause already-successfully-processed tickets to be
  reprocessed and duplicated (session IDs are random UUIDs with no dedup) on
  every subsequent run. The watermark now advances on the max `updated_at`
  seen regardless of individual ticket failures, with a warning logged for
  skipped tickets instead.
- **Deferred `run_sdc.py`'s ingestor/processor imports.** All five ingestors
  and both processors — including `session_llm_analyzer`, which pulls in
  langchain/google-auth/cryptography — were imported unconditionally at
  module load, so even `--help` paid that cost (~10s). Moved those imports
  into each command branch instead; `--help` now returns in well under a
  second.
- **Added local LLM (OpenAI-compatible) support to `get_chat_client`.**
  `active_provider` now also accepts `local_llm`, returning a `ChatOpenAI`
  client pointed at the configured `base_url` instead of
  `ChatGoogleGenerativeAI`. `langchain-openai` was already a dependency.
  Callers only use the common LangChain chat-model interface, so no other
  code needed to change.
