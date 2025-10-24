import calendar

from auth.client_auth import dn_in_list
from datetime import datetime, timedelta
from db.job import job_get_all
from db.models import Group
from db.models import Job, User
from db.session import get_session
from typing import Optional
from utils.log import get_logger

log = get_logger()


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
        user = (
            session.query(User)
            .filter((User.user_id == user_id) | (User.username == username))
            .first()
        )

        if user:
            return user.as_dict()

        user = User(
            username=username,
            realm=realm,
            user_id=user_id,
            transcribed_seconds="0",
            last_login=datetime.utcnow(),
        )

        log.info(f"User {user_id} created from {username}.")

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

        if user is None and dn_in_list(job.user_id):
            return job.user_id

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


def user_get_all(realm) -> list:
    """
    Get all users in a realm.
    """
    with get_session() as session:
        if realm == "*":
            users = session.query(User).all()
        else:
            users = session.query(User).filter(User.realm == realm).all()

        return [user.as_dict() for user in users]


def user_get_quota_left(user_id: str) -> int:
    """
    Get the transcription quota left for a user.
    """

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

        if not user:
            return 0

        groups = (
            session.query(Group).filter(Group.users.any(User.user_id == user_id)).all()
        )

        if not groups:
            return 0

        for group in groups:
            if group.quota_seconds == 0:
                return 0

            if (
                user.transcribed_seconds < 0
                if not group.quota_seconds
                else group.quota_seconds
            ):
                return group.quota_seconds - user.transcribed_seconds

        return -1


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

        log.info(
            f"User {user.user_id} updated: transcribed_seconds={user.transcribed_seconds}, active={user.active}, admin={user.admin}"
        )

        return user.as_dict() if user else {}


def get_username_from_id(user_id: str) -> Optional[str]:
    """
    Get a username by user_id.
    """

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

    return user.username if user else None


def users_statistics(
    group_id: Optional[str] = "",
    realm: Optional[str] = "",
    days: Optional[int] = 30,
    user_id: Optional[str] = "",
) -> dict:
    """
    Get user statistics for the last 'days' days.
    """

    with get_session() as session:
        if group_id == "0":
            if realm == "*":
                users = session.query(User).all()
            else:
                users = session.query(User).filter(User.realm == realm).all()
        else:
            if realm == "*":
                group = session.query(Group).filter(Group.id == group_id).first()
            else:
                group = (
                    session.query(Group)
                    .filter(Group.id == group_id)
                    .filter(Group.users.any(User.user_id == user_id))
                    .first()
                )

            if not group:
                return {
                    "total_users": 0,
                    "active_users": [],
                    "total_transcribed_minutes": 0,
                    "transcribed_minutes_per_day": {},
                    "transcribed_minutes_per_day_previous_month": {},
                    "transcribed_minutes_per_user": {},
                }

            users = group.users

        total_transcribed_minutes = 0
        transcribed_minutes_per_user = {}
        transcribed_minutes_per_day = {}
        transcribed_minutes_per_day_previous_month = {}

        today = datetime.utcnow().date()
        last_day = calendar.monthrange(today.year, today.month)[1]
        last_date_string = f"{today.year}-{today.month:02d}-{last_day}"
        last_date = datetime.fromisoformat(last_date_string).date()
        start_date = today.replace(day=1)

        date_range = [
            (start_date + timedelta(days=i)).isoformat()
            for i in range((last_date - start_date).days + 1)
        ]

        today = datetime.utcnow().date()

        first_day_this_month = today.replace(day=1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)

        num_days_prev_month = last_day_prev_month.day

        date_range_prev_month = [
            (first_day_prev_month + timedelta(days=i)).isoformat()
            for i in range(num_days_prev_month)
        ]

        transcribed_minutes_per_day = {d: 0 for d in date_range}
        transcribed_minutes_per_day_previous_month = {
            d: 0 for d in date_range_prev_month
        }

        for user in users:
            jobs = job_get_all(user.user_id)["jobs"]

            if not jobs:
                continue

            for job in jobs:
                dt = datetime.strptime(job["created_at"], "%Y-%m-%d %H:%M:%S.%f")
                if dt.date() < start_date:
                    continue

                job_date = dt.date().isoformat()

                if user.username not in transcribed_minutes_per_user:
                    transcribed_minutes_per_user[user.username] = 0

                transcribed_seconds = int(job["transcribed_seconds"] // 60)

                transcribed_minutes_per_user[user.username] += (
                    transcribed_seconds if transcribed_seconds > 0 else 1
                )

                transcribed_minutes_per_day[job_date] += (
                    transcribed_seconds if transcribed_seconds > 0 else 1
                )

                total_transcribed_minutes += (
                    transcribed_seconds if transcribed_seconds > 0 else 1
                )

            for job in jobs:
                dt = datetime.strptime(job["created_at"], "%Y-%m-%d %H:%M:%S.%f")
                if dt.date() < first_day_prev_month or dt.date() > last_day_prev_month:
                    continue

                job_date = dt.date().isoformat()

                transcribed_minutes_per_day_previous_month[job_date] += int(
                    job["transcribed_seconds"] // 60
                )

        return {
            "total_users": len(users),
            "active_users": [user.as_dict() for user in users],
            "total_transcribed_minutes": total_transcribed_minutes,
            "transcribed_minutes_per_day": transcribed_minutes_per_day,
            "transcribed_minutes_per_day_previous_month": transcribed_minutes_per_day_previous_month,
            "transcribed_minutes_per_user": transcribed_minutes_per_user,
        }


def user_can_transcribe(user_id: str) -> int:
    """
    Check which group a user belongs to and check whether the user have
    quota left or not.
    """

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

        if not user:
            return 0

        groups = (
            session.query(Group).filter(Group.users.any(User.user_id == user_id)).all()
        )

        if not groups:
            return -1

        for group in groups:
            if group.transcription_quota == 0:
                return -1  # Unlimited quota

            if user.transcribed_seconds < group.transcription_quota:
                return group.transcription_quota - user.transcribed_seconds

        return 0
