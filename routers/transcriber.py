import aiofiles
import requests

from fastapi import APIRouter, UploadFile, Request, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse, Response
from db.job import (
    job_create,
    job_remove,
    job_get,
    job_get_all,
    job_update,
    job_result_get,
    job_result_save,
    job_get_by_external_id,
    job_result_get_external,
)
from db.models import JobStatus, JobType, JobStatusEnum, OutputFormatEnum
from db.user import (
    user_get_quota_left,
    user_create,
    user_get_private_key,
    user_get,
    user_get_public_key,
)
from typing import Optional
from utils.settings import get_settings
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from auth.oidc import get_current_user_id
from auth.client_auth import verify_client_dn
from utils.crypto import (
    deserialize_public_key_from_pem,
    deserialize_private_key_from_pem,
    decrypt_string,
    decrypt_data_from_file,
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

    if not (job_result := job_result_get(user_id, job_id)):
        return JSONResponse(
            content={"result": {"error": "Job result not found"}}, status_code=404
        )

    try:
        deserialized_private_key = deserialize_private_key_from_pem(
            private_key, encryption_password
        )
    except ValueError:
        # If we can't deserialize the private key, assume the
        # data is not encrypted yet.
        encrypted_result = False
    else:
        encrypted_result = True

    match output_format:
        case OutputFormatEnum.TXT:
            content = job_result.get("result", "")

            if encrypted_result:
                content = decrypt_string(deserialized_private_key, content)
        case OutputFormatEnum.SRT:
            content = job_result.get("result_srt", "")

            if encrypted_result:
                content = decrypt_string(deserialized_private_key, content)
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
) -> StreamingResponse:
    """
    Stream an encrypted video for a transcription job.

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job.
        range (str): The byte range for streaming.
        user_id (str): The ID of the user.

    Returns:
        StreamingResponse: The video stream response.
    """

    job = job_get(job_id, user_id)
    data = await request.json()
    encryption_password = data.get("encryption_password", "")

    try:
        private_key = user_get_private_key(user_id)
        private_key = deserialize_private_key_from_pem(private_key, encryption_password)
    except ValueError:
        encrypted_media = False
    else:
        encrypted_media = True

    if not job:
        return JSONResponse({"result": {"error": "Job not found"}}, status_code=404)

    file_path = Path(api_file_storage_dir) / user_id / f"{job_id}.mp4.enc"

    if not file_path.exists():
        return JSONResponse({"result": {"error": "File not found"}}, status_code=404)

    filesize = file_path.stat().st_size

    if not range or not range.startswith("bytes="):
        range_start = 0
        range_end = filesize - 1
    else:
        range_start_str, range_end_str = range.replace("bytes=", "").split("-")
        range_start = int(range_start_str)
        range_end = int(range_end_str) if range_end_str else filesize - 1

    # New way to serve encrypted video files
    if encrypted_media:
        # Determine which chunks correspond to the byte range
        start_chunk = range_start // settings.CRYPTO_CHUNK_SIZE
        end_chunk = range_end // settings.CRYPTO_CHUNK_SIZE

        def stream_chunks():
            offset_in_first_chunk = range_start % settings.CRYPTO_CHUNK_SIZE
            last_chunk_bytes = (range_end % settings.CRYPTO_CHUNK_SIZE) + 1

            for i, chunk in enumerate(
                decrypt_data_from_file(private_key, file_path, start_chunk, end_chunk)
            ):
                if i == 0:
                    # First chunk: apply range_start offset
                    chunk = chunk[offset_in_first_chunk:]
                if i == (end_chunk - start_chunk):
                    # Last chunk: trim to range_end
                    chunk = chunk[:last_chunk_bytes]
                yield chunk
        headers = {
            "Content-Range": f"bytes {range_start}-{range_end}/{filesize}",
            "Accept-Ranges": "bytes",
        }

        return StreamingResponse(
            stream_chunks(), status_code=206, headers=headers, media_type="video/mp4"
        )

    # Old way to serve unencrypted video files
    else:
        filesize = int(file_path.stat().st_size)
        range_start, range_end = range.replace("bytes=", "").split("-")
        range_start = int(range_start)
        range_end = int(range_end) if range_end else filesize - 1

        with open(file_path, "rb") as video:
            video.seek(range_start)
            data = video.read(range_end - range_start + 1)
            headers = {
                "Content-Range": f"bytes {str(range_start)}-{str(range_end)}/{filesize}",
                "Accept-Ranges": "bytes",
            }

            return Response(data, status_code=206, headers=headers, media_type="video/mp4")



@router.get("/transcriber/external/{external_id}")
async def get_job_external(
    request: Request,
    external_id: str = "",
    status: Optional[JobStatus] = None,
) -> JSONResponse:
    """
    Get job by external id.

    Used by external integrations.

    Parameters:
        request (Request): The incoming HTTP request.
        external_id (str): The external ID of the job.
        status (Optional[JobStatus]): Filter jobs by status.

    Returns:
        JSONResponse: The job status.
    """

    client_dn = verify_client_dn(request)
    res = job_get_by_external_id(external_id, client_dn)

    if isinstance(res, dict) and res and res["status"] == "completed":
        job_result = job_result_get_external(external_id)
        res["result_srt"] = job_result["result_srt"]

    return JSONResponse(content={"result": res})


@router.delete("/transcriber/external/{external_id}")
async def delete_external_transcription_job(
    request: Request,
    external_id: str,
) -> JSONResponse:
    """
    Delete an external transcription job.
    Used by integrations to clean up completed/failed jobs.

    Parameters:
        request (Request): The incoming HTTP request.
        external_id (str): The external ID of the job to delete.

    Returns:
        JSONResponse: The result of the deletion.
    """
    client_dn = verify_client_dn(request)
    job = job_get_by_external_id(external_id, client_dn)

    if not job:
        return JSONResponse(
            content={"result": {"error": "Job not found"}}, status_code=404
        )

    # Delete the job from the database
    status = job_remove(job["uuid"])

    if status is False:
        logger.debug(f"JOB REMOVE FALSE: {job}")

    # Remove the video file if it exists
    file_path = Path(api_file_storage_dir) / job["user_id"] / f"{job["uuid"]}.mp4"

    if file_path.exists():
        file_path.unlink()

    return JSONResponse(content={"result": {"status": "OK"}})


@router.post("/transcriber/external")
async def transcribe_external_file(
    request: Request,
) -> JSONResponse:
    """
    Transcribe audio file.

    Used by external integrations to upload files.

    Parameters:
        request (Request): The incoming HTTP request.

    Returns:
        JSONResponse: The job status.
    """

    client_dn = verify_client_dn(request)

    data = await request.json()
    external_id = data.get("id")
    external_user_id = data.get("external_user_id")
    language = data.get("language")
    model = settings.EXTERNAL_JOB_MODEL
    output_format = data.get("output_format")
    user_id = data["user_id"]
    url = data.get("file_url")
    filename = external_id
    job = None

    try:
        kaltura_repsonse = await run_in_threadpool(
            lambda: requests.get(url, timeout=120)
        )

        if kaltura_repsonse.status_code != 200:
            raise Exception(
                "Bad status code response from kaltura: {}".format(
                    kaltura_repsonse.status_code
                )
            )

        user_create(username=user_id, user_id=user_id, realm="external")

        job = job_create(
            user_id=user_id,
            job_type=JobType.TRANSCRIPTION,
            filename=filename,
            language=language,
            model_type=model,
            output_format=output_format,
            external_id=external_id,
            external_user_id=external_user_id,
            client_dn=client_dn,
        )

        file_path = Path(api_file_storage_dir + "/" + user_id)
        dest_path = file_path / job["uuid"]

        if not file_path.exists():
            file_path.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(dest_path, "wb") as out_file:
            await out_file.write(kaltura_repsonse.content)

    except Exception as e:
        logger.error("Caught exception while creating external job - {}".format(e))
        if job is not None:
            job = job_update(
                job["uuid"], user_id, status=JobStatusEnum.FAILED, error=str(e)
            )
        return JSONResponse(content={"result": {"error": str(e)}}, status_code=500)

    job = job_update(job["uuid"], status=JobStatusEnum.PENDING)

    return JSONResponse(
        content={
            "result": {
                "uuid": job["uuid"],
                "user_id": user_id,
                "status": job["status"],
                "job_type": job["job_type"],
                "filename": filename,
            }
        }
    )
