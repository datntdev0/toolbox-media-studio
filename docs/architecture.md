# Novel Media Studio — Architecture

An automated pipeline that turns web novels into translated text, narrated audio,
AI-generated illustrations, and assembled video. This document describes the system
design; see [`deployment.md`](./deployment.md) for infrastructure, CI/CD, and cost.

## Design decisions

1. **Provider posture: premium quality.** Default to the best providers (Claude/GPT for
   translation, ElevenLabs/Azure Neural HD for voice, gpt-image-1/Imagen for illustrations,
   Veo/Kling for video). Providers stay swappable per-project via the "AI Models" page, so
   cheaper tiers can be chosen without code changes.
2. **Web tier:** Nuxt and FastAPI each on an Azure App Service (one shared plan). The browser
   calls FastAPI **directly** (CORS + JWT) — no Nitro BFF.
3. **Job lifecycle via API-owned business queues:** Azure Storage Queues decouple long-running
   work from request/response paths. The first queue is `crawler-jobs`; future capabilities can
   add their own queues while FastAPI hosts the consumers with APScheduler.
4. **Video: slideshow first.** Default output is a free ffmpeg "Ken Burns" slideshow
   (stills + audio); true per-scene AI video generation is a later, opt-in, metered feature.

## System diagram

```mermaid
flowchart TB
    Browser["Browser — Vue SPA"]
    Nuxt["Nuxt<br/>App Service #1 (Node)"]
    API["FastAPI<br/>App Service #2 (Python)<br/>auth · CRUD · crawler metadata/jobs<br/>queue consumers (Always On)"]
    Queue["Azure Storage Queues<br/><b>crawler-jobs</b><br/><b>crawler-jobs-dead-letter</b>"]
    Cosmos[("Cosmos DB<br/>serverless")]
    Blob[("Blob Storage<br/>all binaries")]
    Files[("Azure Files<br/>ffmpeg scratch")]

    Browser -->|load UI| Nuxt
    Browser <-->|HTTPS + JWT / CORS| API

    API -->|publish / consume business jobs| Queue

    API --> Cosmos
    API --> Blob
    API --> Files
```

- **Nuxt** serves the SPA/SSR UI. **FastAPI** is the domain API: auth, CRUD, crawler metadata,
  crawler-job submission, and APScheduler-backed queue consumers. It should avoid blocking a
  request on a long job.
- **Cosmos DB** holds all state (small docs). **Blob** holds all binaries (raw HTML, translated
  text, audio, images, video). **Azure Files** is ffmpeg scratch only.

## Repository layout (`srcs/`)

Building onto the existing scaffold (`srcs/app` Nuxt, `tests/` Playwright):

```
srcs/
  app/                # Nuxt (exists) — pages/components/layouts/middleware; calls FastAPI directly
  api/                # FastAPI: core/ domain/ providers/ routers/ services/ repositories/
                      #   parsers/ + crawler metadata/jobs endpoints + queue consumers
  infra/              # (NEW) Bicep + CI/CD — see deployment.md
```

### FastAPI layering

FastAPI code follows this dependency direction:

```mermaid
flowchart LR
    Routes["routers/<feature>.py"]
    Services["services/<feature>_service.py"]
    Providers["providers/<adapter>_provider.py"]
    Parsers["parsers/<site>_parser.py"]
    Repos["repositories/<entity>_repository.py"]
    CosmosRepos["repositories/cosmosdb/<entity>.py"]

    Routes --> Services
    Services --> Providers
    Providers --> Repos --> CosmosRepos
    Services --> Parsers
```

- **Routers** own HTTP contracts, dependency injection, and status-code mapping.
- **Services** orchestrate use cases.
- **Providers** adapt runtime capabilities such as cache behavior and crawler registry
  validation.
- **Parsers** normalize source-site HTML into domain metadata.
- **Repositories** define persistence contracts; `repositories/cosmosdb/` contains Cosmos DB
  implementations.

## Job lifecycle

Long jobs are never awaited inside an HTTP request. FastAPI persists a job, publishes a message to
the relevant business queue, and runs Always On background consumers inside the API process. The
first slice uses `crawler-jobs` plus `crawler-jobs-dead-letter`.

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant A as FastAPI
    participant Q as Queue (crawler-jobs)
    participant C as Cosmos DB

    U->>A: POST /api/crawlers/{id}/jobs
    A->>C: create job (status = queued)
    A->>Q: publish crawler job message
    A-->>U: 202 { id, status, reused:false }

    Note over A,Q: FastAPI background consumer
    Q-->>A: deliver crawler job
    A->>C: job.status = processing
    A->>C: job.status = completed
    A->>Q: delete message

    U->>A: GET /jobs/{id}  (UI polls)
    A-->>C: read job doc
    A-->>U: status + counters
```

- **Start** is decoupled: the request publishes a business queue message and returns `202`. The
  consumer picks it up and moves the job to `processing`. If the trigger fails, the message
  redelivers.
- **Completion** is persisted by the consumer before deleting the source message. Failed messages
  retry with visibility delays and then move to an application-defined dead-letter queue.
- **Progress** is a `GET /jobs/{id}` point-read (~1 RU) over the job rollup counters. An SSE
  endpoint that server-side-polls the same status is an optional UX upgrade — not websockets.
- **Short ops (single-chapter translation preview)** can remain synchronous with a short timeout,
  returning the result inline.

### Decomposition, retry, idempotency

- Every pipeline = 1 `jobs` doc + N `tasks` docs (per chapter for crawl/translate/tts/image;
  per scene for video). The job runner processes task batches and records aggregate progress.
- **Retry** is configured by the job runner with max attempts + backoff. Past max, the task is
  marked `failed`; the UI "retry failed" re-runs only failed tasks.
- **Idempotency (mandatory):** each task has a deterministic `idempotencyKey = jobId:chapterId`
  and a deterministic Blob output path. Activities short-circuit if the output already exists,
  so a retry never double-charges a premium LLM/TTS/image call.
- **Determinism:** external calls write deterministic outputs and can be safely retried.

## Cosmos DB data model

Cosmos DB for NoSQL, **serverless**. Database `mediastudio`. Keep docs small — large text and
binaries go to Blob with a pointer (2 MB item limit; RU cost scales with item size).

| Container | Partition key | Contents | Hot query it optimizes |
|---|---|---|---|
| `users` | `/id` | user, bcrypt hash, role | point-read on login |
| `novels` | `/userId` | library entry, connector ref, status, counts | "my library" (single-partition) |
| `chapters` | `/novelId` | metadata + Blob pointers (`rawBlobPath`, `translations{lang→ptr}`) | "all chapters of a novel" |
| `projects` | `/novelId` | translation/audio/video project (discriminated by `kind`) | projects viewed per novel |
| `jobs` | `/createdBy` | header + active idempotency key + rollup `{total, completed, failed}` | user-scoped jobs and active dedupe |
| `tasks` | `/jobId` | per-chapter / per-scene unit; status, attempts, output ptr | "all tasks of a job" (fan-out) |
| `aimodels` | `/userId` | provider/model config; credential = Key Vault ref, never inline | AI Models page list |
| `connectors` | `/id` | connector registry/display metadata (code is source of truth) | small catalog |
| `cache` | `/cacheType` | generic app cache records `{cacheKey, value, createdAt}` | point-read cache lookups |

**Access-pattern rules:** progress = point-read on `jobs`; chapter/task lists are
single-partition; never store chapter text in Cosmos (Blob only); update `jobs` counters with
patch + ETag. Blob layout: `raw-chapters/{novelId}/{index}.txt`,
`translations/{projectId}/{chapterId}/{lang}.txt`, `tts/{projectId}/{chapterId}/{seq}.mp3`,
`images/{projectId}/...`, `video/{projectId}/final.mp4`.

The generic `cache` container is intentionally not crawler-specific. The first crawler metadata
slice uses cache types such as `crawler:novel543:html` and `crawler:novel543:metadata`, with the
canonical source URL as `cacheKey`. Cache freshness is enforced in the API cache provider by
checking `createdAt + CACHE_TTL_CRAWLER` from `app_config.py`; the crawler TTL is 7 days.
Cosmos item TTL is not required for this slice.

## Connector abstraction (pluggable crawling)

A **Connector** is a source-site adapter implementing a fixed contract, living in
`srcs/api/app/connectors/impl/<site>.py`, self-registering into a registry:

```python
class Connector(Protocol):
    id: str; name: str
    async def trending(self, limit) -> list[NovelSummary]
    async def search(self, query, page) -> list[NovelSummary]
    async def fetch_manifest(self, source_url) -> NovelManifest    # title/author/cover + chapters
    async def fetch_chapter(self, chapter_url) -> ChapterContent
```

- `trending` / `search` / `fetch_manifest` run in FastAPI at request time (fast, cached).
  `fetch_chapter` runs during crawl jobs (bulk, rate-limited, retried).
- A `BaseConnector` bakes in per-host rate limiting, retry/backoff, and user-agent so new sites
  only implement parsing. Adding a site = one file + one `@register(...)` decorator.

### Current crawler metadata slice

Before full background chapter crawling, the API supports a synchronous metadata endpoint:

- `GET /api/crawlers`
- `GET /api/crawlers/{id}/metadata?url=<source_url>`

The first supported crawler is `novel543`. Its source URL must be the full chapter directory,
ending in `/dir`; metadata responses contain the complete ordered `chapters` list. URL validation lives in
`srcs/api/app/providers/crawler_provider.py`; fetching uses FlareSolverr through
`srcs/api/app/providers/flaresolverr_provider.py`; parsing lives in
`srcs/api/app/parsers/novel543_parser.py`;
HTML and parsed metadata are cached through `srcs/api/app/providers/cache_provider.py` and the
generic `cache` repository.

Crawler jobs are submitted through `POST /api/crawlers/{id}/jobs`. The endpoint hashes the
relative route plus canonical payload for idempotency, stores jobs in Cosmos, and publishes new
work to `crawler-jobs`. FastAPI creates and consumes `crawler-jobs` and
`crawler-jobs-dead-letter`; there is no separate worker application in this stack.

## Media pipeline (audio → video)

Long-running media jobs use Blob for persisted artifacts and Azure Files for ffmpeg scratch.
Provider adapters mirror the connector pattern so providers are swappable via `aimodels` config.

1. **Segment** translated chapter text into speeches (per paragraph; per character line for
   multi-voice dubbing via a `voiceMap`).
2. **TTS** each segment → audio clip to Blob.
3. **Image** (optional): auto-illustrate per segment, or use uploaded images grouped with
   speeches. Character/scene/item generation uses typed image tasks with a `subject`.
4. **Assemble (default, free):** download clips + images to Files scratch; ffmpeg builds a
   Ken Burns slideshow (each image shown for its grouped speech), muxes audio, applies
   enhancement layers (subtitle burn-in, background music, transitions, intro/outro as ordered
   filter passes) → `video/{projectId}/final.mp4`. **Assemble per chapter** to keep each run
   bounded (see deployment.md).
5. **AI video (later phase):** per-scene generation via a video provider, opt-in and metered
   with a cost preview, then a combine step concatenates scenes + enhancement layers.

## Phased roadmap (app usable after each phase)

- **Phase 0 — Infra, Auth, Shell.** Bicep for 2 App Services (one plan);
  Blob/Files, Cosmos, Key Vault, business queues beginning with `crawler-jobs`; CI/CD. FastAPI
  skeleton (config, Cosmos + JWT + CORS, queue consumers), `POST /auth/login` + seeded admin. Nuxt
  `/login`, layout (left nav + top toolbar), `auth.global.ts`, direct API client. AI Models page
  CRUD (creds → Key Vault). *Deliverable: log in, see the empty sections.*
- **Phase 1 — Library + Crawling.** Connector abstraction + 1 real connector; trending/search;
  create novel; crawl job lifecycle via `crawler-jobs`;
  progress polling; chapter viewer. *Deliverable: build a library, watch crawl, read chapters.*
- **Phase 2 — Translation.** Translation project (model + prompts, single-chapter preview via
  synchronous wait, confirm); batched translation jobs; translated viewer. *Deliverable:
  translate a whole novel and read it.*
- **Phase 3 — Audio + free slideshow video.** Audio project (language + voice), per-segment TTS
  tasks, audio player, manual image grouping; per-chapter ffmpeg slideshow.
  *Deliverable: audiobooks and slideshow videos.*
- **Phase 4 — Image AI.** Image provider adapters; auto-illustration; character/scene/item
  generation; group images with speeches. *Deliverable: illustrated audio/slideshows.*
- **Phase 5 — AI video (opt-in, metered).** Per-scene AI video generation with cost preview,
  multi-voice dubbing, full assembly with enhancement layers. *Deliverable: AI-generated video.*

## Functional verification

- **Crawl (Phase 1):** create a novel; confirm a `pending` event is published, the consumer
  starts the job, counters advance, chapters
  land in Blob, a `completed` event flips the job to `done`, and the chapter viewer renders.
  Re-run and confirm idempotency (no duplicate fetches).
- **Translate/Audio (Phase 2–3):** run a single-chapter preview (synchronous wait), then a full
  run; poll status to completion; verify translated text / audio clips in Blob and the slideshow
  mp4 plays. Restart the job runner mid-job and confirm it resumes without double-charging.
- **E2E:** wire the existing Playwright suite (`tests/`) to the running app (`webServer` block)
  with specs for login → create novel → crawl → translate.
