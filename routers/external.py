import aiofiles
from pathlib import Path
from typing import Optional
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from db.job import (
    job_create,
    job_get_by_external_id,
    job_remove,
    job_update,
    job_result_get_external,
)
from db.models import JobStatus, JobType, JobStatusEnum
from db.user import user_create
from auth.client import verify_client_dn
from utils.log import get_logger
from utils.settings import get_settings
from utils.validators import TranscribeExternalPost

logger = get_logger()
router = APIRouter(tags=["external"])
settings = get_settings()
api_file_storage_dir = settings.API_FILE_STORAGE_DIR


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
    item: TranscribeExternalPost,
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
    filename = item.external_id
    job = None

    try:
        kaltura_repsonse = await run_in_threadpool(
            lambda: requests.get(item.url, timeout=120)
        )

        if kaltura_repsonse.status_code != 200:
            raise Exception(
                "Bad status code response from kaltura: {}".format(
                    kaltura_repsonse.status_code
                )
            )

        user_create(username=item.user_id, user_id=item.user_id, realm="external")

        job = job_create(
            user_id=item.user_id,
            job_type=JobType.TRANSCRIPTION,
            filename=filename,
            language=item.language,
            model_type=item.model,
            output_format=item.output_format,
            external_id=item.external_id,
            external_user_id=item.external_user_id,
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
