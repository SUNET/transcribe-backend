from auth.oidc import get_current_user_id, verify_user
from db.user import user_get, user_update, users_statistics
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from utils.log import get_logger
from utils.settings import get_settings

log = get_logger()
router = APIRouter(tags=["user"])
settings = get_settings()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/me")
async def get_user_info(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get user information.
    Used by the frontend to get user information.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(user_id)

    if not user:
        return JSONResponse(
            content={"error": "User not found"},
            status_code=404,
        )

    return JSONResponse(content={"result": user})


@router.get("/admin")
async def statistics(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get user statistics.
    Used by the frontend to get user statistics.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(user_id)["user"]

    if not user["admin"]:
        log.warning(f"User {user_id} is not admin")

        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    if user["bofh"]:
        log.info(f"User {user_id} is bofh, getting stats for all realms")
        realm = "*"
    else:
        realm = user["realm"]

    stats = users_statistics(realm)

    return JSONResponse(content={"result": stats})


@router.put("/admin/{username}")
async def modify_user(
    request: Request,
    username: str,
    admin_user_id: str = Depends(get_current_user_id),
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

    admin_user = user_get(admin_user_id)["user"]

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
            username,
            active=active,
        )

    if admin is not None:
        user_update(
            username,
            admin=admin,
        )

    return JSONResponse(content={"result": {"status": "OK"}})
