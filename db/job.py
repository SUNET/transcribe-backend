import json

from datetime import datetime
from db.models import Job, JobResult, JobStatusEnum, Jobs
from db.session import get_session
from pathlib import Path
from typing import Optional
from utils.settings import get_settings

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

settings = get_settings()


def job_create(
    user_id: Optional[str] = None,
    job_type: Optional[JobStatusEnum] = None,
    language: Optional[str] = "",
    model_type: Optional[str] = "",
    filename: Optional[str] = "",
    output_format: Optional[str] = None,
    external_id: Optional[str] = None,
    billing_id: Optional[str] = None,
    client_dn: Optional[str] = None
) -> dict:
    """
    Create a new job in the database.
    """

    with get_session() as session:
        job = Job(
            user_id=user_id,
            job_type=job_type,
            language=language,
            model_type=model_type,
            status=JobStatusEnum.UPLOADING,
            filename=filename,
            output_format=output_format,
            external_id=external_id,
            billing_id=billing_id,
            client_dn=client_dn
        )

        session.add(job)

        return job.as_dict()


def job_get(uuid: str, user_id: str) -> Optional[Job]:
    """
    Get a job by UUID.
    """

    with get_session() as session:
        job = (
            session.query(Job)
            .filter(Job.uuid == uuid)
            .filter(Job.user_id == user_id)
            .first()
        )

        return job.as_dict() if job else {}


def job_get_by_external_id(external_id: str, client_dn: str) -> Optional[Job]:
    """
    Get a job by External ID.
    """
    logger.info("Job Fetch Started.")
    with get_session() as session:
        job = (
            session.query(Job)
            .filter(Job.external_id == external_id)
            # .filter(Job.client_dn == client_dn)
            .first()
        )

        logger.info("Job fetched. {}".format(job))

        return job.as_dict() if job else {}


def job_get_next() -> dict:
    """
    Get the next available job from the database.
    """

    with get_session() as session:
        job = (
            session.query(Job)
            .filter(Job.status == JobStatusEnum.PENDING)
            .with_for_update()
            .first()
        )

        if job:
            job.status = JobStatusEnum.IN_PROGRESS

        return job.as_dict() if job else {}


def job_get_all(user_id: str) -> list[Job]:
    """
    Get all jobs from the database.
    """

    with get_session() as session:
        jobs = session.query(Job).filter(Job.user_id == user_id).all()

        if not jobs:
            return {"jobs": []}

        return {"jobs": [job.as_dict() for job in jobs]}


def job_get_status(user_id: str) -> dict:
    """
    Get all job UUIDs together with statuses from the database.
    """

    with get_session() as session:
        columns = [Job.uuid, Job.status, Job.job_type, Job.created_at, Job.updated_at]
        query = session.query(*columns).filter(Job.user_id == user_id).all()

        if not query:
            return {}

        jobs = [job for job in query]

        return Jobs(jobs=jobs)


def job_update(
    uuid: str,
    user_id: Optional[str] = None,
    status: Optional[JobStatusEnum] = None,
    language: Optional[str] = None,
    model_type: Optional[str] = None,
    speakers: Optional[int] = None,
    error: Optional[str] = None,
    output_format: Optional[str] = None,
    transcribed_seconds: Optional[int] = 0,
) -> Optional[Job]:
    """
    Update a job by UUID.
    """

    with get_session() as session:
        job = session.query(Job).filter(Job.uuid == uuid).with_for_update().first()

        if not job:
            return None

        if user_id:
            job.user_id = user_id
        if status:
            job.status = status
        if error:
            job.error = error
        if language:
            job.language = language
        if model_type:
            job.model_type = model_type
        if speakers:
            job.speakers = speakers
        if output_format:
            job.output_format = output_format
        if transcribed_seconds:
            job.transcribed_seconds = transcribed_seconds

        return job.as_dict()


def job_delete(uuid: str) -> bool:
    """
    Delete a job by UUID.
    """

    with get_session() as session:
        job = session.query(Job).filter(Job.uuid == uuid).with_for_update().first()

        if not job:
            return False

        file_path = Path(settings.API_FILE_STORAGE_DIR) / job.user_id / job.uuid
        file_path_mp4 = (
            Path(settings.API_FILE_STORAGE_DIR) / job.user_id / f"{job.uuid}.mp4"
        )

        if file_path.exists():
            file_path.unlink()

        if file_path_mp4.exists():
            file_path_mp4.unlink()

        session.delete(job)

    return True


def job_cleanup() -> None:
    """
    Remove all jobs from the database.
    """

    with get_session() as session:
        jobs_to_delete = (
            session.query(Job).filter(Job.deletion_date <= datetime.now()).all()
        )

    for job in jobs_to_delete:
        job_delete(job.uuid)


def job_result_get(
    user_id: str,
    job_id: str,
) -> Optional[JobResult]:
    """
    Get the transcription result for a job by UUID.
    """

    with get_session() as session:
        res = (
            session.query(JobResult)
            .filter(
                JobResult.job_id == job_id,
                JobResult.user_id == user_id,
            )
            .first()
        )

        return res.as_dict() if res else {}

def job_result_get_external(
    external_id: str,
) -> Optional[JobResult]:
    """
    Get the transcription result for a job by UUID.
    """

    with get_session() as session:
        res = (
            session.query(JobResult)
            .filter(
                JobResult.external_id == external_id,
            )
            .first()
        )

        return res.as_dict() if res else {}


def job_result_save(
    uuid: str,
    user_id: str,
    result_srt: Optional[str] = {},
    result: Optional[str] = "",
    external_id: Optional[str] = None,
    result_path: Optional[str] = None
) -> JobResult:
    """
    Save the transcription result for a job.
    """

    with get_session() as session:
        job = session.query(Job).filter(Job.uuid == uuid).first()

        if not job:
            raise ValueError("Job not found")

        job_result = (
            session.query(JobResult)
            .filter(
                JobResult.job_id == uuid,
                JobResult.user_id == user_id,
            )
            .first()
        )

        if job_result:
            if result:
                job_result.result = json.dumps(result)
            if result_srt:
                job_result.result_srt = result_srt
        else:
            job_result = JobResult(
                job_id=uuid,
                user_id=user_id,
                external_id=external_id,
                result=json.dumps(result) if result else None,
                result_srt=result_srt if result_srt else None,
                result_path=result_path if result_path else None
            )

        session.add(job_result)

        return job_result.as_dict()
