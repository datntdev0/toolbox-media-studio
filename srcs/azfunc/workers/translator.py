"""
Translator Durable Functions - Sample
"""

import azure.functions as func
import azure.durable_functions as df

worker_translator_bp = df.Blueprint()


@worker_translator_bp.route(route="translator/start", methods=["POST"])
@worker_translator_bp.durable_client_input(client_name="client")
async def start_translator_job(req: func.HttpRequest, client):
    """HTTP trigger to start translator orchestration."""
    try:
        body = req.get_json()
        texts = body.get('texts', [])
        
        if not texts:
            return func.HttpResponse("Provide 'texts' array", status_code=400)
        
        instance_id = await client.start_new("translator_orchestrator", None, texts)
        return client.create_check_status_response(req, instance_id)
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)


@worker_translator_bp.orchestration_trigger(context_name="context")
def translator_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrator - translates items in parallel."""
    texts = context.get_input()
    
    # Call activity for each text
    tasks = [context.call_activity("translator_activity", text) for text in texts]
    results = yield context.task_all(tasks)
    
    return {"total": len(texts), "results": results}


@worker_translator_bp.activity_trigger(input_name="text")
def translator_activity(text: str) -> dict:
    """Activity - translates single text."""
    return {
        "original": text,
        "translated": f"[Translated] {text}",
        "status": "done"
    }
