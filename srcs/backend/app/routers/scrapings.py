from fastapi import APIRouter

router = APIRouter(prefix="/api/scrapings", tags=["scrapings"])

@router.post("", status_code=201, operation_id="create_scraping")
def create_scraping_route():
    return {"message": "Scraping created"}

@router.get("", status_code=200, operation_id="list_scrapings")
def list_scrapings_route():
    return {"message": "List of scrapings"}

@router.get("/{id}", status_code=200, operation_id="get_scraping")
def get_scraping_route(id: str):
    return {"message": f"Details of scraping {id}"}

@router.delete("/{id}", status_code=204, operation_id="delete_scraping")
def delete_scraping_route(id: str):
    return {"message": f"Scraping {id} deleted"}