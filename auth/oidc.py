from datetime import datetime
from fastapi import HTTPException, Request
from authlib.jose import jwt
from authlib.integrations.starlette_client import OAuth
from typing import Optional
from utils.settings import get_settings

settings = get_settings()

oauth = OAuth()
oauth.register(
    name="auth0",
    server_metadata_url=settings.OIDC_METADATA_URL,
    client_id=settings.OIDC_CLIENT_ID,
    client_secret=settings.OIDC_CLIENT_SECRET,
    client_scope=settings.OIDC_SCOPE,
)


class UnauthenticatedError(HTTPException):
    """
    Custom exception for unauthenticated users.
    Inherits from HTTPException.
    """

    def __init__(self, message: Optional[str] = "") -> None:
        """
        Initialize the UnauthenticatedError.
        Args:
            message (Optional[str]): Custom error message.
        """
        super().__init__(
            status_code=401, detail=f"You are not authenticated. {message}"
        )


async def verify_token(id_token: str):
    """
    Verify the JWT token.
    Args:
        id_token (str): The JWT token to verify.
    Returns:
        dict: The decoded JWT token.
    Raises:
        UnauthenticatedError: If the token is invalid or expired.
    """

    jwks = await oauth.auth0.fetch_jwk_set()

    try:
        decoded_jwt = jwt.decode(s=id_token, key=jwks)
    except Exception:
        raise UnauthenticatedError("Invalid token.")

    metadata = await oauth.auth0.load_server_metadata()

    if decoded_jwt["iss"] != metadata["issuer"]:
        raise UnauthenticatedError(f"Invalid issuer, was {decoded_jwt['iss']}")

    # XXX: Check audience?
    # if decoded_jwt["aud"] != "nac":
    #     raise UnauthenticatedError("Invalid audience: ")

    exp = datetime.fromtimestamp(decoded_jwt["exp"])

    if exp < datetime.now():
        raise UnauthenticatedError(f"Token expired at {exp}")
    return decoded_jwt


async def verify_user(request: Request):
    """
    Verify the user by checking the JWT token in the request headers.
    Args:
        request (Request): The request object.
    Returns:
        str: The user ID from the decoded JWT token.
    Raises:
        UnauthenticatedError: If the token is invalid or expired.
    """

    id_token = request.headers["authorization"].replace("Bearer ", "")

    if id_token is None:
        raise UnauthenticatedError("No token provided.")

    decoded_jwt = await verify_token(id_token=id_token)

    user_id = decoded_jwt["sub"]

    # XXX: Should eventually anonymize the user_id and return a UUID.
    return user_id
