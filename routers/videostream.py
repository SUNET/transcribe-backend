from auth.oidc import get_current_user
from db.job import job_get
from db.user import user_get_private_key
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pathlib import Path
from utils.crypto import (
    decrypt_data_from_file,
    deserialize_private_key_from_pem,
    get_encrypted_file_size,
)
from utils.settings import get_settings
from utils.validators import VideoStreamRequestBody

router = APIRouter(tags=["video"])
settings = get_settings()
api_file_storage_dir = settings.API_FILE_STORAGE_DIR


@router.get("/transcriber/{job_id}/videostream")
async def get_video_stream(
    request: Request,
    item: VideoStreamRequestBody,
    job_id: str,
    range: str = Header(None),
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream an encrypted video for a transcription job.

    Parameters:
        request (Request): The incoming HTTP request.
        job_id (str): The ID of the job.
        range (str): The byte range for streaming.
        user (dict): The current user.

    Returns:
        StreamingResponse: The video stream response.
    """

    job = job_get(job_id, user["user_id"])

    if item.encryption_password != "" and item.encryption_password is not None:
        private_key = user_get_private_key(user["user_id"])
        private_key = deserialize_private_key_from_pem(
            private_key, item.encryption_password
        )
        file_path = Path(api_file_storage_dir) / user["user_id"] / f"{job_id}.mp4.enc"
        encrypted_media = True

        if not file_path.exists():
            file_path = Path(api_file_storage_dir) / user["user_id"] / f"{job_id}.mp4"
            encrypted_media = False
    else:
        file_path = Path(api_file_storage_dir) / user["user_id"] / f"{job_id}.mp4"
        encrypted_media = False

    if not job:
        return JSONResponse({"result": {"error": "Job not found"}}, status_code=404)

    if not file_path.exists():
        return JSONResponse(
            {"result": {"error": "Video file not found"}}, status_code=404
        )

    filesize = file_path.stat().st_size

    if not range or not range.startswith("bytes="):
        range_start = 0
        range_end = filesize - 1
    else:
        range_start_str, range_end_str = range.replace("bytes=", "").split("-")
        range_start = int(range_start_str)
        range_end = int(range_end_str) if range_end_str else filesize - 1

    # Try to decrypt the first chunk of the file to verify the password
    if encrypted_media:
        try:
            decrypt_data_from_file(
                private_key,
                file_path,
                start_chunk=0,
                end_chunk=0,
            )
        except Exception:
            encrypted_media = False

    # New way to serve encrypted video files
    if encrypted_media:
        # Get the ORIGINAL file size first
        filesize_original = get_encrypted_file_size(
            file_path
        )  # I assume this returns the original size

        # Recalculate range_end based on original file size
        if not range or not range.startswith("bytes="):
            range_start = 0
            range_end = filesize_original - 1
        else:
            range_start_str, range_end_str = range.replace("bytes=", "").split("-")
            range_start = int(range_start_str)
            range_end = int(range_end_str) if range_end_str else filesize_original - 1

        # Clamp range_end to file size
        range_end = min(range_end, filesize_original - 1)

        # Determine which chunks correspond to the byte range
        start_chunk = range_start // settings.CRYPTO_CHUNK_SIZE
        end_chunk = range_end // settings.CRYPTO_CHUNK_SIZE

        def stream_chunks():
            offset_in_first_chunk = range_start % settings.CRYPTO_CHUNK_SIZE
            last_chunk_bytes = (range_end % settings.CRYPTO_CHUNK_SIZE) + 1

            for i, chunk in enumerate(
                decrypt_data_from_file(private_key, file_path, start_chunk, end_chunk)
            ):
                if i == 0:
                    chunk = chunk[offset_in_first_chunk:]
                if i == (end_chunk - start_chunk):
                    chunk = chunk[:last_chunk_bytes]
                yield chunk

        content_length = range_end - range_start + 1

        headers = {
            "Content-Range": f"bytes {range_start}-{range_end}/{filesize_original}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
        }

        return StreamingResponse(
            stream_chunks(), status_code=206, headers=headers, media_type="video/mp4"
        )

    # Old way to serve unencrypted video files
    else:
        filesize = int(file_path.stat().st_size)
        range_start, range_end = range.replace("bytes=", "").split("-")
        range_start = int(range_start)
        range_end = int(range_end) if range_end else filesize - 1

        with open(file_path, "rb") as video:
            video.seek(range_start)
            data = video.read(range_end - range_start + 1)
            headers = {
                "Content-Range": f"bytes {str(range_start)}-{str(range_end)}/{filesize}",
                "Accept-Ranges": "bytes",
            }

            return Response(
                data, status_code=206, headers=headers, media_type="video/mp4"
            )
