from auth.oidc import get_current_user
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from utils.settings import get_settings

router = APIRouter(tags=["video"])

settings = get_settings()
api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/video")
async def get_video(
    request: Request,
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Endpoint to retrieve video information.

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job.
        user (dict): The current user.

    Returns:
        FileResponse: The video file response.
    """

    path = f"{settings.API_FILE_STORAGE_DIR}/{user["user_id"]}/{job_id}.mp4"

    return FileResponse(path, filename=f"{job_id}.mp4", media_type="video/mp4")
