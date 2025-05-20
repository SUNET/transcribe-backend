from auth.oidc import verify_user
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from routers.static import router as static_router
from routers.transcriber import router as transcriber_router
from starlette.middleware.sessions import SessionMiddleware
from utils.settings import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    openapi_tags=[
        {
            "name": "transcriber",
            "description": "Transcription operations",
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


app.add_middleware(SessionMiddleware, secret_key="some-secret-key", https_only=True)
app.include_router(transcriber_router, prefix=settings.API_PREFIX, tags=["transcriber"])
app.include_router(static_router, prefix="", tags=["static"])


@app.get("/")
async def index(request: Request) -> JSONResponse:
    """
    Redirect to docs.
    """
    await verify_user(request)

    return JSONResponse(
        content={
            "result": {
                "message": "Welcome to the API. Please refer to the documentation for usage instructions."
            }
        }
    )


@app.get("/docs")
async def docs(request: Request) -> RedirectResponse:
    await verify_user(request)

    return RedirectResponse(url="/docs")
