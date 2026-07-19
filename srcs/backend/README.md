# Novel Media Studio — API (FastAPI)

The domain API for Novel Media Studio. It currently includes JWT authentication, user and novel
management, and crawler metadata/chapter content fetching for `novel543` using FlareSolverr,
Cosmos, and Azure Storage Queues.

See the design docs for the full picture:
[`architecture.md`](../../docs/architecture.md) · [`requirements.md`](../../docs/requirements.md) ·
[`deployment.md`](../../docs/deployment.md).

## Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Framework | FastAPI + Uvicorn (ASGI) |
| Validation | Pydantic v2 / `pydantic-settings` |
| Auth | JWT (`python-jose`); credentials compared against config |
| Dep management | `pyproject.toml` + pip |
| Crawler fetch | FlareSolverr through API provider |
| Background jobs | Azure Storage Queue + APScheduler inside FastAPI |
| HTML parsing | BeautifulSoup in API parser modules |
| Tooling | ruff (lint+format), mypy (types), pytest (tests) |

## Login flow

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant A as FastAPI (/auth)
    participant Cfg as Settings (env)

    U->>A: POST /auth/login { email, password }
    A->>Cfg: read FAST_SECURITY_DEFAULT_ADMIN_EMAIL / FAST_SECURITY_DEFAULT_ADMIN_PASSWORD
    A->>A: compare credentials, sign JWT
    A-->>U: 200 { access_token }  (or 401)

    U->>A: GET /auth/me (Authorization: Bearer <jwt>)
    A->>A: decode + validate JWT
    A-->>U: 200 { email, role }
```

## Layered Architecture

The API keeps a simple dependency direction:

`routers → services → providers → repositories`

Cross-cutting config, security, logging, and dependency resolution live under `core/`.
```mermaid
flowchart TB
    R["routers/<feature>.py<br/>HTTP contracts/status mapping"]
    S["services/<feature>_service.py<br/>use-case orchestration"]
    P["providers/<adapter>_provider.py<br/>runtime adapters"]
    Parsers["parsers/<site>_parser.py<br/>HTML parsing"]
    Repo["repositories/<entity>_repository.py<br/>persistence contracts"]
    Cosmos["repositories/cosmosdb/<entity>.py<br/>Cosmos implementations"]

    R --> S
    S --> P --> Repo --> Cosmos
    S --> Parsers
```

Rules: routers hold no business logic; services orchestrate use cases; providers adapt runtime
capabilities such as cache and crawler registries; repositories own persistence contracts and
Cosmos implementations.

## Directory Structure

```
srcs/api/
  README.md                  # this file
  pyproject.toml             # package metadata + dependencies
  .env.example               # documented env vars (no secrets)
  app/
    main.py                  # FastAPI app factory; mounts routers
    core/
      config.py              # Settings (pydantic-settings)
      runtime.py             # Runtime composition and background consumer lifecycle
      security.py            # JWT encode/decode, password verify
      dependencies.py        # FastAPI dependency providers
    consumers/
      crawler_queue_consumer.py # crawler-jobs consumer
    domain/
      crawlers.py            # Crawler response/domain models
      requests.py            # Inbound request models
      responses.py           # Common outbound response models
    providers/
      cache_provider.py      # Generic cache behavior, TTL enforcement, and cache storage
      crawler_provider.py    # Supported crawler registry and URL validation
      proxy_service_provider.py # Proxy provider + concrete FlareSolver service
      queue_provider.py      # Azure Storage Queue provider/factory
      queue_publisher.py     # Queue publishing abstraction
      queue_subscriber.py    # Queue subscription abstraction
    parsers/
      novel543_parser.py     # Novel543 metadata parsing
    repositories/
      job_repository.py      # Async job persistence contract + in-memory repo
      cosmosdb/              # Cosmos DB implementations
    routers/
      auth.py                # POST /auth/login, GET /auth/me
      crawlers.py            # crawler registry + metadata endpoint
      health.py              # GET /health
      novels.py              # /api/novels
      users.py               # /api/users
    services/
      auth_service.py
      crawler_service.py
      novel_service.py
      user_service.py
  tests/
    conftest.py
    providers/
    repositories/
    routes/
    services/
    test_startup.py
```

## Local development

Requires Python 3.12+, the repository root `.venv`, and local infrastructure from
`deploy/dockercompose.local.infra.yml`.

```bash
# from the repository root
scripts/backend.setup.sh
scripts/backend.start.sh
```

`backend.setup.sh` activates the root `.venv`, installs `srcs/api` with dev dependencies, and
copies `.env.example` to `.env` if needed. `backend.start.sh` activates the same environment and
runs `uvicorn app.main:app --reload --port 8000` from `srcs/api`.

## Quality gates

```bash
pytest
ruff check .
mypy app
```
