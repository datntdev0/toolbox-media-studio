# Multi-stage build for Nuxt frontend
# Stage 1: Build environment
FROM node:22-alpine AS builder

WORKDIR /build

# Nuxt's production bundle exceeds Node's container-aware default heap limit.
ENV NODE_OPTIONS=--max-old-space-size=4096

# Install pnpm
RUN corepack enable && corepack prepare pnpm@11.13.1 --activate

# Copy dependency files
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# Install dependencies with frozen lockfile
RUN pnpm install --frozen-lockfile

# Copy application source
COPY app/ ./app/
COPY public/ ./public/
COPY server/ ./server/
COPY shared/ ./shared/
COPY nuxt.config.ts tsconfig.json ./
COPY eslint.config.mjs ./

# Build application
RUN pnpm build

# Stage 2: Production runtime
FROM node:22-alpine

WORKDIR /app

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built application from builder
COPY --from=builder /build/.output ./.output
COPY --from=builder /build/package.json ./

# Expose Nuxt port
EXPOSE 3000

# Set Node environment to production
ENV NODE_ENV=production

# Run Nuxt server
CMD ["node", ".output/server/index.mjs"]
