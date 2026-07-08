"""
Azure Durable Functions for Media Studio
Main application entry point that registers crawler and translator blueprints.
"""

import azure.functions as func
import azure.durable_functions as df
import logging
import json

# Import blueprints
from workers.crawler import worker_crawler_bp
from workers.translator import worker_translator_bp

# Define a custom formatting blueprint
log_format = '%(name)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format, force=True)

# Create main app
app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Register blueprints
app.register_functions(worker_crawler_bp)
app.register_functions(worker_translator_bp)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

@app.route(route="status/{instance_id}", methods=["GET"])
@app.durable_client_input(client_name="client")
async def get_status(req: func.HttpRequest, client):
    """Get the status of a running orchestration."""
    instance_id = req.route_params.get('instance_id')
    status = await client.get_status(instance_id)
    
    if status:
        return func.HttpResponse(
            json.dumps({
                "instance_id": status.instance_id,
                "runtime_status": status.runtime_status.name,
                "created_time": status.created_time.isoformat() if status.created_time else None,
                "last_updated_time": status.last_updated_time.isoformat() if status.last_updated_time else None,
                "output": status.output
            }, indent=2),
            mimetype="application/json"
        )
    else:
        return func.HttpResponse(
            f"No instance found with ID: {instance_id}",
            status_code=404
        )


@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest):
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "service": "media-studio-workers",
            "functions": ["crawler", "translator"]
        }),
        mimetype="application/json"
    )
