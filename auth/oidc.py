from authlib.integrations.starlette_client import OAuth
from authlib.jose import jwt
from datetime import datetime
from db.session import get_session
from db.user import user_create
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel
from typing import Optional
from utils.log import get_logger
from utils.settings import get_settings


log = get_logger()
settings = get_settings()
db_session = get_session()

oauth = OAuth()
oauth.register(
    name="auth0",
    server_metadata_url=settings.OIDC_METADATA_URL,
    client_id=settings.OIDC_CLIENT_ID,
    client_secret=settings.OIDC_CLIENT_SECRET,
    client_kwargs={"scope": "openid profile email"},
    redirect_uri=settings.OIDC_REDIRECT_URI,
)


async def get_current_user_id(request: Request) -> str:
    """
    Get the current user ID from the request.
    """

    return await verify_user(request)


class UnauthenticatedError(HTTPException):
    """
    Exception raised when the user is not authenticated.
    """

    def __init__(self, error: Optional[str] = "") -> None:
        """
        Initialize the exception.
        """
        super().__init__(status_code=401, detail="You are not authenticated: " + error)


class RefreshToken(BaseModel):
    """
    Refresh token model.
    """

    token: str


async def verify_token(id_token: str):
    """
    Verify the given ID token.
    1. Fetch the JWKS from the OIDC provider.
    2. Decode and verify the JWT using the JWKS.
    3. Check the issuer and expiration time.
    """

    jwks = await oauth.auth0.fetch_jwk_set()

    try:
        decoded_jwt = jwt.decode(s=id_token, key=jwks)
    except Exception as e:
        raise UnauthenticatedError("Invalid token.") from e

    metadata = await oauth.auth0.load_server_metadata()

    if decoded_jwt["iss"] != metadata["issuer"]:
        raise UnauthenticatedError("Invalid issuer.")

    exp = datetime.fromtimestamp(decoded_jwt["exp"])

    if exp < datetime.now():
        raise UnauthenticatedError("Token expired.")
    return decoded_jwt


async def verify_user(request: Request):
    """
    Verify the user from the request.
    1. Extract the ID token from the Authorization header.
    2. Verify the ID token.
    3. Create or update the user in the database.
    4. Return the user ID.
    """

    auth_header = request.headers.get("Authorization")

    if auth_header is None:
        raise UnauthenticatedError("No authorization header found.")

    if not auth_header.startswith("Bearer "):
        raise UnauthenticatedError("Invalid authorization header format.")

    id_token = auth_header.split(" ")[1]

    if id_token is None:
        raise UnauthenticatedError("No id_token found.")

    decoded_jwt = await verify_token(id_token=id_token)

    user_id = decoded_jwt["sub"]
    username = decoded_jwt.get("preferred_username")
    realm = decoded_jwt.get("realm", username.split("@")[-1])

    user = user_create(
        username=username,
        realm=realm,
        user_id=user_id,
    )

    if not user["active"]:
        log.error(f"User {user_id} is not active.")
        raise HTTPException(status_code=403, detail="User is not active.")

    log.info(f"User {user_id} authenticated successfully.")

    return user_id
