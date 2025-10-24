from datetime import datetime, timedelta
from db.models import Group, GroupModelLink, GroupUserLink, Job, User
from db.session import get_session
from typing import Optional


def group_create(
    name: str,
    realm: str,
    description: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    quota_seconds: Optional[int] = 0,
) -> dict:
    """
    Create a new group in the database.
    """

    with get_session() as session:
        group = Group(
            name=name,
            realm=realm,
            description=description,
            owner_user_id=owner_user_id,
            quota_seconds=quota_seconds,
        )

        session.add(group)
        session.flush()

        return group.as_dict()


def group_get(group_id: str, realm: str, user_id: Optional[str] = "") -> Optional[dict]:
    """
    Get a group by id with its users and models.
    """

    with get_session() as session:
        if group_id == "0":
            group = Group(name="All users", realm=realm)
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
            return {}

        if realm == "*":
            other_users = (
                session.query(User).filter(~User.groups.any(Group.id == group_id)).all()
            )
        else:
            other_users = (
                session.query(User)
                .filter(~User.groups.any(Group.id == group_id))
                .filter(User.realm == realm)
                .all()
            )

        group_dict = group.as_dict()

        for user in group_dict["users"]:
            user["in_group"] = True

        if other_users:
            for other in other_users:
                user_dict = other.as_dict()
                user_dict["in_group"] = False
                group_dict["users"].append(user_dict)

        return group_dict


def group_get_all(user_id: str, realm: str) -> list[dict]:
    """
    Get all groups with their users and models.
    """

    groups_list = []

    if realm == "*":
        default_group = {
            "id": 0,
            "name": "All users",
            "realm": realm,
            "description": "Default group with all users",
            "created_at": "",
            "owner_user_id": None,
            "quota_seconds": 0,
            "users": [],
            "models": [],
            "nr_users": 0,
        }

        groups_list.append(default_group)

    with get_session() as session:
        if realm == "*":
            groups = session.query(Group).all()
        else:
            groups = (
                session.query(Group)
                .filter(Group.users.any(User.user_id == user_id))
                .all()
            )
        for group in groups:
            group_dict = group.as_dict()
            group_dict["nr_users"] = len(group_dict["users"])
            groups_list.append(group_dict)

    return groups_list


def group_statistics(group_id: str, realm: str) -> dict:
    """
    Get statistics for a group.
    """

    stats = {
        "month_files": 0,
        "month_seconds": 0,
        "year_files": 0,
        "year_seconds": 0,
    }

    with get_session() as session:
        if group_id == 0:
            group = Group(name="All users", realm=realm)
        else:
            group = (
                session.query(Group)
                .filter(Group.id == group_id)
                .filter(Group.realm == realm)
                .first()
            )

        if not group:
            return stats

        one_month_ago = datetime.utcnow() - timedelta(days=30)
        one_year_ago = datetime.utcnow() - timedelta(days=365)

        if group.name == "All users":
            if realm == "*":
                users = session.query(User).all()
            else:
                users = session.query(User).filter(User.realm == realm).all()
        else:
            users = group.users

        stats["nr_users"] = len(users)

        for user in users:
            user_id = user.user_id

            month_jobs = (
                session.query(Job)
                .filter(Job.user_id == user_id)
                .filter(Job.status == "completed")
                .filter(Job.updated_at >= one_month_ago)
                .filter(Job.status == "completed")
                .all()
            )

            stats["month_files"] += len(month_jobs)
            stats["month_seconds"] += sum(
                job.transcribed_seconds for job in month_jobs if job.transcribed_seconds
            )

            year_jobs = (
                session.query(Job)
                .filter(Job.user_id == user_id)
                .filter(Job.status == "completed")
                .filter(Job.updated_at >= one_year_ago)
                .filter(Job.status == "completed")
                .all()
            )

            stats["year_files"] += len(year_jobs)
            stats["year_seconds"] += sum(
                job.transcribed_seconds for job in year_jobs if job.transcribed_seconds
            )

        return stats


def group_get_quota_left(group_id: int) -> int:
    """
    Get the remaining quota seconds for a group.
    """

    with get_session() as session:
        group = session.query(Group).filter(Group.id == group_id).first()

        if not group:
            return 0

        quota_seconds = group.quota_seconds
        used_seconds = 0

        for user in group.users:
            used_seconds += user.transcribed_seconds if user.transcribed_seconds else 0

        quota_left = quota_seconds - used_seconds

        return max(quota_left, 0)


def group_delete(group_id: int) -> bool:
    """
    Delete a group by id.
    """
    with get_session() as session:
        group = session.query(Group).filter(Group.id == group_id).first()

        if not group:
            return False

        session.delete(group)

        # Also delete all links to users and models
        links = (
            session.query(GroupUserLink)
            .filter(GroupUserLink.group_id == group_id)
            .all()
        )

        if links:
            for link in links:
                session.delete(link)

        links = (
            session.query(GroupModelLink)
            .filter(GroupModelLink.group_id == group_id)
            .all()
        )

        if links:
            for link in links:
                session.delete(link)

        return True

    return False


def group_update(
    group_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    usernames: Optional[list[int]] = None,
    quota_seconds: Optional[int] = 0,
) -> Optional[dict]:
    """
    Update group metadata.
    """

    with get_session() as session:
        group = session.query(Group).filter(Group.id == group_id).first()

        if not group:
            return {}

        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        if quota_seconds is not None:
            group.quota_seconds = quota_seconds
        if usernames is not None:
            links = (
                session.query(GroupUserLink)
                .filter(GroupUserLink.group_id == group.id)
                .all()
            )

            if links:
                for link in links:
                    session.delete(link)

            for username in usernames:
                user = session.query(User).filter(User.username == username).first()

                if user:
                    link = GroupUserLink(
                        group_id=group.id, user_id=user.id, role="member"
                    )

                    session.add(link)

        return group.as_dict()


def group_add_user(group_id: int, username: str, role: str = "member") -> dict:
    """
    Add a user to a group with a given role.
    """
    with get_session() as session:
        user_id = session.query(User.id).filter(User.username == username).scalar()

        link = (
            session.query(GroupUserLink)
            .filter(
                GroupUserLink.group_id == group_id, GroupUserLink.user_id == user_id
            )
            .first()
        )
        if not link:
            link = GroupUserLink(group_id=group_id, user_id=user_id, role=role)
            session.add(link)
        return {"group_id": group_id, "user_id": user_id, "role": role}


def group_remove_user(group_id: int, user_id: int) -> bool:
    """
    Remove a user from a group.
    """
    with get_session() as session:
        link = (
            session.query(GroupUserLink)
            .filter(
                GroupUserLink.group_id == group_id, GroupUserLink.user_id == user_id
            )
            .first()
        )
        if not link:
            return False
        session.delete(link)
        return True


def group_add_model(group_id: int, model_id: int) -> dict:
    """
    Link a model to a group.
    """
    with get_session() as session:
        link = (
            session.query(GroupModelLink)
            .filter(
                GroupModelLink.group_id == group_id, GroupModelLink.model_id == model_id
            )
            .first()
        )
        if not link:
            link = GroupModelLink(group_id=group_id, model_id=model_id)
            session.add(link)
        return {"group_id": group_id, "model_id": model_id}


def group_remove_model(group_id: int, model_id: int) -> bool:
    """
    Unlink a model from a group.
    """
    with get_session() as session:
        link = (
            session.query(GroupModelLink)
            .filter(
                GroupModelLink.group_id == group_id, GroupModelLink.model_id == model_id
            )
            .first()
        )
        if not link:
            return False
        session.delete(link)
        return True


def group_list() -> list[dict]:
    """
    List all groups with their metadata.
    """
    with get_session() as session:
        groups = session.query(Group).all()
        return [g.as_dict() for g in groups]


def group_get_users(group_id: str, realm: str) -> list[dict]:
    """
    Get all users in a group.
    """
    with get_session() as session:
        group = (
            session.query(Group)
            .filter(Group.id == group_id)
            .filter(Group.realm == realm)
            .first()
        )

        if not group:
            return []

        return [user.as_dict() for user in group.users]
