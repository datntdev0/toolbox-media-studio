# API Conventions

## Purpose

This document defines the default conventions for HTTP endpoints in the API.

These conventions should be applied consistently across routers, OpenAPI schemas, tests, and
specification documents.

## Route Prefixes

All feature CRUD endpoints should be rooted under `api/`.

Examples:

- `GET /api/users`
- `POST /api/users`
- `GET /api/novels`

Auth and operational endpoints may remain outside that prefix when they are cross-cutting or
infrastructure-oriented.

Examples:

- `POST /auth/login`
- `GET /auth/me`
- `GET /health`

## Authentication Convention

The application uses login credentials through `POST /auth/login` to issue a bearer access token.

Swagger UI should expose plain HTTP Bearer authentication:

- users call `POST /auth/login`
- users copy the returned `access_token`
- users paste that token into Swagger's `Authorize` dialog

Do not add a Swagger-only token adapter endpoint unless there is a strong compatibility reason.

## Path Parameter Naming

For resource identifiers in routes, use `id` as the path parameter name by default.

Examples:

- `GET /api/users/{id}`
- `PATCH /api/users/{id}`
- `DELETE /api/users/{id}`

Avoid resource-specific path parameter names such as:

- `{user_id}`
- `{novel_id}`
- `{project_id}`

Rationale:

- keeps route signatures consistent
- simplifies OpenAPI output
- reduces naming drift between routers and client code

## Query Parameter Naming

Use camelCase for externally visible query parameter names when the API already exposes camelCase
response fields.

Example:

- `continuationToken`

## Response Field Naming

Use camelCase for JSON response fields.

Examples:

- `displayName`
- `createdAt`
- `updatedAt`
- `continuationToken`

## Error Handling

Prefer consistent HTTP status mapping across feature routers:

- `401` for missing or invalid authentication
- `403` for authenticated callers lacking permission
- `404` for unknown resources
- `409` for business conflicts such as duplicate identities
- `412` for stale concurrency tokens such as `etag`
- `422` for validation failures

## Backend Test Layout

FastAPI tests live under `srcs/api/tests` and are grouped by responsibility:

- `tests/routes/` for HTTP route/API behavior.
- `tests/services/` for use-case and shared parsing behavior.
- `tests/providers/` for runtime adapters such as cache and crawler providers.
- `tests/repositories/` for persistence contract and repository behavior.
- Root-level tests are reserved for cross-cutting startup/config/logging tests and shared
  fixtures such as `conftest.py`.

Prefer placing new tests in the narrowest matching directory. Route tests should assert status
codes and response contracts; provider/repository tests should avoid FastAPI `TestClient` unless
they are intentionally testing HTTP behavior.
