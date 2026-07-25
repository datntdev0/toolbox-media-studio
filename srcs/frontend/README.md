# Novel Media Studio — Frontend (Nuxt)

The web frontend for Novel Media Studio, built with Nuxt 4 and Nuxt UI. This application provides the user interface for managing web novel crawling, translation, audio production, and video generation workflows.

See the design docs for the full picture:
[`architecture.md`](../../docs/architecture.md) · [`requirements.md`](../../docs/requirements.md) ·
[`deployment.md`](../../docs/deployment.md).

## Tech Stack

| Concern | Choice |
|---|---|
| Framework | Nuxt 4 |
| UI Library | Nuxt UI (125+ components) |
| Language | TypeScript |
| Package Manager | pnpm 11+ |
| Styling | Tailwind CSS 4 |
| Icons | @nuxt/icon (Iconify) |
| Tables | @tanstack/table-core |
| Charts | @unovis/vue |
| Validation | Zod |
| Date Handling | date-fns, @internationalized/date |
| API Client | Auto-generated via NSwag |

## Quick Start

### Prerequisites

- Node.js 20+
- pnpm 11+
- Backend API running at `http://localhost:8000`

### Setup & Run

```bash
# From project root
./scripts/frontend.start.sh
```

Or manually:

```bash
cd srcs/frontend

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

The web app will be available at `http://localhost:3000`.

## Available Scripts

```bash
# Development
pnpm dev              # Start dev server with hot reload

# Build
pnpm build            # Build for production
pnpm preview          # Preview production build locally

# Code Quality
pnpm lint             # Run ESLint
pnpm typecheck        # Run TypeScript type checking

# API Client Generation
pnpm generate:api     # Generate TypeScript API client from backend OpenAPI spec
```

## Project Structure

```
srcs/frontend/
  app/
    app.config.ts           # App configuration
    app.vue                 # Root component
    error.vue              # Error page component
    assets/                # Static assets (images, styles)
    components/            # Vue components
    composables/           # Vue composables (reusable logic)
    layouts/               # Page layouts
    middleware/            # Route middleware
    pages/                 # File-based routing pages
    plugins/               # Nuxt plugins
    services/              # Business logic services
    types/                 # TypeScript type definitions
    utils/                 # Utility functions
  public/                  # Public static files
  server/                  # Server-side code
    api/                   # Server API routes
  shared/                  # Shared code
    api-services/          # Generated API client
      srv-core.nswag       # NSwag configuration for API generation
  nuxt.config.ts          # Nuxt configuration
  tsconfig.json           # TypeScript configuration
  eslint.config.mjs       # ESLint configuration
  package.json            # Dependencies and scripts
  llms.txt                # AI/LLM documentation for components
```

## Architecture

### API Communication

The frontend communicates directly with the FastAPI backend:

- **Direct CORS calls** to `http://localhost:8000` (dev) or production API URL
- **JWT authentication** via Bearer tokens in Authorization headers
- **Auto-generated TypeScript client** from OpenAPI spec using NSwag

### Authentication Flow

1. User logs in via `/auth/login` endpoint
2. Receives JWT access token
3. Token stored and included in subsequent API requests
4. Protected routes use middleware to verify authentication

### State Management

- Uses Vue 3 Composition API with composables
- Reactive state management via `@vueuse/core`
- No external state management library (Pinia/Vuex) currently

### Routing

File-based routing powered by Nuxt:
- Pages in `app/pages/` automatically become routes
- Layouts in `app/layouts/` provide page structure
- Middleware in `app/middleware/` handles route guards

## UI Components

This project uses **Nuxt UI**, a comprehensive Vue UI component library with 125+ accessible, production-ready components:

- Built on Tailwind CSS
- Full TypeScript support
- Dark mode support
- Fully customizable via Tailwind Variants API
- Keyboard navigation and accessibility

For component documentation and usage, see:
- [Nuxt UI Documentation](https://ui.nuxt.com)
- [Component Reference](app/llms.txt) — AI-friendly component guide

## API Client Generation

The TypeScript API client is auto-generated from the backend's OpenAPI specification:

```bash
pnpm generate:api
```

This runs NSwag with the configuration in `shared/api-services/srv-core.nswag`, which:
1. Fetches the OpenAPI spec from the running backend
2. Generates TypeScript interfaces and client classes
3. Outputs to `shared/api-services/`

**Important:** The backend must be running at `http://localhost:8000` before generating the client.

## Development Guidelines

### Component Development

- Follow the Nuxt UI component patterns in `llms.txt`
- Use Composition API with `<script setup>` syntax
- Keep components focused and reusable
- Use TypeScript for type safety

### Styling

- Use Tailwind CSS utility classes
- Follow the Nuxt UI theming system
- Use CSS variables for consistent design tokens
- Support both light and dark modes

### Code Quality

- Run `pnpm lint` before committing
- Run `pnpm typecheck` to catch type errors
- Follow the ESLint configuration
- Write meaningful commit messages

## Environment Variables

Configure environment-specific settings in `.env`:

```bash
# API Base URL
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Other environment variables as needed
```

## Related Documentation

- [Architecture Overview](../../docs/architecture.md)
- [Requirements](../../docs/requirements.md)
- [Deployment](../../docs/deployment.md)
- [Main README](../../README.md)

## Nuxt UI Resources

- [Nuxt UI Documentation](https://ui.nuxt.com)
- [Getting Started](https://ui.nuxt.com/docs/getting-started)
- [Component Gallery](https://ui.nuxt.com/components)
- [Theming Guide](https://ui.nuxt.com/docs/getting-started/theme)

