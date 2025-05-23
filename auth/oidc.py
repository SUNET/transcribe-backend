from fastapi import Request
from authlib.jose import jwt
from fastapi import HTTPException
from datetime import datetime
from utils.settings import get_settings
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel

settings = get_settings()


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
    def __init__(self) -> None:
        super().__init__(status_code=401, detail="You are not authenticated.")


class RefreshToken(BaseModel):
    token: str


async def verify_token(id_token: str):
    jwks = await oauth.auth0.fetch_jwk_set()
    try:
        decoded_jwt = jwt.decode(s=id_token, key=jwks)
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        raise UnauthenticatedError(e)
    metadata = await oauth.auth0.load_server_metadata()
    if decoded_jwt["iss"] != metadata["issuer"]:
        print(f"Invalid issuer: {decoded_jwt['iss']}")
        raise UnauthenticatedError()
    exp = datetime.fromtimestamp(decoded_jwt["exp"])
    if exp < datetime.now():
        print(f"JWT expired: {exp}")
        raise UnauthenticatedError()
    return decoded_jwt


async def verify_user(request: Request):
    auth_header = request.headers.get("Authorization")

    if auth_header is None:
        print("No Authorization header found.")
        raise UnauthenticatedError()

    if not auth_header.startswith("Bearer "):
        print("Invalid Authorization header format.")
        raise UnauthenticatedError()

    id_token = auth_header.split(" ")[1]

    if id_token is None:
        print("No ID token found in session.")
        raise UnauthenticatedError()

    decoded_jwt = await verify_token(id_token=id_token)
    user_id = decoded_jwt["sub"]
    print(f"User ID: {user_id}")

    return user_id
