# Novel Media Studio — Requirements

Functional requirements for the platform. For how these are realized, see
[`architecture.md`](./architecture.md); for infrastructure and cost, see
[`deployment.md`](./deployment.md).

## Overview

Novel Media Studio is an automated pipeline that turns web novels into translated text,
narrated audio, AI-generated illustrations, and assembled video — including full
storyboard-driven animated short dramas. Heavy work runs asynchronously; AI providers are
swappable per-project via the AI Models page.

## Key capabilities

1. **Crawl** web-novel content chapter by chapter via pluggable source connectors.
2. **Segment** chapters into larger content parts by narrative content.
3. **Translate** content into a desired language using an AI LLM.
4. **Narrate** — convert text to speech for audiobook-style audio (TTS).
5. **Illustrate characters, scenes, and items** via an image AI model.
5. **Illustrate content passages** — per-passage illustration via an image AI model.
7. **Voice characters** — per-character dubbing via a multi-voice TTS model.
8. **Generate video per scene** via a video AI model.
9. **Novel Video Project** — a storyboard-driven, end-to-end "novel → animated short drama"
   pipeline (see [FR-6](#fr-6-novel-video-project)), inspired by
   [Toonflow](https://github.com/HBAI-Ltd/Toonflow-app).

---

## FR-1 — Authentication & Users

- **FR-1.1** Login page; sessions authenticated with a JWT.
- **FR-1.2** A seeded **admin** user is provisioned on first deploy.
- **FR-1.3** User-scoped data: a user sees only their own novels, projects, and AI-model configs.

## FR-2 — Library & Novel Crawling

Workflow: add a novel to the **Library**.

- **FR-2.1** The user creates a new novel item and selects an available **connector**
  (a pluggable source-site adapter).
- **FR-2.2** The connector returns a list of **trending** novels by default.
- **FR-2.3** The user can **search** or select a novel to crawl.
- **FR-2.4** The system queues a crawling job to the background worker and processes it
  chapter by chapter.
- **FR-2.5** The user can view **crawl progress** per chapter.
- **FR-2.6** The user can view the crawled **content** of each chapter.
- **FR-2.7** Adding a new source site requires only a new connector implementation
  (no core changes).
- **FR-2.8** The API can synchronously fetch and return approved source metadata before a full
  crawl job is created. The first supported source is `novel543`, validated by crawler ID and
  source URL allowlist.
- **FR-2.9** Crawler metadata fetches are cached through the generic cache provider to avoid
  repeated browser-backed fetches for the same source URL.

## FR-3 — Translation Projects

Workflow: translate an existing novel.

- **FR-3.1** On the **Projects** page, the user creates a new **translation** project for a novel.
- **FR-3.2** The user selects an AI LLM model and global/system prompts, and **previews** the
  result on a single chapter, then confirms.
- **FR-3.3** The system runs the translation with the selected configuration via the worker queue.
- **FR-3.4** The user can view **translation progress**.
- **FR-3.5** The user can view the translated language in the novel's detailed chapter view.

## FR-4 — Audio Projects

Workflow: create audio from an existing novel.

- **FR-4.1** On the **Projects** page, the user creates a new **audio** project for a novel.
- **FR-4.2** The user selects a translated language and a **voice** from supported options.
- **FR-4.3** The user can enable an **AI image-generation** model to automatically add
  illustration images.
- **FR-4.4** Or the user can **manually add** their own illustration images into groups of speeches.
- **FR-4.5** The system combines audio + images and exports a final video, with optional
  **enhancement layers** (subtitles, background music, transitions, intro/outro). The default
  video output is a free ffmpeg "Ken Burns" slideshow over the illustrations.
- **FR-4.6** Supports **per-character dubbing** (multi-voice TTS) by mapping characters to voices.

## FR-5 — Novel Video Project

A storyboard-driven, end-to-end pipeline that turns a novel (or a chapter range) into an
**animated short drama**, modeled on [Toonflow](https://github.com/HBAI-Ltd/Toonflow-app). This
is the most advanced project kind; video generation is **opt-in and metered** with a cost preview
before any spend.

- **FR-5.1 Source selection.** The user creates a **video** project for a novel, selecting the
  translated language and a chapter range.
- **FR-5.2 Script / screenplay generation.** An AI LLM adapts the selected chapters into a
  structured **script**: extracts key events (chapter event graph) to preserve long-context
  continuity, then produces a story skeleton, an adaptation strategy, and a structured screenplay
  (scenes, dialogue lines, narration). The user can edit the generated script.
- **FR-5.3 Storyboard / shot breakdown.** The script is split into ordered **shots**. Each shot
  captures: setting/scene, characters present, action/camera notes, and the dialogue/narration
  line(s) for that shot. The user can reorder, split, merge, and edit shots.
- **FR-5.4 Character library.** The system generates and maintains a **consistent character
  library** (reference images per character, reused across shots) plus **scene/background** and
  **item** assets, via the image AI model. Reuses FR-5/image capabilities.
- **FR-5.5 Per-shot imagery.** For each shot, generate a storyboard/background image; the user can
  **refine** a shot's image (regenerate, tweak prompt, or upload a replacement) before video.
- **FR-5.6 Per-shot video generation.** Each shot is rendered to a video clip via the video AI
  model (text-to-video or image-to-video from the shot's refined image). Metered per shot with a
  cost estimate shown.
- **FR-5.7 Voice & subtitles.** Per-character dubbing (multi-voice TTS) and narration are generated
  per shot; subtitles are produced from the script lines.
- **FR-5.8 Assembly & export.** Shots + audio + subtitles are **stitched** into the final video,
  with the same enhancement layers as FR-4.5 (background music, transitions, intro/outro), and
  exported.
- **FR-5.9 Progress & resumability.** The user can watch progress per stage/shot; the pipeline is
  resumable and re-runs only failed/edited shots (no double-charging on retry).
- **FR-5.10 Cost visibility.** Before running video generation, the UI shows an estimated cost
  based on shot count, clip length, and selected model; generation is explicitly confirmed.

## FR-6 — AI Models

- **FR-5.1** Configure and select AI providers/models per family: **LLM, TTS, image, video**.
- **FR-5.2** Store per-model settings and credentials securely (credentials in a secrets vault;
  never inline).
- **FR-5.3** Providers/models are **swappable per project** — including switching to cheaper tiers —
  without code changes.

## FR-7 — Web UI

- **FR-7.1** Main layout with a **left navigation panel** and a **top toolbar**.
- **FR-7.2** **Library** — list of novels.
- **FR-7.3** **Translator** — list of translation jobs.
- **FR-7.4** **Workspace** — list of projects (audio, video).
- **FR-7.5** **AI Models** — provider/model configuration and settings.
- **FR-7.6** Progress views for background jobs (crawl, translate, audio, video), updated by
  polling job status.

---

## Non-functional requirements (summary)

- **NFR-1 Async processing.** All long-running work (crawl, translate, TTS, image, video, assembly)
  runs in the background; the UI never blocks on it. (See `architecture.md` → Job lifecycle.)
- **NFR-2 Idempotency.** Retries never duplicate output or double-charge premium AI calls.
- **NFR-3 Cost control.** Infrastructure runs near-free at low volume; premium AI usage is
  per-project and cost-visible. Video generation is the dominant variable cost and is always
  opt-in/metered. (See `deployment.md` → Cost estimate.)
- **NFR-4 Extensibility.** Connectors (sources) and provider adapters (LLM/TTS/image/video) are
  pluggable without core changes.
- **NFR-5 Security.** Credentials live in a secrets vault, referenced (not stored) by config docs.
- **NFR-6 Crawler safety.** Browser-backed crawler fetches must be restricted to approved crawler
  IDs and source hosts; the API must not expose a general-purpose proxy.
