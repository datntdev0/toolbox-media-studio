# Microsoft Foundry Chapter WAV and SRT

## Summary

Replace per-sentence real-time Speech SDK calls with Azure Batch Synthesis. Batch synthesis
supports audio longer than 10 minutes and returns sentence/word boundary JSON files alongside the
WAV. See the
[Microsoft Batch Synthesis documentation](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-synthesis).

Each chapter will produce exactly:

- `workspaces/{workspaceId}/{taskId}/audio.wav`
- `workspaces/{workspaceId}/{taskId}/captions.srt`

## Backend Changes

- Change `SpeechServiceProvider.synthesize` to accept the ordered chapter sentences and voice,
  returning validated WAV and SRT bytes.
- Implement Batch Synthesis REST API `2024-04-01` using one plain-text input joined with CRLF and:
  - `riff-24khz-16bit-mono-pcm`
  - `wordBoundaryEnabled: true`
  - `sentenceBoundaryEnabled: true`
  - `concatenateResult: true`
- Poll `NotStarted`/`Running` jobs every 5 seconds with a configurable 30-minute deadline. Retry
  transient polling/download failures, surface Azure failure details safely, and best-effort delete
  the remote job afterward.
- Download the result ZIP and require one WAV plus sentence and word boundary JSON. Batch outputs
  these boundary files when requested. See the
  [batch result format](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-synthesis#batch-synthesis-results).
- Build one SRT cue per source chapter sentence:
  - Prefer matching sentence-boundary records.
  - Fall back to sequential word-boundary matching when Azure segments the text differently.
  - Fail rather than publish misaligned subtitles if every source sentence cannot be matched.
  - Use source text with embedded whitespace collapsed to one SRT line; use 1-based cue numbers and
    `HH:MM:SS,mmm` timestamps.
- Reject empty sentences and payloads exceeding Azure's 2 MB batch request limit with actionable
  task errors.
- Replace progressive sentence uploads with an atomic chapter flow: synthesize, upload WAV/SRT,
  persist one result, then mark the task completed.
- Add deterministic chapter artifact uploads and remove legacy numeric WAVs and `export.wav` only
  after successful regeneration.
- Replace stored `audioUrls` with schema-versioned `audioUrl` and `subtitleUrl`; retain sentence
  hashes for source integrity. Deserialize legacy records safely but require regeneration before
  reuse.
- Use `FAST_AZURE_SPEECH_BATCH_TIMEOUT_SECONDS=1800` and
  `FAST_AZURE_SPEECH_POLL_INTERVAL_SECONDS=5`; update local/deployment examples. Remove the
  real-time Speech SDK dependency because Batch Synthesis uses REST.

## API and Frontend

- Change the task result response to:
  - `taskId`, `workspaceId`, `provider`, `voice`
  - `audioUrl`, `subtitleUrl`
  - `createdAt`, `updatedAt`
- Keep the export endpoint contract, but return the existing chapter `audioUrl` directly instead of
  downloading and concatenating files with FFmpeg.
- Regenerate the frontend API client and update the audio workspace types/normalizer.
- Fetch and parse the SRT in `AudioChapterReader`, validating cue count, order, timing, and
  normalized cue text against the displayed chapter.
- Use one `HTMLAudioElement`:
  - Whole-chapter playback runs continuously and updates the highlighted sentence from current
    time.
  - Sentence playback seeks to that cue's start and pauses at its end.
  - Existing pause/resume, navigation cleanup, errors, and download behavior remain.
- Document Blob service CORS as a deployment prerequisite: the frontend origin must be allowed to
  `GET`/`HEAD` the public SRT.

## Tests

- Provider tests: request payload/authentication, polling success and timeout, failed jobs,
  transient retries, malformed ZIPs, sentence matching, word-boundary fallback, Unicode/whitespace
  handling, and exact SRT formatting.
- Handler/blob tests: one provider call per chapter, one WAV/SRT upload, atomic persistence, reuse,
  failure behavior, and allowlisted legacy-file cleanup.
- Repository/API tests: new Cosmos wire shape, legacy deserialization, obsolete-result regeneration
  response, result contract, and direct export URL.
- Frontend validation: malformed/mismatched SRT, sentence seek/stop, continuous highlighting,
  pause/resume, chapter changes, and fetch/playback errors.
- Run backend pytest, Ruff, and mypy; regenerate the API client; then run frontend lint, typecheck,
  and production build.

## Assumptions

- Azure Speech uses a Standard tier that supports Batch Synthesis.
- Public media URLs remain acceptable.
- The worker polls synchronously, occupying the existing single workspace worker until the batch
  job finishes.
- Existing sentence-file results are not migrated automatically; rerunning a completed chapter
  regenerates it in the new format and removes its legacy WAV artifacts.
- Backend and frontend deploy together because the task-result response is intentionally changed.
