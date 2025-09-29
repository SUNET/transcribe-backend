import aiofiles

from fastapi import APIRouter, UploadFile, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from db.job import (
    job_get,
    job_update,
    job_get_next,
    job_result_save,
)
from db.user import user_get_from_job, user_get_username_from_job, user_update
from db.models import JobStatusEnum
from utils.settings import get_settings
from pathlib import Path
from typing import Optional
from utils.log import get_logger

log = get_logger()
router = APIRouter(tags=["job"])
settings = get_settings()


def verify_client_dn(
    request: Request,
) -> Optional[str]:
    """
    Verify the client DN from the request headers.
    """

    if settings.API_WORKER_CLIENT_DN == "":
        log.warning("API_WORKER_CLIENT_DN is not set, skipping client DN verification")
        return "TranscriberWorker"

    client_dn = request.headers.get("x-client-dn")

    if not client_dn or client_dn.strip() != settings.API_WORKER_CLIENT_DN:
        log.error("Invalid client DN.")
        raise HTTPException(status_code=403, detail="Invalid request")

    log.info(f"Client DN {client_dn} verified.")

    return client_dn


@router.put("/job/{job_id}")
async def update_transcription_status(
    request: Request,
    job_id: str,
) -> JSONResponse:
    """
    Update the status of a transcription job.
    """

    verify_client_dn(request)
    data = await request.json()
    user_id = user_get_from_job(job_id)
    username = user_get_username_from_job(job_id)
    file_path = Path(settings.API_FILE_STORAGE_DIR) / user_id / job_id

    job = job_update(
        job_id,
        user_id,
        status=data["status"],
        error=data["error"],
        transcribed_seconds=data["transcribed_seconds"],
    )

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    if job["status"] == JobStatusEnum.COMPLETED:
        if not user_update(
            username,
            transcribed_seconds=data["transcribed_seconds"],
            active=None,
        ):
            return JSONResponse(
                content={"result": {"error": "User not found"}}, status_code=404
            )

    if (
        job["status"] == JobStatusEnum.FAILED
        or job["status"] == JobStatusEnum.COMPLETED
    ):
        if file_path.exists():
            file_path.unlink()

    return JSONResponse(content={"result": job})


@router.get("/job/next")
async def get_transcription_job(
    request: Request,
) -> JSONResponse:
    """
    Get the next available job.
    """
    verify_client_dn(request)
    job = job_get_next()
    return JSONResponse(content={"result": jsonable_encoder(job)})


@router.get("/job/{user_id}/{job_id}/file")
async def get_transcription_file(
    request: Request,
    user_id: str,
    job_id: str,
) -> FileResponse:
    """
    Get the data to transcribe.
    """
    verify_client_dn(request)
    job = job_get(job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    file_path = Path(settings.API_FILE_STORAGE_DIR) / user_id / job_id

    if not file_path.exists():
        return JSONResponse(
            content={"result": {"error": "File not found"}}, status_code=404
        )

    return FileResponse(file_path)


@router.put("/job/{user_id}/{job_id}/file")
async def put_video_file(
    request: Request,
    user_id: str,
    job_id: str,
    file: UploadFile,
) -> JSONResponse:
    """
    Upload the video file to transcribe.
    """

    verify_client_dn(request)
    filename = file.filename

    if not job_get(job_id, user_id):
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    file_path = Path(settings.API_FILE_STORAGE_DIR + "/" + user_id)

    if not file_path.exists():
        file_path.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path / filename, "wb") as out_file:
        while True:
            chunk = await file.read(1024)
            if not chunk:
                break
            await out_file.write(chunk)

    return JSONResponse(
        content={
            "result": {
                "uuid": job_id,
                "user_id": user_id,
                "filename": filename,
            }
        },
        status_code=200,
    )


@router.put("/job/{user_id}/{job_id}/result")
async def put_transcription_result(
    request: Request,
    user_id: str,
    job_id: str,
) -> JSONResponse:
    """
    Upload the transcription result.
    """

    verify_client_dn(request)

    if not job_get(job_id, user_id):
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    data = await request.json()

    match data["format"]:
        case "srt":
            job_result_save(
                job_id,
                user_id,
                result_srt=data["result"],
            )
        case "json":
            job_result_save(
                job_id,
                user_id,
                result=data["result"],
            )
        case "mp4":
            data = await request.body()
            file_path = Path(settings.API_FILE_STORAGE_DIR) / user_id / f"{job_id}.mp4"
            async with aiofiles.open(file_path, "wb") as out_file:
                await out_file.write(data)

    job = job_update(
        job_id,
        status=JobStatusEnum.COMPLETED,
        error=None,
    )

    return JSONResponse(
        content={
            "result": {
                "uuid": job["uuid"],
                "status": job["status"],
                "job_type": job["job_type"],
            }
        }
    )
