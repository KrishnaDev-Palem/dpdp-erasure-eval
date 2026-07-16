# Feature Specification: Live Model Seam Wiring

**Feature Branch**: `006-live-model-seam`

**Created**: 2026-07-09

**Status**: Accepted

**Input**: User description: "Build Feature 006 live model seam wiring: implement real ModelSeam provider adapters behind the existing Protocol so CACHE_MODE=refresh can call live models and write cache entries, while default CACHE_MODE=offline and CI remain FakeModelSeam / committed-cache only with no network and no API keys required. Target models: Anthropic Claude Sonnet 5 and Google Gemini 3.5 Flash (exact API model ids pinned in plan/research). Credentials via ANTHROPIC_API_KEY and GEMINI_API_KEY; MODEL_ID selects active model role; refresh-path documentation in quickstart; offline acceptance tests stay green; do not modify frozen export/ or committed cache unless explicitly regenerating via documented refresh; do not break Features 001–005 offline contracts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Offline Default Unchanged for CI and Clone-and-Run (Priority: P1)

An evaluator cloning the harness or a CI merge gate needs the default experience to remain fully offline: no network calls, no API keys, and all existing acceptance suites green. Default configuration uses the test double at the model seam and replays committed cache entries. Features 001–005 contracts for runners, CLI, scoring, and cache behavior remain satisfied without modification to frozen export content or committed cache entries.

**Why this priority**: Constitution Principle IV requires offline CI with no secrets. Every published number must remain reproducible from a clone. Live wiring must not regress the existing offline spine.

**Independent Test**: On a clean clone with default environment (no provider API keys, default cache mode), run the full offline acceptance suites for core, runners, gate, autonomous, report, and CLI; verify exit code 0, no network activity, and identical behavior to pre-Feature-006 baseline.

**Acceptance Scenarios**:

1. **Given** default environment with no provider API keys and default offline cache mode, **When** the full offline acceptance suite runs, **Then** all tests pass without live model credentials or network access.
2. **Given** default CLI initialization, **When** any evaluation subcommand runs, **Then** the injected model seam is the test double and results replay from committed cache — matching Feature 005 offline contract.
3. **Given** offline cache mode with a cache miss, **When** a runner requests a model response, **Then** the harness surfaces a clear cache miss error and does not silently call a live model.
4. **Given** Features 001–005 acceptance suites, **When** executed after Feature 006 lands, **Then** every previously passing offline test continues to pass without edits to frozen export content or committed cache entries.

---

### User Story 2 - Refresh Path Calls Live Models and Writes Cache (Priority: P1)

An evaluator intentionally regenerating model responses needs refresh mode to call the configured live model through provider adapters, persist raw responses (and tool-call traces for autonomous runs) into the cache using the existing key schema, and allow subsequent offline replays from the new entries. Refresh is an explicit opt-in; it is documented in quickstart and excluded from the CI merge gate.

**Why this priority**: Live model wiring is the core deliverable. Without a working refresh path that writes cache entries, evaluators cannot populate or update committed cache deliberately.

**Independent Test**: With valid provider credentials, refresh cache mode, and a single known cache miss, invoke one adjudication through a runner or CLI subcommand; verify a cache entry is written at the canonical key, contains recorded response metadata, and replays identically in subsequent offline mode.

**Acceptance Scenarios**:

1. **Given** refresh cache mode and valid credentials for the active model role, **When** a runner encounters a cache miss for an adjudication call, **Then** the live model is invoked via the provider adapter, the response is persisted to cache at the canonical key, and grading proceeds from the returned verdicts.
2. **Given** refresh cache mode and valid credentials, **When** the adversarial gate runner invokes classification on a cache miss, **Then** the live model returns a clean-or-adversarial outcome, the entry is cached, and offline replay reproduces the same classification.
3. **Given** refresh cache mode and the autonomous runner with tool-use enabled, **When** adjudication completes after tool invocations, **Then** the cache entry includes an ordered tool-call trace per the shared cache contract.
4. **Given** a cache entry written during refresh, **When** the same case is run in offline mode, **Then** the cached response is replayed with no live model call.
5. **Given** refresh mode documentation in quickstart, **When** an operator follows the documented steps, **Then** they can regenerate cache entries without modifying frozen export content and without requiring refresh in CI.

---

### User Story 3 - Provider Adapters Behind the Existing Model Seam (Priority: P1)

An evaluator comparing target models needs live provider adapters that satisfy the existing model seam contract: adjudication returns one verdict per location in context; classification accepts note text only and returns a clean-or-adversarial outcome. Two target model roles are supported — Anthropic Claude Sonnet 5 and Google Gemini 3.5 Flash — with exact provider model identifiers pinned during plan/research, not hardcoded in runners or CLI.

**Why this priority**: The seam is the injection boundary established in Feature 001. Live adapters must plug in without changing runner or CLI orchestration logic.

**Independent Test**: Inject each live adapter at the seam (or via factory with the corresponding model role), call adjudication with a minimal context bundle and classification with sample note text; verify returned verdict shapes and classification outcomes satisfy the model seam contract.

**Acceptance Scenarios**:

1. **Given** a live adapter for the Claude Sonnet 5 model role, **When** adjudication is invoked with a context bundle containing N locations, **Then** exactly N verdicts are returned with values in {erase, retain, escalate} and invalid responses raise a contract error.
2. **Given** a live adapter for the Gemini 3.5 Flash model role, **When** classify-note is invoked with adversarial note text only, **Then** the result includes outcome in {clean, adversarial} and optional detail — with no request or record fields accepted on that operation.
3. **Given** the autonomous evaluation, **When** adjudication is invoked with an optional tool registry, **Then** the live adapter supports tool-use so the model may invoke filesystem-backed retrieval tools during adjudication.
4. **Given** any runner or CLI subcommand, **When** model identity is resolved, **Then** the active model role comes from configuration (`MODEL_ID`) via the factory — runners and CLI MUST NOT embed provider-specific model strings.

---

### User Story 4 - Factory Swaps Test Double and Live Adapters via Configuration (Priority: P2)

An operator or test author needs a single factory or injection point that selects the test double for offline/default runs and the appropriate live adapter for refresh runs based on cache mode and model role — without each runner or the CLI duplicating selection logic.

**Why this priority**: Centralized factory wiring keeps Features 002–005 runners and Feature 005 CLI consistent and prevents provider logic from leaking into evaluation orchestration.

**Independent Test**: With offline cache mode, request a model seam from the factory and confirm the test double is returned; switch to refresh mode with a supported model role and valid credentials, request again, and confirm the matching live adapter is returned.

**Acceptance Scenarios**:

1. **Given** offline cache mode, **When** the factory resolves the model seam, **Then** the test double is returned regardless of whether provider API keys are set.
2. **Given** refresh cache mode and a supported model role with valid provider credentials, **When** the factory resolves the model seam, **Then** the live adapter for that role is returned.
3. **Given** refresh cache mode and an unsupported or unknown model role, **When** the factory resolves the model seam, **Then** resolution fails with a clear, actionable error before any network call.
4. **Given** refresh cache mode and a supported model role but missing provider credentials, **When** the factory resolves the model seam, **Then** resolution fails with a clear error identifying which credential is required.
5. **Given** any runner constructed with an explicitly injected seam (as in acceptance tests), **When** the runner executes, **Then** the factory default is bypassed and the injected seam is used unchanged.

---

### User Story 5 - Provider Credential Configuration (Priority: P2)

An operator running refresh locally needs provider-specific API keys read from environment variables, with example configuration committed (variable names only, no secrets). Legacy single-key configuration remains supported as a deprecated alias so existing local setups continue to work during transition.

**Why this priority**: Secret hygiene is a constitution quality gate. Provider-specific keys clarify which credential each adapter needs without breaking operators who still use the legacy variable.

**Independent Test**: Configure only provider-specific keys for one target model, run refresh for one cache miss, verify success; repeat with only the legacy alias set, verify backward-compatible fallback; run offline suite with no keys, verify green.

**Acceptance Scenarios**:

1. **Given** refresh mode and the Claude Sonnet 5 model role, **When** `ANTHROPIC_API_KEY` is set, **Then** the Anthropic adapter authenticates successfully.
2. **Given** refresh mode and the Gemini 3.5 Flash model role, **When** `GEMINI_API_KEY` is set, **Then** the Gemini adapter authenticates successfully.
3. **Given** refresh mode, a supported model role, and only the legacy `MODEL_API_KEY` environment variable set (provider-specific key unset), **When** the factory resolves credentials, **Then** the legacy key is accepted as a fallback and a deprecation notice is emitted — refresh still succeeds.
4. **Given** committed example environment file, **When** inspected, **Then** it lists `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MODEL_ID`, `CACHE_MODE`, and notes that `MODEL_API_KEY` is deprecated — with no secret values.
5. **Given** CI merge gate configuration, **When** tests run, **Then** no provider API keys are required or read.

---

### Edge Cases

- What happens when refresh mode encounters a cache hit — existing entry is replayed without a live call (refresh replaces on miss only, consistent with Feature 001 cache contract).
- What happens when a live model returns malformed or incomplete verdicts — contract error is raised; no partial cache write that would corrupt offline replay.
- What happens when a live model call fails due to network, timeout, or provider rate limits — failure is surfaced clearly; the runner does not fall back to offline cache or silently skip the case.
- What happens when `MODEL_ID` names a role with no registered live adapter — factory fails before network with an actionable message.
- What happens when both legacy and provider-specific keys are set — provider-specific key takes precedence; legacy key is ignored for that provider.
- What happens when autonomous tool-use exceeds provider limits — failure is surfaced; no silent truncation of tool-call traces in cache entries that do succeed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide live provider adapters that satisfy the existing model seam contract for adjudication and classify-note operations.
- **FR-002**: System MUST support two configured model roles — Claude Sonnet 5 (Anthropic) and Gemini 3.5 Flash (Google) — with exact provider model identifiers resolved in plan/research and configuration, not hardcoded in runners or CLI.
- **FR-003**: System MUST preserve default offline behavior: test double at the seam, committed cache replay, and no network or API keys required for default runs and CI.
- **FR-004**: System MUST implement refresh cache mode so cache misses invoke the live adapter, persist responses (including optional tool-call traces for autonomous runs) at canonical cache keys, and subsequent offline runs replay written entries.
- **FR-005**: System MUST provide a factory or injection mechanism so CLI and all runners (T1, T2, T3, adversarial gate, autonomous) obtain the correct seam implementation from cache mode and model role without duplicating provider selection logic.
- **FR-006**: System MUST read provider credentials from `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` for refresh runs, with `MODEL_API_KEY` supported as a deprecated legacy alias that falls back when the provider-specific key is unset.
- **FR-007**: System MUST resolve active model identity from `MODEL_ID` configuration; runners and CLI MUST NOT embed provider-specific model strings.
- **FR-008**: Live adjudication adapters MUST support optional tool registry injection for autonomous evaluation tool-use.
- **FR-009**: System MUST update example environment documentation with provider variable names only (no secret values).
- **FR-010**: System MUST document the refresh workflow in feature quickstart; refresh operations MUST be excluded from the CI merge gate.
- **FR-011**: All Features 001–005 offline acceptance suites MUST remain green without API keys after Feature 006 lands.
- **FR-012**: System MUST NOT modify frozen export content or committed cache entries as part of Feature 006 implementation — cache updates occur only through explicit operator-driven refresh.
- **FR-013**: On live model contract violations (invalid verdicts, malformed classification), system MUST raise a clear error and MUST NOT write a corrupt cache entry.
- **FR-014**: On missing credentials in refresh mode, system MUST fail before initiating network calls with an actionable error naming the required variable(s).

### Key Entities

- **Model seam**: The stable injection boundary for adjudication and classification; satisfied by test double (offline) or live provider adapters (refresh).
- **Provider adapter**: A live implementation of the model seam for one target model role, responsible for authentication, request formatting, response parsing, and optional tool-use bridging.
- **Model role (`MODEL_ID`)**: Logical identity used in cache keys and report metadata; maps to a provider adapter and pinned provider model identifier via configuration — not embedded in runners.
- **Cache entry**: Persisted raw model response (and optional tool-call trace) keyed by model role, runner, case, prompt hash, and sample index — unchanged schema from Feature 001.
- **Factory resolution**: Configuration-driven selection of test double versus live adapter based on cache mode, model role, and credential availability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clean clone with default environment runs the full offline acceptance suite (core, runners, gate, autonomous, report, CLI) with 100% pass rate and zero required API keys — matching pre-Feature-006 CI merge gate behavior.
- **SC-002**: An operator following quickstart refresh documentation can regenerate at least one cache entry for each supported model role (Claude Sonnet 5 and Gemini 3.5 Flash) and replay it offline with identical results.
- **SC-003**: All five evaluation runners and the CLI resolve model identity exclusively from configuration — verified by acceptance tests that swap `MODEL_ID` without code changes to runners or CLI.
- **SC-004**: Refresh-path failures (missing key, unknown model role, provider error) surface actionable errors within one command invocation — no silent fallback to live calls in offline mode or to stale cache in refresh mode.
- **SC-005**: Features 001–005 contract documents require no breaking changes; any model-seam contract additions are backward-compatible extensions (e.g., provider credential table, factory behavior).

## Assumptions

- Exact Anthropic and Google API model identifier strings will be web-verified and pinned in plan/research per Constitution Principle VI — not embedded in this specification.
- `MODEL_ID` values for the two target roles will be defined in configuration mapping (e.g., role aliases like `claude-sonnet-5` and `gemini-3.5-flash`) rather than raw provider API strings in operator-facing defaults.
- `MODEL_API_KEY` remains a deprecated legacy alias with documented fallback and deprecation notice; provider-specific keys are the preferred credential source going forward.
- Refresh replaces cache entries only on miss; explicit overwrite of existing keys is out of scope for v1 unless already defined in Feature 001 cache contract.
- Multi-model parallel sweeps in one CLI invocation are out of scope for v1.
- Committing live-generated cache entries into `main` requires an explicit human refresh-and-review workflow — not automated by this feature.
- Network connectivity and valid billing-enabled provider accounts are available to operators running refresh locally.
- Provider SDK or HTTP client dependencies added for live adapters will be justified in plan Complexity Tracking per Constitution Principle VIII.

## Dependencies

- Feature 001 shared core: model seam protocol, test double, cache contract, configuration loading.
- Features 002–004 runners: inject model seam via constructor; read `MODEL_ID` and `CACHE_MODE` through shared config.
- Feature 005 CLI: default offline seam; subcommands delegate to runners that honor cache mode.
- Existing cache key schema and entry format — no breaking changes.

## Out of Scope (v1)

- Running multiple model roles in parallel within a single CLI invocation or sweep.
- Automatically committing live responses into `main` without explicit operator refresh and review.
- Modifying frozen export content or editing committed cache entries as part of implementation (regeneration is operator-driven via refresh only).
- Adding new evaluation runners, scoring metrics, or report formats.
- Live agent calls, Postgres, or harness-side ground-truth re-derivation.
