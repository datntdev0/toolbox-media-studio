# Novel Media Studio

An automated pipeline that turns web novels into translated text, narrated audio, AI-generated illustrations, and assembled video — including full storyboard-driven animated short dramas. Designed to streamline creative workflows with modular components and fully customizable AI pipelines.

## 📋 Project Overview

Novel Media Studio is a cloud-native, multi-stage content generation platform that transforms web novels into rich media experiences. The system orchestrates complex AI pipelines to automate:

- **Novel Crawling** — Extract web-novel content chapter-by-chapter via pluggable source connectors
- **Translation** — Multi-language translation using swappable AI LLM providers (Claude, GPT, Gemini)
- **Audio Production** — Text-to-speech narration with per-character dubbing support (ElevenLabs, Azure Neural)
- **Visual Generation** — AI-powered illustrations for characters, scenes, and content passages
- **Video Assembly** — Automated slideshow creation (ffmpeg) with optional AI-generated video scenes
- **Novel Video Projects** — Storyboard-driven, end-to-end "novel → animated short drama" pipeline

### Key Features

- 🔐 **JWT-based Authentication** — Secure user sessions with role-based access control
- 🏗️ **Microservices Architecture** — FastAPI backend, Nuxt frontend, Azure Durable Functions for background processing
- 🔄 **Async Job Queue** — Event-driven orchestration with fan-out/fan-in patterns for parallel processing
- 🎨 **Provider-Agnostic Design** — Swappable AI providers per project (premium & cost-effective tiers)
- 📊 **Real-time Progress Tracking** — Monitor crawling, translation, and generation jobs
- 🧩 **Modular Connectors** — Plugin system for adding new novel source sites
- ☁️ **Cloud-Native** — Designed for Azure with serverless components (scale-to-zero)

## 🚀 Getting Started

### Prerequisites

- **Node.js** 20+ and **pnpm** 9+ (for frontend)
- **Python** 3.12+ and **pip** (for backend)
- **Docker Desktop** (for local Azure emulators)
- **[Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)**

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/toolbox-media-studio.git
cd toolbox-media-studio
```

### 2. Start Local Infrastructure

Start the Azure CosmosDB Emulator and Azurite (Blob/Queue emulator):

```bash
docker compose -f deploy/dockercompose.local.infra.yml -p datntdev_media_studio_infra up -d
```

This starts:
- CosmosDB Emulator at `http://localhost:8081`
- Azurite (Blob) at `http://localhost:10000`
- Azurite (Queue) at `http://localhost:10001`

### 3. Setup Backend (FastAPI)

```bash
# from srcs/api/
python -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate

pip install -e ".[dev]"

cp .env.example .env                        # then fill in values

uvicorn app.main:app --reload --port 8000  # docs at http://localhost:8000/docs
```

The API will be available at `http://localhost:8000` with automatic docs at `http://localhost:8000/docs`.

### 4. Setup Frontend (Nuxt)

In a new terminal:

```bash
cd srcs/app

# Install dependencies
pnpm install

# Start the development server
pnpm dev
```

The web app will be available at `http://localhost:3000`.

### 5. Running Tests

**Backend Tests (pytest):**

```bash
cd srcs/api
pytest
```

**E2E API Tests (Playwright):**

```bash
cd tests

# Install Playwright browsers (first time only)
npx playwright install

# Run tests
npx playwright test

# View test report
npx playwright show-report
```

### 6. Access the Application

1. Open `http://localhost:3000` in your browser
2. Navigate to the sign-in page
3. Login with:
   - Email: `admin@example.com`
   - Password: `SecurePassword123!`

## 📁 Project Structure

```
.
├── srcs/
│   ├── api/              # FastAPI backend (Python)
│   │   ├── app/
│   │   │   ├── core/     # Config, logging, security, startup
│   │   │   ├── domain/   # Domain models (users, requests, responses)
│   │   │   ├── routers/  # API endpoints (auth, users, health)
│   │   │   ├── services/ # Business logic
│   │   │   └── repositories/ # Data access (Cosmos DB)
│   │   ├── tests/        # pytest tests
│   │   └── pyproject.toml
│   │
│   ├── app/              # Nuxt frontend (TypeScript)
│   │   ├── app/          # Vue components & pages
│   │   ├── pages/        # Route pages (signin, signup)
│   │   ├── layouts/      # Layout components
│   │   ├── components/   # Reusable UI components
│   │   └── nuxt.config.ts
│   │
│   ├── azfunc/           # Azure Durable Functions
│   └── shared/           # Shared schemas & contracts (planned)
│
├── tests/                # E2E tests (Playwright)
│   └── api/              # API integration tests
│
├── docs/                 # Documentation
│   ├── architecture.md   # System design
│   ├── requirements.md   # Functional requirements
│   ├── deployment.md     # Azure deployment guide
│   └── conventions.api.md # API conventions
│
└── deploy/               # Deployment configs
    └── dockercompose.local.infra.yml
```

## 📚 Documentation

- [Architecture Overview](docs/architecture.md) — System design and component interaction
- [Requirements](docs/requirements.md) — Functional requirements and feature roadmap
- [Deployment Guide](docs/deployment.md) — Azure infrastructure and CI/CD
- [API Conventions](docs/conventions.api.md) — REST API design standards

