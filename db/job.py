import json

from datetime import datetime
from datetime import timedelta
from db.models import Job
from db.models import JobResult
from db.models import JobStatusEnum
from db.models import Jobs
from db.session import get_session
from pathlib import Path
from sqlmodel import Session
from typing import Optional
from utils.settings import get_settings

settings = get_settings()


def job_create(
    session: Session,
    user_id: Optional[str] = None,
    job_type: Optional[JobStatusEnum] = None,
    language: Optional[str] = "",
    model_type: Optional[str] = "",
    filename: Optional[str] = "",
) -> dict:
    """
    Create a new job in the database.
    """
    job = Job(
        user_id=user_id,
        job_type=job_type,
        language=language,
        model_type=model_type,
        status=JobStatusEnum.UPLOADING,
        filename=filename,
    )

    session.add(job)
    session.commit()

    return job.as_dict()


def job_get(session: Session, uuid: str, user_id: str) -> Optional[Job]:
    """
    Get a job by UUID.
    """

    job = (
        session.query(Job)
        .filter(Job.uuid == uuid)
        .filter(Job.user_id == user_id)
        .first()
    )

    return job.as_dict() if job else {}


def job_get_next(session: Session) -> dict:
    """
    Get the next available job from the database.
    """

    job = session.query(Job).filter(Job.status == JobStatusEnum.PENDING).first()

    if job:
        job.status = JobStatusEnum.IN_PROGRESS
        session.commit()

    return job.as_dict() if job else {}


def job_get_all(session: Session, user_id: str) -> list[Job]:
    """
    Get all jobs from the database.
    """
    jobs = session.query(Job).filter(Job.user_id == user_id).all()

    if not jobs:
        return {"jobs": []}

    return {"jobs": [job.as_dict() for job in jobs]}


def job_get_status(session: Session, user_id: str) -> dict:
    """
    Get all job UUIDs together with statuses from the database.
    """
    columns = [Job.uuid, Job.status, Job.job_type, Job.created_at, Job.updated_at]
    query = session.query(*columns).filter(Job.user_id == user_id).all()

    if not query:
        return {}

    jobs = [job for job in query]

    return Jobs(jobs=jobs)


def job_update(
    session: Session,
    uuid: str,
    user_id: Optional[str] = None,
    status: Optional[JobStatusEnum] = None,
    language: Optional[str] = None,
    model_type: Optional[str] = None,
    speakers: Optional[int] = None,
    error: Optional[str] = None,
) -> Optional[Job]:
    """
    Update a job by UUID.
    """
    job = session.query(Job).filter(Job.uuid == uuid).first()

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

    session.commit()

    return job.as_dict()


def job_delete(session: Session, uuid: str) -> bool:
    """
    Delete a job by UUID.
    """
    job = session.query(Job).filter(Job.uuid == uuid).first()

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
    session.commit()

    return True


def job_cleanup() -> None:
    """
    Remove all jobs from the database.
    """

    session = get_session()

    jobs_to_delete = (
        session.query(Job).filter(Job.deletion_date <= datetime.now()).all()
    )

    for job in jobs_to_delete:
        job_delete(session, job.uuid)


def job_result_get(
    session: Session,
    user_id: str,
    job_id: str,
) -> Optional[JobResult]:
    """
    Get the transcription result for a job by UUID.
    """
    print(f"Fetching job result for job_id: {job_id}, user_id: {user_id}")
    res = (
        session.query(JobResult)
        .filter(
            JobResult.job_id == job_id,
            JobResult.user_id == user_id,
        )
        .first()
    )

    return res.as_dict() if res else {}


def job_result_save(
    session: Session,
    uuid: str,
    user_id: str,
    result_srt: Optional[str] = {},
    result: Optional[str] = "",
) -> JobResult:
    """
    Save the transcription result for a job.
    """
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
            result=json.dumps(result) if result else None,
            result_srt=result_srt if result_srt else None,
        )

    session.add(job_result)
    session.commit()

    return job_result.as_dict()
