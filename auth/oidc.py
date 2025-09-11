from authlib.integrations.starlette_client import OAuth
from authlib.jose import jwt
from datetime import datetime
from db.session import get_session
from typing import Optional
from db.user import user_create
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel
from utils.settings import get_settings

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


class UnauthenticatedError(HTTPException):
    def __init__(self, error: Optional[str] = "") -> None:
        super().__init__(status_code=401, detail="You are not authenticated: " + error)


class RefreshToken(BaseModel):
    token: str


async def get_current_user_id(request: Request) -> str:
    return await verify_user(request)


async def verify_token(id_token: str):
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
        session=db_session,
        username=username,
        realm=realm,
        user_id=user_id,
    )

    if not user["active"]:
        raise HTTPException(status_code=403, detail="User is not active.")

    return user_id
