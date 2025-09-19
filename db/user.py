import calendar

from datetime import datetime, timedelta
from db.job import job_get_all
from db.models import Job, User
from db.session import get_session
from typing import Optional


def user_create(
    username: str,
    realm: str,
    user_id: Optional[str] = None,
) -> dict:
    """
    Create a new user in the database.
    """

    if not user_id or not realm:
        raise ValueError("user_id and realm must be provided")

    with get_session() as session:
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

        return user.dict()


def user_get_from_job(job_id: str) -> Optional[User]:
    """
    Get a user by job_user_id.
    """
    with get_session() as session:
        job = session.query(Job).filter(Job.uuid == job_id).first()

        if not job:
            return None

        user = session.query(User).filter(User.user_id == job.user_id).first()

        return user.as_dict()["user_id"] if user else None


def user_get_username_from_job(job_id: str) -> Optional[User]:
    """
    Get a user by job_user_id.
    """
    with get_session() as session:
        job = session.query(Job).filter(Job.uuid == job_id).first()

        if not job:
            return None

        user = session.query(User).filter(User.user_id == job.user_id).first()

        return user.as_dict()["username"] if user else None


def user_get(user_id: str) -> Optional[User]:
    """
    Get a user by user_id.
    """
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

        result = {
            "user": user.as_dict(),
            "jobs": job_get_all(user_id) if user else [],
        }

    return result


def user_update(
    username: str,
    transcribed_seconds: Optional[str] = "",
    active: Optional[bool] = None,
    admin: Optional[bool] = None,
) -> dict:
    """
    Update a user's transcribed seconds.
    """

    with get_session() as session:
        user = (
            session.query(User)
            .filter(User.username == username)
            .with_for_update()
            .first()
        )

        if not user:
            return {}

        if transcribed_seconds:
            user.transcribed_seconds += int(transcribed_seconds)

        user.last_login = datetime.utcnow()

        if active is not None:
            user.active = active

        if admin is not None:
            user.admin = admin

        return user.as_dict() if user else {}


def get_username_from_id(user_id: str) -> Optional[str]:
    """
    Get a username by user_id.
    """

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

    return user.username if user else None


def users_statistics(
    realm: str,
    days: int = 30,
) -> dict:
    """
    Get user statistics for the last 'days' days.
    """

    with get_session() as session:
        if realm == "*":
            users = session.query(User).all()
        else:
            users = session.query(User).filter(User.realm == realm).all()

        total_transcribed_seconds = sum(
            int(user.transcribed_seconds) for user in users if user.transcribed_seconds
        )

        transcribed_seconds_per_day = {}
        transcribed_seconds_per_user = {}

        today = datetime.utcnow().date()
        last_day = calendar.monthrange(today.year, today.month)[1]
        last_date_string = f"{today.year}-{today.month:02d}-{last_day}"
        last_date = datetime.fromisoformat(last_date_string).date()
        start_date = today.replace(day=1)

        date_range = [
            (start_date + timedelta(days=i)).isoformat()
            for i in range((last_date - start_date).days + 1)
        ]

        transcribed_seconds_per_day = {d: 0 for d in date_range}

        for user in users:
            jobs = job_get_all(user.user_id)["jobs"]

            if not jobs:
                continue

            for job in jobs:
                dt = datetime.strptime(job["created_at"], "%Y-%m-%d %H:%M:%S.%f")
                if dt.date() < start_date:
                    continue

                job_date = dt.date().isoformat()

                transcribed_seconds_per_day[job_date] = transcribed_seconds_per_day.get(
                    job_date, 0
                ) + job.get("transcribed_seconds", 0)

        return {
            "total_users": len(users),
            "active_users": [user.as_dict() for user in users],
            "total_transcribed_seconds": total_transcribed_seconds,
            "transcribed_seconds_per_day": transcribed_seconds_per_day,
            "transcribed_seconds_per_user": transcribed_seconds_per_user,
        }
