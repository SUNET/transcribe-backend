import calendar

from datetime import datetime, timedelta
from db.models import Group, GroupModelLink, GroupUserLink, Job, User
from db.session import get_session
from sqlalchemy import or_
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
                admin_domains = (
                    session.query(User.admin_domains)
                    .filter(User.user_id == user_id)
                    .scalar()
                )

                group = (
                    session.query(Group)
                    .filter(Group.id == group_id)
                    .filter(
                        or_(
                            Group.users.any(User.user_id == user_id),
                            Group.owner_user_id == user_id,
                            Group.realm.in_(
                                [domain.strip() for domain in admin_domains.split(",")]
                            ),
                        )
                    )
                    .first()
                )

        if not group:
            return {}

        if realm == "*":
            other_users = (
                session.query(User).filter(~User.groups.any(Group.id == group_id)).all()
            )
        else:
            admin_domains = (
                session.query(User.admin_domains)
                .filter(User.user_id == user_id)
                .scalar()
            )

            if not admin_domains:
                return group.as_dict()

            other_users = (
                session.query(User)
                .filter(~User.groups.any(Group.id == group_id))
                .filter(
                    User.realm.in_(
                        [domain.strip() for domain in admin_domains.split(",")]
                    )
                )
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


def group_get_from_user_id(user_id: str) -> list[dict]:
    """
    Get all groups for a specific user id.
    """

    with get_session() as session:
        groups = (
            session.query(Group).filter(Group.users.any(User.user_id == user_id)).all()
        )

    return groups


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
        admin_domains = (
            session.query(User.admin_domains).filter(User.user_id == user_id).scalar()
        )

        if realm == "*":
            groups = session.query(Group).all()
        elif admin_domains:
            domains = [
                domain.strip() for domain in admin_domains.split(",") if domain.strip()
            ]

            groups = session.query(Group).filter(Group.realm.in_(domains)).all()
        else:
            groups = (
                session.query(Group)
                .filter(
                    or_(
                        Group.users.any(User.user_id == user_id),
                        Group.owner_user_id == user_id,
                    )
                )
                .all()
            )
        for group in groups:
            group_dict = group.as_dict()
            group_dict["nr_users"] = len(group_dict["users"])
            groups_list.append(group_dict)

    return groups_list


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
            for username in usernames:
                user = session.query(User).filter(User.username == username).first()

                found = (
                    session.query(GroupUserLink)
                    .filter(
                        GroupUserLink.group_id != group.id,
                        GroupUserLink.user_id == user.id,
                    )
                    .first()
                )

                if found:
                    raise ValueError(f"User {username} is already in another group.")

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
