import json

from auth.client import dn_in_list, verify_client_dn
from fastapi import APIRouter, UploadFile, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, JSONResponse
from db.job import (
    job_get,
    job_get_next,
    job_result_save,
    job_update,
)
from db.user import (
    user_get,
    user_get_from_job,
    user_get_private_key,
    user_get_public_key,
    user_get_username_from_job,
    user_update,
    user_get_notifications,
)
from db.models import JobStatusEnum
from pathlib import Path
from utils.log import get_logger
from utils.settings import get_settings

from utils.crypto import (
    decrypt_data_from_file,
    deserialize_private_key_from_pem,
    deserialize_public_key_from_pem,
    encrypt_data_to_file,
    encrypt_string,
)
from utils.notifications import notifications
from utils.validators import TranscriptionJobUpdateRequest, TranscriptionResultRequest

log = get_logger()
router = APIRouter(tags=["job"])
settings = get_settings()


@router.put("/job/{job_id}")
async def update_transcription_status(
    request: Request,
    item: TranscriptionJobUpdateRequest,
    job_id: str,
) -> JSONResponse:
    """
    Update the status of a transcription job.

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job to update.

    Returns:
        JSONResponse: The updated job status.
    """

    verify_client_dn(request)

    user_id = user_get_from_job(job_id)
    username = user_get_username_from_job(job_id)

    if user_id is None or job_id is None:
        raise Exception("Job or user not found: {} - {}".format(job_id, user_id))

    file_path = Path(settings.API_FILE_STORAGE_DIR) / user_id / job_id

    job = job_update(
        job_id,
        user_id,
        status=item.status,
        error=item.error,
        transcribed_seconds=item.transcribed_seconds,
    )

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    if job["status"] == JobStatusEnum.COMPLETED:
        # Check if the user exists or if the user_id is in the dn list (used
        # by integrations)
        if not user_update(
            username,
            transcribed_seconds=item.transcribed_seconds,
            active=None,
        ) and not dn_in_list(user_id):
            return JSONResponse(
                content={"result": {"error": "User not found"}}, status_code=404
            )

        if email := user_get_notifications(user_id, "job"):
            notifications.send_transcription_finished(email)
    elif job["status"] == JobStatusEnum.FAILED:
        if email := user_get_notifications(user_id, "job"):
            notifications.send_transcription_failed(email)

    # We don't want to keep files for failed or completed jobs
    # for security and storage reasons. Remove them.
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

    Parameters:
        request (Request): The incoming HTTP request.

    Returns:
        JSONResponse: The next available job.
    """
    verify_client_dn(request)

    return JSONResponse(content={"result": jsonable_encoder(job_get_next())})


@router.get("/job/{user_id}/{job_id}/file")
async def get_transcription_file(
    request: Request,
    user_id: str,
    job_id: str,
) -> StreamingResponse:
    """
    Get the data to transcribe.

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the user.
        job_id (str): The ID of the job.

    Returns:
        StreamingResponse: The encrypted file stream.
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

    api_user = user_get(username="api_user")

    if not api_user:
        return JSONResponse(
            content={"result": {"error": "API user not found"}}, status_code=500
        )

    private_key = user_get_private_key(api_user["user"]["user_id"])
    private_key = deserialize_private_key_from_pem(
        private_key, settings.API_PRIVATE_KEY_PASSWORD
    )

    stream = decrypt_data_from_file(
        private_key,
        str(file_path),
    )

    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.bin"'},
    )


@router.put("/job/{user_id}/{job_id}/file")
async def put_video_file(
    request: Request,
    user_id: str,
    job_id: str,
    file: UploadFile,
) -> JSONResponse:
    """
    Upload the video file to transcribe.

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the user.
        job_id (str): The ID of the job.
        file (UploadFile): The uploaded file.

    Returns:
        JSONResponse: The result of the upload.
    """

    verify_client_dn(request)
    filename = file.filename + ".enc"

    if not job_get(job_id, user_id):
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    file_path = Path(settings.API_FILE_STORAGE_DIR + "/" + user_id)

    if not file_path.exists():
        file_path.mkdir(parents=True, exist_ok=True)

    file_bytes = await file.read()
    public_key = user_get_public_key(user_id)
    public_key = deserialize_public_key_from_pem(public_key)

    encrypt_data_to_file(
        public_key,
        file_bytes,
        str(file_path / filename),
    )

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
    item: TranscriptionResultRequest,
    user_id: str,
    job_id: str,
) -> JSONResponse:
    """
    Upload the transcription result.

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the user.
        job_id (str): The ID of the job.

    Returns:
        JSONResponse: The result of the upload.
    """

    verify_client_dn(request)

    job = job_get(job_id, user_id)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    # Encrypt the data with the users public key
    public_key = user_get_public_key(user_id)
    public_key = deserialize_public_key_from_pem(public_key)

    match item.format:
        case "srt":
            encrypted_result = encrypt_string(public_key, item.result)
            job_result_save(
                job_id,
                user_id,
                result_srt=encrypted_result,
                external_id=job["external_id"],
            )
        case "json":
            json_str = json.dumps(item.result)
            encrypted_result = encrypt_string(public_key, json_str)
            job_result_save(
                job_id, user_id, result=encrypted_result, external_id=job["external_id"]
            )
        case "mp4":
            pass
        case _:
            return JSONResponse(
                content={"result": {"error": "Unsupported format"}}, status_code=400
            )

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
