from auth.oidc import get_current_user_id
from db.job import job_result_get
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from utils.settings import get_settings

router = APIRouter(tags=["video"])

settings = get_settings()
api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/vtt")
async def get_vtt(
    request: Request,
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Endpoint to retrieve VTT file for a transcription job.
    """

    result = job_result_get(user_id, job_id)

    if not result:
        return Response(status_code=404, content="Job not found")

    subtitle = result["result_srt"]

    return Response(
        content=subtitle,
        media_type="text/vtt",
        headers={"Content-Disposition": f"attachment; filename={job_id}.vtt"},
    )


@router.get("/video")
async def get_video(
    request: Request,
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Endpoint to retrieve video information.
    """

    path = f"{settings.API_FILE_STORAGE_DIR}/{user_id}/{job_id}.mp4"

    return FileResponse(path, filename=f"{job_id}.mp4", media_type="video/mp4")
