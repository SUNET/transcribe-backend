from auth.oidc import verify_user
from db.session import get_session
from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import JSONResponse
from utils.settings import get_settings

from db.user import user_get, users_statistics, user_update

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


@router.get("/admin")
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


@router.put("/admin/{username}")
async def modify_user(
    request: Request,
    username: str,
) -> JSONResponse:
    """
    Modify a user's active status.
    Used by the frontend to modify a user's active status.
    """
    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    admin_user = user_get(db_session, admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    data = await request.json()
    active = data.get("active", None)
    admin = data.get("admin", None)

    if active is not None:
        user_update(
            db_session,
            username,
            active=active,
        )

    if admin is not None:
        user_update(
            db_session,
            username,
            admin=admin,
        )

    return JSONResponse(content={"result": {"status": "OK"}})
