import requests

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_utils.tasks import repeat_every
from starlette.middleware.sessions import SessionMiddleware

from auth.oidc import RefreshToken, oauth, verify_user
from db.job import job_cleanup
from routers.job import router as job_router
from routers.transcriber import router as transcriber_router
from routers.user import router as user_router
from routers.video import router as video_router
from utils.log import get_logger
from utils.settings import get_settings

settings = get_settings()
log = get_logger()

log.info(f"Starting API: {settings.API_TITLE} {settings.API_VERSION}")

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    secret_key=settings.API_SECRET_KEY,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {
            "name": "transcriber",
            "description": "Transcription operations",
        },
        {
            "name": "job",
            "description": "Job management operations",
        },
        {
            "name": "video",
            "description": "Video retrieval operations",
        },
        {
            "name": "user",
            "description": "User management operations",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, settings.API_SECRET_KEY, https_only=False)
app.include_router(transcriber_router, prefix=settings.API_PREFIX, tags=["transcriber"])
app.include_router(job_router, prefix=settings.API_PREFIX, tags=["job"])
app.include_router(video_router, prefix=settings.API_PREFIX, tags=["video"])
app.include_router(user_router, prefix=settings.API_PREFIX, tags=["user"])


@app.get("/api/auth")
async def auth(request: Request):
    token = await oauth.auth0.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        raise ValueError("Failed to get userinfo from token")

    request.session["id_token"] = token["access_token"]

    if "refresh_token" in token:
        request.session["refresh_token"] = token["refresh_token"]

    url = f"{settings.OIDC_FRONTEND_URI}/?token={token['id_token']}"

    if "refresh_token" in token:
        url += f"&refresh_token={token['refresh_token']}"

    return RedirectResponse(url=url)


@app.get("/api/login")
async def login(request: Request):
    return await oauth.auth0.authorize_redirect(request, settings.OIDC_REDIRECT_URI)


@app.get("/api/logout")
async def logout(request: Request):
    return RedirectResponse(url=settings.OIDC_FRONTEND_URI)


@app.post("/api/refresh")
async def refresh(request: Request, refresh_token: RefreshToken):
    data = {
        "client_id": settings.OIDC_CLIENT_ID,
        "client_secret": settings.OIDC_CLIENT_SECRET,
        "refresh_token": refresh_token.token,
        "grant_type": "refresh_token",
    }

    try:
        response = requests.post(
            settings.OIDC_REFRESH_URI,
            data=data,
        )
        response.raise_for_status()
    except Exception:
        return JSONResponse({"error": "Failed to refresh token"}, status_code=400)

    return JSONResponse({"access_token": response.json()["access_token"]})


@app.get("/api/docs")
async def docs(request: Request) -> RedirectResponse:
    await verify_user(request)

    return RedirectResponse(url="/docs")


@app.on_event("startup")
@repeat_every(seconds=60 * 60)
def remove_old_jobs() -> None:
    job_cleanup()
