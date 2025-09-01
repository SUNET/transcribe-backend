from db.models import User, Job
from db.job import job_get_all
from typing import Optional
from sqlmodel import Session
from datetime import datetime, timedelta


def user_create(
    session: Session,
    username: str,
    realm: str,
    user_id: Optional[str] = None,
) -> dict:
    """
    Create a new user in the database.
    """

    if not user_id or not realm:
        raise ValueError("user_id and realm must be provided")

    user = session.query(User).filter(User.user_id == user_id).first()

    if user:
        return user.as_dict()

    user = User(
        username=username,
        realm=realm,
        user_id=user_id,
        transcribed_seconds="0",
        last_login=datetime.utcnow(),
    )

    session.add(user)
    session.commit()

    return user.dict()


def user_get_from_job(session: Session, job_id: str) -> Optional[User]:
    """
    Get a user by job_user_id.
    """
    job = session.query(Job).filter(Job.uuid == job_id).first()

    if not job:
        return None

    user = session.query(User).filter(User.user_id == job.user_id).first()

    return user.as_dict()["user_id"] if user else None


def user_get(session: Session, user_id: str) -> Optional[User]:
    """
    Get a user by user_id.
    """
    user = session.query(User).filter(User.user_id == user_id).first()

    result = {
        "user": user.as_dict(),
        "jobs": job_get_all(session, user_id) if user else [],
    }

    return result


def user_update(
    session: Session,
    username: str,
    transcribed_seconds: Optional[str] = "",
    active: Optional[bool] = None,
    admin: Optional[bool] = None,
) -> dict:
    """
    Update a user's transcribed seconds.
    """
    user = session.query(User).filter(User.username == username).first()

    if not user:
        return {}

    if transcribed_seconds:
        user.transcribed_seconds += int(transcribed_seconds)

    user.last_login = datetime.utcnow()

    if active is not None:
        user.active = active

    if admin is not None:
        user.admin = admin

    session.add(user)
    session.commit()

    return user.as_dict() if user else {}


def get_username_from_id(session: Session, user_id: str) -> Optional[str]:
    """
    Get a username by user_id.
    """
    user = session.query(User).filter(User.user_id == user_id).first()

    return user.username if user else None


def users_statistics(
    session: Session,
    realm: str,
    days: int = 30,
) -> dict:
    """
    Get user statistics for the last 'days' days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    users = (
        session.query(User)
        .filter(User.realm == realm)
        .filter(User.last_login >= start_date)
        .all()
    )

    total_transcribed_seconds = sum(
        int(user.transcribed_seconds) for user in users if user.transcribed_seconds
    )

    transcribed_seconds_per_day = {}
    transcribed_seconds_per_user = {}
    transcribed_seconds_per_user_and_day = {}

    for user in users:
        transcribed_seconds_per_user[user.user_id] = user.transcribed_seconds or 0

        for job in job_get_all(session, user.user_id)["jobs"]:
            username = get_username_from_id(session, user.user_id)
            if username not in transcribed_seconds_per_user_and_day:
                transcribed_seconds_per_user_and_day[username] = {}

            dt = datetime.strptime(job["created_at"], "%Y-%m-%d %H:%M:%S.%f")
            job_date = dt.date().isoformat()

            if job_date not in transcribed_seconds_per_user_and_day[username]:
                transcribed_seconds_per_user_and_day[username][job_date] = 0

            transcribed_seconds_per_user_and_day[username][job_date] += (
                job["transcribed_seconds"] or 0
            )

            transcribed_seconds_per_day[job_date] = transcribed_seconds_per_day.get(
                job_date, 0
            ) + (job["transcribed_seconds"] or 0)

    return {
        "total_users": len(users),
        "active_users": [user.as_dict() for user in users],
        "total_transcribed_seconds": total_transcribed_seconds,
        "transcribed_seconds_per_day": transcribed_seconds_per_day,
        "transcribed_seconds_per_user": transcribed_seconds_per_user,
        "transcribed_seconds_per_day_and_user": transcribed_seconds_per_user_and_day,
    }
