import aiofiles

from fastapi import APIRouter, UploadFile, Request, Header
from fastapi.responses import FileResponse, JSONResponse, Response
from db.session import get_session
from db.job import (
    job_create,
    job_delete,
    job_get,
    job_get_all,
    job_update,
    job_result_get,
    job_result_save,
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


@router.delete("/transcriber/{job_id}")
async def delete_transcription_job(
    request: Request,
    job_id: str,
) -> JSONResponse:
    """
    Delete a transcription job.

    Used by the frontend to delete a transcription job.
    """

    user_id = await verify_user(request)

    job = job_get(db_session, job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    # Delete the job from the database
    job_delete(db_session, job_id)

    # Remove the video file if it exists
    file_path = Path(api_file_storage_dir) / user_id / f"{job_id}.mp4"
    if file_path.exists():
        file_path.unlink()

    return JSONResponse(content={"result": {"status": "OK"}})


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
    speakers = data.get("speakers", 0)
    status = data.get("status")
    error = data.get("error")

    job = job_update(
        db_session,
        job_id,
        user_id=user_id,
        language=language,
        model_type=model,
        speakers=speakers,
        status=status,
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
async def put_transcription_result(request: Request, job_id: str) -> JSONResponse:
    """
    Upload the transcription result.
    """
    user_id = await verify_user(request)
    json_data = await request.json()

    try:
        if not job_get(db_session, job_id, user_id):
            print(f"Job with ID {job_id} not found for user {user_id}.")
            return JSONResponse(
                content={"result": {"error": "Job not found"}}, status_code=404
            )

        if json_data["format"] == "srt":
            print(f"Saving SRT result for job {job_id} for user {user_id}.")
            job_result_save(
                db_session,
                job_id,
                user_id,
                result_srt=json_data["data"],
            )
        elif json_data["format"] == "json":
            print(f"Saving JSON result for job {job_id} for user {user_id}.")
            job_result_save(
                db_session,
                job_id,
                user_id,
                result=json_data,
            )
    except Exception as e:
        print(e)
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)

    return JSONResponse(content={"result": {"status": "OK"}}, status_code=200)


@router.get("/transcriber/{job_id}/result/{output_format}")
async def get_transcription_result(
    request: Request, job_id: str, output_format: OutputFormatEnum
) -> FileResponse:
    """
    Get the transcription result.
    """

    user_id = await verify_user(request)
    job = job_get(db_session, job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    job_result = job_result_get(db_session, user_id, job_id)

    if not job_result:
        return JSONResponse(
            content={"result": {"error": "Job result not found"}}, status_code=404
        )

    match output_format:
        case OutputFormatEnum.TXT:
            content = job_result.get("result", "")
        case OutputFormatEnum.SRT:
            content = job_result.get("result_srt", "")
        case OutputFormatEnum.CSV:
            pass
        case _:
            return JSONResponse(
                content={"result": {"error": "Unsupported output format"}},
                status_code=400,
            )

    return JSONResponse(
        content={"result": content},
        media_type="text/plain",
    )


@router.get("/transcriber/{job_id}/videostream")
async def get_video_stream(
    request: Request, job_id: str, range: str = Header(None)
) -> FileResponse:
    """
    Get the video stream for a transcription job.
    """

    user_id = await verify_user(request)

    job = job_get(db_session, job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    file_path = Path(api_file_storage_dir) / user_id / f"{job_id}.mp4"

    if not file_path.exists():
        return JSONResponse({"result": {"error": "File not found"}}, status_code=404)

    if not range or not range.startswith("bytes="):
        return JSONResponse(
            {"result": {"error": "Invalid or missing Range header"}}, status_code=416
        )

    filesize = int(file_path.stat().st_size)
    start, end = range.replace("bytes=", "").split("-")
    start = int(start)
    end = int(end) if end else filesize

    with open(file_path, "rb") as video:
        video.seek(start)
        data = video.read(end - start)
        headers = {
            "Content-Range": f"bytes {str(start)}-{str(end)}/{filesize}",
            "Accept-Ranges": "bytes",
        }

        return Response(data, status_code=206, headers=headers, media_type="video/mp4")
