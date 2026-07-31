# Session Linking State Machine & Project Init — Design Doc

## Problem

Running a fresh install of the project end-to-end against the test data
surfaced a cluster of related problems. Two were blocking, the rest were
found while fixing them.

The blocking one: **sessions that failed to link were permanently stuck.**
`session_customer_linker.py` marked every unlinked session
`processing_status = 'error'`, and the linker only ever picks up sessions in
`'Needs Linking'`. So a session that couldn't be linked was excluded from
every subsequent run. This mattered specifically because
`chat_api.get_chat_client()` returns `None` (not an exception) when no LLM
provider is configured, and the match cascade treats that `None` exactly
like "the LLM was consulted and found nothing." The practical failure: run
the linker before configuring an LLM, and every ambiguous name is written
off as `'error'` forever — configuring a provider afterwards does not
recover them, because they are no longer eligible for processing.

The second: **the project could not be installed as a package.** The source
tree was laid out like one (`src/sdc/...`) but had no packaging metadata, so
`python -m sdc.run_sdc` only resolved when run from inside `src/`.

Four changes came out of this, done together because they all touch the same
session-status state machine, plus a fifth (packaging) that was the
precondition for testing any of it from a clean environment.

## 1. A real terminal state for "no match", separate from "error"

Conflating "the linker ran and found nothing" with "something broke" is what
made the original bug possible. These are different outcomes and need
different states:

- **`'No Match Found'`** — the cascade ran to completion and produced no
  match. Not an error. Retryable, because the input to the decision (the
  customer cache, or whether an LLM was available) can change between runs.
- **`'Linking Failed'`** — a genuine failure. Also retryable.

The naive fix — the one initially proposed — was to simply leave unmatched
sessions in `'Needs Linking'`. That does fix the stuck-forever bug, but it
overcorrects: every unmatched session would then be re-attempted on *every*
run, forever, including the LLM fallback, for names that will never match
(one-off ScreenConnect display names, for instance). Given that the whole
linking cascade exists to minimise LLM spend, silently reintroducing
unbounded per-run LLM calls is not an acceptable trade. It also leaves no
way to distinguish "never processed" from "processed, no match."

So `'No Match Found'` is terminal *by default* and re-entered only on an
explicit retry (section 4).

### Recording *why* a session went unmatched

Knowing a session is unmatched is not enough to know whether retrying it is
worthwhile. "No match, and no LLM was available" is worth retrying after
configuring a provider; "no match, with the full cascade available" probably
is not.

`get_chat_client()` is therefore probed **once per run** (not once per
session — it is a cheap constructor call, but there is no reason to repeat
it 21 times) and the result is recorded against each unmatched session in
the existing `SessionMeta.processing_log` field:

```
session_customer_linker_v2.1: no_match (no match for 'Acme Inc.' (llm_available=False))
```

`processing_log` already existed for exactly this purpose (its own field
description cites `'customer_linker_v2.1'` as the example), so this needed
no schema change. Entries from this processor are stripped before a new one
is appended, so repeated retries replace the note rather than growing the
log without bound.

Touched: `src/sdc/processors/session_customer_linker.py`.

## 2. Centralised the status vocabulary

The status values were bare string literals spread across six files with no
single definition. The spelling had already drifted: `'Needs Linking'`,
`'Linked'`, `'Complete'` and `'Reviewed'` are Title Case With Spaces, but
`'error'` was lowercase — a pre-existing inconsistency, not one introduced
here.

All of it now lives in `src/sdc/utils/constants.py`, which already served
this role for `UNDEFINED_TIMESTAMP` and the ScreenConnect constants, so this
follows the existing structure rather than inventing a new one. Alongside
the `STATUS_*` values are three frozensets that make the state machine
greppable in one place: `LINKABLE_STATUSES`, `RETRYABLE_LINK_STATUSES`,
`ANALYZABLE_STATUSES`.

`'error'` was renamed to `'Linking Failed'` to match the convention. Because
sessions written before this change still carry the old lowercase spelling
on disk, `LEGACY_STATUS_ERROR = "error"` is retained inside
`RETRYABLE_LINK_STATUSES` — a retry run therefore recovers sessions stranded
by the original bug with no data migration required. This is the only reason
that constant exists; it should not be used for new writes.

`session_v2.py`'s field description now points at the constants module
rather than restating a partial list that would drift again.

Touched: `src/sdc/utils/constants.py`, `src/sdc/models/session_v2.py`,
`src/sdc/utils/session_builder.py`, `src/sdc/ingestors/st_chat_ingestor.py`,
`src/sdc/ingestors/syncro_ticket_ingestor.py`,
`src/sdc/processors/session_customer_linker.py`,
`src/sdc/processors/session_llm_analyzer.py`.

## 3. Decoupled analysis eligibility from linking outcome

`session_llm_analyzer.py` only analysed sessions in
`['Linked', 'Complete', 'Reviewed']`. Adding `'No Match Found'` as a new
terminal state would, without further thought, have silently excluded
unmatched sessions from LLM analysis — inheriting the old `'error'`
behaviour by accident.

That is wrong on the merits. LLM analysis summarises session *content*,
which does not depend on whether a customer link was established. The
precedent is already in the codebase: SillyTavern sessions are never
linkable at all, are ingested directly as `'Complete'`, and are analysed
normally. An unlinked ScreenConnect session likewise still describes real
billable work worth titling and summarising.

`'No Match Found'` is therefore included in `ANALYZABLE_STATUSES`. Linking
state and analysis eligibility are now independent concerns.

### Dead code removed from the linker's skip logic

While tracing this, the linker's explicit non-linkable-source guard
(`unlinkable_sources = ['SillyTavern']`) turned out to be **unreachable**:
SillyTavern sessions arrive as `'Complete'`, so the status check above it
skipped them first and the guard never ran. The visible symptom was that
SillyTavern sessions were skipped with a generic status message instead of
an explanatory one, making the summary counts hard to account for.

Fix: the source check now runs *before* the status check, so the explanatory
message is actually emitted. Ordering, not deletion, was chosen because the
message has diagnostic value.

Touched: `src/sdc/processors/session_llm_analyzer.py`,
`src/sdc/processors/session_customer_linker.py`.

## 4. One generalised `--retry` flag, not four specific ones

The states above are only useful if there is a way to re-enter them. The
first sketch was a `--rerun-unmatched` flag on `process`, which was rejected
as too narrow: it is meaningful for exactly one value of `--step`, and the
same reasoning would later demand `--rerun-failed` and `--rerun-empty` for
the LLM steps — four flags describing one concept.

Instead there is a single `--retry` on `process`, with a uniform meaning:
*also re-process sessions that previously reached a terminal non-success
state for this step.*

- `customer_linking` → additionally picks up `'No Match Found'` and
  `'Linking Failed'` (and the legacy `'error'`).
- LLM analysis steps → additionally re-run sessions logged as analysed but
  holding no usable output (missing or empty), which is the failure mode
  where a call succeeded structurally but produced nothing.

Because the meaning is uniform across every step, `--step all` works without
special-casing and no `parser.error()` scope guard is needed — unlike the
ScreenConnect-only `ingest` flags, which required exactly such a guard. That
guard is a wart being tolerated, not a pattern worth extending.

Default behaviour is unchanged: a plain run touches neither unmatched
sessions nor already-analysed ones, so routine runs cost nothing extra. When
a run ends with unmatched sessions, the summary tells the operator the exact
command to recover them.

Touched: `src/sdc/run_sdc.py`, `src/sdc/processors/session_customer_linker.py`,
`src/sdc/processors/session_llm_analyzer.py`.

## 5. Packaging and project initialisation

**`pyproject.toml` (new).** Declares the project with
`package-dir = {"" = "src"}`, so `pip install -e .` makes `sdc` importable
from anywhere and `python -m sdc.run_sdc` works from the project root.
`requires-python = ">=3.11"` records the constraint reported from a clean
install attempt, where 3.10 failed to resolve the dependency set and 3.11
succeeded. See the caveat under *Verification performed* — that pin has not
been independently re-verified here.

**`requirements.txt`** pinned to exact versions, mirroring the
`pyproject.toml` dependency list, so an install is reproducible rather than
resolving to whatever is current.

**`setup.py` → `initialize_project.py` (renamed).** The old name collided
with setuptools' conventional meaning — with `pyproject.toml` present, a
`setup.py` doing unrelated interactive first-run setup is actively
misleading. The new name describes what the script does. Its config-loading
behaviour is unchanged: it still reuses `load_yaml_config()` and
`resolve_project_paths()` from `config_loader.py` rather than
re-implementing them, as established in the YAML migration.

New capabilities, driven by the observation that the original script could
hang a CI run or an agent-driven session on an interactive prompt:

- `--status` — reports whether config exists and which data directories
  contain files, so "is this project initialised?" is answerable without
  guessing.
- `--reset [input|output|cache|logs|all]` with `--yes` — clears generated
  data. **Logs are excluded from `all`** and must be named explicitly; the
  logs are usually the only record of whatever prompted the reset, so
  deleting them by default destroys the evidence.
- `--install-test-data` — headless test-data installation.
- The default interactive prompt now times out after 5 seconds and defaults
  to "no", printing the headless equivalents.

Touched: `pyproject.toml` (new), `initialize_project.py` (new),
`setup.py` (deleted), `requirements.txt`.

## Explicitly deferred

- **`'Linking Failed'` has no writer.** The constant is defined and is
  retryable, but no code path currently assigns it — both former `'error'`
  sites were genuine "no match" cases and became `'No Match Found'`. It is
  reserved for real failures (per-session cache or save errors) rather than
  being retrofitted onto paths that are not failures. Kept deliberately, not
  by oversight.
- **Single-candidate LLM disambiguation.** Observed during live testing: when
  exactly one candidate clears the viability floor but sits below the fuzzy
  threshold, the code asks the LLM to choose from a list of one — a leading
  question the model will almost always accept. In testing this produced a
  correct match (`'Acme Inc.'` → `'Acme Incorporated'`) and a dubious one
  (`'Sample Corp'` → `'Test Corp'`). Since this writes customer IDs onto
  billable work, the fix is a business-judgement call (a hard floor below
  which a lone candidate is rejected, and/or a prompt that permits "none of
  these"), not a bug fix, and is left as a separate decision.
- **Status validation via pydantic `Literal[...]`.** `processing_status`
  remains a plain `str`. Now that the vocabulary is centralised, pinning it
  is a small change — but it belongs with the config-schema validation
  already deferred in the YAML migration doc, as one piece of work.
- **Verifying the pinned dependency set.** The pins were adopted as written
  and not install-tested here (see the caveat under *Verification
  performed*). A clean `pip install -e .` on Python 3.11 is the outstanding
  check.
- **Reconciling `run_sdc.py clean` with `initialize_project.py --reset`.**
  These now overlap. `clean` is per-source operational cleanup during normal
  use; `--reset` is bulk "return to a known starting state." The distinction
  is defensible but undocumented, and deduplicating them was out of scope.

## Verification performed

All of the following ran against the bundled test data (21 sessions across
ScreenConnect, SillyTavern, SyncroRMM and notes.json), with a live Gemini
`gemini-2.5-flash-lite` provider for the LLM paths.

> **Caveat on the environment.** Verification ran in the pre-existing `sdc`
> conda environment: **Python 3.10.18**, with dependency versions *older*
> than the new pins (e.g. `langchain` 1.1.3 vs the pinned 1.2.10, `numpy`
> 1.26.4 vs 2.3.1). Two things therefore remain unverified: the pinned
> dependency set in `requirements.txt` / `pyproject.toml` has not been
> installed and exercised, and neither has `requires-python = ">=3.11"`.
> Everything below confirms the *application logic*; a clean
> `pip install -e .` on 3.11 is still outstanding and should be done before
> relying on the pins.

**The original bug, reproduced and confirmed fixed**, in three phases:

1. Linking with no provider configured: 14 linked, **3 unmatched**, 0
   errors, each recording `llm_available=False`. Under the old code these
   would have been `'error'` and permanently unrecoverable.
2. Provider configured, plain re-run: **21 skipped** — the unmatched
   sessions were *not* re-attempted, confirming no per-run LLM cost.
3. `--retry`: LLM disambiguation fired and linked 2 of the 3
   (`'Acme Inc.'` → `'Acme Incorporated'`, `'Sample Corp'` → `'Test Corp'`).
   The third recorded `llm_available=True`, correctly distinguishing
   "exhausted the cascade" from "never had the chance."

**Analysis eligibility**: the surviving `'No Match Found'` session was
analysed successfully, receiving a title (*"Server Hardware and Management
Portal Check"*) and category (*Hardware*) — confirming unlinked sessions are
no longer frozen out.

**Analyzer `--retry`**: a session's stored title was blanked while leaving
its processor entry in `processing_log`. A plain run skipped all 21; a
`--retry` run detected the empty output, re-ran exactly that one session,
restored the title, and added no duplicate log entry.

**`initialize_project.py`**: `--status` on both an uninitialised and an
initialised project; `--reset input --yes`; `--reset all logs --yes`;
`--reset all --install-test-data --yes`; and the default flow's 5-second
timeout defaulting to "no".

**Regression**: `tests/` passes (4/4) unchanged; `run --pipeline full` still
drives the linker correctly; `--list-commands` and `process -h` render the
new flag.

## Addendum: bugs found while testing

These were pre-existing or newly-introduced defects surfaced by actually
running the above, fixed on the same branch.

- **`--reset` crashed on every invocation.** `handle_reset()` looked up
  `paths.get('log_folder')`, but the config key is `logs_folder`. With no
  default supplied, this returned `None` and `os.path.normpath(None)` raised
  `TypeError`. The dict was built before target selection, so *every*
  `--reset` variant failed regardless of target. `check_status()` had the
  same typo but supplied a `''` default, so instead of crashing it silently
  reported on `os.path.normpath('')` — the current working directory.
- **`--reset ... --install-test-data` silently skipped the install.** Test
  data installation was gated on `config_created` being `True`, but a reset
  does not delete `config.yaml`, so `setup_config()` returned `False` and
  the install never ran. Directories were wiped and nothing was restored.
  Install now runs directly after a reset.
- **LLM analysis could not parse fenced JSON.** The `comprehensive_json`
  output path passed the raw response to `json.loads()`, but models
  routinely wrap JSON in a ```` ```json ```` fence. Every
  `notes_json_analysis` call failed. Added `_strip_code_fence()`; the task
  went from 4 errors to 4 analysed. (A missing `import json` in the same
  module — the reported symptom — was a separate, earlier layer of this
  same failure.)
- **`excluded_source_systems` was a no-op.** Four of the five entries in
  `llm_configs.yaml` declare `excluded_source_systems`, but the analyzer
  only ever read `applicable_source_systems`. Those four exclusions did
  nothing, so `notes.json` sessions were being analysed by every task
  despite the config saying otherwise — wasted LLM calls, failing silently.
  The analyzer now honours both keys with their own semantics: an allow-list
  and a deny-list.
- **Test-data guard misread an empty project as populated.**
  `install_test_data` used `any(os.scandir(input_folder))`, but
  `create_directories()` creates the input subfolder skeleton first — so a
  freshly initialised, genuinely empty project always tripped the "not
  empty" safeguard and refused to install. Now walks for actual files.
- **Confirmation prompts crashed instead of declining.** `input()` raised
  `EOFError` where `sys.stdin.isatty()` was true but stdin yielded EOF
  immediately (CI runners, tool harnesses), producing a `FATAL` exit from
  the broad exception handler. Both prompts now treat `EOFError` /
  `KeyboardInterrupt` as "no".
- **Stale CLI hint.** The `run --pipeline full` completion message pointed
  at `process --step llm_title`; the actual task key is `title`.
- **Dangling `'flash'` capability.** `ChatCapability` in `chat_api.py`
  listed a `'flash'` capability with no corresponding entry under any
  provider's `models` block. Removed. The `local_llm` sample config also had
  a Gemini model name pasted into its `lightweight` slot; replaced with a
  local-model placeholder.
