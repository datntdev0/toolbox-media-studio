# Prototype Plan: Azure Foundry TTS and Sentence Playback

## Summary

Build a single-provider prototype that synthesizes chapter sentences with Microsoft Foundry
Speech, stores WAV files in the existing public blob container, exposes completed results, and
plays them in the audio chapter reader.

Prioritize the working end-to-end flow. Do not add new unit tests; only update existing tests and
fakes where interface changes would otherwise break the suite.

## Backend Changes

- Add `azure-cognitiveservices-speech`, `FAST_AZURE_SPEECH_ENDPOINT`, and
  `FAST_AZURE_SPEECH_API_KEY`; document both variables in `.env.example` and keep Speech
  credentials separate from the Foundry Responses API configuration.
- Configure `FAST_AZURE_SPEECH_TIMEOUT_SECONDS` with a 60-second default. Wait for SDK completion
  and cancellation events instead of using a blocking native Speech call; stop and fail the task
  when the timeout expires so Speech cannot freeze the API process.
- Add `SpeechServiceProvider.synthesize(text, voice) -> bytes`. Create `SpeechConfig` per call, set
  the requested voice and `Riff24Khz16BitMonoPcm`, use `SpeechSynthesizer(audio_config=None)`, and
  require a completed result with non-empty audio.
- Treat `Built-in Microsoft Foundry` as the prototype's only supported provider and fail the task
  cleanly for unsupported values.
- Add `PublicBlobProvider.upload_audio(...)`, overwriting
  `workspaces/{workspace_id}/{task_id}/{index}.wav` with MIME type `audio/wav`.
- Add `audio_urls: list[str]` to `WorkspaceResult`; serialize it as `audioUrls` and default missing
  stored fields to an empty list.
- For non-reused tasks, initialize a fresh result. For each sentence, synthesize and upload before
  appending its hash and URL together and persisting. Mark the task completed only after every
  sentence succeeds; retain partial metadata and mark the task failed after an error.
- Build the provider without validating credentials during application startup; validate them when
  synthesis is invoked.

## API and Frontend

- Add authenticated `GET /api/workspaces/{id}/tasks/{taskId}/result` with operation ID
  `get_workspace_task_result`.
- Return `taskId`, `workspaceId`, `provider`, `voice`, zero-based
  `sentences: [{ index, audioUrl }]`, `createdAt`, and `updatedAt`.
- Return 404 for a missing workspace or task, 409 for an incomplete or stale task, and 503 when
  result storage is missing, inaccessible, or contains mismatched hash/URL counts.
- Regenerate `srv-core.client.ts` and use its generated workspace-result method from
  `useAudioWorkspaceApi`.
- In `AudioChapterReader`, derive the selected task from `workspace.tasks`. Reload or reset its
  result when the chapter, language, `resultAvailable`, `sourceUpdated`, or `completedAt` changes.
- Enable playback only when a complete result matches the displayed sentence count.
- Use one active `HTMLAudioElement`: resume it after pause, stop and detach it before changing
  sentences, advance on `ended` in sequential mode, handle playback errors, and clean up on chapter
  change or unmount.
- Leave chapter text available when narration is absent and disable its playback controls.

## Verification

- Do not add new unit tests.
- Update existing tests, constructors, and fakes only where required by changed interfaces.
- Run the existing backend test suite, Ruff, and mypy.
- Regenerate the API client, then run frontend lint, typecheck, and production build.
- Manually verify successful generation, realtime result appearance, individual play/pause/resume,
  sequential playback, chapter navigation, stale results, unsupported providers, and failed Speech
  requests.

## Prototype Assumptions and Deferred Enhancements

- WAV files and unauthenticated public blob URLs are acceptable for the prototype.
- Speech calls remain sequential and failed tasks use the existing manual force-retry flow.
- Blob cleanup on workspace deletion or shortened regeneration is deferred.
- Managed identity, private media URLs, transient retries, dead-letter handling, structured
  sentence-result records, compressed audio, and new automated tests are deferred.
