from auth.oidc import get_current_user_id
from db.user import (
    user_get,
    user_get_private_key,
    user_update,
)

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from utils.log import get_logger
from utils.settings import get_settings
from utils.crypto import validate_private_key_password
from utils.validators import UserUpdateRequest

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

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The user information.
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


@router.put("/me")
async def set_user_info(
    item: UserUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Set user information.
    Used by the frontend to set user information.

    Parameters:
        item (UserUpdateRequest): The user update data.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse:  The result of the operation.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    if item.encryption and item.encryption_password:
        user_update(
            user_id,
            encryption_settings=item.encryption,
            encryption_password=item.encryption_password,
        )
    elif item.reset_password:
        user_update(user_id, reset_encryption=True)
    elif item.verify_password:
        private_key = user_get_private_key(user_id)

        if not validate_private_key_password(private_key, item.encryption_password):
            return JSONResponse(
                content={"error": "Invalid encryption password"},
                status_code=403,
            )
    elif item.email is not None:
        user_update(user_id, email=item.email)
    elif item.notifications:
        notifications_str = ""

        if item.notifications.notify_on_job:
            notifications_str += "job,"
        if item.notifications.notify_on_deletion:
            notifications_str += "deletion,"
        if item.notifications.notify_on_user:
            notifications_str += "user,"

        user_update(user_id, notifications_str=notifications_str)

    return JSONResponse(content={"result": {"status": "OK"}})
