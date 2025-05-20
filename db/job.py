from db.models import Job, JobStatusEnum, Jobs
from typing import Optional
from sqlmodel import Session
from datetime import datetime, timedelta


def job_create(
    session: Session,
    job_type: Optional[JobStatusEnum] = None,
    language: Optional[str] = "",
    model_type: Optional[str] = "",
    filename: Optional[str] = "",
    output_format: Optional[str] = "",
) -> dict:
    """
    Create a new job in the database.
    """
    job = Job(
        job_type=job_type,
        language=language,
        model_type=model_type,
        status=JobStatusEnum.UPLOADING,
        output_format=output_format,
        filename=filename,
    )

    session.add(job)
    session.commit()

    return job.as_dict()


def job_get(session: Session, uuid: str) -> Optional[Job]:
    """
    Get a job by UUID.
    """

    job = session.query(Job).filter(Job.uuid == uuid).first()

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


def job_get_all(session: Session) -> list[Job]:
    """
    Get all jobs from the database.
    """
    jobs = session.query(Job).all()

    return {"jobs": [job.as_dict() for job in jobs]}


def job_get_status(session: Session) -> dict:
    """
    Get all job UUIDs together with statuses from the database.
    """
    columns = [Job.uuid, Job.status, Job.job_type, Job.created_at, Job.updated_at]
    query = session.query(*columns)

    if not query:
        return {}

    jobs = [job for job in query]

    return Jobs(jobs=jobs)


def job_update(
    session: Session,
    uuid: str,
    status: Optional[JobStatusEnum] = None,
    language: Optional[str] = None,
    model_type: Optional[str] = None,
    output_format: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[Job]:
    """
    Update a job by UUID.
    """
    job = session.query(Job).filter(Job.uuid == uuid).first()

    if not job:
        return None

    if status:
        job.status = status
    if error:
        job.error = error
    if language:
        job.language = language
    if model_type:
        job.model_type = model_type
    if output_format:
        job.output_format = output_format

    session.commit()

    return job.as_dict()


def job_cleanup(session: Session) -> None:
    """
    Remove all jobs from the database.
    """

    # Get all jobs that have been in progress for more than 1 hour
    jobs_to_delete = (
        session.query(Job)
        .filter(Job.updated_at < datetime.utcnow() - timedelta(hours=1))
        .all()
    )

    # Delete the jobs
    for job in jobs_to_delete:
        if job.status == JobStatusEnum.COMPLETED:
            continue
        session.delete(job)
    session.commit()
