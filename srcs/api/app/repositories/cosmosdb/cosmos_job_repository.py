"""Azure Cosmos DB implementation of the job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.azure import should_verify_connection
from app.core.config import Settings
from app.domain.jobs import Job, JobCreateResult, JobKind, JobStatus
from app.repositories.job_repository import JobNotFoundError

JOBS_CONTAINER_NAME = "jobs"


class CosmosJobRepository:
    """Job repository backed by Azure Cosmos DB."""

    def __init__(self, client: CosmosClient, settings: Settings) -> None:
        self._database = client.create_database_if_not_exists(id=settings.az_cosmosdb_database_name)
        self._container = self._database.create_container_if_not_exists(
            id=JOBS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/createdBy"),
            unique_key_policy={"uniqueKeys": [{"paths": ["/activeKey"]}]},
        )

    def create_or_get_active(self, candidate: Job) -> JobCreateResult:
        candidate.active_key = candidate.idempotency_key
        try:
            item = cast(
                dict[str, Any],
                self._container.create_item(body=self._serialize(candidate)),
            )
        except exceptions.CosmosResourceExistsError:
            existing = self._get_active(candidate.created_by, candidate.idempotency_key)
            if existing is None:
                raise
            return JobCreateResult(job=existing, created=False)
        except exceptions.CosmosHttpResponseError as exc:
            if getattr(exc, "status_code", None) != 409:
                raise
            existing = self._get_active(candidate.created_by, candidate.idempotency_key)
            if existing is None:
                raise
            return JobCreateResult(job=existing, created=False)
        return JobCreateResult(job=self._deserialize(item), created=True)

    def get(self, id: str, created_by: str) -> Job | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=id, partition_key=created_by),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def mark_processing(self, id: str, created_by: str, attempt: int) -> Job:
        return self._transition(id, created_by, JobStatus.PROCESSING, attempt, None, False)

    def mark_retrying(self, id: str, created_by: str, attempt: int, error: str) -> Job:
        return self._transition(id, created_by, JobStatus.RETRYING, attempt, error, False)

    def mark_completed(self, id: str, created_by: str) -> Job:
        return self._transition(id, created_by, JobStatus.COMPLETED, None, None, True)

    def mark_failed(self, id: str, created_by: str, attempt: int, error: str) -> Job:
        return self._transition(id, created_by, JobStatus.FAILED, attempt, error, True)

    def _transition(
        self,
        id: str,
        created_by: str,
        status: JobStatus,
        attempt: int | None,
        error: str | None,
        terminal: bool,
    ) -> Job:
        job = self.get(id, created_by)
        if job is None:
            raise JobNotFoundError
        if job.status.is_terminal:
            return job

        job.status = status
        if attempt is not None:
            job.attempts = max(job.attempts, attempt)
        job.last_error = error
        job.updated_at = datetime.now(UTC)
        if terminal:
            job.active_key = f"terminal:{job.id}"

        item = cast(
            dict[str, Any],
            self._container.replace_item(item=job.id, body=self._serialize(job)),
        )
        return self._deserialize(item)

    def _get_active(self, created_by: str, idempotency_key: str) -> Job | None:
        query = """
        SELECT TOP 1 * FROM c
        WHERE c.createdBy = @created_by AND c.idempotencyKey = @idempotency_key
        AND c.status IN ("queued", "processing", "retrying")
        """
        items = list(
            self._container.query_items(
                query=query,
                parameters=[
                    {"name": "@created_by", "value": created_by},
                    {"name": "@idempotency_key", "value": idempotency_key},
                ],
                partition_key=created_by,
            )
        )
        if not items:
            return None
        return self._deserialize(items[0])

    @staticmethod
    def _serialize(job: Job) -> dict[str, Any]:
        return {
            "id": job.id,
            "kind": job.kind.value,
            "crawlerId": job.crawler_id,
            "sourceUrl": job.source_url,
            "idempotencyKey": job.idempotency_key,
            "activeKey": job.active_key,
            "status": job.status.value,
            "attempts": job.attempts,
            "lastError": job.last_error,
            "createdBy": job.created_by,
            "createdAt": job.created_at.isoformat(),
            "updatedAt": job.updated_at.isoformat(),
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> Job:
        return Job(
            id=cast(str, item["id"]),
            kind=JobKind(cast(str, item["kind"])),
            crawler_id=cast(str, item["crawlerId"]),
            source_url=cast(str, item["sourceUrl"]),
            idempotency_key=cast(str, item["idempotencyKey"]),
            active_key=cast(str, item["activeKey"]),
            status=JobStatus(cast(str, item["status"])),
            attempts=cast(int, item["attempts"]),
            last_error=cast(str | None, item.get("lastError")),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_job_repository(settings: Settings) -> CosmosJobRepository:
    """Construct the default Cosmos-backed job repository."""

    client = CosmosClient.from_connection_string(
        settings.az_cosmosdb_connection_string,
        connection_verify=should_verify_connection(settings),
    )
    return CosmosJobRepository(client=client, settings=settings)
