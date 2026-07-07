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
