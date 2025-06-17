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
    job_get,
    job_update,
    job_get_next,
    job_result_save,
)
from db.user import user_get_from_job, user_update
from db.models import JobStatusEnum
from utils.settings import get_settings
from pathlib import Path

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

    if job["status"] == JobStatusEnum.COMPLETED:
        user_id = user_get_from_job(db_session, job_id)
        user_update(db_session, user_id, data["transcribed_seconds"])

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
    job = job_get(db_session, job_id, user_id)

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


@router.put("/job/{user_id}/{job_id}/file")
async def put_video_file(
    request: Request, user_id: str, job_id: str, file: UploadFile
) -> JSONResponse:
    """
    Upload the video file to transcribe.
    """

    filename = file.filename

    if not job_get(db_session, job_id, user_id):
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
    request: Request, user_id: str, job_id: str
) -> JSONResponse:
    """
    Upload the transcription result.
    """

    if not job_get(db_session, job_id, user_id):
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    data = await request.json()

    match data["format"]:
        case "srt":
            job_result_save(
                db_session,
                job_id,
                user_id,
                result_srt=data["result"],
            )
        case "json":
            job_result_save(
                db_session,
                job_id,
                user_id,
                result=data["result"],
            )
        case "mp4":
            data = await request.body()
            file_path = Path(api_file_storage_dir) / user_id / f"{job_id}.mp4"
            async with aiofiles.open(file_path, "wb") as out_file:
                await out_file.write(data)

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
            }
        }
    )
