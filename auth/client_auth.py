from fastapi import HTTPException, Request
from typing import Optional
from utils.log import get_logger
from utils.settings import get_settings

settings = get_settings()
logger = get_logger()

dn_list = [settings.API_WORKER_CLIENT_DN, settings.API_KALTURA_CLIENT_DN]


def verify_client_dn(
    request: Request,
) -> Optional[str]:
    """
    Verify the client DN from the request headers.
    """

    client_dn = request.headers.get(settings.API_CLIENT_VERIFICATION_HEADER, "").strip()

    if settings.API_CLIENT_VERIFICATION_ENABLED is False:
        return "bypass-client-cert"

    if not client_dn.strip() not in dn_list:
        logger.info(f"Client failed to authenticate with {client_dn}")
        raise HTTPException(status_code=403, detail="Invalid request")

    logger.info(f"Client authenticated successfully with {client_dn}")

    return client_dn


def dn_in_list(dn):
    return dn in dn_list
