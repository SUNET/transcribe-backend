import aiofiles

from fastapi import (
    APIRouter,
    UploadFile,
    Request,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from db.session import get_session
from db.job import (
    job_create,
    job_get,
    job_get_all,
    job_update,
    job_get_next,
)
from db.models import JobStatus, JobType, JobStatusEnum, OutputFormatEnum
from typing import Optional
from utils.settings import get_settings
from pathlib import Path
from auth.oidc import verify_user

router = APIRouter(tags=["job"])
settings = get_settings()
db_session = get_session()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.put("/job/{job_id}")
async def update_transcription_status(
    request: Request,
    job_id: str,
) -> JSONResponse:
    """
    Update the status of a transcription job.
    """

    data = await request.json()

    job = job_update(
        db_session,
        job_id,
        status=data["status"],
        error=data["error"],
    )

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    return JSONResponse(content={"result": job})


@router.get("/job/next")
async def get_transcription_job(request: Request) -> JSONResponse:
    """
    Get the next available job.
    """
    job = job_get_next(db_session)
    return JSONResponse(content={"result": jsonable_encoder(job)})


@router.get("/job/{user_id}/{job_id}/file")
async def get_transcription_file(
    request: Request, user_id: str, job_id: str
) -> FileResponse:
    """
    Get the data to transcribe.
    """
    job = job_get(db_session, job_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    file_path = Path(api_file_storage_dir) / user_id / job_id

    if not file_path.exists():
        return JSONResponse(
            content={"result": {"error": "File not found"}}, status_code=404
        )

    return FileResponse(file_path)


@router.put("/job/{user_id}/{job_id}/result")
async def put_transcription_result(
    request: Request, user_id: str, job_id: str, file: UploadFile
) -> JSONResponse:
    """
    Upload the transcription result.
    """
    filename = file.filename

    if not job_get(db_session, job_id):
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    file_path = Path(api_file_storage_dir + "/" + user_id)
    if not file_path.exists():
        file_path.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(file_path / filename, "wb") as out_file:
        while True:
            chunk = await file.read(1024)
            if not chunk:
                break
            await out_file.write(chunk)

    job = job_update(
        db_session,
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
                "filename": file.filename,
            }
        }
    )
