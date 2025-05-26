import aiofiles

from fastapi import (
    APIRouter,
    UploadFile,
    Request,
)
from fastapi.responses import FileResponse, JSONResponse
from db.session import get_session
from db.job import (
    job_create,
    job_get,
    job_get_all,
    job_update,
)
from db.models import JobStatus, JobType, JobStatusEnum, OutputFormatEnum
from typing import Optional
from utils.settings import get_settings
from pathlib import Path
from auth.oidc import verify_user

router = APIRouter(tags=["transcriber"])
settings = get_settings()
db_session = get_session()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/transcriber")
async def transcribe(
    request: Request, job_id: str = "", status: Optional[JobStatus] = None
) -> JSONResponse:
    """
    Transcribe audio file.

    Used by the frontend to get the status of a transcription job.
    """

    user_id = await verify_user(request)

    if job_id:
        res = job_get(db_session, job_id, user_id)
    else:
        res = job_get_all(db_session, user_id)

    return JSONResponse(content={"result": res})


@router.post("/transcriber")
async def transcribe_file(
    request: Request,
    file: UploadFile,
) -> JSONResponse:
    """
    Transcribe audio file.

    Used by the frontend to upload an audio file for transcription.
    """

    user_id = await verify_user(request)

    # Create a job for the transcription
    job = job_create(
        db_session,
        user_id=user_id,
        job_type=JobType.TRANSCRIPTION,
        filename=file.filename,
        output_format=OutputFormatEnum.SRT,
    )

    try:
        file_path = Path(api_file_storage_dir + "/" + user_id)
        if not file_path.exists():
            file_path.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path / job["uuid"], "wb") as out_file:
            while True:
                chunk = await file.read(1024)
                if not chunk:
                    break
                await out_file.write(chunk)
    except Exception as e:
        job = job_update(
            db_session, job["uuid"], user_id, status=JobStatus.FAILED, error=str(e)
        )
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)

    job = job_update(db_session, job["uuid"], status=JobStatusEnum.UPLOADED)

    return JSONResponse(
        content={
            "result": {
                "uuid": job["uuid"],
                "user_id": user_id,
                "status": job["status"],
                "job_type": job["job_type"],
                "filename": file.filename,
            }
        }
    )


@router.put("/transcriber/{job_id}")
async def update_transcription_status(
    request: Request,
    job_id: str,
) -> JSONResponse:
    """
    Update the status of a transcription job.

    Used by the frontend and worker to update the status of a transcription job.
    """

    user_id = await verify_user(request)
    data = await request.json()
    language = data.get("language")
    model = data.get("model")
    status = data.get("status")
    output_format = data.get("output_format")
    error = data.get("error")

    print(f"Job ID: {job_id}")
    print(f"User ID: {user_id}")
    print(f"Language: {language}")
    print(f"Model: {model}")
    print(f"Status: {status}")
    print(f"Output Format: {output_format}")

    job = job_update(
        db_session,
        job_id,
        user_id=user_id,
        language=language,
        model_type=model,
        status=status,
        output_format=output_format,
        error=error,
    )

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    return JSONResponse(
        content={
            "result": {
                "uuid": job["uuid"],
                "user_id": user_id,
                "status": job["status"],
                "job_type": job["job_type"],
                "filename": job["filename"],
                "language": job["language"],
                "model_type": job["model_type"],
            }
        }
    )


@router.put("/transcriber/{job_id}/result")
async def put_transcription_result(
    request: Request, user_id: str, job_id: str, file: UploadFile
) -> JSONResponse:
    """
    Upload the transcription result.
    """
    user_id = await verify_user(request)

    if not job_get(db_session, job_id, user_id):
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    try:
        file_path = Path(api_file_storage_dir) / user_id / file.filename
        print(file_path)
        async with aiofiles.open(file_path, "wb") as out_file:
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
    except Exception as e:
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)


@router.get("/transcriber/{job_id}/result")
async def get_transcription_result(request: Request, job_id: str) -> FileResponse:
    """
    Get the transcription result.
    """

    user_id = await verify_user(request)
    job = job_get(db_session, job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    match job["output_format"]:
        case OutputFormatEnum.TXT:
            file_path = Path(api_file_storage_dir) / user_id / f"{job['uuid']}.txt"
        case OutputFormatEnum.SRT:
            file_path = Path(api_file_storage_dir) / user_id / f"{job['uuid']}.srt"
        case OutputFormatEnum.CSV:
            file_path = Path(api_file_storage_dir) / user_id / f"{job['uuid']}.csv"
        case _:
            return JSONResponse(
                content={"result": {"error": "Unsupported output format"}},
                status_code=400,
            )

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return JSONResponse({"result": {"error": "File not found"}}, status_code=404)

    return FileResponse(file_path)
