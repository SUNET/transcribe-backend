from auth.oidc import verify_user
from db.session import get_session
from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import JSONResponse
from utils.settings import get_settings

from db.user import user_get
from db.user import users_statistics

router = APIRouter(tags=["user"])
settings = get_settings()
db_session = get_session()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/me")
async def get_user_info(
    request: Request,
) -> JSONResponse:
    """
    Get user information.
    Used by the frontend to get user information.
    """
    user_id = await verify_user(request)

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(db_session, user_id)

    if not user:
        return JSONResponse(
            content={"error": "User not found"},
            status_code=404,
        )

    return JSONResponse(content={"result": user})


@router.get("/statistics")
async def statistics(
    request: Request,
) -> JSONResponse:
    """
    Get user statistics.
    Used by the frontend to get user statistics.
    """
    user_id = await verify_user(request)

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(db_session, user_id)["user"]

    if not user["admin"]:
        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    stats = users_statistics(db_session, user["realm"])

    return JSONResponse(content={"result": stats})
