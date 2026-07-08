"""
Crawler Durable Functions - Sample
"""

import azure.functions as func
import azure.durable_functions as df

worker_crawler_bp = df.Blueprint()

@worker_crawler_bp.route(route="crawler/start", methods=["POST"])
@worker_crawler_bp.durable_client_input(client_name="client")
async def start_crawler_job(req: func.HttpRequest, client):
    """HTTP trigger to start crawler orchestration."""
    try:
        body = req.get_json()
        items = body.get('items', [])
        
        if not items:
            return func.HttpResponse("Provide 'items' array", status_code=400)
        
        instance_id = await client.start_new("crawler_orchestrator", None, items)
        return client.create_check_status_response(req, instance_id)
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)


@worker_crawler_bp.orchestration_trigger(context_name="context")
def crawler_orchestrator(context: df.DurableOrchestrationContext):
    """Orchestrator - processes items in parallel."""
    items = context.get_input()
    
    # Call activity for each item
    tasks = [context.call_activity("crawler_activity", item) for item in items]
    results = yield context.task_all(tasks)
    
    return {"total": len(items), "results": results}


@worker_crawler_bp.activity_trigger(input_name="item")
def crawler_activity(item: str) -> dict:
    """Activity - processes single item."""
    return {
        "item": item,
        "status": "processed",
        "length": len(item)
    }
