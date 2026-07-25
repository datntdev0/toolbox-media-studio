# Novel Media Studio

An automated pipeline that turns web novels into translated text, narrated audio, AI-generated illustrations, and assembled video — including full storyboard-driven animated short dramas. Designed to streamline creative workflows with modular components and fully customizable AI pipelines.

## 📋 Project Overview

Novel Media Studio is a cloud-native, multi-stage content generation platform that transforms web novels into rich media experiences. The system orchestrates complex AI pipelines to automate:

- **Novel Crawling** — Extract web-novel content chapter-by-chapter via pluggable source connectors
- **Translation** — Multi-language translation using swappable AI LLM providers (Claude, GPT, Gemini)
- **Audio Production** — Text-to-speech narration with per-character dubbing support (ElevenLabs, Azure Neural)
- **Visual Generation** — AI-powered illustrations for characters, scenes, and content passages
- **Video Assembly** — Automated slideshow creation (ffmpeg) with optional AI-generated video scenes
- **Novel Video Projects** — Storyboard-driven, end-to-end "novel → animated short drama" workflows

### Key Features

- 🔐 **JWT-based Authentication** — Secure user sessions with role-based access control
- 🏗️ **Web Architecture** — FastAPI backend and Nuxt frontend
- 🔄 **Async Job Queue** — Event-driven job coordination for longer media workflows
- 🎨 **Provider-Agnostic Design** — Swappable AI providers per project (premium & cost-effective tiers)
- 📊 **Real-time Progress Tracking** — Monitor crawling, translation, and generation jobs
- 🧩 **Modular Connectors** — Plugin system for adding new novel source sites
- ☁️ **Cloud-Native** — Designed for Azure with serverless components (scale-to-zero)


## 📁 Project Structure

```
.
├── srcs/
│   ├── backend/          # FastAPI backend (Python)
│   │   ├── app/
│   │   │   ├── core/     # Config, logging, security, events, injection
│   │   │   ├── domain/   # Domain models (users, novels, crawlers, requests, responses)
│   │   │   ├── providers/# Runtime adapters (cache, crawler parsers, proxy services)
│   │   │   ├── routers/  # API endpoints (auth, users, novels, crawlers, health)
│   │   │   ├── services/ # Business logic
│   │   │   ├── repositories/ # Data access (Cosmos DB)
│   │   │   ├── consumers/# Background job consumers
│   │   │   └── events/   # Event handlers
│   │   ├── tests/        # pytest tests grouped by routes/services/providers/repositories
│   │   ├── shared/       # Shared utilities and decorators
│   │   └── pyproject.toml
│   │
│   ├── frontend/         # Nuxt frontend (TypeScript)
│   │   ├── app/          # Application code
│   │   │   ├── components/ # Vue components
│   │   │   ├── pages/    # Route pages
│   │   │   ├── layouts/  # Layout components
│   │   │   ├── composables/ # Vue composables
│   │   │   ├── services/ # Business logic
│   │   │   ├── types/    # TypeScript types
│   │   │   └── utils/    # Utility functions
│   │   ├── public/       # Static files
│   │   ├── shared/       # Shared code and API client
│   │   └── nuxt.config.ts
│
├── tests/                # E2E tests (Playwright)
│   └── backend/          # API integration tests
│
├── docs/                 # Documentation
│   ├── architecture.md   # System design
│   ├── requirements.md   # Functional requirements
│   ├── deployment.md     # Azure deployment guide
│   └── conventions.api.md # API conventions
│
├── scripts/              # Developer helpers
│   ├── backend.setup.sh
│   └── backend.start.sh
│
└── deploy/               # Deployment configs
    └── dockercompose.local.infra.yml
```

## 🔧 Technology Stack

**Backend:**
- FastAPI + Uvicorn (ASGI)
- Python 3.12+
- Azure Cosmos DB (NoSQL, serverless)
- Azure Storage (Blob + Queues)
- APScheduler (background jobs)
- BeautifulSoup4 (HTML parsing)

**Frontend:**
- Nuxt 4
- Nuxt UI (125+ components)
- TypeScript
- pnpm (package manager)

**Infrastructure:**
- Azure App Services (B1 plan)
- Azure Cosmos DB (serverless)
- Azure Storage (Blob/Queue)
- Azure Key Vault
- Docker (local development)

## 📚 Documentation

- [Architecture](docs/architecture.md) — System design, data model, and job lifecycle
- [Requirements](docs/requirements.md) — Functional requirements and capabilities
- [Deployment](docs/deployment.md) — Azure infrastructure, CI/CD, and cost estimates
- [API Conventions](docs/conventions.api.md) — HTTP endpoint conventions and standards

## 🔐 Security

- JWT-based authentication with role-based access control
- Credentials stored in Azure Key Vault (never inline)
- Managed identities for Azure resource access
- CORS configuration for frontend/backend separation

## 🚢 Development Workflow

1. Start local infrastructure with Docker Compose
2. Run backend API with auto-reload enabled
3. Run frontend with hot module replacement
4. Make changes and test
5. Run test suites before committing

## 🚀 Getting Started

### Prerequisites

- **Node.js** 20+ and **pnpm** 9+ (for frontend)
- **Python** 3.12+ and **pip** (for backend)
- **Docker Desktop** (for local Azure emulators and FlareSolverr)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/toolbox-media-studio.git
cd toolbox-media-studio
```

### 2. Start Local Infrastructure

Start the Azure CosmosDB Emulator, Azurite (Blob/Queue emulator), and FlareSolverr for local
crawler metadata fetches:

```bash
docker compose -f deploy/dockercompose.local.infra.yml -p datntdev_media_studio_infra up -d
```

This starts:
- CosmosDB Emulator at `http://localhost:8081`
- Azurite (Blob) at `http://localhost:10000`
- Azurite (Queue) at `http://localhost:10001`
- FlareSolverr at `http://localhost:8191`

### 3. Setup Backend (FastAPI)

```bash
scripts/backend.setup.sh
scripts/backend.start.sh
```

The API will be available at `http://localhost:8000` with automatic docs at `http://localhost:8000/docs`.

The scripts are thin Bash helpers around the standard commands. `backend.setup.sh` activates the
root `.venv`, installs the FastAPI package with dev dependencies, and creates `srcs/backend/.env` from
`srcs/backend/.env.example` when missing. `backend.start.sh` activates the virtual environment and
starts Uvicorn from `srcs/backend`. You can still run the commands manually if you prefer.

### 4. Setup Frontend (Nuxt)

In a new terminal:

```bash
scripts/frontend.start.sh
```

Or manually:

```bash
cd srcs/frontend

# Install dependencies
pnpm install

# Start the development server
pnpm dev
```

The web app will be available at `http://localhost:3000`.

### 5. Running Tests

**Backend Tests (pytest):**

```bash
cd srcs/backend
pytest
```

**E2E API Tests (Playwright):**

```bash
cd tests

# Install Playwright browsers (first time only)
npx playwright install

# Run tests
npm test
```

### 6. Access the Application

1. Open `http://localhost:3000` in your browser
2. Navigate to the sign-in page
3. Login with:
   - Email: `admin@example.com`
   - Password: `SecurePassword123!`


