from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from db.user import (
    user_get,
    users_statistics,
    user_get_all,
    user_update,
    group_statistics,
)
from db.group import (
    group_get,
    group_get_all,
    group_create,
    group_update,
    group_delete,
    group_add_user,
    group_remove_user,
)
from db.customer import (
    customer_create,
    customer_get,
    customer_get_all,
    customer_update,
    customer_delete,
    customer_get_statistics,
    get_all_realms,
    export_customers_to_csv,
)

from utils.log import get_logger

from utils.settings import get_settings
from auth.oidc import get_current_user_id, verify_user

from utils.validators import (
    ModifyUserRequest,
    CreateGroupRequest,
    UpdateGroupRequest,
    CreateCustomerRequest,
    UpdateCustomerRequest,
)

log = get_logger()
router = APIRouter(tags=["user"])
settings = get_settings()


@router.get("/admin")
async def statistics(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get user statistics.
    Used by the frontend to get user statistics.

    Parameters:
        request (Request): The incoming HTTP request.
        user_id (str): The ID of the current user.

    Returns:
        JSONResponse: The user statistics.
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
        realm = "*"
    else:
        realm = user["realm"]

    stats = users_statistics(realm=realm)

    return JSONResponse(content={"result": stats})


@router.get("/admin/users")
async def list_users(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    List all users with statistics.
    Used by the frontend to list all users.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The list of users with statistics.
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
    item: ModifyUserRequest,
    username: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Modify a user's active status.
    Used by the frontend to modify a user's active status.

    Parameters:
        request (Request): The incoming HTTP request.
        username (str): The username of the user to modify.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The result of the operation.
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

    if not (user_id := user_get(username=username)["user"]["user_id"]):
        return JSONResponse(
            content={"error": "User not found"},
            status_code=404,
        )

    if item.active is not None:
        user_update(
            user_id,
            active=item.active,
        )

    if item.admin is not None:
        user_update(
            user_id,
            admin=item.admin,
        )

    if item.admin_domains is not None:
        user_update(
            user_id,
            admin_domains=item.admin_domains,
        )

    return JSONResponse(content={"result": {"status": "OK"}})


@router.get("/admin/groups")
async def list_groups(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    List all groups with statistics and member counts.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The list of groups with statistics and member counts.
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

    groups = group_get_all(admin_user_id, realm=realm)
    result = []

    for g in groups:
        stats = group_statistics(str(g["id"]), admin_user_id, realm)

        if g["name"] == "All users":
            g["nr_users"] = stats["total_users"]

        group_dict = {
            "id": g["id"],
            "name": g["name"],
            "realm": g["realm"],
            "description": g["description"],
            "created_at": g["created_at"],
            "users": g["users"],
            "nr_users": stats["total_users"],
            "stats": stats,
            "quota_seconds": g["quota_seconds"],
        }

        result.append(group_dict)

    return JSONResponse(content={"result": result})


@router.post("/admin/groups")
async def create_group(
    request: Request,
    item: CreateGroupRequest,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Create a new group.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The result of the operation.
    """

    admin_user_id = await verify_user(request)
    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    if not item.name:
        return JSONResponse(content={"error": "Missing group name"}, status_code=400)

    group = group_create(
        name=item.name,
        realm=admin_user["realm"],
        description=item.description,
        quota_seconds=item.quota,
        owner_user_id=admin_user_id,
    )

    return JSONResponse(content={"result": {"id": group["id"], "name": group["name"]}})


@router.get("/admin/groups/{group_id}")
async def get_group(
    request: Request,
    group_id: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get group details.

    Parameters:
        request (Request): The incoming HTTP request.
        group_id (str): The ID of the group.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The group details.
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

    group = group_get(group_id, realm=realm, user_id=admin_user_id)

    if not group:
        return JSONResponse(content={"error": "Group not found"}, status_code=404)

    return JSONResponse(content={"result": group})


@router.put("/admin/groups/{group_id}")
async def update_group(
    request: Request,
    item: UpdateGroupRequest,
    group_id: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Update group details (name/description).

    Parameters:
        request (Request): The incoming HTTP request.
        group_id (str): The ID of the group.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The result of the operation.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    try:
        if not group_update(
            group_id,
            name=item.name,
            description=item.description,
            usernames=item.usernames,
            quota_seconds=int(item.quota),
        ):
            return JSONResponse(content={"error": "Group not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    return JSONResponse(content={"result": {"status": "ok"}})


@router.delete("/admin/groups/{group_id}")
async def delete_group(
    request: Request,
    group_id: int,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Delete a group.

    Parameters:
        request (Request): The incoming HTTP request.
        group_id (int): The ID of the group.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The result of the operation.
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
    """
    Remove a user from a group.

    Parameters:
        admin_user_id = await verify_user(request)
        request (Request): The incoming HTTP request.
        group_id (int): The ID of the group.
        username (str): The username of the user to remove.

    Returns:
        JSONResponse: The result of the operation.
    """
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


@router.get("/admin/groups/{group_id}/stats")
async def group_stats(
    request: Request,
    group_id: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get group statistics.

    Parameters:
        request (Request): The incoming HTTP request.
        group_id (str): The ID of the group.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The group statistics.
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

    group = group_get(group_id, realm=realm, user_id=admin_user_id)

    if not group:
        return JSONResponse(content={"error": "Group not found"}, status_code=404)

    stats = users_statistics(group_id, realm=realm, user_id=admin_user_id)

    return JSONResponse(content={"result": stats})


@router.get("/admin/customers")
async def list_customers(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    List all customers with statistics.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The list of customers with statistics.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"] and not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    customers = customer_get_all(admin_user)

    result = []

    for customer in customers:
        stats = customer_get_statistics(customer["id"])
        customer["stats"] = stats
        result.append(customer)

    return JSONResponse(content={"result": result})


@router.post("/admin/customers")
async def create_customer(
    request: Request,
    item: CreateCustomerRequest,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Create a new customer.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The result of the operation.
    """

    admin_user_id = await verify_user(request)
    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    if not item.partner_id or not item.name:
        return JSONResponse(
            content={"error": "Missing required fields"}, status_code=400
        )

    customer = customer_create(
        customer_abbr=item.customer_abbr,
        partner_id=item.partner_id,
        name=item.name,
        priceplan=item.priceplan,
        base_fee=item.base_fee,
        realms=item.realms,
        contact_email=item.contact_email,
        notes=item.notes,
        blocks_purchased=item.blocks_purchased,
    )

    return JSONResponse(content={"result": customer})


@router.get("/admin/customers/{customer_id}")
async def get_customer(
    request: Request,
    customer_id: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get customer details.

    Parameters:
        request (Request): The incoming HTTP request.
        customer_id (str): The ID of the customer.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The customer details.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"] and not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    customer = customer_get(customer_id)

    if not customer:
        return JSONResponse(content={"error": "Customer not found"}, status_code=404)

    return JSONResponse(content={"result": customer})


@router.put("/admin/customers/{customer_id}")
async def update_customer(
    request: Request,
    item: UpdateCustomerRequest,
    customer_id: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Update customer details.

    Parameters:
        request (Request): The incoming HTTP request.
        customer_id (str): The ID of the customer.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The updated customer details.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    customer = customer_update(
        customer_id,
        customer_abbr=item.customer_abbr,
        partner_id=item.partner_id,
        name=item.name,
        priceplan=item.priceplan,
        base_fee=item.base_fee,
        realms=item.realms,
        contact_email=item.contact_email,
        notes=item.notes,
        blocks_purchased=item.blocks_purchased,
    )

    if not customer:
        return JSONResponse(content={"error": "Customer not found"}, status_code=404)

    return JSONResponse(content={"result": customer})


@router.delete("/admin/customers/{customer_id}")
async def delete_customer(
    request: Request,
    customer_id: int,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Delete a customer.

    Parameters:
        request (Request): The incoming HTTP request.
        customer_id (int): The ID of the customer.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The result of the operation.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    if not customer_delete(customer_id):
        return JSONResponse(content={"error": "Customer not found"}, status_code=404)

    return JSONResponse(content={"result": {"status": "OK"}})


@router.get("/admin/realms")
async def list_realms(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    List all unique realms.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The list of unique realms.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    realms = get_all_realms()

    return JSONResponse(content={"result": realms})


@router.get("/admin/customers/{customer_id}/stats")
async def customer_stats(
    request: Request,
    customer_id: str,
    admin_user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    """
    Get detailed customer statistics.

    Parameters:
        request (Request): The incoming HTTP request.
        customer_id (str): The ID of the customer.
        admin_user_id (str): The ID of the admin user.

    Returns:
        JSONResponse: The customer statistics.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"] and not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    customer = customer_get(customer_id)
    if not customer:
        return JSONResponse(content={"error": "Customer not found"}, status_code=404)

    stats = customer_get_statistics(customer_id)

    return JSONResponse(content={"result": stats})


@router.get("/admin/customers/export/csv")
async def export_customers_csv(
    request: Request,
    admin_user_id: str = Depends(get_current_user_id),
):
    """
    Export all customers with statistics to CSV format.

    Parameters:
        request (Request): The incoming HTTP request.
        admin_user_id (str): The ID of the admin user.

    Returns:
        Response: The CSV file response.
    """

    admin_user_id = await verify_user(request)

    if not admin_user_id:
        return JSONResponse(
            content={"error": "User not authenticated"}, status_code=401
        )

    admin_user = user_get(admin_user_id)["user"]

    if not admin_user["bofh"] and not admin_user["admin"]:
        return JSONResponse(content={"error": "User not authorized"}, status_code=403)

    csv_data = export_customers_to_csv(admin_user).encode("utf-8")

    if not csv_data:
        return JSONResponse(
            content={"error": "No customer data to export"}, status_code=404
        )

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="customers_export.csv"'},
    )
