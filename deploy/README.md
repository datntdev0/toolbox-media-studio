# Docker Deployment Guide

This directory contains Docker Compose configurations for running the Toolbox Media Studio application in different modes.

## Available Compose Files

### 1. `dockercompose.local.infra.yml`
Infrastructure services only (CosmosDB, Azurite, FlareSolverr).

**Use when:** You want to run backend/frontend locally via scripts but need infrastructure services.

```bash
docker compose -f dockercompose.local.infra.yml -p datntdev_media_studio_infra up -d
```

### 2. `dockercompose.local.full.yml`
Complete application stack (infrastructure + backend + frontend).

**Use when:** You want to run the entire application in Docker containers.

```bash
docker compose -f dockercompose.local.full.yml -p datntdev_media_studio up -d
```

This file defines the infrastructure and application services directly and is fully standalone.

## Quick Start: Full Stack with Docker

### Prerequisites
- Docker Desktop installed and running
- Docker Compose V2 (included with Docker Desktop)
- Backend `.env` file configured (see below)

### Step 1: Configure Environment Variables

Create or verify `srcs/backend/.env` from the template:

```bash
cp srcs/backend/.env.example srcs/backend/.env
```

Edit `srcs/backend/.env` with required values:
- `FAST_SECURITY_JWT_SIGNING_KEY` — Generate a secure random string
- `FAST_SECURITY_DEFAULT_ADMIN_EMAIL` — Admin login email
- `FAST_SECURITY_DEFAULT_ADMIN_PASSWORD` — Admin login password

**Note:** Connection strings for CosmosDB, Azurite, and FlareSolverr are automatically overridden in the Docker Compose file to use container network names.

### Step 2: Start the Full Stack

```bash
docker compose -f deploy/dockercompose.local.full.yml up -d
```

This will:
1. Start infrastructure services (CosmosDB, Azurite, FlareSolverr)
2. Build and start the backend API
3. Build and start the frontend web app

### Step 3: Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **CosmosDB Explorer:** http://localhost:8081/_explorer/index.html

### Step 4: View Logs

```bash
# All services
docker compose -f deploy/dockercompose.local.full.yml logs -f

# Specific service
docker compose -f deploy/dockercompose.local.full.yml logs -f backend
docker compose -f deploy/dockercompose.local.full.yml logs -f frontend
```

### Step 5: Stop the Stack

```bash
docker compose -f deploy/dockercompose.local.full.yml down
```

To also remove volumes (data will be lost):

```bash
docker compose -f deploy/dockercompose.local.full.yml down -v
```

## Building Images Locally

To rebuild images after code changes:

```bash
# Rebuild all services
docker compose -f deploy/dockercompose.local.full.yml build

# Rebuild specific service
docker compose -f deploy/dockercompose.local.full.yml build backend
docker compose -f deploy/dockercompose.local.full.yml build frontend

# Rebuild and restart
docker compose -f deploy/dockercompose.local.full.yml up -d --build
```

## Development Workflow

### Option 1: Pure Docker (Full Stack)
Run everything in containers. Good for testing production-like environment.

```bash
docker compose -f deploy/dockercompose.local.full.yml up -d
```

### Option 2: Hybrid (Infrastructure + Local Dev)
Run infrastructure in Docker, backend/frontend locally for faster iteration.

```bash
# Start infrastructure only
docker compose -f deploy/dockercompose.local.infra.yml up -d

# In separate terminals, run locally:
./scripts/backend.start.sh
./scripts/frontend.start.sh
```

## Publishing to GitHub Container Registry

The GitHub Actions workflow `.github/workflows/publish-docker-images.yml` builds and publishes Docker images to GitHub Packages.

### Trigger the Workflow

1. Go to your GitHub repository
2. Navigate to **Actions** tab
3. Select **Publish Docker Images** workflow
4. Click **Run workflow**
5. Run the workflow for the commit you want to publish

### Published Images

- `ghcr.io/<owner>/toolbox-media-studio-backend:<short-commit-sha>`
- `ghcr.io/<owner>/toolbox-media-studio-frontend:<short-commit-sha>`

### Using Published Images

To use published images instead of building locally, update `dockercompose.local.full.yml`:

```yaml
services:
  backend:
    image: ghcr.io/<owner>/toolbox-media-studio-backend:<short-commit-sha>
    # Remove the 'build' section
    
  frontend:
    image: ghcr.io/<owner>/toolbox-media-studio-frontend:<short-commit-sha>
    # Remove the 'build' section
```

## Troubleshooting

### Backend health check fails

Check backend logs for startup errors:

```bash
docker compose -f deploy/dockercompose.local.full.yml logs backend
```

Common issues:
- Missing or invalid environment variables in `.env`
- CosmosDB emulator not ready (wait 30-60 seconds after first start)

### Frontend can't connect to backend

Verify `NUXT_PUBLIC_SERV_URL` environment variable points to `http://localhost:8000` (accessible from browser, not container network).

### Port conflicts

If ports 3000, 8000, 8081, 10000-10002, or 8191 are in use:

```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Change ports in docker-compose files or stop conflicting services
```

### Container name conflicts

If container names are already in use:

```bash
# List all containers
docker ps -a

# Remove conflicting containers
docker rm -f toolbox-backend toolbox-frontend
```

### Cosmos DB emulator issues on Windows

The CosmosDB emulator may have memory/performance issues on Windows. Consider:
- Allocating more memory to Docker Desktop (Settings → Resources)
- Using Azure Cosmos DB free tier instead for development

## Network Architecture

All services communicate via the `toolbox-network` bridge network:

```
Browser → frontend:3000 (host port 3000)
       ↓
     backend:8000 (container network)
       ↓
     ┌─────────────────┬──────────────────┬──────────────┐
     ↓                 ↓                  ↓              ↓
cosmosdb:8081    azurite:10000    azurite:10001    flaresolverr:8191
```

- **Host access:** Use `localhost:<port>` from your browser/terminal
- **Container-to-container:** Use container names (e.g., `backend:8000`)

## Health Checks

The full-stack Compose configuration defines health checks for the backend and frontend:

- **Backend:** `curl -f http://localhost:8000/health`
- **Frontend:** `curl -f http://localhost:3000`

View health status:

```bash
docker compose -f deploy/dockercompose.local.full.yml ps
```

## Volumes

- `cosmosdb-data` — Cosmos DB data persistence
- `azurite-data` — Azure Storage emulator data persistence
- `backend-logs` — Backend application logs (mounted to `./deploy/backend-logs/`)

## Resource Usage

Approximate resource requirements:
- **CosmosDB Emulator:** 2-4 GB RAM, 2 CPUs
- **Azurite:** 100-200 MB RAM
- **FlareSolverr:** 500 MB - 1 GB RAM (varies with usage)
- **Backend:** 200-500 MB RAM
- **Frontend:** 100-200 MB RAM

**Total:** ~3-6 GB RAM recommended for comfortable development.

## Security Notes

⚠️ **These configurations are for local development only.**

- Default CosmosDB emulator key is well-known and insecure
- Azurite uses default development credentials
- No SSL/TLS termination
- FlareSolverr launches browsers and should not be exposed publicly

For production deployment, see `docs/deployment.md`.
