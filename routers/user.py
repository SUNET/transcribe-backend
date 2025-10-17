from auth.oidc import get_current_user_id, verify_user
from db.user import user_get, user_update, users_statistics, user_get_all
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from utils.log import get_logger
from utils.settings import get_settings
from db.group import (
    group_get,
    group_get_all,
    group_create,
    group_update,
    group_delete,
    group_add_user,
    group_remove_user,
    group_statistics,
)


log = get_logger()
router = APIRouter(tags=["user"])
settings = get_settings()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/me")
async def get_user_info(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get user information.
    Used by the frontend to get user information.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(user_id)

    if not user:
        return JSONResponse(
            content={"error": "User not found"},
            status_code=404,
        )

    return JSONResponse(content={"result": user})


@router.get("/admin")
async def statistics(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get user statistics.
    Used by the frontend to get user statistics.
    """

    if not user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    user = user_get(user_id)["user"]

    if not user["admin"]:
        log.warning(f"User {user_id} is not admin")

        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    if user["bofh"]:
        log.info(f"User {user_id} is bofh, getting stats for all realms")
        realm = "*"
    else:
        realm = user["realm"]

    stats = users_statistics(realm)

    return JSONResponse(content={"result": stats})


@router.get("/admin/users")
async def list_users(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    List all users with statistics.
    Used by the frontend to list all users.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    if admin_user["bofh"]:
        realm = "*"
    else:
        realm = admin_user["realm"]

    users = user_get_all(realm=realm)

    return JSONResponse(content={"result": users})


@router.put("/admin/{username}")
async def modify_user(
    request: Request,
    username: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Modify a user's active status.
    Used by the frontend to modify a user's active status.
    """
    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"},
            status_code=401,
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(
            content={"error": "User not authorized"},
            status_code=403,
        )

    data = await request.json()
    active = data.get("active", None)
    admin = data.get("admin", None)

    if active is not None:
        user_update(
            username,
            active=active,
        )

    if admin is not None:
        user_update(
            username,
            admin=admin,
        )

    return JSONResponse(content={"result": {"status": "OK"}})


@router.get("/admin/groups")
async def list_groups(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    List all groups with statistics and member counts.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    if admin_user["bofh"]:
        realm = "*"
    else:
        realm = admin_user["realm"]

    groups = group_get_all(realm=realm)
    result = []

    for g in groups:
        stats = group_statistics(g["name"], g["realm"])

        if g["name"] == "All users":
            g["nr_users"] = stats["nr_users"]

        result.append(
            {
                "id": g["id"],
                "name": g["name"],
                "realm": g["realm"],
                "description": g["description"],
                "created_at": g["created_at"],
                "users": g["users"],
                "nr_users": g["nr_users"],
                "stats": stats,
            }
        )

    return JSONResponse(content={"result": result})


@router.post("/admin/groups")
async def create_group(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """Create a new group."""
    admin_user_id = await verify_user(request)
    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]
    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    data = await request.json()
    name = data.get("name")
    description = data.get("description", "")

    if not name:
        return JSONResponse(content={"error": "Missing group name"}, status_code=400)

    group = group_create(name=name, realm=admin_user["realm"], description=description)
    return JSONResponse(content={"result": {"id": group["id"], "name": group["name"]}})


@router.get("/admin/groups/{groupname}")
async def get_group(
    request: Request,
    groupname: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get group details.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    if admin_user["bofh"]:
        realm = "*"
    else:
        realm = admin_user["realm"]

    group = group_get(groupname, realm=realm)

    if not group:
        return JSONResponse(content={"error": "Group not found"}, status_code=404)

    return JSONResponse(content={"result": group})


@router.put("/admin/groups/{groupname}")
async def update_group(
    request: Request,
    groupname: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Update group details (name/description).
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]
    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    data = await request.json()
    name = data.get("name")
    description = data.get("description")
    usernames = data.get("usernames", [])

    print("Updating group", groupname, name, description, usernames)

    group_update(groupname, name=name, description=description, usernames=usernames)

    return JSONResponse(content={"result": {"status": "ok"}})


@router.delete("/admin/groups/{group_id}")
async def delete_group(
    request: Request,
    group_id: int,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Delete a group.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    group_delete(group_id)

    return JSONResponse(content={"result": {"status": "OK"}})


@router.post("/admin/groups/{group_id}/users/{username}")
async def add_user_to_group(
    request: Request,
    group_id: int,
    username: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """Add a user to a group."""
    admin_user_id = await verify_user(request)
    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]
    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    group_add_user(group_id, username)

    return JSONResponse(content={"result": {"status": "OK"}})


@router.delete("/admin/groups/{group_id}/users/{username}")
async def remove_user_from_group(
    request: Request,
    group_id: int,
    username: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """Remove a user from a group."""
    admin_user_id = await verify_user(request)
    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]
    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    group_remove_user(group_id, username)
    return JSONResponse(content={"result": {"status": "OK"}})


@router.get("/admin/groups/{groupname}/stats")
async def group_stats(
    request: Request,
    groupname: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get group statistics.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    if admin_user["bofh"]:
        realm = "*"
    else:
        realm = admin_user["realm"]

    group = group_get(groupname, realm=realm)

    if not group:
        return JSONResponse(content={"error": "Group not found"}, status_code=404)

    stats = users_statistics(groupname, realm=realm)

    return JSONResponse(content={"result": stats})
