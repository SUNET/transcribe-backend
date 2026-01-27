import uuid

from auth.oidc import UnauthenticatedError, verify_token
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from utils.inference_ws_manager import inference_ws_manager
from utils.log import get_logger
from utils.ws_manager import WSManager

log = get_logger()
router = APIRouter(tags=["inference"])
ws_manager = WSManager()


async def authenticate_websocket(websocket: WebSocket, token: str) -> dict:
    """
    Authenticate a WebSocket connection using JWT token.

    Parameters:
        websocket (WebSocket): The WebSocket connection.
        token (str): The JWT token.

    Returns:
        dict: The decoded JWT payload containing user info.

    Raises:
        UnauthenticatedError: If authentication fails.
    """
    try:
        decoded_jwt = await verify_token(id_token=token)
        return decoded_jwt
    except Exception as e:
        log.error(f"WebSocket authentication failed: {e}")
        raise UnauthenticatedError("Invalid token.")


@router.websocket("/inference")
async def inference_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
):
    """
    WebSocket endpoint for inference requests.

    Parameters:
        websocket (WebSocket): The WebSocket connection.
        token (str): JWT token passed as query parameter.

    Returns:
        None
    """
    try:
        decoded_jwt = await authenticate_websocket(websocket, token)
        user_id = decoded_jwt["sub"]
    except UnauthenticatedError:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()
    await ws_manager.connect(user_id, websocket)
    log.info(f"WebSocket connected for user {user_id}")

    try:
        while True:
            data = await websocket.receive_json()
            log.info(f"Received inference request from {user_id}: {data}")
            # Route to worker via inference_ws_manager
            try:
                request_id = str(uuid.uuid4())
                response = await inference_ws_manager.send_request(
                    request_id,
                    {
                        "prompt": data.get("message", ""),
                        "model": data.get("model", "gemma3"),
                        "stream": data.get("stream", False),
                    },
                )
                await websocket.send_json(response)
            except RuntimeError as e:
                await websocket.send_json({"error": str(e)})
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
        log.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        log.error(f"WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(user_id, websocket)
