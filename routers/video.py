from fastapi import APIRouter, Response, Request
from auth.oidc import verify_user
from fastapi.responses import FileResponse
from utils.settings import get_settings
from pathlib import Path
import subprocess

router = APIRouter(tags=["video"])

settings = get_settings()
api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/video")
async def get_video(request: Request, job_id: str):
    """
    Endpoint to retrieve video information.
    """

    user_id = await verify_user(request)

    path = f"{settings.API_FILE_STORAGE_DIR}/{user_id}/{job_id}.mp4"

    return FileResponse(path, filename=f"{job_id}.mp4", media_type="video/mp4")
