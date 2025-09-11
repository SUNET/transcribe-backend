import shutil

from fastapi import APIRouter, UploadFile, Request, Header, Depends
from fastapi.responses import FileResponse, JSONResponse, Response
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
from fastapi.concurrency import run_in_threadpool
from auth.oidc import get_current_user_id

router = APIRouter(tags=["transcriber"])
settings = get_settings()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/transcriber")
async def transcribe(
    request: Request,
    job_id: str = "",
    status: Optional[JobStatus] = None,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Transcribe audio file.

    Used by the frontend to get the status of a transcription job.
    """

    if job_id:
        res = job_get(job_id, user_id)
    else:
        res = job_get_all(user_id)

    return JSONResponse(content={"result": res})


@router.post("/transcriber")
async def transcribe_file(
    request: Request,
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Transcribe audio file.

    Used by the frontend to upload an audio file for transcription.
    """

    # Create a job for the transcription
    job = job_create(
        user_id=user_id,
        job_type=JobType.TRANSCRIPTION,
        filename=file.filename,
    )

    try:
        file_path = Path(api_file_storage_dir + "/" + user_id)
        dest_path = file_path / job["uuid"]

        if not file_path.exists():
            file_path.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as f:
            await run_in_threadpool(shutil.copyfileobj, file.file, f, 1024 * 1024)
    except Exception as e:
        job = job_update(job["uuid"], user_id, status=JobStatus.FAILED, error=str(e))
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)

    job = job_update(job["uuid"], status=JobStatusEnum.UPLOADED)

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
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Delete a transcription job.

    Used by the frontend to delete a transcription job.
    """

    job = job_get(job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    # Delete the job from the database
    job_delete(job_id)

    # Remove the video file if it exists
    file_path = Path(api_file_storage_dir) / user_id / f"{job_id}.mp4"
    if file_path.exists():
        file_path.unlink()

    return JSONResponse(content={"result": {"status": "OK"}})


@router.put("/transcriber/{job_id}")
async def update_transcription_status(
    request: Request,
    job_id: str,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Update the status of a transcription job.

    Used by the frontend and worker to update the status of a transcription job.
    """

    data = await request.json()
    language = data.get("language")
    model = data.get("model")
    speakers = data.get("speakers", 0)
    status = data.get("status")
    error = data.get("error")
    output_format = data.get("output_format")

    job = job_update(
        job_id,
        user_id=user_id,
        language=language,
        model_type=model,
        speakers=speakers,
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
                "output_format": job["output_format"],
            }
        }
    )


@router.put("/transcriber/{job_id}/result")
async def put_transcription_result(
    request: Request,
    job_id: str,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Upload the transcription result.
    """
    json_data = await request.json()

    try:
        if not job_get(job_id, user_id):
            return JSONResponse(
                content={"result": {"error": "Job not found"}}, status_code=404
            )

        if json_data["format"] == "srt":
            job_result_save(
                job_id,
                user_id,
                result_srt=json_data["data"],
            )
        elif json_data["format"] == "json":
            job_result_save(
                job_id,
                user_id,
                result=json_data["data"],
            )
    except Exception as e:
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)

    return JSONResponse(content={"result": {"status": "OK"}}, status_code=200)


@router.get("/transcriber/{job_id}/result/{output_format}")
async def get_transcription_result(
    request: Request,
    job_id: str,
    output_format: OutputFormatEnum,
    user_id: str = Depends(get_current_user_id),
) -> FileResponse:
    """
    Get the transcription result.
    """

    job = job_get(job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    job_result = job_result_get(user_id, job_id)

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
    request: Request,
    job_id: str,
    range: str = Header(None),
    user_id: str = Depends(get_current_user_id),
) -> FileResponse:
    """
    Get the video stream for a transcription job.
    """

    job = job_get(job_id, user_id)

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
    end = int(end) if end else filesize - 1

    with open(file_path, "rb") as video:
        video.seek(start)
        data = video.read(end - start)
        headers = {
            "Content-Range": f"bytes {str(start)}-{str(end)}/{filesize}",
            "Accept-Ranges": "bytes",
        }

        return Response(data, status_code=206, headers=headers, media_type="video/mp4")
