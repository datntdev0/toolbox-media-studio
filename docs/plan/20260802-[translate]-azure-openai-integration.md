# Translation Task Lifecycle and Azure OpenAI Structured Outputs

**Date:** 2026-08-02  
**Type:** Refactor and provider integration

## Summary

Refactor translations so projects start with no tasks. Submitting a chapter-range job creates or
refreshes only the selected tasks; novel synchronization no longer changes the task manifest.
Remove `translation_service.py`, move its orchestration into the translation router, and integrate
Azure OpenAI structured outputs using `{ title: string, content: string }`.

## Implementation Changes

### Translation lifecycle and persistence

- Create translations with `tasks=[]` and zeroed task progress after validating the novel.
- Remove `PATCH /api/translations/{id}/sync`, its domain/response types, converters, frontend
  client method, UI state, button, and notifications.
- Change `queue_tasks` to accept task snapshots built from the selected current novel chapters
  rather than selecting from pre-existing tasks.
- At job submission:
  - Resolve the inclusive one-based range against live novel chapters.
  - Upsert task metadata by chapter ID and preserve tasks outside the range.
  - Skip already queued/running tasks unless `force=true`.
  - Preserve existing-result behavior: `refetch=false` reuses a result; `refetch=true` regenerates
    it.
  - Persist the upsert and queued state atomically before publishing queue events.
- Keep stop, claim, completion, failure, retry, progress, result, and realtime behavior task-based.
- Block changing `novelId` once any task exists. Users must create another translation project for
  a different novel.
- Manual result editing remains task-only; chapters never submitted through a job cannot create
  translation tasks through the result endpoint.
- Preserve existing persisted tasks without migration. Legacy task documents and results remain
  readable.

### Router ownership

- Delete `app/services/translation_service.py`, its service tests, dependency factory, and
  `ServiceTranslationDep`.
- Move create, list, detail, update, delete, novel resolution, status transitions, result cleanup,
  and response enrichment into `routers/translations.py` using repository injections.
- Retain optimistic-concurrency retries and existing HTTP status behavior.
- Move service-level coverage into route and repository tests.

### Frontend chapter and progress model

- Fetch translation detail and novel detail separately.
- Build the chapter list from the current novel manifest and merge translation task state by
  chapter ID.
- Chapters without tasks appear as `not_started`; source availability and chapter metadata come
  from the novel.
- Use task rollups for the progress bar: completed, total, queued, running, and failed tasks.
- Display the novel chapter count separately from task totals.
- Disable translated-content creation/editing until the selected chapter has a task.
- Rehydrate the novel manifest after detail, start, stop, and realtime refresh operations.
- Regenerate `srv-core.client.ts` after removing the sync API.

### Azure OpenAI structured outputs

- Rename configuration to `AzureOpenAISettings` / `AppConfig.azure_openai`.
- Replace environment variables everywhere, without fallback to the old names:
  - `FAST_AZURE_OPENAI_ENDPOINT`
  - `FAST_AZURE_OPENAI_API_KEY`
- Update deployment mappings to use `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`; document
  the endpoint as the full `https://<resource>.openai.azure.com/openai/v1/` base URL.
- Keep the existing Microsoft Foundry provider class and provider IDs for
  persisted-configuration compatibility.
- Use key-based `OpenAI` authentication and `client.beta.chat.completions.parse(...)` with a
  Pydantic model containing required `title: str` and `content: str`.
- Convert the parsed content string into the existing paragraph-array result contract after
  validating non-empty title and content.
- Handle refusals, missing parsed output, and SDK failures as translation provider errors; remove
  the regex/XML response parser.
- Raise minimum dependencies to versions supporting structured parsing (`openai>=1.42`,
  `pydantic[email]>=2.8.2`), following the
  [Microsoft structured outputs example](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs?pivots=programming-language-python&tabs=python-secure%2Cdotnet-entra-id).

## Public Interface Changes

- Removed: `PATCH /api/translations/{id}/sync`, `TranslationSyncResponse`, sync change counters,
  and generated `sync_translation`.
- Unchanged: translation start request range, force/refetch flags, task/result endpoints, and
  paragraph-array preview/result responses.
- Behavioral change: new translation detail responses initially contain no tasks and zero task
  progress.
- Configuration change: deployments must provide the new Azure OpenAI environment variable names.

## Test Plan

- Verify creation returns an empty task list while the frontend still displays all novel chapters.
- Verify a partial-range job creates only selected tasks, queues events, and calculates progress
  from those tasks.
- Verify repeated, forced, refetching, stopped, completed, failed, and overlapping jobs retain the
  selected retry semantics.
- Verify unavailable/empty chapter ranges, missing configuration, stale ETags, missing
  translations, and queue publication failures.
- Verify changing novels is rejected after any task exists and manual editing rejects chapters
  without tasks.
- Verify legacy serialized task documents remain readable without migration.
- Verify the sync route and generated client method are absent.
- Mock Azure OpenAI to cover parsed `{title, content}`, paragraph splitting, refusal, empty output,
  missing credentials, and SDK failure.
- Run backend `pytest`, Ruff, and mypy; regenerate the API client; run frontend lint, typecheck, and
  production build.

## Assumptions

- Existing task data is preserved as-is; no cleanup or backfill is included.
- Novel chapters are obtained through the existing novel detail endpoint rather than being added
  to translation responses.
- Provider identifiers and frontend model choices remain unchanged.
- The structured `content` field is a single string, while external preview and stored result
  contracts continue using paragraph arrays.
