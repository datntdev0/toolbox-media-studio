"""
Translator Durable Functions - Sample
"""

import time
import logging

import azure.functions as func
import azure.durable_functions as df

worker_translator_bp = df.Blueprint()
logger = logging.getLogger(__name__)


@worker_translator_bp.route(route="translator/start", methods=["POST"])
@worker_translator_bp.durable_client_input(client_name="client")
async def start_translator_job(req: func.HttpRequest, client):
    """HTTP trigger to start translator orchestration."""
    try:
        body = req.get_json()
        texts = body.get('texts', [])

        if not texts:
            logger.warning("Translator start request rejected: missing texts array")
            return func.HttpResponse("Provide 'texts' array", status_code=400)

        logger.info("Starting translator orchestration with %d texts", len(texts))
        instance_id = await client.start_new("translator_orchestrator", None, texts)
        logger.info("Translator orchestration started: instance_id=%s", instance_id)
        return client.create_check_status_response(req, instance_id)
    except ValueError:
        logger.warning("Translator start request rejected: invalid JSON")
        return func.HttpResponse("Invalid JSON", status_code=400)


@worker_translator_bp.orchestration_trigger(context_name="context")
def translator_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrator - translates items in parallel."""
    texts = context.get_input()

    if not getattr(context, "is_replaying", False):
        logger.info("Translator orchestration scheduling %d activities", len(texts))

    # Call activity for each text
    tasks = [context.call_activity("translator_activity", text) for text in texts]
    results = yield context.task_all(tasks)

    if not getattr(context, "is_replaying", False):
        logger.info("Translator orchestration completed %d activities", len(results))

    return {"total": len(texts), "results": results}


@worker_translator_bp.activity_trigger(input_name="text")
def translator_activity(text: str) -> dict:
    """Activity - translates single text."""
    logger.info("Translating text: length=%d", len(text))
    time.sleep(5) # Simulate processing time
    logger.info("Text translated: length=%d", len(text))
    return {
        "original": text,
        "translated": f"[Translated] {text}",
        "status": "done"
    }
