from auth.oidc import get_current_user_id, verify_user
from db.user import (
    user_get,
    user_get_private_key,
    user_update,
)

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from utils.log import get_logger
from utils.settings import get_settings
from utils.crypto import validate_private_key_password

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

    data = await request.json()
    encryption_password = data.get("encryption_password", "")

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

    if encryption_password:
        private_key = user_get_private_key(user_id)

        if not validate_private_key_password(private_key, encryption_password):
            return JSONResponse(
                content={"error": "Invalid encryption password"},
                status_code=403,
            )

    return JSONResponse(content={"result": user})


@router.put("/me")
async def set_user_info(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Set user information.
    Used by the frontend to set user information.

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The result of the operation.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    # Get json data
    data = await request.json()

    encryption_settings = data.get("encryption", False)
    encryption_password = data.get("encryption_password", "")
    reset_password = data.get("reset_password", False)
    verify_password = data.get("verify_password", "")
    email = data.get("email", "")

    if encryption_settings and encryption_password:
        user_update(
            user_id,
            encryption_settings=encryption_settings,
            encryption_password=encryption_password,
        )
    elif reset_password:
        user_update(user_id, reset_encryption=True)
    elif verify_password:
        private_key = user_get_private_key(user_id)

        if not validate_private_key_password(private_key, encryption_password):
            return JSONResponse(
                content={"error": "Invalid encryption password"},
                status_code=403,
            )
    elif email:
        user_update(user_id, email=email)

    return JSONResponse(content={"result": {"status": "OK"}})
