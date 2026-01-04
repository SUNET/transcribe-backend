from fastapi import APIRouter, UploadFile, Request, Depends
from fastapi.responses import JSONResponse
from db.job import (
    job_create,
    job_remove,
    job_get,
    job_get_all,
    job_update,
    job_result_get,
    job_result_save,
)
from db.models import JobStatus, JobType, JobStatusEnum, OutputFormatEnum
from db.user import (
    user_get_quota_left,
    user_get_private_key,
    user_get,
    user_get_public_key,
)
from typing import Optional
from utils.settings import get_settings
from pathlib import Path
from auth.oidc import get_current_user_id
from utils.crypto import (
    deserialize_public_key_from_pem,
    deserialize_private_key_from_pem,
    decrypt_string,
    encrypt_data_to_file,
)
from utils.log import get_logger

router = APIRouter(tags=["transcriber"])
settings = get_settings()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR

logger = get_logger()


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

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job to get. If empty, get all jobs for the user.
        status (Optional[JobStatus]): Filter jobs by status.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The job status or list of jobs.
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

    Parameters:
        request (Request): The incoming HTTP request.
        file (UploadFile): The uploaded audio file.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The job status.
    """

    job = job_create(
        user_id=user_id,
        job_type=JobType.TRANSCRIPTION,
        filename=file.filename,
    )

    api_user = user_get(username="api_user")

    if not api_user:
        return JSONResponse(
            content={"result": {"error": "API user not found"}}, status_code=500
        )

    public_key = user_get_public_key(api_user["user"]["user_id"])
    public_key = deserialize_public_key_from_pem(public_key)

    try:
        file_path = Path(api_file_storage_dir + "/" + user_id)
        dest_path = file_path / job["uuid"]

        if not file_path.exists():
            file_path.mkdir(parents=True, exist_ok=True)

        file_bytes = await file.read()

        encrypt_data_to_file(
            public_key,
            file_bytes,
            dest_path,
        )

        job = job_update(job["uuid"], status=JobStatusEnum.UPLOADED)
    except Exception as e:
        job = job_update(
            job["uuid"], user_id, status=JobStatusEnum.FAILED, error=str(e)
        )
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)

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

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job to delete.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The result of the deletion.
    """

    job = job_get(job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    # Delete the job from the database
    job_remove(job_id)

    # Remove the video file if it exists
    file_path = Path(api_file_storage_dir) / user_id / f"{job_id}.mp4.enc"

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

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job to update.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The updated job status.
    """

    quota_left = user_get_quota_left(user_id)

    if not quota_left:
        return JSONResponse(
            content={
                "result": {
                    "error": "Quota exceeded, please contact your administrator."
                }
            },
            status_code=403,
        )

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

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job.
        user_id (str): The ID of the user.

    Returns:
        JSONResponse: The result of the upload.
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
) -> JSONResponse:
    """
    Get the transcription result.

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job.
        output_format (OutputFormatEnum): The desired output format.
        user_id (str): The ID of the user.

    Returns:
        JSONResponse: The transcription result.
    """

    data = await request.json()
    encryption_password = data.get("encryption_password", "")
    private_key = user_get_private_key(user_id)

    if encryption_password == "":
        encrypted_result = False

    if not (job_result := job_result_get(user_id, job_id)):
        return JSONResponse(
            content={"result": {"error": "Job result not found"}}, status_code=404
        )

    if encryption_password != "" and encryption_password is not None:
        encrypted_result = True

        try:
            deserialized_private_key = deserialize_private_key_from_pem(
                private_key, encryption_password
            )
        except Exception:
            encrypted_result = False
    else:
        encrypted_result = False

    match output_format:
        case OutputFormatEnum.TXT:
            content = job_result.get("result", "")

            if encrypted_result:
                try:
                    content = decrypt_string(deserialized_private_key, content)
                except ValueError:
                    content = job_result.get("result", "")
        case OutputFormatEnum.SRT:
            content = job_result.get("result_srt", "")

            if encrypted_result:
                try:
                    content = decrypt_string(deserialized_private_key, content)
                except ValueError:
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
