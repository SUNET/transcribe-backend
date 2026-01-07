from auth.client import verify_client_dn
from auth.oidc import get_current_user_id
from db.user import user_get
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from utils.health import HealthStatus

router = APIRouter(tags=["healthcheck"])
health = HealthStatus()


@router.post("/healthcheck")
async def healthcheck(request: Request) -> JSONResponse:
    """
    Recevice a JSON blob with system data from the GPU workers.

    Parameters:
        request (Request): The incoming HTTP request.

    Returns:
        JSONResponse: The result of the health check.
    """

    verify_client_dn(request)

    data = await request.json()

    health.add(data)

    return JSONResponse(content={"result": "ok"})


@router.get("/healthcheck")
async def get_healthcheck(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get the health status of all workers.

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the user.

    Returns:
        JSONResponse: The health status of all workers.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(user_id)["user"]

    if not user["bofh"]:
        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    data = health.get()

    return JSONResponse(content={"result": data})
