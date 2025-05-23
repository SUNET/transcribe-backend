from auth.oidc import verify_user
from db.session import get_session
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from utils.settings import get_settings

router = APIRouter(tags=["transcriber"])
settings = get_settings()
db_session = get_session()

api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/static/{user_id}/{job_id}")
async def get_static_file(request: Request, user_id: str, job_id: str) -> FileResponse:
    """
    Get the static file.
    """

    file_path = Path(api_file_storage_dir) / user_id / job_id
    print(file_path)
    if not file_path.exists():
        return JSONResponse(
            content={"detail": {"error": "File not found"}},
            status_code=404,
        )

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=file_path.name,
        headers={
            "Content-Disposition": f"attachment; filename={file_path.name}",
            "X-Accel-Buffering": "no",
        },
    )
