# shell-next engineering requirements

## Verified project mappings and adoption status

- Distribution: `shell-next`; import: `shell_next`; source: `src/shell_next`.
- Python: 3.14+; Windows (PowerShell 7 and cmd) and Linux Bash, with RHEL 8
  as the reference Linux platform. License: MIT, recorded in `LICENSE`.
- Runtime dependencies: Python standard library only. Development/build tools
  are in the `dev` extra and MkDocs is in the `docs` extra in `pyproject.toml`.
- Version source: `pyproject.toml`; there is no runtime `__version__` copy.
  Published tags use `v<version>`. Default branch: `main`; feature branches:
  `codex/<description>` or `codex/<issue-number>-<description>`.
- GitHub repository: https://github.com/gokurakujoudo/shell-next, remote `origin`.
  Preserve the established `release/<version>` branches (currently
  `release/0.1.1`), rather than introducing a branch named `release`.
- Contracts: `docs/development/specification.md`; architecture:
  `docs/development/architecture.md`; guides: `docs/usage.md` and
  `docs/getting-started.md`; implemented inventory: `docs/index.md` and
  `README.md`; change record: `CHANGELOG.md`. The root development
  specification and `wiki/` are earlier reference/draft material; canonical
  published documentation is in `docs/`.
- Production dependencies flow from backends and frontend to models. Preserve
  the shared lifecycle used by native and mock sessions. Original command
  objects are trusted input, not a hostile-code sandbox. Authentication secrets
  and secret stdin payloads must stay out of results and call history.
- Tests mirror responsibilities under `tests/`; shared fixtures are in
  `tests/support/`. Mock scenarios remain deterministic and free of real
  subprocesses, filesystem writes, network calls, and sleeps. Keep native
  Bash/sudo/Windows differences explicit.

The authoritative complete quality gate is `.github/workflows/ci.yml`:
Ruff check/format, strict mypy, `python scripts/quality/check_source.py`,
platform behavioral contracts, installed-wheel probes, combined 100% branch
coverage across Windows/Linux/RHEL 8, builds, and Twine checks. Per-platform
coverage collection uses a zero threshold only for combination; acceptance
still requires the combined 100% gate. Genuine platform skips are reported.

Use `venv/Scripts/python.exe` in this Windows checkout, or the selected Python
3.14+ environment elsewhere. Local handoff runs `git diff --check`,
`python -m ruff check .`, `python -m ruff format --check .`,
`python scripts/quality/check_source.py`, `python -m mypy`, documentation
checks, then `python -m pytest --cov --cov-branch --cov-report=xml`.
Report any platform-only coverage shortfall; local Windows evidence cannot
substitute for the combined hosted gate. Installed-wheel/build checks use
`python -m scripts.release.check_wheel`, `python -m build`, and
`python -m twine check dist/*`.

Documentation checks are `python -m pytest tests/docs`,
`python -m mkdocs build --strict`, and `python -m scripts.docs.validate`.
`.github/workflows/docs.yml` builds PR documentation and deploys Pages from
`main`. It generates `site/` from canonical Markdown; generated files stay ignored.

Adoption gaps: `scripts/quality/__init__.py` is empty and no local
`python -m scripts.quality` entry point exists. A consolidated local entry point,
automated architecture/capability inventory checks, complete constant/exception
policy enforcement, and executable marking of legacy examples remain required
but unimplemented. Existing source-policy checks enforce line counts, names,
and parameter/return docstrings. Newly marked `python-doc-exec` examples are
executed by the documentation tests; do not claim legacy examples are covered.
This policy adoption does not authorize an unrelated mass refactor or release.

## Established publication profile and explicit exceptions

Preserve `docs/development/release.md`: prepare versions through a PR to `main`,
squash merge after verification, then create `release/<version>` at that exact
merged commit. Do not introduce release-only commits or overwrite published tags.
Use compatibility-aware PEP 440 versions and `v<version>` tags. The dated,
nonempty release-note requirement below applies to future releases; existing
undated changelog sections are historical adoption gaps.

The requested default publication target is PyPI and matching GitHub Releases.
`.github/workflows/publish.yml` is manually dispatched and verifies exact-commit
quality evidence before building and using Trusted Publishing in environment
`pypi`. It does not currently create the matching GitHub Release. The existing
explicit alternative, `python -m scripts.release.publish`, uses configured
local Twine credentials and stages matching GitHub artifacts after the same
quality evidence. Preserve this authorized local-release option. Automatic
release-branch triggering and CI creation of matching GitHub Releases remain
adoption gaps, not completed capabilities. No publication is part of a feature
request unless the user requests it.

## Scope, project facts, and sources of truth

These requirements govern engineering quality and delivery. Keep the project's
business purpose, domain model, public behavior, and specialized architecture
in their existing sections. Read AGENTS.md, README.md, pyproject.toml, the
feature/status inventory if present, and relevant reference/development
documentation before changing code.

Record the actual distribution/import names, production source root, supported
Python versions and platforms, license, dependency policy, version source,
default branch, release branch, quality command, and documentation entry points.
Use pyproject.toml for packaging/tool metadata. Resolve license and compatibility
decisions from the project's choices; do not assume a license, Python minimum,
fixed version series, or release destination.

Reference documentation owns public contracts; executable guides own workflows;
tests own behavioral evidence; the feature inventory and README describe
implemented capability. The changelog records user-visible changes. Requirements
are not evidence of compliance: identify missing enforcement or documentation
without claiming that it already exists.

## Design and public API

- Organize production code into small packages by responsibility. Dependencies
  flow toward core types and domain logic; CLI, filesystem, network, and other
  adapters depend on the core. Avoid cyclic imports and cross-layer shortcuts.
  Package __init__.py files curate re-exports without behavioral initialization.
- Prefer the standard library and existing project mechanisms. Keep runtime
  dependencies minimal and separate development, documentation, build, and
  publishing dependencies. Do not introduce speculative abstractions or new
  backends without a concrete requirement; preserve explicitly chosen native
  integrations or dependencies.
- Design typed public APIs with explicit input validation, stable result/error
  contracts, and documented compatibility. Use __all__ to curate exports and
  ship py.typed for typed distributions. Distinguish intentional exceptions
  from unexpected failures; preserve causes and useful context.
- For asynchronous I/O and resource workflows, prefer async public entry points.
  Keep synchronous convenience boundaries explicit and prevent nested event
  loops. Pure calculations need not become async merely for uniformity.
- Define resource ownership, cleanup order, cancellation behavior, and allowed
  concurrency scope. Close caller-owned resources explicitly or through context
  managers. Document whether objects are task-, thread-, or process-safe.
  Specify cache consistency and recalculation/invalidation rules where caching
  exists; do not import another project's cache semantics by default.
- State the actual trust boundary. Do not describe trusted configuration or
  static capability checks as a hostile-code sandbox. Dynamic execution,
  reflection, imports, ambient I/O, and connectivity need an explicit role in
  the design rather than appearing accidentally through convenience helpers.

## Production source requirements

- Each production Python file has at most 200 code-bearing physical lines,
  excluding imports, declaration/attribute docstrings, pure comments, and blank
  lines. Multiline signatures, expressions, and runtime strings count by their
  physical lines. Do not compress statements or embed code in strings to evade
  the limit. Split by responsibility, not arbitrary line count.
- Production functions and classes use descriptive names without an underscore
  prefix. Only required Python protocol methods use dunder spellings. Do not
  replace meaningful names with generic internal prefixes; curate exports with
  __all__. These declaration rules do not forbid ordinary private state fields.
- Every production docstring is English rST. Functions and methods, including
  nested helpers, explain how they work, every parameter with :param name:,
  returned values with :returns: unless returning no value, and intentional
  escaping exceptions with :raises Type:. Value classes document constructor
  fields and edge cases. Use notes for useful special behavior, not repetition.
- Document every named constant and coherent constant group, including enums:
  units or absence of units, actual source, purpose, and choice rationale.
  Never invent external sources or annotate every ordinary control-flow literal.
- These size, naming, docstring, and constant requirements apply to production
  source. Tests and scripts still pass Ruff and strict mypy. Existing explicit
  project exceptions must be recorded rather than silently broadened.

## Behavioral tests and isolation

- Mirror production subsystem responsibilities in tests. A test file may cover
  several related implementation modules; each behavior has one obvious owner.
  Keep integration contracts explicit and reusable fixtures in support modules
  when actually shared. Do not require one test file per source file.
- Assert public behavior, observable state, and meaningful diagnostics rather
  than private method calls or a second implementation of the same algorithm.
  Cover sunny, rainy, boundary, and composite cases where applicable.
- Unit tests mock external connectivity, clocks, randomness, and other
  nondeterminism as needed. Isolate file I/O and enabled logs in a separate
  TemporaryDirectory per test. CLI test configuration sources are static
  fixtures declared with their cases. No test should depend on a live account.
- Include deterministic stress, concurrency, cancellation, and lifecycle/leak
  tests for relevant behavior in the ordinary full gate. Use property or
  differential tests where there is a useful invariant or independent oracle.
  Keep performance benchmarks separate from correctness acceptance.
- Require 100% production branch coverage, with no threshold reductions,
  exclusions, ignores, weakened assertions, or invented skips merely to pass.
  Report genuine platform/dependency skips explicitly and cover supported
  platforms in the appropriate environment. Use strict test markers/config.
- If filesystem or temporary-directory permissions block a tool or test, stop
  that operation and obtain the required permission. Do not relocate temporary
  files, change temporary environment variables, weaken isolation, skip checks,
  or change paths solely to bypass the restriction. Continue independent work.

## Change workflow and quality gate

- For a bug: update the relevant English contract; add a behavioral regression
  test and prove the intended failure; implement the smallest correct fix;
  prove the test passes; refactor if needed and run focused/full checks.
- For a feature: prototypes may precede the settled contract, but acceptance
  requires reference documentation and behavioral tests. Update README,
  changelog, and the feature inventory when public claims change.
- For a refactor: pass existing tests first, change production code, pass the
  same tests, then reorganize test ownership and verify again.
- Use one authoritative, reproducible quality entry point, preferably
  python -m scripts.quality if no project equivalent exists. Define its concrete
  command and environment in this file; identify it as required but unimplemented
  if it does not exist yet.
- The gate fails fast through whitespace validation, Ruff, production-policy
  checks, architecture/capability checks, strict mypy over source/tests/scripts,
  documentation checks without coverage, and full behavioral tests with branch
  coverage, including stress tests. Keep all checks in the same environment.
- Run affected checks during editing. Each completed code-refactor stage and
  final code handoff runs the full gate. Re-run after new changes, failures, or
  unresolved concerns; do not repeat unchanged successful suites without cause.
- Pure prose needs relevant structure and link checks. Execute the exact source
  of changed examples. Structural documentation changes run the documentation
  suite once without coverage; avoid chapter/series/full-gate duplication.
- Produce useful JUnit and machine-readable/browsable coverage reports when
  supported. Keep generated reports ignored. Record actual commands, results,
  skips, and tested revisions; never equate configured checks with passing ones.

## Documentation and tutorials

- Keep public documentation in English with reference contracts, practical
  guides, an accessible README, and a concise implemented-feature inventory.
  Explain behavior and limitations; never present plans as implemented features.
- Each tutorial series has a useful standalone introduction and one ordered
  table of contents. Link every published chapter; do not list planned chapters
  as available or duplicate the inventory in other documentation entry points.
  Use stable ordered topic filenames, such as NN-topic-name.md.
- Mark every complete copyable Python example with a project-specific execution
  marker, using `<!-- python-doc-exec -->` when no marker exists. Documentation
  tests extract and execute that exact Markdown source, not a copied equivalent.
- Teach the smallest useful operation first, add one concept at a time, and end
  with a realistic composition. Put observable results in inline assertions
  where practical. Explain why each result follows, what resolves or executes,
  and who owns state; do not duplicate assertions in expected-result sections.
- Examples are deterministic and independent. Mock connectivity, isolate file
  examples in TemporaryDirectory, and close async/resource scopes explicitly.
  Examples must not use production credentials or persistent external effects.
- Test chapter discovery against the single table of contents and published
  files. Update navigation and changelog when adding, renaming, reordering, or
  retiring chapters. Do not impose word counts, slogans, one test per chapter,
  or arbitrary exact example counts.
- Check relative links and anchors, CLI/API inventories, and executable snippets.
  If a site/export exists, generate it from canonical Markdown after checks,
  preserve exact examples, and validate navigation/assets. Avoid a competing
  manually maintained copy of the same documentation.

## Packaging and release integrity

- Declare build metadata, supported Python versions, license, project identity,
  and tool settings in pyproject.toml. Keep a real license file and accurate
  compatibility claims; do not silently change the license or support matrix.
- Keep one authoritative version source or verify all maintained copies agree,
  including runtime __version__ when present. Respect established version and
  tag conventions; for new projects use a documented PEP 440-compatible policy
  with compatibility-aware version increments, not a fixed release series.
- Use isolated/reproducible build tooling appropriate to the project. Build a
  wheel and source distribution from the verified release revision; include
  production code, required runtime resources, typing data, packaging metadata,
  license, and README. Keep local secrets, reports, environments, development
  scratch files, and unrelated artifacts out of distributions.
- A release is a separate requested operation. Prepare a nonempty dated
  changelog section for its version, retaining unreleased work separately.
  Check notes and metadata before promotion. Preserve the selected source SHA
  and artifact identity through the release; never silently replace a version's
  published tag or distribution.
- Do not publish, push, merge, delete branches, or contact collaborators merely
  because this policy was installed. Follow the authorized task scope, preserve
  unrelated changes, and honor existing approvals without asking again.

## GitHub feature delivery

Use issue -> feature branch -> pull request -> squash merge -> branch cleanup.

1. Create or reuse an issue in the configured GitHub repository for authorized
   feature/bug work. Record scope, public behavior, and acceptance criteria.
   Fetch the configured remote and base a feature branch on the current default
   branch. Prefer codex/<issue-number>-<description> unless the project uses an
   explicit alternative.
2. Keep implementation, tests, and documentation together. Follow the change
   workflow and full gate, commit, push, and open a PR against the default
   branch. Link the issue with Closes #number. Describe the final behavior,
   material limitations, and actual verification results.
3. Wait for all applicable checks on the exact latest PR head, including push
   and PR verification/builds. Honor required reviews and branch rules. Fix
   failures and re-check the updated head; earlier green checks do not approve
   new commits. Intentional workflow-condition exclusions are not missing
   checks. Keep PR metadata current.
4. When merging is within scope, squash merge with an expected-head-SHA guard.
   Preserve draft/review-only requests. Confirm merge and issue closure.
   Synchronize the local default branch and confirm the merged content.
5. Verify no post-review work remains on the feature branch before deleting
   its remote and local copies. Squash merges lose feature-commit ancestry;
   inspect merged content before a necessary forced local deletion. Finish
   on the default branch without discarding unrelated work.

## GitHub version publication

Use version update -> verified PR -> squash merge -> release/<version> promotion
-> CI quality/build -> PyPI -> matching Git tag and GitHub Release.

1. On a feature or dedicated release-preparation branch, update the canonical
   version and all maintained copies, including runtime metadata. Finalize a
   dated changelog section. Validate notes, run the full gate, and verify the
   latest PR's CI before squash merging.
2. Select the verified merged commit on `main`. Create `release/<version>` at
   exactly that commit and push it. Never add release-only commits, force an
   existing release branch, or publish a feature head.
3. Verify version notes and default-branch ancestry, then require the complete
   exact-commit quality gate. The configured release workflow checks quality
   evidence, builds distributions, and publishes with Trusted Publishing. Use
   least-privilege permissions, environment `pypi`, and serialized uploads.
4. After PyPI succeeds, create `v<version>` and its GitHub Release at the same
   source commit with changelog notes and the same wheel/source artifacts.
   CI automation of this final stage remains a gap; the established authorized
   local publishing command is the existing alternative. Never run competing
   publication paths for the same immutable version.
5. Verify completion, not dispatch: latest applicable CI results, successful
   registry publication, tag target, published Release, attached artifacts, and
   any applicable documentation deployment. Fetch the tag and report links.
   If PyPI succeeds and Release creation fails, retry only the failed final
   stage; never repeat a successful immutable-version upload. After uncertain
   publication, inspect remote state before any retry.
6. Keep the default and release branches. For a combined feature/release task,
   clean up the implementation branch only after publication succeeds and
   verification shows no unmerged work remains.

Apply this pipeline only when publication is part of the project and requested
task. A package deliberately not published to PyPI must state its actual release
destination instead. Missing credentials, environments, CI workflows, or required
approvals are concrete blockers to the affected stage; do not bypass branch or
registry controls or claim a release succeeded.

