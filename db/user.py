import calendar

from auth.client_auth import dn_in_list
from datetime import datetime, timedelta
from db.job import job_get_all
from db.models import Group, GroupUserLink
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
            q = (
                session.query(User, Group)
                .outerjoin(GroupUserLink, GroupUserLink.user_id == User.id)
                .outerjoin(Group, Group.id == GroupUserLink.group_id)
            )
            rows = q.all()

        else:
            q = (
                session.query(User, Group)
                .outerjoin(GroupUserLink, GroupUserLink.user_id == User.id)
                .outerjoin(Group, Group.id == GroupUserLink.group_id)
                .filter(User.realm == realm)
            )
            rows = q.all()

        group_map = {}

        #Work out groups from the returned data.
        for row in rows:
            user_dict = row[0].as_dict()
            group_dict = row[1].as_dict() if row[1] else []
            if user_dict["id"] in group_map:
                group_map[user_dict["id"]]["groups"] += f", {group_dict["name"]}"
            else:
                group_map[user_dict["id"]] = user_dict
                group_map[user_dict["id"]]["groups"] = group_dict["name"] if group_dict else ""

        result = list(group_map.values())

        return result

def user_get_quota_left(user_id: str) -> int:
    """
    Get the transcription quota left for a user.
    """

    with get_session() as session:
        groups = (
            session.query(Group).filter(Group.users.any(User.user_id == user_id)).all()
        )

        if not groups:
            return 0

        for group in groups:
            if group.quota_seconds == 0:
                return 0

            group_statistics_res = group_statistics(group.id, group.realm)

            if not group_statistics_res:
                return -1

            if group_statistics_res["month_seconds"] < group.quota_seconds:
                return 0

    return -1


def user_update(
    username: str,
    transcribed_seconds: Optional[str] = "",
    active: Optional[bool] = None,
    admin: Optional[bool] = None,
    admin_domains: Optional[str] = None,
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

        if admin_domains is not None:
            user.admin_domains = admin_domains

        log.info(
            f"User {user.user_id} updated: "
            + f"transcribed_seconds={user.transcribed_seconds}, "
            + f"active={user.active}, admin={user.admin}"
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
    Shows customer names instead of usernames when available.
    """

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        user_domains = (
            user.admin_domains.split(",") if user and user.admin_domains else []
        )

        if group_id == "0":
            if realm == "*":
                users = session.query(User).all()
            else:
                users = session.query(User).filter(User.realm.in_(user_domains)).all()
        else:
            if realm == "*":
                group = session.query(Group).filter(Group.id == group_id).first()
            else:
                group = (
                    session.query(Group)
                    .filter(Group.id == group_id)
                    .first()
                )

            if not group:
                return {
                    "total_users": 0,
                    "active_users": [],
                    "transcribed_files": 0,
                    "transcribed_files_last_month": 0,
                    "total_transcribed_minutes": 0,
                    "total_transcribed_minutes_last_month": 0,
                    "transcribed_minutes_per_day": {},
                    "transcribed_minutes_per_day_previous_month": {},
                    "transcribed_minutes_per_user": {},
                    "job_queue": {},
                }

            users = group.users

        # Get all customers for realm-to-customer mapping
        from db.models import Customer

        customers = session.query(Customer).all()
        realm_to_customer = {}
        for customer in customers:
            customer_realms = [
                r.strip() for r in customer.realms.split(",") if r.strip()
            ]
            for realm_item in customer_realms:
                realm_to_customer[realm_item] = customer.name

        total_transcribed_minutes = 0
        total_transcribed_minutes_last_month = 0

        transcribed_files = 0
        transcribed_files_last_month = 0

        transcribed_minutes_per_user = {}
        transcribed_minutes_per_user_last_month = {}

        transcribed_minutes_per_day = {}
        transcribed_minutes_per_day_last_month = {}

        job_queue = []

        today = datetime.utcnow().date()
        last_day = calendar.monthrange(today.year, today.month)[1]
        last_date_string = f"{today.year}-{today.month:02d}-{last_day}"
        last_date = datetime.fromisoformat(last_date_string).date()
        start_date = today.replace(day=1)

        date_range = [
            (start_date + timedelta(days=i)).isoformat()
            for i in range((last_date - start_date).days + 1)
        ]

        first_day_this_month = today.replace(day=1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)

        num_days_prev_month = last_day_prev_month.day

        date_range_prev_month = [
            (first_day_prev_month + timedelta(days=i)).isoformat()
            for i in range(num_days_prev_month)
        ]

        transcribed_minutes_per_day = {d: 0 for d in date_range}
        transcribed_minutes_per_day_last_month = {d: 0 for d in date_range_prev_month}

        for user in users:
            jobs = job_get_all(user.user_id, cleaned=True)["jobs"]

            if not jobs:
                continue

            # Determine display name: customer name if available, otherwise username
            display_name = user.username
            if user.realm in realm_to_customer:
                display_name = realm_to_customer[user.realm]

            for job in jobs:
                job_date = datetime.strptime(
                    job["created_at"], "%Y-%m-%d %H:%M:%S.%f"
                ).date()

                job_date_str = job_date.isoformat()

                if job_date >= first_day_this_month:
                    if job["status"] == "completed":
                        transcribed_files += 1
                        total_transcribed_minutes += job["transcribed_seconds"] // 60

                        transcribed_minutes_per_day[job_date_str] += (
                            job["transcribed_seconds"] / 60
                        )

                        if display_name not in transcribed_minutes_per_user:
                            transcribed_minutes_per_user[display_name] = 0

                        transcribed_minutes_per_user[display_name] += (
                            job["transcribed_seconds"] / 60
                        )

                    if job["status"] == "uploaded" or job["status"] == "in_progress":
                        if job["status"] == "in_progress":
                            status = "transcribing"
                        else:
                            status = job["status"]

                        job_data = {
                            "status": status,
                            "created_at": job["created_at"],
                            "updated_at": job["updated_at"],
                            "job_id": job["uuid"],
                            "username": display_name,  # Use display name
                        }

                        job_queue.append(job_data)
                elif first_day_prev_month <= job_date <= last_day_prev_month:
                    if job["status"] == "completed":
                        transcribed_files_last_month += 1

                        total_transcribed_minutes_last_month += (
                            job["transcribed_seconds"] / 60
                        )

                        transcribed_minutes_per_day_last_month[job_date_str] += (
                            job["transcribed_seconds"] / 60
                        )

                        if display_name not in transcribed_minutes_per_user_last_month:
                            transcribed_minutes_per_user_last_month[display_name] = 0

                        transcribed_minutes_per_user_last_month[display_name] += (
                            job["transcribed_seconds"] / 60
                        )

                    if job["status"] == "uploaded" or job["status"] == "in_progress":
                        if job["status"] == "in_progress":
                            status = "transcribing"
                        else:
                            status = job["status"]

                        job_data = {
                            "status": status,
                            "created_at": job["created_at"],
                            "updated_at": job["updated_at"],
                            "job_id": job["uuid"],
                            "username": display_name,  # Use display name
                        }

                        job_queue.append(job_data)
                else:
                    log.debug(
                        f"Skipping job {job['uuid']} for user {user.username}"
                        + f" with date {job_date_str}"
                    )

        return {
            "total_users": len(users),
            "active_users": [user.as_dict() for user in users],
            "transcribed_files": int(transcribed_files),
            "transcribed_files_last_month": int(transcribed_files_last_month),
            "total_transcribed_minutes": int(total_transcribed_minutes),
            "total_transcribed_minutes_last_month": int(
                total_transcribed_minutes_last_month
            ),
            "transcribed_minutes_per_day": transcribed_minutes_per_day,
            "transcribed_minutes_per_day_last_month": transcribed_minutes_per_day_last_month,
            "transcribed_minutes_per_user": transcribed_minutes_per_user,
            "transcribed_minutes_per_user_last_month": transcribed_minutes_per_user_last_month,
            "job_queue": job_queue,
        }


def group_statistics(group_id: str, user_id: str, realm: str) -> dict:
    """
    Get group statistics for a user.
    """

    stats = users_statistics(group_id=group_id, user_id=user_id, realm=realm)

    condensed_stats = {
        "total_users": stats["total_users"],
        "transcribed_files": stats["transcribed_files"],
        "transcribed_files_last_month": stats["transcribed_files_last_month"],
        "total_transcribed_minutes": stats["total_transcribed_minutes"],
        "total_transcribed_minutes_last_month": stats[
            "total_transcribed_minutes_last_month"
        ],
    }

    return condensed_stats


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
