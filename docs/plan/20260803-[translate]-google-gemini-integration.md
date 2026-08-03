# Google Gemini Translation Integration

**Date:** 2026-08-03  
**Type:** Provider integration

## Summary

- Add an end-to-end Gemini translation provider using Google GenAI's Interactions API.
- Keep translation text-only, using separate `system_instruction` and `input` parameters and the
  existing structured `{title, content}` result contract.

## Implementation Changes

- Add `google-genai>=2.3.0` and implement `GeminiServiceProvider`.
- Send translator guidance, target language, paragraph rules, and global instructions through
  `system_instruction`.
- Send the chapter title and blank-line-separated paragraphs through `input`.
- Request structured JSON using `_StructuredTranslation.model_json_schema()`, set `store=False`,
  validate `output_text` with Pydantic, and close the client after each request.
- Convert missing configuration, missing or malformed output, invalid or empty fields, and SDK
  failures into provider-specific `TranslationServiceProviderError` messages.
- Refactor prompt construction and response normalization into provider-neutral helpers shared
  with Azure.
- Register canonical provider ID `gemini` while preserving existing Azure aliases and all current
  API and domain contracts.
- Add `GeminiSettings.api_key` sourced from `FAST_GEMINI_API_KEY`.
- Add `FAST_GEMINI_API_KEY` to the backend environment example and map Portainer's
  `GEMINI_API_KEY` into it.
- Add Google Gemini to the frontend provider catalog with `gemini-3.6-flash` as the default,
  followed by `gemini-3.5-flash`, `gemini-3.5-flash-lite`.

## Test Plan

- Test Gemini client configuration, model selection, separate system and input channels,
  stateless requests, schema configuration, client cleanup, structured parsing, and paragraph
  normalization.
- Test missing API keys, blank output, malformed JSON, invalid schemas, empty fields, and SDK
  exceptions.
- Test configuration loading and case-insensitive factory selection.
- Correct the existing Azure test double to expose `client.chat`; retain Azure production behavior
  while making paragraph separation consistent.
- Run backend tests, Ruff, and mypy, followed by frontend lint, typecheck, and production build.

## Assumptions

- No image, audio, video, document-upload, database, or public API changes are included.
- Existing persisted `providerId` and `modelId` fields support Gemini without migration.
- Generated frontend API code will not be regenerated because the HTTP contract remains unchanged.
